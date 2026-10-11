"""Render prepared release contracts using Compose; no Docker daemon or secrets."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLANE = ROOT / "stacks/plane"
RELEASE = PLANE / "maintenance"
MANIFEST = json.loads((RELEASE / "release.json").read_text())
APP_SERVICES = ["web", "space", "admin", "live", "api", "worker", "beat-worker", "migrator", "proxy"]
BACKENDS = ["api", "worker", "beat-worker", "migrator"]
REQUIRED = ["SECRET_KEY", "LIVE_SERVER_SECRET_KEY", "POSTGRES_PASSWORD", "DATABASE_URL",
            "AMQP_URL", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]


class ManifestTests(unittest.TestCase):
    def test_original_storage_pin_agrees_without_promoting_candidate(self):
        digest = "quay.io/minio/minio@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e"
        self.assertEqual(MANIFEST["baseline"]["PLANE_STORAGE_IMAGE"], digest)
        self.assertEqual(MANIFEST["observations_not_defaults"]["storage_repo_digest"], digest)
        self.assertEqual(MANIFEST["observations_not_defaults"]["storage_image_id"],
                         "sha256:69b2ec208575b69597784255eec6fa6a2985ee9e1a47f4411a51f7f5fdd193a9")
        for path in [ROOT / ".env.example", PLANE / "plane.env.example"]:
            values = dict(line.split("=", 1) for line in path.read_text().splitlines()
                          if line and not line.startswith("#"))
            self.assertEqual(values["PLANE_STORAGE_IMAGE"], digest)
        self.assertIn("PLANE_STORAGE_IMAGE:-" + digest, (PLANE / "compose.yaml").read_text())

    def test_manifest_schema_and_paths(self):
        self.assertEqual(set(MANIFEST), {"schema_version", "status", "project", "official_assets",
                                        "baseline", "observations_not_defaults", "stages"})
        self.assertEqual(MANIFEST["schema_version"], 1)
        self.assertEqual(MANIFEST["status"], "prepared-not-deployed")
        self.assertEqual(MANIFEST["project"], "ops-board")
        self.assertEqual([s["id"] for s in MANIFEST["stages"]],
                         ["3-db", "3-cache", "4-app", "5-storage", "6-rabbit-bridge", "6-rabbit-final"])
        for stage in MANIFEST["stages"]:
            self.assertEqual(set(stage), {"id", "overlay", "versions", "services", "gate"})
            self.assertTrue((RELEASE / stage["overlay"]).is_file())
            self.assertEqual(len(stage["versions"]), 1)
            self.assertTrue(stage["gate"])
        for name, asset in MANIFEST["official_assets"].items():
            self.assertEqual(asset["url"], f"https://github.com/makeplane/plane/releases/download/v1.4.2/{name}")
            self.assertRegex(asset["sha256"], r"^[0-9a-f]{64}$")


class ComposeReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("docker"):
            raise unittest.SkipTest("Docker Compose CLI required (no daemon used)")
        result = subprocess.run(["docker", "compose", "version"], capture_output=True)
        if result.returncode:
            raise unittest.SkipTest("Docker Compose CLI unavailable")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        stack = self.root / "stacks/plane"
        shutil.copytree(PLANE, stack, ignore=shutil.ignore_patterns("plane.env"))
        self.env = dict(line.split("=", 1) for line in (stack / "plane.env.example").read_text().splitlines()
                        if line and not line.startswith("#"))
        for key in REQUIRED:
            self.env[key] = "fixture-" + key.lower()
        self.env["DATABASE_URL"] = "postgresql://plane:fixture@plane-db/plane"
        self.env["AMQP_URL"] = "amqp://plane:fixture@plane-mq:5672/plane"
        (self.root / "compose.yaml").write_text(json.dumps({"name": "ops-board", "include": [
            {"path": "stacks/plane/compose.yaml", "env_file": "stacks/plane/plane.env"}],
            "services": {"sentinel": {"image": "unchanged:1", "command": ["sleep", "infinity"]}}}))

    def render(self, *overlays, changes=None, missing=(), expect_error=False, all_profiles=True):
        values = self.env | (changes or {})
        for key in missing:
            values.pop(key, None)
        envfile = self.root / "stacks/plane/plane.env"
        envfile.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
        command = ["docker", "compose", "--env-file", str(envfile), "-f", str(self.root / "compose.yaml")]
        if all_profiles:
            command.extend(["--profile", "*"])
        for overlay in overlays:
            command.extend(["-f", str(self.root / "stacks/plane/maintenance" / overlay)])
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in self.env and k not in values and k not in REQUIRED
                     and not k.startswith(("PLANE_", "COMPOSE_"))}
        result = subprocess.run(command + ["config", "--format", "json"], env=clean_env,
                                capture_output=True, text=True, timeout=30)
        if expect_error:
            self.assertNotEqual(result.returncode, 0)
            return
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_fresh_example_and_fallbacks_agree_with_live_baseline(self):
        normal = self.render()
        fallback = self.render(missing=MANIFEST["baseline"])
        for name, expected in {"plane-db": "postgres:15.7-alpine", "plane-redis": "valkey/valkey:7.2.11-alpine",
                               "plane-mq": "rabbitmq:3.13.6-management-alpine",
                               "plane-minio": MANIFEST["baseline"]["PLANE_STORAGE_IMAGE"]}.items():
            self.assertEqual(normal["services"][name]["image"], expected)
            self.assertEqual(fallback["services"][name]["image"], expected)
        for name in APP_SERVICES:
            self.assertTrue(normal["services"][name]["image"].endswith(":v1.3.1"))
            self.assertEqual(normal["services"][name]["image"], fallback["services"][name]["image"])

    def test_optional_hostname_preserves_absent_baseline_and_explicit_identity(self):
        absent = self.render(missing=["PLANE_RABBITMQ_HOSTNAME"])
        self.assertIn(absent["services"]["plane-mq"].get("hostname"), [None, ""])
        explicit = self.render(changes={"PLANE_RABBITMQ_HOSTNAME": "3bb3429c1ce3"})
        self.assertEqual(explicit["services"]["plane-mq"]["hostname"], "3bb3429c1ce3")

    def test_baseline_dependencies_can_be_pinned_independently(self):
        for key, service, image in [
            ("PLANE_POSTGRES_VERSION", "plane-db", "postgres:fixture"),
            ("PLANE_VALKEY_VERSION", "plane-redis", "valkey/valkey:fixture"),
            ("PLANE_RABBITMQ_VERSION", "plane-mq", "rabbitmq:fixture"),
            ("PLANE_STORAGE_IMAGE", "plane-minio", "fixture/storage:pin")]:
            value = image if key == "PLANE_STORAGE_IMAGE" else "fixture"
            baseline = self.render()
            candidate = self.render(changes={key: value})
            self.assertEqual(candidate["services"][service]["image"], image)
            changed = {name for name in baseline["services"]
                       if baseline["services"][name]["image"] != candidate["services"][name]["image"]}
            self.assertEqual(changed, {service})

    def test_each_stage_changes_only_its_images_and_preserves_resources(self):
        baseline = self.render()
        for stage in MANIFEST["stages"]:
            with self.subTest(stage=stage["id"]):
                changes = stage["versions"] | {"PLANE_RABBITMQ_HOSTNAME": "3bb3429c1ce3"}
                candidate = self.render(stage["overlay"], changes=changes)
                changed = {name for name, service in candidate["services"].items()
                           if service["image"] != baseline["services"][name]["image"]}
                self.assertEqual(changed, set(stage["services"]))
                self.assertEqual(candidate["volumes"], baseline["volumes"])
                self.assertEqual(candidate["services"]["sentinel"], baseline["services"]["sentinel"])
                for name in baseline["services"]:
                    for key in ["volumes", "ports", "depends_on", "networks", "command"]:
                        self.assertEqual(candidate["services"][name].get(key), baseline["services"][name].get(key))

    def test_app_lockstep_explicit_migrator_and_required_credentials(self):
        for release in ["v1.4.2", "v-fixture"]:
            candidate = self.render("stage4-app.yaml", changes={"PLANE_APP_TARGET_RELEASE": release})
            for name in APP_SERVICES:
                self.assertTrue(candidate["services"][name]["image"].endswith(":" + release))
            job = candidate["services"]["migrator"]
            self.assertEqual(job["profiles"], ["manual-jobs"])
            self.assertEqual(job["deploy"]["restart_policy"]["condition"], "none")
            self.assertEqual(job["command"], ["./bin/docker-entrypoint-migrator.sh"])
            for name in BACKENDS:
                for key in REQUIRED:
                    self.assertEqual(candidate["services"][name]["environment"][key], self.env[key])
                self.assertEqual(candidate["services"][name]["environment"]["DEBUG"], "0")
        for key in REQUIRED:
            for value in [None, ""]:
                with self.subTest(key=key, value=value):
                    self.render("stage4-app.yaml", missing=[key] if value is None else [],
                                changes={} if value is None else {key: value}, expect_error=True)

    def test_storage_uses_silo_entrypoint_command_and_requires_credentials(self):
        service = self.render("stage5-storage.yaml")["services"]["plane-minio"]
        self.assertEqual(service["image"], "pgsty/silo:RELEASE.2026-09-16T00-00-00Z")
        self.assertEqual(service["command"], ["server", "/export", "--console-address", ":9090"])
        self.assertIsNone(service.get("entrypoint"))
        self.assertNotIn("ports", service)
        for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]:
            self.render("stage5-storage.yaml", missing=[key], expect_error=True)

    def test_rabbit_requires_selected_stop_and_preserved_node(self):
        for version in ["4.2.9-management-alpine", "4.3.6-management-alpine"]:
            candidate = self.render("stage6-rabbit.yaml", changes={
                "PLANE_RABBITMQ_TARGET_VERSION": version, "PLANE_RABBITMQ_HOSTNAME": "3bb3429c1ce3"})
            broker = candidate["services"]["plane-mq"]
            self.assertEqual(broker["image"], "rabbitmq:" + version)
            self.assertEqual(broker["hostname"], "3bb3429c1ce3")
            self.assertNotIn("RABBITMQ_NODENAME", broker["environment"])
        self.render("stage6-rabbit.yaml", expect_error=True)
        self.render("stage6-rabbit.yaml", changes={"PLANE_RABBITMQ_TARGET_VERSION": "4.2.9-management-alpine"},
                    expect_error=True)

    def test_app_migrator_is_not_implicitly_selected(self):
        candidate = self.render("stage4-app.yaml", all_profiles=False)
        self.assertNotIn("migrator", candidate["services"])
        self.assertIn("api", candidate["services"])

    def test_only_worker_and_beat_use_readonly_exec_launcher(self):
        for overlays in [(), ("stage4-app.yaml",)]:
            candidate = self.render(*overlays)
            for name, role in [("worker", "worker"), ("beat-worker", "beat")]:
                service = candidate["services"][name]
                self.assertEqual(service["command"], ["bash", "/code/ops-board/launch-celery.sh", role])
                binds = [mount for mount in service["volumes"] if mount["type"] == "bind"]
                self.assertEqual(len(binds), 1)
                self.assertEqual(binds[0]["source"], str(self.root / "stacks/plane/lifecycle/launch-celery.sh"))
                self.assertEqual(binds[0]["target"], "/code/ops-board/launch-celery.sh")
                self.assertTrue(binds[0]["read_only"])
            for name, role in [("api", "api"), ("migrator", "migrator")]:
                service = candidate["services"][name]
                self.assertEqual(service["command"], [f"./bin/docker-entrypoint-{role}.sh"])
                self.assertFalse(any(mount["type"] == "bind" for mount in service["volumes"]))

    def test_cumulative_overlays_do_not_revert_previously_accepted_images(self):
        overlays = ["stage3-db.yaml", "stage3-cache.yaml", "stage4-app.yaml", "stage5-storage.yaml", "stage6-rabbit.yaml"]
        candidate = self.render(*overlays, changes={"PLANE_RABBITMQ_TARGET_VERSION": "4.3.6-management-alpine",
                                                   "PLANE_RABBITMQ_HOSTNAME": "3bb3429c1ce3"})
        self.assertEqual(candidate["services"]["plane-db"]["image"], "postgres:15.19-alpine")
        self.assertEqual(candidate["services"]["plane-redis"]["image"], "valkey/valkey:7.2.14-alpine")
        self.assertEqual(candidate["services"]["plane-mq"]["image"], "rabbitmq:4.3.6-management-alpine")
        self.assertEqual(candidate["services"]["plane-minio"]["image"], "pgsty/silo:RELEASE.2026-09-16T00-00-00Z")
        for name in APP_SERVICES:
            self.assertTrue(candidate["services"][name]["image"].endswith(":v1.4.2"))


if __name__ == "__main__":
    unittest.main()
