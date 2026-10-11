"""Nonzero cold exits never certify a checkpoint or resume held writers."""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
from backup import validate_checkpoint_states
from common import MaintenanceError
import test_maintenance_plane_checkpoint as plane


class CleanStopTests(unittest.TestCase):
    setUp = plane.PlaneCheckpointTests.setUp
    docker = plane.PlaneCheckpointTests.docker
    fake_run = plane.PlaneCheckpointTests.fake_run
    helper = plane.PlaneCheckpointTests.helper
    execute = plane.PlaneCheckpointTests.execute

    def test_every_nonrunning_nonzero_or_unknown_exit_is_unclean(self):
        for code in [None, 1, 2, 42, 137, 143]:
            with self.subTest(code=code), self.assertRaisesRegex(MaintenanceError, "unclean stop"):
                validate_checkpoint_states([{"Config": {"Labels": {"com.docker.compose.service": "signoz"}},
                                            "State": {"Running": False, "ExitCode": code}}])

    def test_exit_two_after_stop_keeps_incomplete_bundle_and_never_resumes_held_writers(self):
        writer = next(c for c in self.deployment.containers if c["Id"] == "api-id")
        writer["State"].update(Running=True, Status="running", ExitCode=0)
        original_run, original_docker = self.fake_run, self.docker
        def stop_two(args, **kwargs):
            if args[:2] in [["docker", "stop"], ["docker", "start"]]:
                self.commands.append(args)
                self.assertEqual(args[-1], "api-id")
                if args[1] == "stop":
                    writer["State"].update(Running=False, Status="exited", ExitCode=2)
                else:
                    writer["State"].update(Running=True, Status="running", ExitCode=0)
                return ""
            return original_run(args, **kwargs)
        def inspect_writer(*args, **kwargs):
            if args == ("inspect", "api-id"):
                return [writer]
            return original_docker(*args, **kwargs)
        self.fake_run, self.docker = stop_two, inspect_writer
        with self.assertRaisesRegex(MaintenanceError, "did not stop cleanly"):
            self.execute()
        manifest_path = next((self.parent / "backups").glob("*/manifest.json"))
        manifest = json.loads(manifest_path.read_text())
        self.assertFalse(manifest["complete"])
        self.assertFalse(self.archived)
        self.assertEqual([cmd[-1] for cmd in self.commands if cmd[:2] == ["docker", "start"]], ["api-id"])
        self.assertTrue(all(not c["State"]["Running"] for c in self.deployment.containers if c is not writer))
        cleanup = json.loads((manifest_path.parent / "cleanup.json").read_text())
        self.assertEqual(cleanup["prior_running_ids"], ["api-id"])
        self.assertEqual(cleanup["stop_attempt_ids"], ["api-id"])

    def test_prestopped_exit_two_refuses_capture_without_start_or_stop(self):
        writer = next(c for c in self.deployment.containers if c["Id"] == "beat-worker-id")
        writer["State"]["ExitCode"] = 2
        with self.assertRaisesRegex(MaintenanceError, "unclean stop"):
            self.execute()
        self.assertFalse((self.parent / "backups").exists())
        self.assertFalse(self.commands)
        self.assertTrue(all(not c["State"]["Running"] for c in self.deployment.containers))


if __name__ == "__main__":
    unittest.main()
