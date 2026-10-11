"""Only a proven, managed coordinator TERM may use the JVM's expected status."""

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
import backup
from archives import validate_bundle
from common import MaintenanceError
from deployment import GROUPS
import shutdown
import test_maintenance_workflows as workflows


MAIN = "org.apache.zookeeper.server.quorum.QuorumPeerMain"
ARGV = "\0".join(["java", "-Xmx1024m", MAIN, "/conf/zoo.cfg"]) + "\0"
MONITOR = "zk_version\t3.7.1-release\nzk_server_state\tstandalone\n" \
          "zk_num_alive_connections\t1.0\nzk_outstanding_requests\t0.0\n"


def coordinator():
    return {"Id": "zk-id", "Image": shutdown.ZOOKEEPER_IMAGE,
            "Config": {"Entrypoint": ["/opt/bitnami/scripts/zookeeper/entrypoint.sh"],
                       "Cmd": ["/opt/bitnami/scripts/zookeeper/run.sh"], "Env": [],
                       "Labels": {"com.docker.compose.service": "zookeeper-1",
                                  "com.docker.compose.project": "ops-board"}},
            "State": {"Running": True, "ExitCode": 0, "OOMKilled": False,
                      "StartedAt": "2026-10-08T00:00:00Z", "Health": {"Status": "healthy"}}}


def clients():
    result = []
    for service in ["signoz", "clickhouse"]:
        client = coordinator()
        client["Id"] = service + "-id"
        client["Config"]["Labels"]["com.docker.compose.service"] = service
        client["State"].update(Running=False, Status="exited")
        result.append(client)
    return result


