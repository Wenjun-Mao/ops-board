"""Workflow failure tests; live Linux recovery remains a separate acceptance gate."""

import contextlib
import copy
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
import backup
import cli
import restore
from archives import validate_bundle
from archives import seal
from common import MaintenanceError
from test_maintenance import IMAGE, fixture, tar_file


class FakeDeployment:
    def __init__(self, root):
        self.root = root
        self.stack, self.context, self.project = "uptime-kuma", "root", "ops-board"
        self.services = ["uptime-kuma"]
        self.config, container = fixture(root)
        self.containers = [container]
        self.volumes, self.anonymous = {"data": "uptime-kuma-data"}, {}

    def inspect(self):
        return self

    def ordered_running(self):
        return [c for c in self.containers if c["State"]["Running"]]


class BackupWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name).resolve()
        self.root = self.parent / "repo"
        self.root.mkdir()
        for name in (".env", ".env.example", "compose.yaml"):
            (self.root / name).write_text("secret configuration")
        (self.root / "secrets").mkdir()
        (self.root / "secrets/password").write_text("preserved-secret")
        self.deployment = FakeDeployment(self.root)
        self.commands, self.fail_archive, self.fail_start = [], False, False

    def docker(self, *args, **kwargs):
        if args[0] == "info":
            return {"ID": "daemon", "Architecture": "x86_64"}
        if args[:2] == ("image", "inspect"):
            return [{"Id": IMAGE, "Size": 1, "Architecture": "amd64", "Os": "linux"}]
        if args[:2] == ("volume", "inspect"):
            return [{"Name": args[2]}]
        if args[0] == "inspect":
            return self.deployment.containers
        raise AssertionError(args)

    def fake_run(self, args, **kwargs):
        self.commands.append(args)
        if args[:2] == ["docker", "stop"]:
            self.deployment.containers[0]["State"]["Running"] = False
        if args[:2] == ["docker", "start"]:
            if self.fail_start:
                raise MaintenanceError("injected start failure")
            self.deployment.containers[0]["State"]["Running"] = True
        if args[:3] == ["docker", "image", "save"]:
            kwargs["output"].write(b"opaque-image-export")
        return "revision"

    def helper(self, image, args, volume=None, **kwargs):
        if args[:2] == ["du", "-sk"]:
            return "1 /volume"
        if self.fail_archive:
            raise MaintenanceError("injected export failure")
        tar_file(Path(kwargs["output"].name))
        return ""

    def execute(self):
        with patch("backup.docker_json", side_effect=self.docker), patch("backup.run", side_effect=self.fake_run), \
             patch("backup.helper", return_value={"Id": IMAGE}), patch("backup.helper_run", side_effect=self.helper), \
             patch("backup.wait_containers"):
            return backup.backup(self.deployment, self.parent / "backups", IMAGE, 70)

    def test_successful_checkpoint_checksums_permissions_exact_resume_set(self):
        bundle = self.execute()
        manifest = validate_bundle(bundle)
        self.assertEqual(manifest["resume_container_ids"], ["kuma-id"])
        self.assertTrue(self.deployment.containers[0]["State"]["Running"])
        self.assertEqual([c[-1] for c in self.commands if c[:2] == ["docker", "start"]], ["kuma-id"])
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in bundle.iterdir()))

    def test_backup_failure_resumes_only_paused_and_keeps_incomplete_artifacts(self):
        self.fail_archive = True
        with self.assertRaises(MaintenanceError):
            self.execute()
        self.assertTrue(self.deployment.containers[0]["State"]["Running"])
        manifest = next((self.parent / "backups").glob("*/manifest.json"))
        self.assertFalse(json.loads(manifest.read_text())["complete"])
        cleanup = json.loads((manifest.parent / "cleanup.json").read_text())
        self.assertTrue(cleanup["ready"])
        self.assertEqual(cleanup["prior_running_ids"], ["kuma-id"])

    def test_backup_resume_failure_is_reported_not_hidden(self):
        self.fail_start = True
        with self.assertRaisesRegex(MaintenanceError, "cleanup failed"):
            self.execute()
        self.assertFalse(self.deployment.containers[0]["State"]["Running"])

    def test_configuration_symlink_refused_before_stop(self):
        (self.root / "secrets/password").unlink()
        (self.root / "secrets/password").symlink_to(self.root / ".env")
        with self.assertRaises(MaintenanceError):
            self.execute()
        self.assertFalse(any(c[:2] == ["docker", "stop"] for c in self.commands))

    def test_helper_failure_removes_only_own_transient_container(self):
        commands = []
        def call(args, **kwargs):
            commands.append(args)
            if args[1] == "run":
                raise MaintenanceError("timeout")
            return ""
        with patch("backup.run", side_effect=call):
            with self.assertRaises(MaintenanceError):
                backup.helper_run(IMAGE, ["tar", "-cpf", "-", "."])
        self.assertEqual(commands[1][:3], ["docker", "rm", "-f"])
        self.assertTrue(re.fullmatch("ops-board-archive-[a-f0-9]{32}", commands[1][-1]))

    def test_image_export_precedes_stop_and_identity_drift_blocks_quiesce(self):
        bundle = self.execute()
        self.assertTrue(bundle.exists())
        save = next(i for i, c in enumerate(self.commands) if c[:3] == ["docker", "image", "save"])
        stop = next(i for i, c in enumerate(self.commands) if c[:2] == ["docker", "stop"])
        self.assertLess(save, stop)
        config = copy.deepcopy(self.deployment.config)
        self.deployment.containers[0]["Image"] = "changed"
        old = copy.deepcopy(self.deployment.containers)
        old[0]["Image"] = IMAGE
        with self.assertRaisesRegex(MaintenanceError, "identity/config changed"):
            backup.unchanged(self.deployment, old, config)

    def test_interrupted_stop_waits_for_daemon_settlement_before_restart(self):
        commands = []
        states = iter([{"Running": True}, {"Running": False}, {"Running": False}])
        with patch("backup.run", side_effect=lambda args, **kwargs: commands.append(args)), \
             patch("backup.docker_json", side_effect=lambda *args, **kwargs: [{"State": next(states)}]), \
             patch("backup.time.sleep"), patch("backup.wait_containers") as readiness:
            report = backup.resume_after_backup(["prior-id"], {"prior-id"}, 70)
        self.assertTrue(report["ready"])
        self.assertEqual(commands, [["docker", "stop", "--time", "60", "prior-id"], ["docker", "start", "prior-id"]])
        readiness.assert_called_once_with(["prior-id"], 70)

    def test_unsettled_stop_blocks_resume_and_reports_readiness(self):
        with patch("backup.run") as run, patch("backup.wait_stopped", side_effect=MaintenanceError("unsettled")), \
             patch("backup.wait_containers") as readiness:
            report = backup.resume_after_backup(["old-writer", "old-storage"], {"old-storage"}, 70)
        self.assertEqual(report["unsettled_stops"], ["old-storage"])
        self.assertFalse(report["ready"])
        self.assertFalse(any(call.args[0][1] == "start" for call in run.call_args_list))
        readiness.assert_called_once_with(["old-writer", "old-storage"], 70)

    def test_settlement_wait_is_bounded(self):
        with patch("backup.time.monotonic", side_effect=[0, 0, 71, 71]), \
             patch("backup.time.sleep"), patch("backup.docker_json", return_value=[{"State": {"Running": True}}]):
            with self.assertRaisesRegex(MaintenanceError, "bounded wait"):
                backup.wait_stopped("old-id", 70)

    def test_cleanup_checks_all_prior_running_ids_but_restarts_only_attempted_ids(self):
        with patch("backup.run") as run, patch("backup.docker_json", return_value=[{"State": {"Running": False}}]), \
             patch("backup.wait_containers") as readiness:
            report = backup.resume_after_backup(["paused"], set(), 70, prior_running=["paused", "untouched"])
        self.assertTrue(report["ready"])
        run.assert_called_once_with(["docker", "start", "paused"], timeout=70)
        readiness.assert_called_once_with(["paused", "untouched"], 70)

    def test_archive_error_and_readiness_failure_keep_nonzero_cleanup_evidence(self):
        self.fail_archive = True
        with patch("backup.docker_json", side_effect=self.docker), patch("backup.run", side_effect=self.fake_run), \
             patch("backup.helper", return_value={"Id": IMAGE}), patch("backup.helper_run", side_effect=self.helper), \
             patch("backup.wait_containers", side_effect=MaintenanceError("health failure")) as readiness:
            with self.assertRaisesRegex(MaintenanceError, "cleanup failed"):
                backup.backup(self.deployment, self.parent / "backups", IMAGE, 70)
        readiness.assert_called_once_with(["kuma-id"], 70)
        report_path = next((self.parent / "backups").glob("*/cleanup.json"))
        self.assertTrue(json.loads(report_path.read_text())["readiness_failed"])
        self.assertFalse(json.loads((report_path.parent / "manifest.json").read_text())["complete"])

    def test_stop_client_exception_still_settles_and_restores_on_error_path(self):
        interrupted = False
        def call(args, **kwargs):
            nonlocal interrupted
            if args[:2] == ["docker", "stop"] and not interrupted:
                interrupted = True
                self.commands.append(args)
                raise MaintenanceError("interrupted stop client")
            return self.fake_run(args, **kwargs)
        with patch("backup.docker_json", side_effect=self.docker), patch("backup.run", side_effect=call), \
             patch("backup.helper", return_value={"Id": IMAGE}), patch("backup.helper_run", side_effect=self.helper), \
             patch("backup.wait_containers") as readiness:
            with self.assertRaisesRegex(MaintenanceError, "interrupted stop client"):
                backup.backup(self.deployment, self.parent / "backups", IMAGE, 70)
        self.assertTrue(self.deployment.containers[0]["State"]["Running"])
        self.assertEqual(sum(c[:2] == ["docker", "stop"] for c in self.commands), 2)
        self.assertEqual([c[-1] for c in self.commands if c[:2] == ["docker", "start"]], ["kuma-id"])
        readiness.assert_called_once_with(["kuma-id"], 70)


