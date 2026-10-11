"""Contract tests use fake Docker metadata, not a production daemon."""

import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
from archives import safe_tar, seal, validate_bundle
from common import MaintenanceError, lock, run
from deployment import Deployment
from restore import isolated_config, validate_target

IMAGE = "sha256:" + "a" * 64


def tar_file(path, name="data/value", contents=b"state", *, link=None):
    with tarfile.open(path, "w") as archive:
        member = tarfile.TarInfo(name)
        if link:
            member.type, member.linkname = tarfile.SYMTYPE, link
            archive.addfile(member)
        else:
            member.size = len(contents)
            archive.addfile(member, io.BytesIO(contents))


def fixture(root):
    config = {"name": "ops-board", "services": {"uptime-kuma": {
        "image": "kuma:2.5.5", "container_name": "uptime-kuma",
        "volumes": [{"type": "volume", "source": "data", "target": "/app/data"}],
        "ports": [{"target": 3001, "published": "3001"}], "extra_hosts": ["host.docker.internal:host-gateway"]}},
        "volumes": {"data": {"name": "uptime-kuma-data"}}}
    container = {"Id": "kuma-id", "Name": "/uptime-kuma", "Image": IMAGE, "RestartCount": 0,
        "Config": {"Hostname": "old-node", "Env": ["PASSWORD=do-not-print"],
                   "Labels": {"com.docker.compose.project": "ops-board", "com.docker.compose.service": "uptime-kuma",
                              "com.docker.compose.project.working_dir": str(root)}, "Volumes": {"/app/data": {}}},
        "State": {"Running": True, "Status": "running", "ExitCode": 0},
        "Mounts": [{"Type": "volume", "Name": "uptime-kuma-data", "Source": "/docker/data", "Destination": "/app/data", "RW": True}]}
    return config, container


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config, self.container = fixture(self.root)
        self.extra = []

    def docker(self, *args):
        if args[0] == "compose":
            return self.config
        if args[0] == "inspect":
            return [self.container, *self.extra]
        if args[:2] == ("volume", "inspect"):
            return [{"Labels": {"com.docker.compose.project": "ops-board", "com.docker.compose.volume": "data"}}]
        if args[:2] == ("image", "inspect"):
            return [{"Config": {"Volumes": {"/data": {}}}}]
        raise AssertionError(args)

    def inspect(self):
        with patch("deployment.docker_json", side_effect=self.docker), patch("deployment.run", return_value="kuma-id"):
            return Deployment(self.root, "uptime-kuma").inspect()

    def test_root_group_does_not_switch_project_or_include_other_services(self):
        deployment = self.inspect()
        self.assertEqual(deployment.services, ["uptime-kuma"])
        self.assertIn("ops-board", deployment.compose)
        self.assertIn(str(self.root / "compose.yaml"), deployment.compose)

    def test_explicit_standalone(self):
        deployment = Deployment(self.root, "uptime-kuma", "standalone")
        self.assertEqual(deployment.project, "uptime-kuma")
        self.assertIn(str(self.root / "stacks/uptime-kuma/compose.yaml"), deployment.compose)
        with self.assertRaises(MaintenanceError):
            Deployment(self.root, "ops-board", "standalone")

    def test_wrong_project_fixed_name_refused(self):
        self.container["Config"]["Labels"]["com.docker.compose.project"] = "uptime-kuma"
        with self.assertRaises(MaintenanceError):
            self.inspect()

    def test_wrong_checkout_refused(self):
        self.container["Config"]["Labels"]["com.docker.compose.project.working_dir"] = "/another/checkout"
        with self.assertRaises(MaintenanceError):
            self.inspect()

    def test_generic_target_cannot_implicitly_scale(self):
        self.config["services"]["uptime-kuma"]["deploy"] = {"replicas": 2}
        with self.assertRaisesRegex(MaintenanceError, "replica count"):
            self.inspect()

    def test_shared_volume_refused_even_if_other_container_stopped(self):
        other = copy.deepcopy(self.container)
        other["Id"], other["Name"] = "outside", "/other"
        other["Config"]["Labels"]["com.docker.compose.project"] = "other"
        other["State"]["Running"] = False
        self.extra = [other]
        with self.assertRaises(MaintenanceError):
            self.inspect()

    def test_anonymous_declared_mount_is_manifested(self):
        self.container["Mounts"].append({"Type": "volume", "Name": "b" * 64, "Source": "/docker/anon", "Destination": "/data", "RW": True})
        self.container["Config"]["Volumes"]["/data"] = {}
        deployment = self.inspect()
        self.assertIn("b" * 64, deployment.volumes.values())
        self.assertEqual(next(iter(deployment.anonymous.values()))["target"], "/data")

    def test_undeclared_mount_refused(self):
        self.container["Mounts"].append({"Type": "volume", "Name": "extra", "Source": "/extra", "Destination": "/surprise", "RW": True})
        with self.assertRaises(MaintenanceError):
            self.inspect()

    def test_wrong_named_volume_at_same_target_cannot_become_anonymous(self):
        self.container["Mounts"][0]["Name"] = "b" * 64
        with self.assertRaisesRegex(MaintenanceError, "target-to-source"):
            self.inspect()

    def test_wrong_bind_source_at_configured_target_refused(self):
        self.config["services"]["uptime-kuma"]["volumes"].append({"type": "bind", "source": str(self.root / "config"), "target": "/config"})
        self.container["Mounts"].append({"Type": "bind", "Source": str(self.root / "other"), "Destination": "/config", "RW": True})
        with self.assertRaisesRegex(MaintenanceError, "target-to-source"):
            self.inspect()

    def test_wrong_secret_bind_at_same_target_refused(self):
        self.config["secrets"] = {"password": {"file": str(self.root / "secret")}}
        self.config["services"]["uptime-kuma"]["secrets"] = [{"source": "password"}]
        self.container["Mounts"].append({"Type": "bind", "Source": str(self.root / "wrong"), "Destination": "/run/secrets/password", "RW": False})
        with self.assertRaisesRegex(MaintenanceError, "target-to-source"):
            self.inspect()

    def test_parent_bind_outside_writer_refused(self):
        self.config["services"]["uptime-kuma"]["volumes"].append({"type": "bind", "source": str(self.root / "config"), "target": "/config"})
        self.container["Mounts"].append({"Type": "bind", "Source": str(self.root / "config"), "Destination": "/config", "RW": True})
        other = copy.deepcopy(self.container)
        other["Id"], other["Name"] = "outside", "/other"
        other["Config"]["Labels"]["com.docker.compose.project"] = "other"
        other["Mounts"] = [{"Type": "bind", "Source": str(self.root), "Destination": "/repo", "RW": True}]
        self.extra = [other]
        with self.assertRaisesRegex(MaintenanceError, "overlaps"):
            self.inspect()


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_safe_archive_and_escapes(self):
        path = self.root / "state.tar"
        tar_file(path)
        self.assertEqual(len(safe_tar(path)), 1)
        for name in ("../outside", "/absolute"):
            tar_file(path, name)
            with self.assertRaises(MaintenanceError):
                safe_tar(path)
        tar_file(path, "link", link="../../outside")
        with self.assertRaises(MaintenanceError):
            safe_tar(path)

    def test_link_parent_rejected_independent_of_member_order(self):
        path = self.root / "state.tar"
        with tarfile.open(path, "w") as archive:
            member = tarfile.TarInfo("link/child")
            archive.addfile(member)
            member = tarfile.TarInfo("link")
            member.type, member.linkname = tarfile.SYMTYPE, "safe"
            archive.addfile(member)
        with self.assertRaises(MaintenanceError):
            safe_tar(path)

    def bundle(self):
        for name in ("config.tar", "volume-0.tar"):
            tar_file(self.root / name)
        for name in ("compose.json", "containers.json", "images.tar"):
            (self.root / name).write_text("[]")
        manifest = {"format": 1, "complete": True, "volumes": {"data": {"archive": "volume-0.tar"}}}
        seal(self.root, manifest)

    def test_checksum_corruption_refused(self):
        self.bundle()
        validate_bundle(self.root)
        (self.root / "volume-0.tar").write_bytes(b"corrupt")
        with self.assertRaises(MaintenanceError):
            validate_bundle(self.root)

    def test_missing_or_unexpected_files_refused(self):
        self.bundle()
        (self.root / "unexpected").touch()
        with self.assertRaises(MaintenanceError):
            validate_bundle(self.root)
        (self.root / "unexpected").unlink()
        (self.root / "images.tar").unlink()
        with self.assertRaises(MaintenanceError):
            validate_bundle(self.root)

    def test_incomplete_and_linked_bundle_refused(self):
        self.bundle()
        manifest = json.loads((self.root / "manifest.json").read_text())
        manifest["complete"] = False
        (self.root / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(MaintenanceError):
            validate_bundle(self.root)

    def test_lock_exclusion_and_release(self):
        path = self.root / "maintenance.lock"
        with lock(path):
            with self.assertRaises(MaintenanceError):
                with lock(path):
                    self.fail("Lock reused")
        with lock(path):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_subprocess_output_never_leaks_secret(self):
        error = subprocess.CalledProcessError(1, ["docker"], stderr=b"PASSWORD=secret")
        with patch("common.subprocess.run", side_effect=error):
            with self.assertRaises(MaintenanceError) as result:
                run(["docker", "inspect"])
        self.assertNotIn("PASSWORD", str(result.exception))
        self.assertNotIn("secret", str(result.exception).replace("secrets", ""))


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config, self.container = fixture(self.root)
        self.manifest = {"source_root": str(self.root), "services": ["uptime-kuma"],
            "volumes": {"data": {"name": "uptime-kuma-data"}}, "project": "ops-board",
            "context": "root", "stack": "uptime-kuma", "architecture": "x86_64"}

    def test_isolation_and_image_data_identity(self):
        restored = isolated_config(self.config, [self.container], self.manifest, self.root / "target", "ops-board-rehearsal-test")
        service = restored["services"]["uptime-kuma"]
        self.assertTrue(restored["networks"]["recovery"]["internal"])
        self.assertEqual(service["image"], IMAGE)
        self.assertEqual(service["hostname"], "old-node")
        for unsafe in ("ports", "extra_hosts", "depends_on", "privileged", "network_mode"):
            self.assertNotIn(unsafe, service)
        self.assertEqual(restored["volumes"]["data"]["name"], "ops-board-rehearsal-test-data")

    def test_manifest_preserves_unattached_volume_not_in_rendered_config(self):
        self.manifest["volumes"]["unattached"] = {"name": "retained-unattached-volume"}
        self.assertNotIn("unattached", self.config.get("volumes", {}))
        restored = isolated_config(self.config, [self.container], self.manifest,
                                  self.root / "target", "ops-board-rehearsal-test")
        self.assertEqual(restored["volumes"]["unattached"],
                         {"name": "ops-board-rehearsal-test-unattached", "external": True})
        self.assertEqual(set(restored["volumes"]), {"data", "unattached"})

    def test_unmanifested_runtime_anonymous_volume_refused(self):
        self.container["Mounts"].append({"Type": "volume", "Name": "new-job-anonymous",
                                         "Destination": "/job-data", "RW": True})
        with self.assertRaisesRegex(MaintenanceError, "captured volume identity"):
            isolated_config(self.config, [self.container], self.manifest,
                            self.root / "target", "ops-board-rehearsal-test")

    def test_target_scope_existing_volume_and_architecture_refused(self):
        args = (self.root / "bundle", self.manifest, self.root / "fresh", "ops-board-rehearsal-test", "uptime-kuma", "root")
        with patch("restore.docker_json", return_value={"Architecture": "x86_64"}), patch("restore.run", return_value=""):
            validate_target(*args)
            with self.assertRaises(MaintenanceError):
                validate_target(*args[:3], "ops-board", *args[4:])
            with self.assertRaises(MaintenanceError):
                validate_target(*args[:4], "plane", "root")
        with patch("restore.docker_json", return_value={"Architecture": "arm64"}):
            with self.assertRaises(MaintenanceError):
                validate_target(*args)
        with patch("restore.docker_json", return_value={"Architecture": "x86_64"}), patch("restore.run", side_effect=["", "", "ops-board-rehearsal-test-data"]):
            with self.assertRaises(MaintenanceError):
                validate_target(*args)


if __name__ == "__main__":
    unittest.main()
