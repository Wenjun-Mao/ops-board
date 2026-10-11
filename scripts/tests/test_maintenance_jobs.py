"""Created containers have exit zero without having completed their one-shot job."""

import contextlib
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
import cli
from common import MaintenanceError
from deployment import job_completed
from test_maintenance import IMAGE
import test_maintenance_workflows as workflows
import verify


class JobCompletionTests(unittest.TestCase):
    def setUp(self):
        self.fake = workflows.FakeDeployment(Path("/repo"))
        self.fake.stack = "plane"
        self.fake.services = ["api", "migrator"]
        self.fake.compose = ["docker", "compose"]
        self.fake.summary = lambda: None
        app = self.fake.containers[0]
        app["Config"]["Labels"]["com.docker.compose.service"] = "api"
        self.fake.config["services"] = {"api": self.fake.config["services"]["uptime-kuma"]}
        self.job = copy.deepcopy(app)
        self.job["Id"] = "migrator-id"
        self.job["Config"]["Labels"]["com.docker.compose.service"] = "migrator"
        self.job["State"] = {"Status": "exited", "Running": False, "ExitCode": 0, "OOMKilled": False}
        self.fake.config["services"]["migrator"] = copy.deepcopy(self.fake.config["services"]["api"])
        self.fake.containers.append(self.job)

    def update(self):
        with patch("sys.argv", ["cli.py", "update", "--stack", "plane"]), \
             patch("cli.Deployment", return_value=self.fake), \
             patch("cli.lock", return_value=contextlib.nullcontext()), \
             patch("cli.run") as run, patch("cli.docker_json", return_value=[{"Id": IMAGE}]), \
             patch("cli.wait_containers"):
            cli.main()
        return run

    def test_only_exited_zero_nonrunning_nonoom_certifies_completion(self):
        self.assertTrue(job_completed(self.job["State"]))
        for changes in [{"Status": "created"}, {"Status": "running"}, {"Running": True},
                        {"ExitCode": 1}, {"OOMKilled": True}, {"Status": None}]:
            with self.subTest(changes=changes):
                self.assertFalse(job_completed(self.job["State"] | changes))
        missing_status = dict(self.job["State"])
        del missing_status["Status"]
        self.assertFalse(job_completed(missing_status))

    def test_created_or_oom_job_refuses_passive_verify_before_probes(self):
        for changes in [{"Status": "created"}, {"OOMKilled": True}]:
            self.job["State"].update({"Status": "exited", "OOMKilled": False} | changes)
            with patch("verify.wait_containers") as wait, patch("verify.run") as run:
                with self.assertRaisesRegex(MaintenanceError, "not successfully completed"):
                    verify.verify(self.fake, 70)
            wait.assert_not_called()
            run.assert_not_called()

    def test_created_job_refuses_generic_update_before_pull_or_up(self):
        self.job["State"]["Status"] = "created"
        with patch("sys.argv", ["cli.py", "update", "--stack", "plane"]), \
             patch("cli.Deployment", return_value=self.fake), \
             patch("cli.lock", return_value=contextlib.nullcontext()), patch("cli.run") as run:
            with self.assertRaisesRegex(MaintenanceError, "not successfully completed"):
                cli.main()
        run.assert_not_called()

    def test_successful_job_remains_completed_and_is_never_restarted(self):
        with patch("verify.wait_containers") as wait, patch("verify.run") as run:
            verify.verify(self.fake, 70)
        wait.assert_called_once_with([self.fake.containers[0]["Id"]], 70)
        run.assert_not_called()
        update = self.update()
        self.assertFalse(any("migrator" in call.args[0] for call in update.call_args_list))
        self.assertEqual(self.job["State"]["Status"], "exited")

    def test_absent_one_shot_retains_optional_container_contract(self):
        self.fake.containers.remove(self.job)
        with patch("verify.wait_containers"), patch("verify.run"):
            verify.verify(self.fake, 70)
        self.update()


if __name__ == "__main__":
    unittest.main()
