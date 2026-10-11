"""Ordered source guards and matched stage recovery, without a live daemon."""

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
import cli
import restore
from archives import seal, validate_bundle
from common import MaintenanceError
from deployment import Deployment, GROUPS, JOBS
from overlays import input_records, validate_contract
import test_maintenance_workflows as workflows
import test_plane_release as plane_tests
import test_signoz_release as signoz_tests


class OverlayGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.directory = self.root / "stacks/signoz/maintenance"
        self.directory.mkdir(parents=True)
        self.layer = self.directory / "stage.yaml"
        self.layer.write_text("services: {}\n")
        (self.root / "compose.yaml").write_text("name: ops-board\n")
        self.deployment = Deployment(self.root, "signoz", overlays=[self.layer])
        self.base = {"name": "ops-board", "services": {
            s: {"image": "old:1", "container_name": s} for s in GROUPS["signoz"]},
            "volumes": {"store": {"name": "owned-store"}},
            "networks": {"default": {"name": "ops-board_default"}},
            "secrets": {"jwt": {"file": str(self.root / "secrets/jwt")}}}
        self.base["services"]["outside"] = {"image": "unchanged:1"}
        self.base["services"]["signoz"]["volumes"] = [
            {"type": "volume", "source": "store", "target": "/data"}]

    def test_relative_and_absolute_inputs_retain_order(self):
        other = self.directory / "next.yaml"
        other.write_text("services: {}\n")
        with patch("os.getcwd", return_value=str(self.root)):
            value = Deployment(self.root, "signoz", overlays=["stacks/signoz/maintenance/stage.yaml", other])
        self.assertEqual(value.compose_inputs, [self.root / "compose.yaml", self.layer, other])

    def test_path_scope_traversal_symlinks_and_special_files_refused(self):
        link = self.directory / "link.yaml"
        link.symlink_to(self.layer)
        fifo = self.directory / "fifo"
        os.mkfifo(fifo)
        outside = self.root / "outside.yaml"
        outside.write_text("services: {}\n")
        for path in [link, fifo, outside, self.directory, self.directory / "missing",
                     self.directory / "../maintenance/stage.yaml"]:
            with self.subTest(path=path), self.assertRaises(MaintenanceError):
                Deployment(self.root, "signoz", overlays=[path])
        for stack, context in [("ops-board", "root"), ("homepage", "root"), ("plane", "standalone")]:
            with self.assertRaises(MaintenanceError):
                Deployment(self.root, stack, context, [self.layer])

    def test_project_environment_cannot_mask_yaml_name(self):
        with patch.dict(os.environ, {"COMPOSE_PROJECT_NAME": "ops-board"}):
            with self.assertRaisesRegex(MaintenanceError, "Unset COMPOSE_PROJECT_NAME"):
                Deployment(self.root, "signoz", overlays=[self.layer])

    def test_cross_stack_resources_ports_security_and_volume_changes_refused(self):
        changes = [lambda c: c.update(name="other"),
                   lambda c: c["services"].update(intruder={"image": "x"}),
                   lambda c: c["services"].pop("outside"),
                   lambda c: c["services"]["outside"].update(image="changed"),
                   lambda c: c["volumes"]["store"].update(name="other"),
                   lambda c: c["volumes"]["store"].update(external=True),
                   lambda c: c["networks"].update(other={"name": "shared"}),
                   lambda c: c["secrets"].update(other={"file": "/tmp/secret"}),
                   lambda c: c["services"]["signoz"]["volumes"][0].update(source="other")]
        for field, value in [("ports", [{"target": 8080, "published": "80"}]),
                             ("privileged", True), ("network_mode", "host"),
                             ("devices", ["/dev/mem"]), ("container_name", "other"),
                             ("networks", {"outside": {}}), ("scale", 2)]:
            changes.append(lambda c, k=field, v=value: c["services"]["signoz"].update({k: v}))
        for change in changes:
            candidate = copy.deepcopy(self.base)
            change(candidate)
            with self.subTest(change=change), self.assertRaises(MaintenanceError):
                validate_contract(self.base, candidate, self.deployment)

    def test_scoped_readonly_binds_allowed_but_persistent_mount_contract_kept(self):
        candidate = copy.deepcopy(self.base)
        collector = candidate["services"]["otel-collector"]
        collector.update(image="stage:1", command=["--copy-path=/var/tmp/config.yaml"],
                         environment={"KEY": "stage"}, profiles=["manual-writers"])
        collector["volumes"] = [{"type": "bind", "source": str(self.layer),
                                  "target": "/etc/otel-collector-config.yaml", "read_only": True}]
        validate_contract(self.base, candidate, self.deployment)
        for update in [{"read_only": False}, {"source": str(self.root / "compose.yaml")}, {"type": "volume"}]:
            bad = copy.deepcopy(candidate)
            bad["services"]["otel-collector"]["volumes"][0].update(update)
            with self.assertRaises(MaintenanceError):
                validate_contract(self.base, bad, self.deployment)
        candidate["services"]["signoz"]["volumes"] = []
        with self.assertRaises(MaintenanceError):
            validate_contract(self.base, candidate, self.deployment)

    def test_every_intermediate_layer_guarded_before_runtime_queries(self):
        next_layer = self.directory / "next.yaml"
        next_layer.write_text("services: {}\n")
        deployment = Deployment(self.root, "signoz", overlays=[self.layer, next_layer])
        bad = copy.deepcopy(self.base)
        bad["services"]["outside"]["image"] = "changed"
        with patch("deployment.docker_json", side_effect=[self.base, bad, self.base]) as docker, \
             patch("deployment.run") as runtime:
            with self.assertRaises(MaintenanceError):
                deployment.inspect()
        self.assertEqual(docker.call_count, 2)
        runtime.assert_not_called()

    def test_metric_log_policy_addition_is_exact_scoped_and_readonly(self):
        policy = self.directory / "metric-log-merges.xml"
        policy.write_text("<clickhouse><metric_log/></clickhouse>")
        mount = {"type": "bind", "source": str(policy),
                 "target": "/etc/clickhouse-server/config.d/metric-log-merges.xml", "read_only": True}
        candidate = copy.deepcopy(self.base)
        candidate["services"]["clickhouse"]["volumes"] = [mount]
        validate_contract(self.base, candidate, self.deployment)
        for changed in [{"read_only": False}, {"target": "/etc/clickhouse-server/config.xml"},
                        {"source": str(self.layer)}, {"type": "volume"}]:
            bad = copy.deepcopy(candidate)
            bad["services"]["clickhouse"]["volumes"][0].update(changed)
            with self.subTest(changed=changed), self.assertRaises(MaintenanceError):
                validate_contract(self.base, bad, self.deployment)

    def test_source_dry_run_renders_only_and_restore_refuses_layers(self):
        with patch("sys.argv", ["cli.py", "status", "--stack", "signoz", "--dry-run",
                                "--compose-overlay", str(self.layer)]), \
             patch("cli.Deployment", return_value=self.deployment), \
             patch("deployment.docker_json", side_effect=[self.base, self.base]) as docker, \
             patch("cli.run") as run, contextlib.redirect_stdout(io.StringIO()) as output:
            cli.main()
        self.assertIn("Source overlay contract validated", output.getvalue())
        self.assertTrue(all("config" in call.args and "*" in call.args for call in docker.call_args_list))
        run.assert_not_called()
        with patch("sys.argv", ["cli.py", "restore", "--compose-overlay", str(self.layer)]):
            with self.assertRaisesRegex(MaintenanceError, "captured bytes"):
                cli.main()


