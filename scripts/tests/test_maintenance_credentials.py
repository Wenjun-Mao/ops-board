"""Release inputs cannot rotate owned credentials or adopt another Rabbit node."""

import contextlib
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
import cli
from common import MaintenanceError
from credentials import CREDENTIALS, SIGNOZ_PROVIDERS, validate_environment
from deployment import Deployment, GROUPS, JOBS
from overlays import validate_contract
import test_signoz_release as signoz_tests
import test_plane_release as plane_tests


class EnvironmentIdentityTests(unittest.TestCase):
    def test_every_owned_credential_refuses_rotation_removal_and_injection(self):
        for stack, keys in CREDENTIALS.items():
            for key in keys:
                original = {"environment": {key: "existing-private-value"}}
                validate_environment(stack, original, copy.deepcopy(original))
                for changed in [{key: "rotated-private-value"}, {}, {key: None}]:
                    with self.subTest(stack=stack, key=key, changed=changed):
                        with self.assertRaises(MaintenanceError) as error:
                            validate_environment(stack, original, {"environment": changed})
                        self.assertNotIn("private-value", str(error.exception))
                with self.assertRaises(MaintenanceError):
                    validate_environment(stack, {}, original)

    def test_stage_flags_endpoints_and_explicit_canonical_providers_remain_allowed(self):
        validate_environment("plane", {"environment": {"SECRET_KEY": "owned"}}, {
            "environment": {"SECRET_KEY": "owned", "AUTHENTICATION_RATE_LIMIT": "10/minute",
                            "AWS_S3_ENDPOINT_URL": "http://reviewed-storage:9000"}})
        for key, provider in SIGNOZ_PROVIDERS.items():
            explicit = {"environment": {key: provider}}
            validate_environment("signoz", {}, explicit)
            validate_environment("signoz", explicit, copy.deepcopy(explicit))
            with self.assertRaises(MaintenanceError):
                validate_environment("signoz", {}, {"environment": {key: "other"}})
            with self.assertRaises(MaintenanceError):
                validate_environment("signoz", explicit, {})

    def test_storage_endpoint_address_can_change_but_embedded_credentials_cannot(self):
        original = {"environment": {"AWS_S3_ENDPOINT_URL": "http://owned:secret@old:9000"}}
        validate_environment("plane", original, {"environment": {"AWS_S3_ENDPOINT_URL": "http://owned:secret@new:9000"}})
        with self.assertRaisesRegex(MaintenanceError, "endpoint credential"):
            validate_environment("plane", original, {"environment": {"AWS_S3_ENDPOINT_URL": "http://owned:rotated@new:9000"}})


class RabbitIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.layer = self.root / "stacks/plane/maintenance/stage.yaml"
        self.layer.parent.mkdir(parents=True)
        self.layer.write_text("services: {}\n")
        self.config = {"name": "ops-board", "services": {
            service: {"image": "owned:1", "container_name": service} for service in GROUPS["plane"]}}
        self.config["services"]["plane-mq"].update(hostname="3bb3429c1ce3", environment={
            "RABBITMQ_DEFAULT_PASS": "owned-secret", "RABBITMQ_NODENAME": "rabbit@3bb3429c1ce3"})
        self.containers = [{"Id": service + "-id", "Name": "/" + service, "Image": "owned-id",
            "Config": {"Hostname": "3bb3429c1ce3", "Env": [], "Labels": {
                "com.docker.compose.project": "ops-board", "com.docker.compose.service": service,
                "com.docker.compose.project.working_dir": str(self.root)}}, "Mounts": [],
            "State": {"Running": service not in JOBS, "Status": "exited" if service in JOBS else "running", "ExitCode": 0}}
            for service in GROUPS["plane"]]
        self.broker = next(c for c in self.containers if c["Id"] == "plane-mq-id")
        self.broker["Config"]["Env"] = ["RABBITMQ_DEFAULT_PASS=owned-secret", "RABBITMQ_NODENAME=rabbit@3bb3429c1ce3"]

    def inspect(self, *, overlays=True, deployment=None):
        deployment = deployment or Deployment(self.root, "plane", overlays=[self.layer] if overlays else [])
        with patch.object(deployment, "resolve_config", return_value=self.config), \
             patch("deployment.run", return_value="selected-ids"), \
             patch("deployment.docker_json", return_value=self.containers):
            return deployment.inspect()

    def test_correct_explicit_historical_hostname_and_nodename_are_accepted(self):
        deployment = self.inspect()
        self.assertEqual(deployment.broker_identity, {"hostname": "3bb3429c1ce3", "nodename": "rabbit@3bb3429c1ce3", "longname": None})
        self.inspect(deployment=deployment)
        self.inspect(overlays=False)

    def test_wrong_explicit_hostname_refused_with_or_without_layers(self):
        self.config["services"]["plane-mq"]["hostname"] = "new-empty-node"
        for overlays in [True, False]:
            with self.subTest(overlays=overlays), self.assertRaisesRegex(MaintenanceError, "Rabbit hostname"):
                self.inspect(overlays=overlays)

    def test_wrong_explicit_nodename_refused_even_with_correct_hostname(self):
        self.config["services"]["plane-mq"]["environment"]["RABBITMQ_NODENAME"] = "rabbit@new-node"
        for overlays in [True, False]:
            with self.subTest(overlays=overlays), self.assertRaises(MaintenanceError):
                self.inspect(overlays=overlays)

    def test_node_identity_cannot_be_recaptured_after_first_inspect(self):
        deployment = self.inspect()
        self.broker["Config"]["Hostname"] = "changed"
        self.config["services"]["plane-mq"]["hostname"] = "changed"
        with self.assertRaisesRegex(MaintenanceError, "node identity changed"):
            self.inspect(deployment=deployment)

    def test_live_credential_drift_refused(self):
        self.broker["Config"]["Env"][0] = "RABBITMQ_DEFAULT_PASS=rotated"
        with self.assertRaisesRegex(MaintenanceError, "Configured/live credential"):
            self.inspect()

    def test_generic_update_refuses_wrong_hostname_before_pull_or_up(self):
        deployment = Deployment(self.root, "plane", overlays=[self.layer])
        self.config["services"]["plane-mq"]["hostname"] = "new-empty-node"
        with patch("sys.argv", ["cli.py", "update", "--stack", "plane", "--compose-overlay", str(self.layer)]), \
             patch("cli.Deployment", return_value=deployment), patch("cli.lock", return_value=contextlib.nullcontext()), \
             patch.object(deployment, "resolve_config", return_value=self.config), \
             patch("deployment.run", return_value="selected-ids"), \
             patch("deployment.docker_json", return_value=self.containers), patch("cli.run") as mutation:
            with self.assertRaisesRegex(MaintenanceError, "Rabbit hostname"):
                cli.main()
            mutation.assert_not_called()