class CoordinatorStopTests(unittest.TestCase):
    def intent(self, container=None, cohort=None, argv=ARGV, monitor=MONITOR):
        container = container or coordinator()
        with patch("shutdown.run", side_effect=[argv, monitor]) as run:
            result = shutdown.prepare_stop(container, clients() if cohort is None else cohort, 70)
        return result, run

    def proof(self):
        container = coordinator()
        intent, _ = self.intent(container)
        finished = datetime.fromisoformat(intent["requested_at"]) + timedelta(seconds=0.5)
        container["State"].update(Running=False, Status="exited", ExitCode=143,
                                  FinishedAt=finished.isoformat())
        return container, shutdown.finish_stop(intent, container["State"], 0.5)

    def test_managed_quiescent_term_is_accepted_without_translating_143(self):
        container, proof = self.proof()
        self.assertTrue(shutdown.checkpoint_stopped(container, proof))
        self.assertEqual(container["State"]["ExitCode"], 143)
        backup.validate_checkpoint_states([container], {container["Id"]: proof})
        with self.assertRaisesRegex(MaintenanceError, "unclean stop"):
            backup.validate_checkpoint_states([container])

    def test_intent_is_sanitized_and_probes_only_the_owned_container(self):
        intent, run = self.intent(argv=ARGV.replace("-Xmx1024m", "-Dexample.secret=not-printed"))
        self.assertNotIn("not-printed", json.dumps(intent))
        self.assertEqual(intent["monitor"]["zk_outstanding_requests"], 0)
        self.assertTrue(all(call.args[0][:3] == ["docker", "exec", "zk-id"] for call in run.call_args_list))

    def test_unrecognized_image_and_other_service_have_no_special_rule(self):
        for change in ["image", "service"]:
            container = coordinator()
            if change == "image":
                container["Image"] = "sha256:" + "a" * 64
            else:
                container["Config"]["Labels"]["com.docker.compose.service"] = "signoz"
            with patch("shutdown.run") as run:
                self.assertIsNone(shutdown.prepare_stop(container, clients(), 70))
            run.assert_not_called()
            container["State"].update(Running=False, ExitCode=143)
            self.assertFalse(shutdown.checkpoint_stopped(container))

    def test_runtime_startup_wrapper_and_stop_signal_changes_are_refused(self):
        for change in [{"State": {"Running": False}}, {"State": {"OOMKilled": True}},
                       {"State": {"Health": {"Status": "starting"}}},
                       {"Config": {"Entrypoint": ["sh", "-c"]}},
                       {"Config": {"Cmd": ["sleep", "600"]}},
                       {"Config": {"StopSignal": "SIGKILL"}}]:
            container = coordinator()
            for key, values in change.items():
                container[key].update(values)
            with self.subTest(change=change), patch("shutdown.run") as run:
                with self.assertRaisesRegex(MaintenanceError, "runtime shutdown"):
                    shutdown.prepare_stop(container, clients(), 70)
                run.assert_not_called()

    def test_missing_running_failed_or_foreign_clients_refuse_before_probe(self):
        cohorts = [[], clients()[:1]]
        for field, value in [("Running", True), ("ExitCode", 2), ("OOMKilled", True),
                             ("Status", "created")]:
            cohort = clients()
            cohort[0]["State"][field] = value
            cohorts.append(cohort)
        cohort = clients()
        cohort[0]["Config"]["Labels"]["com.docker.compose.project"] = "another-project"
        cohorts.append(cohort)
        for cohort in cohorts:
            with self.subTest(cohort=cohort), patch("shutdown.run") as run:
                with self.assertRaisesRegex(MaintenanceError, "clients must be stopped"):
                    shutdown.prepare_stop(coordinator(), cohort, 70)
                run.assert_not_called()

    def test_wrong_pid1_and_disabled_signal_or_wal_defaults_are_refused(self):
        for argv in [ARGV.replace("java\0", "sh\0"), ARGV.replace(MAIN, "OtherMain"),
                     ARGV.replace("-Xmx1024m", "-Xrs"),
                     ARGV.replace("-Xmx1024m", "-Dzookeeper.forceSync=no")]:
            with self.subTest(argv=argv), self.assertRaisesRegex(MaintenanceError, "PID-1 JVM"):
                self.intent(argv=argv)
        for value in ["-Xrs", "'-Dzookeeper.forceSync=no'", "'unterminated"]:
            container = coordinator()
            container["Config"]["Env"] = ["JAVA_TOOL_OPTIONS=" + value]
            with self.subTest(value=value), self.assertRaises(MaintenanceError):
                self.intent(container)

    def test_monitor_requires_supported_standalone_and_no_other_client_or_requests(self):
        for monitor in ["", MONITOR + "zk_version\t3.7.1-release\n",
                        MONITOR.replace("standalone", "leader"), MONITOR.replace("3.7.1-", "3.9.0-"),
                        MONITOR.replace("connections\t1.0", "connections\t2.0"),
                        MONITOR.replace("requests\t0.0", "requests\t1.0"),
                        MONITOR.replace("requests\t0.0", "requests\tNaN"),
                        MONITOR.replace("connections\t1.0", "connections\t0.5")]:
            with self.subTest(monitor=monitor), self.assertRaises(MaintenanceError):
                self.intent(monitor=monitor)

    def test_stale_changed_incomplete_and_wrong_signal_proofs_are_refused(self):
        container, proof = self.proof()
        changes = {"container_id": "wrong", "image": "wrong", "contract": "wrong", "project": "wrong",
                   "started_at": "old", "config_sha256": "wrong", "pid1_cmdline_sha256": None,
                   "clients": [], "signal": "SIGKILL", "docker_stop_completed": False,
                   "elapsed_seconds": 60, "exit_code": 0, "finished_at": "wrong", "monitor": []}
        for key, value in changes.items():
            with self.subTest(key=key):
                self.assertFalse(shutdown.checkpoint_stopped(container, {**proof, key: value}))
        for key in proof:
            changed = {k: v for k, v in proof.items() if k != key}
            with self.subTest(missing=key):
                self.assertFalse(shutdown.checkpoint_stopped(container, changed))
        for key, values in {"clients": [[None, "client"], ["", "client"], ["same", "same"]],
                            "elapsed_seconds": [True, float("nan"), float("inf"), -1]}.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    self.assertFalse(shutdown.checkpoint_stopped(container, {**proof, key: value}))

    def test_bad_final_states_and_finish_before_request_are_refused(self):
        original, proof = self.proof()
        for change in [{"Running": True}, {"OOMKilled": True}, {"ExitCode": None},
                       {"ExitCode": 2}, {"ExitCode": 137}, {"Status": "created"},
                       {"StartedAt": "new"}, {"FinishedAt": "not-a-date"}]:
            container = copy.deepcopy(original)
            container["State"].update(change)
            with self.subTest(change=change):
                self.assertFalse(shutdown.checkpoint_stopped(container, proof))
        requested = datetime.fromisoformat(proof["requested_at"]) - timedelta(seconds=1)
        proof["requested_at"] = (requested + timedelta(seconds=10)).isoformat()
        self.assertFalse(shutdown.checkpoint_stopped(original, proof))