class PlaneStageRenderTests(unittest.TestCase):
    setUpClass = classmethod(lambda cls: plane_tests.ComposeReleaseTests.setUpClass())
    setUp = plane_tests.ComposeReleaseTests.setUp
    render = plane_tests.ComposeReleaseTests.render

    def test_ordered_all_plane_layers_pass_shared_contract(self):
        self.root = self.root.resolve()
        self.render(changes={"PLANE_RABBITMQ_TARGET_VERSION": "4.2.9-management-alpine",
                             "PLANE_RABBITMQ_HOSTNAME": "3bb3429c1ce3"})
        paths = [self.root / "stacks/plane/maintenance" / name for name in [
            "stage3-db.yaml", "stage3-cache.yaml", "stage4-app.yaml", "stage5-storage.yaml", "stage6-rabbit.yaml"]]
        deployment = Deployment(self.root, "plane", overlays=paths)
        config = deployment.resolve_config()
        self.assertEqual(config["services"]["migrator"]["profiles"], ["manual-jobs"])
        self.assertEqual(config["services"]["plane-mq"]["hostname"], "3bb3429c1ce3")
        self.assertEqual(config["services"]["plane-db"]["image"], "postgres:15.19-alpine")

    def test_stack_env_cannot_conceal_malicious_project_layer(self):
        self.root = self.root.resolve()
        self.render()
        envfile = self.root / "stacks/plane/plane.env"
        with envfile.open("a") as output:
            output.write("COMPOSE_PROJECT_NAME=ops-board\n")
        layer = self.root / "stacks/plane/maintenance/bad.yaml"
        layer.write_text("name: other\nservices: {}\n")
        with self.assertRaisesRegex(MaintenanceError, "project/resources/imports"):
            Deployment(self.root, "plane", overlays=[layer]).resolve_config()