class SigNozSecretRenderTests(unittest.TestCase):
    setUpClass = classmethod(lambda cls: signoz_tests.ComposeContractTests.setUpClass())
    setUp = signoz_tests.ComposeContractTests.setUp
    render = signoz_tests.ComposeContractTests.render

    def test_jwt_secret_bind_shadowing_and_launcher_redirection_refused(self):
        self.root = self.root.resolve()
        self.render()
        directory = self.root / "stacks/signoz/maintenance"
        secret = directory / "replacement-secret"
        secret.write_text("test-only-replacement")
        definitions = [{"volumes": [str(secret) + ":/run/secrets/signoz_jwt_secret:ro"]},
                       {"entrypoint": ["/bin/sh", "/opt/signoz/lifecycle/launch-server.sh", str(secret), "./signoz", "server"]},
                       {"command": ["--tokenizer-jwt-secret=rotated"]},
                       {"environment": {"SIGNOZ_TOKENIZER_JWT_SECRET": "rotated"}}]
        for definition in definitions:
            layer = directory / "attack.json"
            layer.write_text(json.dumps({"services": {"signoz": definition}}))
            with self.subTest(definition=definition), self.assertRaises(MaintenanceError):
                Deployment(self.root, "signoz", overlays=[layer]).resolve_config()

    def test_existing_secret_bind_cannot_be_replaced_by_scoped_readonly_file(self):
        self.root = self.root.resolve()
        baseline = self.render()
        secret = self.root / "stacks/signoz/maintenance/new-secret"
        secret.write_text("test-only")
        baseline["services"]["signoz"]["volumes"].append({"type": "bind", "source": str(self.root / "secrets/fixture"),
            "target": "/run/secrets/custom-jwt", "read_only": True})
        changed = copy.deepcopy(baseline)
        changed["services"]["signoz"]["volumes"][-1]["source"] = str(secret)
        with self.assertRaisesRegex(MaintenanceError, "Secret/owned bind"):
            validate_contract(baseline, changed, Deployment(self.root, "signoz"))

    def test_launcher_bind_cannot_be_replaced(self):
        self.root = self.root.resolve()
        baseline = self.render()
        replacement = self.root / "stacks/signoz/maintenance/new-launcher"
        replacement.write_text("test-only")
        changed = copy.deepcopy(baseline)
        mount = next(m for m in changed["services"]["signoz"]["volumes"] if m["target"].endswith("launch-server.sh"))
        mount["source"] = str(replacement)
        with self.assertRaisesRegex(MaintenanceError, "Secret/owned bind"):
            validate_contract(baseline, changed, Deployment(self.root, "signoz"))


class PlaneCredentialRenderTests(unittest.TestCase):
    setUpClass = classmethod(lambda cls: plane_tests.ComposeReleaseTests.setUpClass())
    setUp = plane_tests.ComposeReleaseTests.setUp
    render = plane_tests.ComposeReleaseTests.render

    def test_existing_backend_credential_rotation_refused_by_real_layer_render(self):
        self.root = self.root.resolve()
        self.render()
        layer = self.root / "stacks/plane/maintenance/rotate.json"
        for key in ["SECRET_KEY", "DATABASE_URL", "POSTGRES_PASSWORD", "REDIS_URL", "AMQP_URL",
                    "RABBITMQ_DEFAULT_PASS", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "MINIO_ROOT_PASSWORD"]:
            layer.write_text(json.dumps({"services": {"api": {"environment": {key: "rotated"}}}}))
            with self.subTest(key=key), self.assertRaisesRegex(MaintenanceError, "credential identity/value"):
                Deployment(self.root, "plane", overlays=[layer]).resolve_config()


if __name__ == "__main__":
    unittest.main()
