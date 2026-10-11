"""Command printer scope and refusal; no execution of printed commands."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "stacks/signoz/maintenance/commands.py"
SPEC = importlib.util.spec_from_file_location("signoz_commands", PATH)
COMMANDS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMMANDS)


class CommandTests(unittest.TestCase):
    def test_all_stage_commands_use_exact_root_project_and_only_one_stop(self):
        for stage in COMMANDS.MANIFEST["stages"]:
            for phase in COMMANDS.PHASES:
                args = COMMANDS.command(stage["id"], phase)
                self.assertEqual(args[:4], ["docker", "compose", "--project-name", "ops-board"])
                overlays = [args[i + 1] for i, value in enumerate(args) if value == "-f"]
                self.assertEqual(overlays, [str(ROOT / "compose.yaml"),
                    str(PATH.parent / "prepared.yaml"), str(PATH.parent / stage["overlay"])])
                self.assertNotIn("down", args)
                self.assertNotIn("--remove-orphans", args)
                self.assertNotIn("--volumes", args)
                self.assertNotIn("exec", args)
                self.assertNotIn("latest", " ".join(args))

    def test_job_up_is_explicit_scoped_nonretry_and_exit_gated(self):
        for phase, service in [("init", "init-clickhouse"), ("migrate", "signoz-telemetrystore-migrator")]:
            args = COMMANDS.command("0.131.1", phase)
            self.assertEqual(args[args.index("up"):], ["up", "--no-deps", "--pull", "never",
                "--force-recreate", "--abort-on-container-exit", "--exit-code-from", service, service])
            self.assertNotIn("-d", args)
            self.assertEqual(args[args.index("--profile") + 1], "manual-jobs")

    def test_longrunning_ups_one_service_at_a_time_never_pull(self):
        for phase, service in [("coordinator", "zookeeper-1"), ("store", "clickhouse"),
                               ("server", "signoz"), ("collector", "otel-collector")]:
            args = COMMANDS.command("0.145.0", phase)
            self.assertEqual(args[args.index("up"):], ["up", "-d", "--no-deps", "--pull", "never", service])

    def test_stop_phases_keep_stateful_order_and_original_timeout(self):
        for phase, services in [("stop-writers", ["otel-collector", "signoz"]),
                                ("stop-store", ["clickhouse"])]:
            args = COMMANDS.command("0.131.1", phase)
            self.assertEqual(args[args.index("stop"):], ["stop", "--timeout", "60", *services])
            if phase == "stop-writers":
                self.assertEqual(args[args.index("--profile") + 1], "manual-writers")

    def test_coordinator_stop_cannot_bypass_checkpoint_evidence(self):
        self.assertNotIn("stop-coordinator", COMMANDS.PHASES)
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            COMMANDS.command("0.131.1", "stop-coordinator")

    def test_cli_prints_only_and_rejects_unknown_stops_or_phases(self):
        result = subprocess.run([sys.executable, str(PATH), "--stage", "0.143.0", "--phase", "migrate"],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertIn("--no-deps --pull never", result.stdout)
        self.assertEqual(result.stderr, "")
        for args in [[], ["--stage", "0.144.0", "--phase", "server"],
                     ["--stage", "0.145.0", "--phase", "cast"],
                     ["--stage", "0.131.1", "--phase", "stop-coordinator"]]:
            result = subprocess.run([sys.executable, str(PATH), *args], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")

    def test_maintenance_phases_capture_explicit_current_stage_without_inferred_gates(self):
        for stage in COMMANDS.MANIFEST["stages"]:
            for phase in COMMANDS.MAINTENANCE_PHASES:
                args = COMMANDS.command(stage["id"], phase, archive_image="sha256:" + "a" * 64)
                self.assertEqual(args[1:5], ["--stack", "signoz", "--context", "root"])
                layers = [args[i + 1] for i, value in enumerate(args) if value == "--compose-overlay"]
                self.assertEqual(layers, [str(PATH.parent / "prepared.yaml"), str(PATH.parent / stage["overlay"])])
                self.assertNotIn("up", args)
                self.assertNotIn("--profile", args)
                self.assertNotIn("--dry-run", args)
        with self.assertRaisesRegex(ValueError, "archive-image"):
            COMMANDS.command("0.131.1", "checkpoint")


if __name__ == "__main__":
    unittest.main()