class SigNozStageRenderTests(unittest.TestCase):
    setUpClass = classmethod(lambda cls: signoz_tests.ComposeContractTests.setUpClass())
    setUp = signoz_tests.ComposeContractTests.setUp
    render = signoz_tests.ComposeContractTests.render

    def test_current_signoz_layers_and_historical_provider_removal_rejection(self):
        self.root = self.root.resolve()
        self.render()
        directory = self.root / "stacks/signoz/maintenance"
        for stage in signoz_tests.STAGES:
            deployment = Deployment(self.root, "signoz", overlays=[directory / "prepared.yaml",
                                    directory / stage["overlay"]])
            if stage["id"] in ["0.131.1", "0.135.0"]:
                with self.subTest(stage=stage["id"]), self.assertRaisesRegex(MaintenanceError, "provider identity"):
                    deployment.resolve_config()
                continue
            config = deployment.resolve_config()
            self.assertEqual(config["services"]["otel-collector"]["profiles"], ["manual-writers"])
            self.assertEqual(config["services"]["signoz-telemetrystore-migrator"]["profiles"], ["manual-jobs"])
        bad = directory / "bad.yaml"
        bad.write_text("name: other\nservices: {}\n")
        with self.assertRaisesRegex(MaintenanceError, "project/resources/imports"):
            Deployment(self.root, "signoz", overlays=[bad]).resolve_config()

    def test_real_compose_refuses_malicious_scope_resource_and_port_layers(self):
        self.root = self.root.resolve()
        baseline = self.render()
        definitions = [{"services": {"sentinel": {"image": "changed:1"}}},
                       {"services": {"signoz": {"ports": ["9999:8080"]}}},
                       {"services": {"signoz": {"privileged": True}}},
                       {"volumes": {next(iter(baseline["volumes"])): {"name": "other-owned-store"}}},
                       {"volumes": {"foreign": {"external": True}}},
                       {"networks": {"foreign": {"external": True}}}]
        layer = self.root / "stacks/signoz/maintenance/adversarial.json"
        for definition in definitions:
            layer.write_text(json.dumps(definition))
            with self.subTest(layer=definition), self.assertRaises(MaintenanceError):
                Deployment(self.root, "signoz", overlays=[layer]).resolve_config()


