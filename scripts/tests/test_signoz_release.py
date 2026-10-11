"""Prepared Compose/config contracts only; never start containers."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[2]
STACK = ROOT / "stacks/signoz"
RELEASE = STACK / "maintenance"
MANIFEST = json.loads((RELEASE / "release.json").read_text())
STAGES = MANIFEST["stages"]


class CollectorContractTests(unittest.TestCase):
    def test_metric_log_merges_are_table_scoped_without_increased_limits(self):
        policy = ET.parse(RELEASE / "metric-log-merges.xml").getroot()
        self.assertEqual(policy.tag, "clickhouse")
        self.assertEqual([node.tag for node in policy], ["metric_log"])
        self.assertEqual([node.tag for node in policy.find("metric_log")], ["settings"])
        self.assertEqual(policy.findtext("metric_log/settings"),
                         "enable_vertical_merge_algorithm = 1, vertical_merge_algorithm_min_rows_to_activate = 0, "
                         "vertical_merge_algorithm_min_bytes_to_activate = 0")
        self.assertIsNone(ET.parse(STACK / "common/clickhouse/config.xml").find("metric_log/settings"))

    def test_prepared_configs_preserve_baseline_with_only_named_changes(self):
        baseline = yaml.safe_load((STACK / "otel-collector-config.yaml").read_text())
        self.assertEqual(hashlib.sha256((STACK / "otel-collector-config.yaml").read_bytes()).hexdigest(),
                         MANIFEST["baseline"]["collector_config_sha256"])
        for stage in STAGES:
            prepared = yaml.safe_load((RELEASE / stage["config"]).read_text())
            normalized = copy.deepcopy(prepared)
            normalized["extensions"]["health_check"] = normalized["extensions"].pop("signoz_health_check")
            normalized["service"]["extensions"][0] = "health_check"
            if stage["collector"] != "v0.144.5":
                self.assertEqual(normalized["processors"].pop("signozspanmapper"), {"groups": []})
                pricing = normalized["processors"].pop("signozllmpricing")
                self.assertEqual(pricing["default_pricing"], {"rules": []})
                self.assertEqual(pricing["attrs"]["model"], "gen_ai.request.model")
                self.assertEqual(pricing["output_attrs"]["total"], "signoz.gen_ai.usage.tokens.cost")
                self.assertEqual(normalized["service"]["pipelines"]["traces"]["processors"],
                                 ["signozspanmetrics/delta", "signozspanmapper", "signozllmpricing", "batch"])
                normalized["service"]["pipelines"]["traces"]["processors"] = ["signozspanmetrics/delta", "batch"]
            self.assertEqual(normalized, baseline)
        self.assertEqual(yaml.safe_load((RELEASE / "opamp.yaml").read_text()),
                         {"server_endpoint": "ws://signoz:4320/v1/opamp"})

    def test_manifest_pairs_predecessors_and_storage_identity(self):
        self.assertEqual(MANIFEST["status"], "live-verified")
        self.assertEqual(MANIFEST["deployment"]["host"], "hp-15")
        self.assertEqual(MANIFEST["deployment"]["stage"], STAGES[-1]["id"])
        self.assertTrue((ROOT / MANIFEST["deployment"]["receipt"]).is_file())
        self.assertEqual(MANIFEST["project"], "ops-board")
        self.assertEqual([(s["id"], s["predecessor"], s["collector"]) for s in STAGES], [
            ("0.131.1", "0.125.1", "v0.144.5"), ("0.135.0", "0.131.1", "v0.144.6"),
            ("0.143.0", "0.135.0", "v0.144.11"), ("0.145.0", "0.143.0", "v0.144.12")])
        for stage in STAGES:
            self.assertEqual(stage["clickhouse"], "25.12.5")
            self.assertTrue(stage["gate"])
            for path in [stage["overlay"], stage["casting"], stage["config"]]:
                self.assertTrue((RELEASE / path).is_file())
            casting = yaml.safe_load((RELEASE / stage["casting"]).read_text())["spec"]
            self.assertEqual(casting["signoz"]["spec"]["image"], "signoz/signoz:" + stage["app"])
            self.assertEqual(casting["ingester"]["spec"]["image"], "signoz/signoz-otel-collector:" + stage["collector"])
            self.assertEqual(casting["metastore"]["kind"], "sqlite")
            self.assertEqual(casting["telemetrykeeper"], {"kind": "zookeeper", "spec": {"image": "signoz/zookeeper:3.7.1"}})
            xml = ET.parse(STACK / "common/clickhouse/config.xml")
            macros = yaml.safe_load(casting["telemetrystore"]["spec"]["config"]["data"]["config-0-0.yaml"])["macros"]
            self.assertEqual(macros, {"replica": xml.findtext("macros/replica"), "shard": xml.findtext("macros/shard")})

    def test_official_provenance_has_exact_template_and_archive_hashes(self):
        foundry = MANIFEST["foundry"]
        self.assertEqual(foundry["version"], "v0.3.0")
        self.assertEqual(foundry["operation"], "forge-only --no-ledger --no-updater")
        self.assertEqual(len(foundry["templates"]), 4)
        for asset in foundry["templates"]:
            self.assertRegex(asset["sha256"], r"^[a-f0-9]{64}$")
        for digest in foundry["archive_sha256"].values():
            self.assertRegex(digest, r"^[a-f0-9]{64}$")


class ComposeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("docker") or subprocess.run(["docker", "compose", "version"], capture_output=True).returncode:
            raise unittest.SkipTest("Docker Compose CLI required; no daemon used")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(STACK, self.root / "stacks/signoz")
        self.values = {"SIGNOZ_VERSION": "v0.145.0", "SIGNOZ_OTELCOL_TAG": "v0.144.12",
                       "SIGNOZ_JWT_SECRET_FILE": "../../secrets/fixture"}
        (self.root / "secrets").mkdir()
        (self.root / "secrets/fixture").write_text("fixture-secret-not-real")
        (self.root / "compose.yaml").write_text(json.dumps({"name": "ops-board", "include": [
            {"path": "stacks/signoz/compose.yaml", "env_file": ".env"}],
            "services": {"sentinel": {"image": "unchanged:1", "command": ["sleep", "infinity"]}}}))

    def render(self, stage=None, profiles=True, values=None):
        envfile = self.root / ".env"
        envfile.write_text("".join(f"{key}={value}\n" for key, value in (values or self.values).items()))
        args = ["docker", "compose", "--env-file", str(envfile), "-f", str(self.root / "compose.yaml")]
        if stage:
            for overlay in [MANIFEST["common_overlay"], stage["overlay"]]:
                args += ["-f", str(self.root / "stacks/signoz/maintenance" / overlay)]
        if profiles:
            args += ["--profile", "*"]
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith(("SIGNOZ_", "COMPOSE_"))}
        result = subprocess.run(args + ["config", "--format", "json"], env=clean_env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_promoted_fallbacks_launchers_and_exact_secret_contract(self):
        normal = self.render()
        fallback = self.render(values={"SIGNOZ_JWT_SECRET_FILE": self.values["SIGNOZ_JWT_SECRET_FILE"]})
        for name, image in [("signoz", "signoz/signoz:v0.145.0"),
                            ("otel-collector", "signoz/signoz-otel-collector:v0.144.12"),
                            ("signoz-telemetrystore-migrator", "signoz/signoz-otel-collector:v0.144.12"),
                            ("clickhouse", "clickhouse/clickhouse-server:25.12.5"),
                            ("init-clickhouse", "clickhouse/clickhouse-server:25.12.5"),
                            ("zookeeper-1", "signoz/zookeeper:3.7.1")]:
            self.assertEqual(normal["services"][name]["image"], image)
            self.assertEqual(fallback["services"][name]["image"], image)
        for name, script in [("signoz", "launch-server.sh"), ("otel-collector", "launch-collector.sh")]:
            service = normal["services"][name]
            self.assertEqual(service["entrypoint"][:2], ["/bin/sh", "/opt/signoz/lifecycle/" + script])
            mount = next(m for m in service["volumes"] if m["target"].endswith(script))
            self.assertTrue(mount["read_only"])
            self.assertEqual(mount["source"], str(self.root / "stacks/signoz/lifecycle" / script))
            self.assertEqual(service["restart"], "unless-stopped")
        server = normal["services"]["signoz"]
        self.assertEqual(server["entrypoint"][2:], ["/run/secrets/signoz_jwt_secret", "./signoz", "server"])
        self.assertEqual(server["environment"]["SIGNOZ_TOKENIZER_PROVIDER"], "jwt")
        self.assertEqual(server["environment"]["SIGNOZ_SQLSTORE_PROVIDER"], "sqlite")
        self.assertEqual(server["environment"]["SIGNOZ_TELEMETRYSTORE_PROVIDER"], "clickhouse")
        self.assertEqual(normal["services"]["otel-collector"]["command"],
                         ["/signoz-otel-collector", "--config=/etc/otel-collector-config.yaml",
                          "--manager-config=/etc/opamp-config.yaml", "--copy-path=/var/tmp/collector-config.yaml"])
        for name in ["init-clickhouse", "signoz-telemetrystore-migrator"]:
            self.assertEqual(normal["services"][name]["restart"], "no")
            self.assertNotIn("profiles", normal["services"][name])

    def test_every_stop_pins_both_pairs_and_preserves_root_resources(self):
        baseline = self.render()
        for stage in STAGES:
            with self.subTest(stage=stage["id"]):
                candidate = self.render(stage, values=self.values | {"SIGNOZ_VERSION": "ignored", "SIGNOZ_OTELCOL_TAG": "ignored"})
                self.assertEqual(candidate["name"], "ops-board")
                self.assertEqual(candidate["services"]["sentinel"], baseline["services"]["sentinel"])
                for key in ["volumes", "networks", "secrets"]:
                    self.assertEqual(candidate[key], baseline[key])
                images = {"signoz": "signoz/signoz:" + stage["app"],
                          "otel-collector": "signoz/signoz-otel-collector:" + stage["collector"],
                          "signoz-telemetrystore-migrator": "signoz/signoz-otel-collector:" + stage["collector"],
                          "clickhouse": "clickhouse/clickhouse-server:25.12.5",
                          "init-clickhouse": "clickhouse/clickhouse-server:25.12.5",
                          "zookeeper-1": "signoz/zookeeper:3.7.1"}
                for name, image in images.items():
                    self.assertEqual(candidate["services"][name]["image"], image)
                    for key in ["container_name", "networks", "ports", "secrets", "entrypoint"]:
                        self.assertEqual(candidate["services"][name].get(key), baseline["services"][name].get(key))
                for name in ["signoz", "zookeeper-1", "init-clickhouse"]:
                    self.assertEqual(candidate["services"][name]["volumes"], baseline["services"][name]["volumes"])
                old_mounts = baseline["services"]["clickhouse"]["volumes"]
                mounts = candidate["services"]["clickhouse"]["volumes"]
                self.assertEqual(mounts, old_mounts)
                policy = next(m for m in mounts if m["target"] == "/etc/clickhouse-server/config.d/metric-log-merges.xml")
                self.assertEqual(policy["source"], str(self.root / "stacks/signoz/maintenance/metric-log-merges.xml"))
                self.assertTrue(policy["read_only"])
                collector = candidate["services"]["otel-collector"]
                self.assertEqual(collector["environment"], baseline["services"]["otel-collector"]["environment"])
                expected = {"/etc/otel-collector-config.yaml": "maintenance/" + stage["config"],
                            "/etc/opamp-config.yaml": "maintenance/opamp.yaml",
                            "/opt/signoz/lifecycle/launch-collector.sh": "lifecycle/launch-collector.sh"}
                self.assertEqual(len(collector["volumes"]), len(expected))
                for mount in collector["volumes"]:
                    self.assertEqual(mount["source"], str(self.root / "stacks/signoz" / expected[mount["target"]]))
                    self.assertTrue(mount["read_only"])
                self.assertEqual(collector["command"], ["/signoz-otel-collector", "--config=/etc/otel-collector-config.yaml",
                                                        "--manager-config=/etc/opamp-config.yaml", "--copy-path=/var/tmp/collector-config.yaml"])
                server = candidate["services"]["signoz"]["environment"]
                self.assertEqual(server["SIGNOZ_SQLSTORE_PROVIDER"], "sqlite")
                self.assertEqual(server["SIGNOZ_SQLSTORE_SQLITE_PATH"], "/var/lib/signoz/signoz.db")
                if stage["id"] in {"0.143.0", "0.145.0"}:
                    self.assertEqual(server["SIGNOZ_TOKENIZER_PROVIDER"], "jwt")
                else:
                    self.assertNotIn("SIGNOZ_TOKENIZER_PROVIDER", server)

    def test_manual_jobs_writers_and_no_retry_or_implicit_initializer(self):
        for stage in STAGES:
            active = self.render(stage, profiles=False)["services"]
            for name in ["init-clickhouse", "signoz-telemetrystore-migrator", "signoz", "otel-collector"]:
                self.assertNotIn(name, active)
            complete = self.render(stage)["services"]
            self.assertEqual(set(complete["clickhouse"]["depends_on"]), {"zookeeper-1"})
            for name in ["init-clickhouse", "signoz-telemetrystore-migrator"]:
                self.assertEqual(complete[name]["profiles"], ["manual-jobs"])
                self.assertEqual(complete[name]["restart"], "no")
            for name in ["signoz", "otel-collector"]:
                self.assertEqual(complete[name]["profiles"], ["manual-writers"])
                self.assertEqual(complete[name]["restart"], "unless-stopped")
            self.assertEqual(complete["signoz-telemetrystore-migrator"]["command"], ["-c",
                "/signoz-otel-collector migrate ready &&\n/signoz-otel-collector migrate bootstrap &&\n"
                "/signoz-otel-collector migrate sync up &&\n/signoz-otel-collector migrate async up\n"])


class OfficialForgeComparisonTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("FOUNDRYCTL"), "Set verified FOUNDRYCTL for optional local forge-only comparison")
    def test_official_paired_renders_and_owned_adaptations(self):
        inputs = RELEASE / "foundry"
        before = {path.relative_to(inputs): path.read_bytes() for path in inputs.rglob("*") if path.is_file()}
        for stage in STAGES:
            with self.subTest(stage=stage["id"]), tempfile.TemporaryDirectory() as output:
                # Forge writes a lock beside its input, so both input and output must be disposable.
                casting = Path(output) / "casting.yaml"
                shutil.copyfile(RELEASE / stage["casting"], casting)
                pours = Path(output) / "pours"
                result = subprocess.run([os.environ["FOUNDRYCTL"], "--no-ledger", "--no-updater", "-f",
                                         str(casting), "-p", str(pours), "forge"], cwd=output,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(casting.read_bytes(), before[Path(stage["casting"]).relative_to("foundry")])
                directory = pours / "deployment"
                vendor = yaml.safe_load((directory / "ingester/ingester.yaml").read_text())
                owned = yaml.safe_load((RELEASE / stage["config"]).read_text())
                self.assertEqual(vendor["extensions"], owned["extensions"])
                self.assertEqual(vendor["service"]["pipelines"]["traces"]["processors"],
                                 owned["service"]["pipelines"]["traces"]["processors"])
                for processor in ["signozspanmapper", "signozllmpricing"]:
                    self.assertEqual(vendor["processors"].get(processor), owned["processors"].get(processor))
                compose = yaml.safe_load((directory / "compose.yaml").read_text())["services"]
                self.assertEqual(compose["ingester"]["image"], "signoz/signoz-otel-collector:" + stage["collector"])
                self.assertEqual(compose["signoz-signoz-0"]["image"], "signoz/signoz:" + stage["app"])
                self.assertEqual(compose["signoz-telemetrystore-migrator"]["image"], compose["ingester"]["image"])
                self.assertEqual(compose["signoz-telemetrystore-migrator"]["command"], ["-c",
                    "/signoz-otel-collector migrate ready &&\n/signoz-otel-collector migrate bootstrap &&\n"
                    "/signoz-otel-collector migrate sync up &&\n/signoz-otel-collector migrate async up\n"])
                self.assertNotIn("postgres", " ".join(compose))
                self.assertEqual(compose["signoz-telemetrykeeper-zookeeper-0"]["image"], "signoz/zookeeper:3.7.1")
                self.assertIn("--manager-config=/etc/opamp-config.yaml --copy-path=/var/tmp/collector-config.yaml",
                              compose["ingester"]["command"][1])
        self.assertEqual({path.relative_to(inputs): path.read_bytes() for path in inputs.rglob("*") if path.is_file()}, before)


if __name__ == "__main__":
    unittest.main()