class CoordinatorCheckpointWorkflowTests(unittest.TestCase):
    helper = workflows.BackupWorkflowTests.helper
    execute = workflows.BackupWorkflowTests.execute

    def setUp(self):
        workflows.BackupWorkflowTests.setUp(self)
        self.deployment.stack = "signoz"
        self.deployment.services = GROUPS["signoz"]
        template = copy.deepcopy(self.deployment.containers[0])
        self.deployment.containers = []
        self.deployment.config["services"] = {}
        for service in self.deployment.services:
            container = coordinator() if service == "zookeeper-1" else copy.deepcopy(template)
            container["Id"] = service + "-id"
            container["Config"]["Labels"]["com.docker.compose.service"] = service
            container["State"].update(Status="running", ExitCode=0, OOMKilled=False)
            if service in {"init-clickhouse", "signoz-telemetrystore-migrator"}:
                container["State"].update(Running=False, Status="exited")
            container["Mounts"] = []
            self.deployment.containers.append(container)
            self.deployment.config["services"][service] = {"image": container["Image"]}
        self.zoo_exit = 143

    def docker(self, *args, **kwargs):
        if args[0] == "inspect":
            return [c for c in self.deployment.containers if c["Id"] in args[1:]]
        if args[:2] == ("image", "inspect"):
            return [{"Id": image, "Size": 1, "Architecture": "amd64", "Os": "linux"} for image in args[2:]]
        return workflows.BackupWorkflowTests.docker(self, *args, **kwargs)

    def fake_run(self, args, **kwargs):
        if args[:2] in [["docker", "stop"], ["docker", "start"]]:
            self.commands.append(args)
            container = next(c for c in self.deployment.containers if c["Id"] == args[-1])
            if args[1] == "stop":
                if args[-1] == "zookeeper-1-id":
                    bundle = next((self.parent / "backups").iterdir())
                    self.assertTrue((bundle / "shutdown-intent.json").is_file())
                    self.assertTrue(all(not c["State"]["Running"] for c in self.deployment.containers
                                        if c is not container))
                container["State"].update(Running=False, Status="exited",
                    ExitCode=self.zoo_exit if args[-1] == "zookeeper-1-id" else 0,
                    FinishedAt=datetime.now(timezone.utc).isoformat())
            else:
                container["State"].update(Running=True, Status="running")
            return ""
        return workflows.BackupWorkflowTests.fake_run(self, args, **kwargs)

    def test_success_seals_evidence_preserves_143_and_resumes_only_prior_running(self):
        with patch("shutdown.run", side_effect=[ARGV, MONITOR]):
            bundle = self.execute()
        manifest = validate_bundle(bundle)
        self.assertIn("shutdown-intent.json", manifest["files"])
        self.assertIn("shutdown-evidence.json", manifest["files"])
        evidence = json.loads((bundle / "shutdown-evidence.json").read_text())
        self.assertEqual(evidence["zookeeper-1-id"]["exit_code"], 143)
        self.assertEqual([cmd[-1] for cmd in self.commands if cmd[:2] == ["docker", "start"]],
                         ["zookeeper-1-id", "clickhouse-id", "signoz-id", "otel-collector-id"])
        self.assertTrue(all(not c["State"]["Running"] for c in self.deployment.containers
                            if c["Id"] in {"init-clickhouse-id", "signoz-telemetrystore-migrator-id"}))

    def test_other_coordinator_status_still_keeps_incomplete_bundle(self):
        self.zoo_exit = 137
        with patch("shutdown.run", side_effect=[ARGV, MONITOR]):
            with self.assertRaisesRegex(MaintenanceError, "did not stop cleanly"):
                self.execute()
        manifest = json.loads(next((self.parent / "backups").glob("*/manifest.json")).read_text())
        self.assertFalse(manifest["complete"])

    def test_prestopped_coordinator_143_refuses_before_checkpoint_work(self):
        container = next(c for c in self.deployment.containers if c["Id"] == "zookeeper-1-id")
        container["State"].update(Running=False, Status="exited", ExitCode=143)
        with patch("shutdown.run") as probe:
            with self.assertRaisesRegex(MaintenanceError, "unclean stop"):
                self.execute()
            probe.assert_not_called()
        self.assertEqual(self.commands, [])
        self.assertFalse((self.parent / "backups").exists())


if __name__ == "__main__":
    unittest.main()