class FullRootStageTests(unittest.TestCase):
    setUpClass = classmethod(lambda cls: signoz_tests.ComposeContractTests.setUpClass())

    def test_all_root_groups_and_daemon_free_cli_dryruns(self):
        repo = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            shutil.copytree(repo / "stacks", root / "stacks", ignore=shutil.ignore_patterns("*.env", ".env", "__pycache__"))
            shutil.copytree(repo / "scripts/maintenance", root / "scripts/maintenance", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copyfile(repo / "compose.yaml", root / "compose.yaml")
            shutil.copyfile(repo / ".env.example", root / ".env")
            values = dict(line.split("=", 1) for line in (root / "stacks/plane/plane.env.example").read_text().splitlines()
                          if line and not line.startswith("#"))
            values.update({key: "fixture" for key in plane_tests.REQUIRED})
            values.update(PLANE_RABBITMQ_TARGET_VERSION="4.2.9-management-alpine", PLANE_RABBITMQ_HOSTNAME="3bb3429c1ce3")
            (root / "stacks/plane/plane.env").write_text("".join(f"{k}={v}\n" for k, v in values.items()))
            clean = {k: v for k, v in os.environ.items() if k not in values and not k.startswith(("COMPOSE_", "SIGNOZ_", "HOMEPAGE_", "PLANE_"))}
            clean["DOCKER_HOST"] = "unix:///nonexistent-ops-board-test-daemon.sock"
            stages = {"plane": ["stage3-db.yaml", "stage3-cache.yaml", "stage4-app.yaml", "stage5-storage.yaml", "stage6-rabbit.yaml"],
                      "signoz": ["prepared.yaml", "stop-0.145.0.yaml"]}
            for stack, layers in stages.items():
                args = [item for layer in layers for item in ["--compose-overlay", str(root / "stacks" / stack / "maintenance" / layer)]]
                for operation in ["status", "verify", "backup", "update"]:
                    result = subprocess.run([sys.executable, str(root / "scripts/maintenance/cli.py"), operation,
                        "--stack", stack, "--dry-run", "--archive-image", workflows.IMAGE, *args], cwd=root,
                        env=clean, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("Source overlay contract validated", result.stdout)
                    self.assertNotIn("--profile", result.stdout)


class StageCheckpointTests(unittest.TestCase):
    docker = workflows.BackupWorkflowTests.docker
    fake_run = workflows.BackupWorkflowTests.fake_run
    helper = workflows.BackupWorkflowTests.helper
    execute = workflows.BackupWorkflowTests.execute

    def setUp(self):
        workflows.BackupWorkflowTests.setUp(self)
        self.deployment.stack = "signoz"
        self.deployment.services = GROUPS["signoz"]
        template = self.deployment.containers[0]
        self.deployment.containers = []
        self.deployment.config = {"name": "ops-board", "services": {}, "volumes": {}}
        self.deployment.volumes = {}
        directory = self.root / "stacks/signoz/maintenance"
        directory.mkdir(parents=True)
        shutil.copyfile(signoz_tests.RELEASE / "prepared.yaml", directory / "prepared.yaml")
        shutil.copyfile(signoz_tests.RELEASE / "stop-0.131.1.yaml", directory / "stop-0.131.1.yaml")
        for name in ["collector-v0.144.5.yaml", "opamp.yaml"]:
            shutil.copyfile(signoz_tests.RELEASE / name, directory / name)
        self.deployment.overlays = [directory / "prepared.yaml", directory / "stop-0.131.1.yaml"]
        self.deployment.compose_inputs = [self.root / "compose.yaml", *self.deployment.overlays]
        for service in GROUPS["signoz"]:
            container = copy.deepcopy(template)
            container.update(Id=service + "-id", Name="/" + service, Mounts=[])
            container["Config"].update(Entrypoint=["collector"], Cmd=["--copy-path=/var/tmp/collector-config.yaml"])
            container["Config"]["Labels"]["com.docker.compose.service"] = service
            container["State"].update(Running=False, Status="exited", ExitCode=0)
            self.deployment.containers.append(container)
            self.deployment.config["services"][service] = {"image": "stage:1", "volumes": []}
            if service in JOBS:
                self.deployment.config["services"][service]["profiles"] = ["manual-jobs"]
        for service, key, target in [("signoz", "sqlite", "/var/lib/signoz"),
                                     ("clickhouse", "clickhouse", "/var/lib/clickhouse"),
                                     ("zookeeper-1", "data", "/data"), ("zookeeper-1", "logs", "/datalog")]:
            container = next(c for c in self.deployment.containers if c["Id"] == service + "-id")
            name = "owned-" + key
            container["Mounts"].append({"Type": "volume", "Name": name, "Destination": target, "RW": True})
            self.deployment.volumes[key] = name
            self.deployment.config["volumes"][key] = {"name": name}
            self.deployment.config["services"][service]["volumes"].append({"type": "volume", "source": key, "target": target})
        collector = self.deployment.containers[0]
        for source, target in [("collector-v0.144.5.yaml", "/etc/otel-collector-config.yaml"),
                               ("opamp.yaml", "/etc/opamp-config.yaml")]:
            collector["Mounts"].append({"Type": "bind", "Source": str(directory / source), "Destination": target, "RW": False})
            self.deployment.config["services"]["otel-collector"]["volumes"].append({
                "type": "bind", "source": str(directory / source), "target": target, "read_only": True})

    def test_exact_stage_archive_and_fresh_restore_use_old_bytes_without_source(self):
        records = input_records(self.deployment)
        bundle = self.execute()
        manifest = validate_bundle(bundle)
        self.assertEqual(manifest["compose_inputs"], records)
        self.assertEqual(manifest["compose_overlays"], [item["path"] for item in records[1:]])
        self.assertEqual(manifest["resume_container_ids"], [])
        with tarfile.open(bundle / "config.tar") as archive:
            for path in self.deployment.overlays:
                self.assertEqual(archive.extractfile(str(path.relative_to(self.root))).read(), path.read_bytes())
        shutil.rmtree(self.root)
        target = self.parent / "fresh"
        commands = []
        with patch("restore.validate_target"), patch("restore.run", side_effect=lambda args, **kw: commands.append(args) or ""), \
             patch("restore.docker_json", return_value=[{"Id": workflows.IMAGE, "Architecture": "amd64", "Os": "linux"}]), \
             patch("restore.helper"), patch("restore.helper_run"):
            restore.restore(bundle, target, "ops-board-rehearsal-stage", "signoz", "root", 70)
        restored = json.loads((target / "compose.json").read_text())
        collector = restored["services"]["otel-collector"]
        self.assertEqual(collector["image"], workflows.IMAGE)
        self.assertIn("--copy-path=/var/tmp/collector-config.yaml", collector["command"])
        self.assertTrue(all(m["source"].startswith(str(target / "config")) for m in collector["volumes"]))
        self.assertEqual(restored["services"]["signoz-telemetrystore-migrator"]["profiles"], ["manual-jobs"])
        self.assertTrue(restored["networks"]["recovery"]["internal"])
        self.assertTrue(all("ports" not in s for s in restored["services"].values()))
        self.assertFalse(any("up" in cmd or "start" in cmd for cmd in commands))
        if shutil.which("docker"):
            result = subprocess.run(["docker", "compose", "-f", str(target / "compose.json"), "config", "--quiet"],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_input_audit_rejects_hash_or_order_tampering(self):
        bundle = self.execute()
        manifest = validate_bundle(bundle)
        manifest["compose_inputs"][1]["sha256"] = "0" * 64
        seal(bundle, manifest)
        with self.assertRaisesRegex(MaintenanceError, "input checksum"):
            validate_bundle(bundle)

    def test_layer_audit_order_and_path_tampering_refused(self):
        bundle = self.execute()
        original = validate_bundle(bundle)
        for layers in [list(reversed(original["compose_overlays"])), ["../outside.yaml"]]:
            manifest = copy.deepcopy(original)
            manifest["compose_overlays"] = layers
            seal(bundle, manifest)
            with self.assertRaisesRegex(MaintenanceError, "layer order"):
                validate_bundle(bundle)

    def test_source_drift_refused_before_cold_archival(self):
        inspect = self.deployment.inspect
        count = 0
        def drifting():
            nonlocal count
            count += 1
            if count == 2:
                self.deployment.overlays[0].write_text("changed during image export")
            return inspect()
        with patch.object(self.deployment, "inspect", side_effect=drifting):
            with self.assertRaisesRegex(MaintenanceError, "source inputs changed"):
                self.execute()
        manifest = json.loads(next((self.parent / "backups").glob("*/manifest.json")).read_text())
        self.assertFalse(manifest["complete"])

    def test_actual_live_stage_bind_mismatch_is_still_refused(self):
        config = self.deployment.config
        # Guard an accepted selected-stage bind using the unchanged inspect path.
        actual = Deployment(self.root, "signoz", overlays=self.deployment.overlays)
        with patch.object(actual, "resolve_config", return_value=config), \
             patch("deployment.run", return_value="selected-ids"), \
             patch("deployment.docker_json", return_value=self.deployment.containers):
            self.deployment.containers[0]["Mounts"][0]["Source"] = str(self.root / "wrong.yaml")
            with self.assertRaisesRegex(MaintenanceError, "target-to-source"):
                actual.inspect()


if __name__ == "__main__":
    unittest.main()
