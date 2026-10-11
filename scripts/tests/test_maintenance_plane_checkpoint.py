"""Already-held Plane writers and stopped broker must remain stopped at backup."""

import copy
import json
from pathlib import Path
import sys
import tarfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
import backup
from archives import validate_bundle
from broker import capture_broker_evidence
from common import MaintenanceError
from deployment import GROUPS
from test_maintenance import IMAGE
import test_maintenance_workflows as workflows


class PlaneCheckpointTests(unittest.TestCase):
    docker = workflows.BackupWorkflowTests.docker
    fake_run = workflows.BackupWorkflowTests.fake_run
    execute = workflows.BackupWorkflowTests.execute

    def setUp(self):
        workflows.BackupWorkflowTests.setUp(self)
        template = copy.deepcopy(self.deployment.containers[0])
        self.deployment.stack = "plane"
        self.deployment.services = GROUPS["plane"]
        self.deployment.containers = []
        self.deployment.config = {"services": {}, "volumes": {}}
        self.deployment.volumes = {}
        for service in self.deployment.services:
            container = copy.deepcopy(template)
            container["Id"] = service + "-id"
            container["Config"]["Labels"]["com.docker.compose.service"] = service
            container["State"].update(Running=False, Status="exited", ExitCode=0)
            container["Mounts"] = []
            self.deployment.config["services"][service] = {"image": IMAGE}
            self.deployment.containers.append(container)
        for service, key, target in [("plane-db", "pgdata", "/var/lib/postgresql/data"),
                                     ("plane-redis", "redisdata", "/data"),
                                     ("plane-mq", "rabbitmq_data", "/var/lib/rabbitmq"),
                                     ("plane-minio", "uploads", "/export"),
                                     ("plane-minio", "anonymous-minio", "/data"),
                                     ("api", "logs_api", "/code/plane/logs"),
                                     ("worker", "logs_worker", "/code/plane/logs"),
                                     ("beat-worker", "logs_beat-worker", "/code/plane/logs"),
                                     ("migrator", "logs_migrator", "/code/plane/logs"),
                                     ("proxy", "proxy_config", "/config"),
                                     ("proxy", "proxy_data", "/data")]:
            name = "plane_" + key
            container = next(c for c in self.deployment.containers
                             if c["Config"]["Labels"]["com.docker.compose.service"] == service)
            container["Mounts"].append({"Type": "volume", "Name": name, "Destination": target})
            self.deployment.volumes[key] = name
        self.broker = next(c for c in self.deployment.containers if c["Id"] == "plane-mq-id")
        self.broker["Config"]["Hostname"] = "3bb3429c1ce3"
        launcher = self.root / "stacks/plane/lifecycle/launch-celery.sh"
        launcher.parent.mkdir(parents=True)
        launcher.write_text("captured launcher contract")
        for service in ["worker", "beat-worker"]:
            container = next(c for c in self.deployment.containers if c["Id"] == service + "-id")
            container["Mounts"].append({"Type": "bind", "Source": str(launcher),
                                        "Destination": "/code/ops-board/launch-celery.sh", "RW": False})
            self.deployment.config["services"][service]["volumes"] = [
                {"type": "bind", "source": str(launcher), "target": "/code/ops-board/launch-celery.sh",
                 "read_only": True}]
        self.archived = []

    def helper(self, image, args, volume=None, **kwargs):
        if args[:2] != ["du", "-sk"]:
            self.archived.append(volume)
        return workflows.BackupWorkflowTests.helper(self, image, args, volume, **kwargs)

    def test_already_stopped_family_captures_all_volumes_with_empty_resume_set(self):
        bundle = self.execute()
        manifest = validate_bundle(bundle)
        self.assertTrue(manifest["complete"])
        self.assertEqual(manifest["resume_container_ids"], [])
        self.assertEqual(set(self.archived), set(self.deployment.volumes.values()))
        self.assertTrue(all((bundle / value["archive"]).is_file() for value in manifest["volumes"].values()))
        self.assertFalse(any(c["State"]["Running"] for c in self.deployment.containers))
        self.assertFalse(any(cmd[:2] in [["docker", "exec"], ["docker", "stop"], ["docker", "start"]]
                             for cmd in self.commands))
        audit = manifest["rabbitmq_identity"]
        self.assertEqual(audit["hostname"], "3bb3429c1ce3")
        self.assertEqual(audit["recorded_state"]["Running"], False)
        self.assertEqual(audit["cold_volume_keys"], ["rabbitmq_data"])
        self.assertEqual(audit["live_diagnostics"], {"available": False, "reason": "broker already stopped"})
        self.assertIsNone(audit["node_status"])
        self.assertIsNone(audit["definitions"])
        self.assertFalse((bundle / "rabbitmq-definitions.json").exists())
        self.assertTrue(audit["isolated_restore_verification"]["required"])
        self.assertFalse(audit["isolated_restore_verification"]["passed"])
        self.assertEqual(json.loads((bundle / "cleanup.json").read_text())["prior_running_ids"], [])
        with tarfile.open(bundle / "config.tar") as archive:
            self.assertEqual(archive.extractfile("stacks/plane/lifecycle/launch-celery.sh").read(),
                             b"captured launcher contract")

    def test_running_broker_keeps_live_diagnostics(self):
        self.broker["State"].update(Running=True, Status="running")
        folder = self.parent / "audit"
        folder.mkdir()
        manifest = {"volumes": {key: {"name": name} for key, name in self.deployment.volumes.items()}}
        with patch("broker.run", return_value="live-evidence") as run:
            capture_broker_evidence(folder, self.deployment.containers, manifest, 70)
        self.assertEqual(run.call_count, 2)
        self.assertTrue(all(call.args[0][:3] == ["docker", "exec", "plane-mq-id"] for call in run.call_args_list))
        self.assertTrue(manifest["rabbitmq_identity"]["live_diagnostics"]["available"])
        self.assertEqual((folder / "rabbitmq-definitions.json").read_text(), "live-evidence")

    def test_already_stopped_unclean_exit_or_oom_is_refused_without_resume(self):
        for state in [{"ExitCode": 1}, {"ExitCode": 2}, {"ExitCode": 137}, {"OOMKilled": True}]:
            with self.subTest(state=state):
                self.broker["State"].update({"ExitCode": 0, "OOMKilled": False} | state)
                with self.assertRaisesRegex(MaintenanceError, "unclean stop"):
                    self.execute()
                self.assertFalse(self.archived)
                self.assertFalse(any(cmd[:2] == ["docker", "start"] for cmd in self.commands))

    def assert_preflight_refusal(self, message):
        destination = self.parent / "backups"
        prior_states = [copy.deepcopy(c["State"]) for c in self.deployment.containers]
        with patch("backup.docker_json") as docker, patch("backup.helper") as helper, \
             patch("backup.run") as run, patch("backup.capture_broker_evidence") as audit:
            with self.assertRaisesRegex(MaintenanceError, message):
                backup.backup(self.deployment, destination, IMAGE, 70)
        docker.assert_not_called()
        helper.assert_not_called()
        run.assert_not_called()
        audit.assert_not_called()
        self.assertFalse(destination.exists())
        self.assertEqual([c["State"] for c in self.deployment.containers], prior_states)

    def test_unclean_prestopped_writers_are_refused_before_export_or_bundle(self):
        writer = next(c for c in self.deployment.containers if c["Id"] == "beat-worker-id")
        for state in [{"ExitCode": 1}, {"ExitCode": 2}, {"ExitCode": 137}, {"OOMKilled": True}]:
            with self.subTest(state=state):
                writer["State"].update({"ExitCode": 0, "OOMKilled": False} | state)
                self.assert_preflight_refusal("unclean stop")

    def test_inactive_failed_one_shot_is_refused_without_restart(self):
        job = next(c for c in self.deployment.containers if c["Id"] == "migrator-id")
        for state in [{"ExitCode": 1}, {"ExitCode": 137}, {"OOMKilled": True}]:
            with self.subTest(state=state):
                job["State"].update({"ExitCode": 0, "OOMKilled": False} | state)
                self.assert_preflight_refusal("did not complete cleanly")

    def test_active_one_shot_still_refuses_preflight_without_any_state_change(self):
        job = next(c for c in self.deployment.containers if c["Id"] == "migrator-id")
        job["State"].update(Running=True, Status="running")
        self.assert_preflight_refusal("is active")

    def test_created_one_shot_is_not_completed_and_refuses_preflight(self):
        job = next(c for c in self.deployment.containers if c["Id"] == "migrator-id")
        job["State"].update(Running=False, Status="created", ExitCode=0, OOMKilled=False)
        self.assert_preflight_refusal("did not complete cleanly")

    def test_missing_or_unmanifested_broker_mount_refused(self):
        folder = self.parent / "audit"
        folder.mkdir()
        with patch("broker.run") as run:
            with self.assertRaisesRegex(MaintenanceError, "unique checkpoint identity"):
                capture_broker_evidence(folder, [self.broker], {"volumes": {}}, 70)
            self.broker["Mounts"] = []
            with self.assertRaisesRegex(MaintenanceError, "complete declared state"):
                capture_broker_evidence(folder, [self.broker], {"volumes": {}}, 70)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
