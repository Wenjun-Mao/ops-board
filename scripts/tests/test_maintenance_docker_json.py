"""Docker's info output contract differs from inspect's JSON default."""

from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
from common import MaintenanceError, docker_json


class DockerJsonTests(unittest.TestCase):
    def test_info_requests_json_at_cli_boundary(self):
        def docker(args, **kwargs):
            self.assertEqual(args, ["docker", "info", "--format", "{{json .}}"])
            self.assertEqual(kwargs["timeout"], 90)
            return subprocess.CompletedProcess(args, 0, b'{"ID":"daemon","Architecture":"x86_64"}')

        with patch("common.subprocess.run", side_effect=docker):
            self.assertEqual(docker_json("info", timeout=90),
                             {"ID": "daemon", "Architecture": "x86_64"})

    def test_other_json_commands_keep_existing_argv(self):
        for args in [("inspect", "container"), ("image", "inspect", "image"),
                     ("compose", "config", "--format", "json")]:
            with self.subTest(args=args), patch("common.subprocess.run") as execute:
                execute.return_value = subprocess.CompletedProcess(args, 0, b"[]")
                self.assertEqual(docker_json(*args), [])
                self.assertEqual(execute.call_args.args[0], ["docker", *args])

    def test_text_or_malformed_output_is_still_refused(self):
        for output in [b"Server: Docker Engine\n Architecture: x86_64", b'{"ID":', b""]:
            with self.subTest(output=output), patch("common.subprocess.run") as execute:
                execute.return_value = subprocess.CompletedProcess([], 0, output)
                with self.assertRaisesRegex(MaintenanceError, "Invalid Docker JSON response"):
                    docker_json("info")


if __name__ == "__main__":
    unittest.main()
