"""The accepted dashboard pin preserves its explicit private access contract."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class HomepageReleaseTests(unittest.TestCase):
    def assert_restricted_monitor_address(self, hosts):
        entries = hosts.split(",")
        self.assertIn("host.docker.internal:3000", entries)
        self.assertIn("localhost:3000", entries)
        self.assertIn("127.0.0.1:3000", entries)
        self.assertNotIn("arbitrary.example:3000", entries)
        self.assertTrue(all("*" not in entry for entry in entries))

    @unittest.skipUnless(shutil.which("docker"), "Docker Compose CLI is unavailable")
    def test_default_pin_access_model_and_host_allowlist(self):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("HOMEPAGE_", "COMPOSE_"))}
        result = subprocess.run(
            ["docker", "compose", "--env-file", str(ROOT / ".env.example"),
             "-f", str(ROOT / "stacks/homepage/compose.yaml"),
             "config", "--format", "json"], env=env, capture_output=True,
            text=True, timeout=30, check=True,
        )
        service = json.loads(result.stdout)["services"]["homepage"]
        self.assertEqual(service["image"], "ghcr.io/gethomepage/homepage:v2.4.0")
        self.assertEqual(service["environment"]["HOMEPAGE_AUTH_ENABLED"], "false")
        self.assertEqual(service["environment"]["HOMEPAGE_VAR_SIGNOZ_INTERNAL_URL"],
                         "http://host.docker.internal:8080")
        hosts = service["environment"]["HOMEPAGE_ALLOWED_HOSTS"]
        self.assert_restricted_monitor_address(hosts)
        self.assertIn("your-hostname:3000", hosts.split(","))
        self.assertEqual(service["ports"][0]["published"], "3000")
        self.assertFalse(any("docker.sock" in v["source"]
                             for v in service.get("volumes", [])))

    @unittest.skipUnless(shutil.which("docker"), "Docker Compose CLI is unavailable")
    def test_browser_link_and_server_probe_have_separate_addresses(self):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("HOMEPAGE_", "COMPOSE_", "SIGNOZ_"))}
        with tempfile.TemporaryDirectory() as directory:
            envfile = Path(directory) / "fixture.env"
            envfile.write_text("SIGNOZ_PUBLIC_URL=http://public.example:8080\n"
                               "SIGNOZ_INTERNAL_URL=http://host.docker.internal:18080\n")
            result = subprocess.run(
                ["docker", "compose", "--env-file", str(envfile),
                 "-f", str(ROOT / "stacks/homepage/compose.yaml"), "config", "--format", "json"],
                env=env, capture_output=True, text=True, timeout=30, check=True,
            )
        values = json.loads(result.stdout)["services"]["homepage"]["environment"]
        self.assertEqual(values["HOMEPAGE_VAR_SIGNOZ_URL"], "http://public.example:8080")
        self.assertEqual(values["HOMEPAGE_VAR_SIGNOZ_INTERNAL_URL"], "http://host.docker.internal:18080")
        groups = yaml.safe_load((ROOT / "stacks/homepage/config/services.yaml").read_text())
        signoz = next(item["SigNoz"] for group in groups for items in group.values()
                      for item in items if "SigNoz" in item)
        self.assertEqual(signoz["href"], "{{HOMEPAGE_VAR_SIGNOZ_URL}}")
        self.assertEqual(signoz["ping"], "{{HOMEPAGE_VAR_SIGNOZ_INTERNAL_URL}}/api/v1/health")

    @unittest.skipUnless(shutil.which("docker"), "Docker Compose CLI is unavailable")
    def test_fallback_keeps_internal_monitor_alias_without_wildcard(self):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("HOMEPAGE_", "COMPOSE_"))}
        with tempfile.NamedTemporaryFile() as empty_env:
            result = subprocess.run(
                ["docker", "compose", "--env-file", empty_env.name,
                 "-f", str(ROOT / "stacks/homepage/compose.yaml"),
                 "config", "--format", "json"], env=env, capture_output=True,
                text=True, timeout=30, check=True,
            )
        service = json.loads(result.stdout)["services"]["homepage"]
        self.assert_restricted_monitor_address(service["environment"]["HOMEPAGE_ALLOWED_HOSTS"])
        self.assertEqual(service["environment"]["HOMEPAGE_AUTH_ENABLED"], "false")
        self.assertEqual(service["image"], "ghcr.io/gethomepage/homepage:v2.4.0")
        self.assertEqual(service["ports"][0]["published"], "3000")


if __name__ == "__main__":
    unittest.main()
