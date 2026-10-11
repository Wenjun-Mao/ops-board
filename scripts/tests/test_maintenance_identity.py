"""Checkpoint identity ignores only top-level Docker Mounts ordering."""

import copy
import itertools
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
from backup import unchanged
from common import MaintenanceError


class CheckpointIdentityTests(unittest.TestCase):
    def setUp(self):
        self.original = [{
            "Id": "container-id",
            "Image": "sha256:unchanged-image",
            "Config": {"Env": ["FIRST=1", "SECOND=2"], "Cmd": ["server", "--config", "file"]},
            "Mounts": [
                {"Type": "volume", "Source": "/docker/volumes/data", "Name": "data",
                 "Destination": "/data", "RW": True, "Mode": "z", "Propagation": ""},
                {"Type": "bind", "Source": "/repo/config", "Destination": "/config",
                 "RW": False, "Mode": "ro", "Propagation": "rprivate"},
                {"Type": "volume", "Source": "/docker/volumes/other", "Name": "other",
                 "Destination": "/other", "RW": True, "Driver": "local"}],
            "State": {"Running": True}}]
        self.config = {"services": {"app": {"command": ["server", "--config", "file"],
                                           "volumes": ["data:/data", "config:/config"]}}}
        self.deployment = SimpleNamespace(containers=copy.deepcopy(self.original), config=copy.deepcopy(self.config))

    def check(self, **kwargs):
        unchanged(self.deployment, self.original, self.config, **kwargs)

    def test_all_equivalent_permutations_accepted_without_mutating_either_snapshot(self):
        for cold in [False, True]:
            for mounts in itertools.permutations(self.original[0]["Mounts"]):
                with self.subTest(cold=cold, destinations=[m["Destination"] for m in mounts]):
                    self.deployment.containers[0]["Mounts"] = copy.deepcopy(list(mounts))
                    self.deployment.containers[0]["State"]["Running"] = not cold
                    before_original = copy.deepcopy(self.original)
                    before_actual = copy.deepcopy(self.deployment.containers)
                    self.check(cold=cold)
                    self.assertEqual(self.original, before_original)
                    self.assertEqual(self.deployment.containers, before_actual)

    def test_any_mount_field_change_is_refused_even_with_reordering(self):
        for field, value in [("Type", "bind"), ("Source", "/different"), ("Name", "different"),
                             ("Destination", "/different"), ("RW", False), ("Mode", "ro"),
                             ("Propagation", "rshared"), ("AdditionalField", "new")]:
            with self.subTest(field=field):
                self.deployment.containers = copy.deepcopy(self.original)
                self.deployment.containers[0]["Mounts"][0][field] = value
                self.deployment.containers[0]["Mounts"].reverse()
                with self.assertRaisesRegex(MaintenanceError, "identity/config changed"):
                    self.check()

    def test_missing_mount_or_mount_field_is_refused(self):
        for side in ["original", "actual"]:
            for missing in ["mount", "field"]:
                with self.subTest(side=side, missing=missing):
                    self.setUp()
                    container = self.original[0] if side == "original" else self.deployment.containers[0]
                    if missing == "mount":
                        container["Mounts"].pop()
                    else:
                        container["Mounts"][0].pop("RW")
                    with self.assertRaisesRegex(MaintenanceError, "identity/config changed"):
                        self.check()

    def test_duplicate_destination_refused_on_either_or_both_snapshots(self):
        for side in ["original", "actual", "both"]:
            for identical in [False, True]:
                with self.subTest(side=side, identical=identical):
                    self.setUp()
                    snapshots = {"original": self.original, "actual": self.deployment.containers}
                    for name in ([side] if side != "both" else snapshots):
                        mounts = snapshots[name][0]["Mounts"]
                        duplicate = copy.deepcopy(mounts[0])
                        if not identical:
                            duplicate["Source"] = "/different"
                        mounts.append(duplicate)
                    with self.assertRaisesRegex(MaintenanceError, "Duplicate mount destination"):
                        self.check()

    def test_invalid_or_missing_destination_is_refused(self):
        for destination in [None, "", 42]:
            with self.subTest(destination=destination):
                self.deployment.containers = copy.deepcopy(self.original)
                self.deployment.containers[0]["Mounts"][0]["Destination"] = destination
                with self.assertRaisesRegex(MaintenanceError, "Invalid mount destination"):
                    self.check()
        self.deployment.containers[0]["Mounts"][0].pop("Destination")
        with self.assertRaisesRegex(MaintenanceError, "Invalid mount destination"):
            self.check()

    def test_image_and_container_config_changes_remain_refused(self):
        for field in ["Image", "Config"]:
            with self.subTest(field=field):
                self.deployment.containers = copy.deepcopy(self.original)
                if field == "Image":
                    self.deployment.containers[0][field] = "changed-image"
                else:
                    self.deployment.containers[0][field]["Env"].reverse()
                with self.assertRaisesRegex(MaintenanceError, "identity/config changed"):
                    self.check()

    def test_compose_and_nested_mount_lists_keep_order_significance(self):
        self.deployment.config["services"]["app"]["volumes"].reverse()
        with self.assertRaisesRegex(MaintenanceError, "identity/config changed"):
            self.check()
        self.deployment.config = copy.deepcopy(self.config)
        self.original[0]["Mounts"][0]["Nested"] = {"order": ["first", "second"]}
        self.deployment.containers = copy.deepcopy(self.original)
        self.deployment.containers[0]["Mounts"][0]["Nested"]["order"].reverse()
        with self.assertRaisesRegex(MaintenanceError, "identity/config changed"):
            self.check()

    def test_running_state_guard_remains_strict_with_equivalent_mounts(self):
        self.deployment.containers[0]["Mounts"].reverse()
        self.deployment.containers[0]["State"]["Running"] = False
        with self.assertRaisesRegex(MaintenanceError, "running-state change"):
            self.check()
        self.deployment.containers[0]["State"]["Running"] = True
        with self.assertRaisesRegex(MaintenanceError, "running-state change"):
            self.check(cold=True)


if __name__ == "__main__":
    unittest.main()