class CLIWorkflowTests(unittest.TestCase):
    def test_update_refuses_stopped_writers_before_pull(self):
        fake = FakeDeployment(Path("/repo"))
        fake.containers[0]["State"]["Running"] = False
        fake.compose = ["docker", "compose"]
        with patch("sys.argv", ["cli.py", "update", "--stack", "uptime-kuma"]), \
             patch("cli.Deployment", return_value=fake), patch("cli.lock", return_value=contextlib.nullcontext()), \
             patch("cli.run") as run:
            with self.assertRaises(MaintenanceError):
                cli.main()
            run.assert_not_called()

    def test_update_changed_image_does_not_up_or_run_migrator(self):
        fake = FakeDeployment(Path("/repo"))
        fake.compose = ["docker", "compose"]
        with patch("sys.argv", ["cli.py", "update", "--stack", "uptime-kuma"]), \
             patch("cli.Deployment", return_value=fake), patch("cli.lock", return_value=contextlib.nullcontext()), \
             patch("cli.run") as run, patch("cli.docker_json", return_value=[{"Id": "different"}]):
            with self.assertRaises(MaintenanceError):
                cli.main()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][-2:], ["pull", "uptime-kuma"])

    def test_restore_invalid_bundle_has_no_docker_mutations(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("restore.run") as run:
                with self.assertRaises(MaintenanceError):
                    restore.restore(Path(folder), Path(folder) / "target", "ops-board-rehearsal-t", "uptime-kuma", "root", 70)
                run.assert_not_called()

    def test_compose_preserves_literal_dollars(self):
        self.assertEqual(restore.compose_literals({"environment": ["SECRET=$value${other}"]}),
                         {"environment": ["SECRET=$$value$${other}"]})
        runtime = {"command": ["sh", "-c", 'node_os=$(uname -s); printf "%s" "${node_os}"']}
        self.assertEqual(restore.compose_literals(runtime),
                         {"command": ["sh", "-c", 'node_os=$$(uname -s); printf "%s" "$${node_os}"']})

    def test_failed_restore_removes_only_new_volume_and_starts_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            bundle, target = root / "bundle", root / "target"
            bundle.mkdir()
            config, container = fixture(root / "source")
            (bundle / "compose.json").write_text(json.dumps(config))
            (bundle / "containers.json").write_text(json.dumps([container]))
            (bundle / "images.tar").write_bytes(b"image")
            tar_file(bundle / "config.tar")
            tar_file(bundle / "volume-0.tar")
            manifest = {"format": 1, "complete": True, "project": "ops-board", "context": "root",
                "stack": "uptime-kuma", "services": ["uptime-kuma"], "architecture": "x86_64",
                "source_root": str(root / "source"), "archive_image": IMAGE,
                "images": [{"id": IMAGE, "architecture": "amd64", "os": "linux"}],
                "volumes": {"data": {"name": "uptime-kuma-data", "archive": "volume-0.tar"}}}
            seal(bundle, manifest)
            commands = []
            def call(args, **kwargs):
                commands.append(args)
                return ""
            def docker(*args):
                return {"Architecture": "x86_64"} if args[0] == "info" else [{"Id": IMAGE, "Architecture": "amd64", "Os": "linux"}]
            with patch("restore.run", side_effect=call), patch("restore.docker_json", side_effect=docker), \
                 patch("restore.helper"), patch("restore.helper_run", side_effect=MaintenanceError("injected restore failure")):
                with self.assertRaises(MaintenanceError):
                    restore.restore(bundle, target, "ops-board-rehearsal-t", "uptime-kuma", "root", 70)
            removals = [c for c in commands if c[:3] == ["docker", "volume", "rm"]]
            self.assertEqual(removals, [["docker", "volume", "rm", "ops-board-rehearsal-t-data"]])
            self.assertFalse(any("up" in c or "start" in c for c in commands))
            self.assertTrue((target / "failure.json").exists())


class InitConfigurationTests(unittest.TestCase):
    def test_example_is_fresh_release_authority_and_existing_credentials_unchanged(self):
        repo = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("scripts/init-local-config.sh", "scripts/lib/ops-board.sh", ".env.example", "stacks/plane/plane.env.example"):
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(repo / name, destination)
            example = root / "stacks/plane/plane.env.example"
            example.write_text(re.sub(r"^APP_RELEASE=.*$", "APP_RELEASE=v9.8.7", example.read_text(), flags=re.M))
            command = ["bash", str(root / "scripts/init-local-config.sh"), "--host", "hp-15"]
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
            plane = root / "stacks/plane/plane.env"
            self.assertIn("APP_RELEASE=v9.8.7", plane.read_text())
            original = plane.read_bytes()
            secrets = {p.name: p.read_bytes() for p in (root / "secrets").iterdir()}
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
            self.assertEqual(plane.read_bytes(), original)
            self.assertEqual(secrets, {p.name: p.read_bytes() for p in (root / "secrets").iterdir()})
            self.assertEqual(plane.stat().st_mode & 0o777, 0o600)

    def test_checked_in_defaults_agree(self):
        repo = Path(__file__).resolve().parents[2]
        example = (repo / "stacks/plane/plane.env.example").read_text()
        release = re.search(r"^APP_RELEASE=(.+)$", example, re.M).group(1)
        defaults = re.findall(r"APP_RELEASE:-([^}]+)", (repo / "stacks/plane/compose.yaml").read_text())
        self.assertTrue(defaults)
        self.assertEqual(set(defaults), {release})
        self.assertIn("UPTIME_KUMA_VERSION=2.5.5", (repo / ".env.example").read_text())
        self.assertIn("UPTIME_KUMA_VERSION:-2.5.5", (repo / "stacks/uptime-kuma/compose.yaml").read_text())

    @unittest.skipUnless(shutil.which("docker"), "Docker Compose CLI not installed")
    def test_isolated_compose_schema_with_real_cli_without_daemon_or_start(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            config, container = fixture(root)
            manifest = {"source_root": str(root), "services": ["uptime-kuma"],
                        "volumes": {"data": {"name": "uptime-kuma-data"}}}
            result = restore.isolated_config(config, [container], manifest, root, "ops-board-rehearsal-schema")
            path = root / "compose.json"
            path.write_text(json.dumps(restore.compose_literals(result)))
            subprocess.run(["docker", "compose", "-f", str(path), "config", "--quiet"],
                           check=True, timeout=30, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


if __name__ == "__main__":
    unittest.main()
