"""Exercise exec and TERM delivery with real processes, without live containers."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "stacks/plane/lifecycle/launch-celery.sh"


class CeleryLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.trace = self.root / "trace.jsonl"
        self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ["PATH"],
                        TRACE=str(self.trace), SECRET_KEY="unchanged-secret", AMQP_URL="unchanged-url")
        self.program("python", '''import json, os, signal, sys
if os.environ.get("BLOCK_STEP") in sys.argv[1:]:
    def stop(signum, _frame):
        with open(os.environ["TRACE"], "a") as f:
            f.write(json.dumps({"initializer_signal": signum, "pid": os.getpid()}) + "\\n")
        sys.exit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    if os.environ.get("IGNORE_SIGNALS"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    with open(os.environ["TRACE"], "a") as f:
        f.write(json.dumps({"blocking": sys.argv[-1], "pid": os.getpid()}) + "\\n")
    while True:
        signal.pause()
with open(os.environ["TRACE"], "a") as f:
    f.write(json.dumps({"initialize": sys.argv[1:]}) + "\\n")
sys.exit(23 if os.environ.get("FAIL_STEP") in sys.argv[1:] else 0)
''')
        self.program("celery", '''import json, os, signal, sys
def stop(signum, _frame):
    with open(os.environ["TRACE"], "a") as f:
        f.write(json.dumps({"signal": signum, "pid": os.getpid()}) + "\\n")
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
with open(os.environ["TRACE"], "a") as f:
    f.write(json.dumps({"pid": os.getpid(), "command": sys.argv[1:],
                       "SECRET_KEY": os.environ["SECRET_KEY"], "AMQP_URL": os.environ["AMQP_URL"]}) + "\\n")
while True:
    signal.pause()
''')

    def program(self, name, source):
        path = self.root / name
        path.write_text(f"#!{sys.executable}\n" + source)
        path.chmod(0o700)

    def records(self):
        if not self.trace.exists():
            return []
        text = self.trace.read_text()
        return [json.loads(line) for line in text.splitlines() if line] if text.endswith("\n") else []

    def test_exec_preserves_pid_command_secrets_and_receives_term_for_both_roles(self):
        for role in ["worker", "beat"]:
            with self.subTest(role=role):
                self.trace.unlink(missing_ok=True)
                process = subprocess.Popen(["bash", str(LAUNCHER), role], cwd=self.root, env=self.env,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    deadline = time.monotonic() + 5
                    while not any("command" in record for record in self.records()):
                        if process.poll() is not None or time.monotonic() >= deadline:
                            self.fail("Celery fixture did not start within bounded wait")
                        time.sleep(0.01)
                    records = self.records()
                    self.assertEqual(records[:2], [{"initialize": ["manage.py", "wait_for_db"]},
                                                  {"initialize": ["manage.py", "wait_for_migrations"]}])
                    self.assertEqual(records[2], {"pid": process.pid, "command": ["-A", "plane", role, "-l", "info"],
                                                 "SECRET_KEY": "unchanged-secret", "AMQP_URL": "unchanged-url"})
                    process.send_signal(signal.SIGTERM)
                    output, errors = process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 0)
                    self.assertEqual(self.records()[-1], {"signal": signal.SIGTERM, "pid": process.pid})
                    self.assertEqual(output + errors, b"")
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.communicate(timeout=5)

    def test_wait_failure_prevents_celery_start_and_preserves_exit(self):
        for step, count in [("wait_for_db", 1), ("wait_for_migrations", 2)]:
            self.trace.unlink(missing_ok=True)
            result = subprocess.run(["bash", str(LAUNCHER), "worker"], cwd=self.root,
                                    env=dict(self.env, FAIL_STEP=step), capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 23)
            self.assertEqual(len(self.records()), count)
            self.assertFalse(any("command" in record for record in self.records()))

    def test_interrupted_initializer_forwards_signal_reaps_child_and_never_starts_celery(self):
        for role in ["worker", "beat"]:
            for step in ["wait_for_db", "wait_for_migrations"]:
                for signum, status in [(signal.SIGTERM, 143), (signal.SIGINT, 130)]:
                    with self.subTest(role=role, step=step, signal=signum):
                        self.trace.unlink(missing_ok=True)
                        process = subprocess.Popen(["bash", str(LAUNCHER), role], cwd=self.root,
                            env=dict(self.env, BLOCK_STEP=step), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        child_pid = None
                        try:
                            deadline = time.monotonic() + 5
                            while child_pid is None:
                                child_pid = next((r["pid"] for r in self.records() if "blocking" in r), None)
                                if child_pid is None:
                                    if process.poll() is not None or time.monotonic() >= deadline:
                                        self.fail("Initializer did not enter blocking wait")
                                    time.sleep(0.01)
                            process.send_signal(signum)
                            process.communicate(timeout=7)
                            self.assertEqual(process.returncode, status)
                            self.assertIn({"initializer_signal": signum, "pid": child_pid}, self.records())
                            self.assertFalse(any("command" in r for r in self.records()))
                            with self.assertRaises(ProcessLookupError):
                                os.kill(child_pid, 0)
                        finally:
                            if process.poll() is None:
                                process.kill()
                            process.communicate(timeout=5)
                            if child_pid is not None:
                                try:
                                    os.kill(child_pid, signal.SIGKILL)
                                except ProcessLookupError:
                                    pass

    def test_unknown_or_extra_role_refused_before_initialization(self):
        for args in [[], ["api"], ["migrator"], ["worker", "extra"]]:
            result = subprocess.run(["bash", str(LAUNCHER), *args], cwd=self.root,
                                    env=self.env, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 64)
            self.assertEqual(self.records(), [])
            self.assertNotIn(b"unchanged-secret", result.stderr)

    def test_unresponsive_initializer_is_reaped_and_reports_unclean_exit_137(self):
        process = subprocess.Popen(["bash", str(LAUNCHER), "beat"], cwd=self.root,
            env=dict(self.env, BLOCK_STEP="wait_for_db", IGNORE_SIGNALS="1"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        child_pid = None
        try:
            deadline = time.monotonic() + 5
            while child_pid is None:
                child_pid = next((r["pid"] for r in self.records() if "blocking" in r), None)
                if child_pid is None:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        self.fail("Initializer did not enter blocking wait")
                    time.sleep(0.01)
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=8)
            self.assertEqual(process.returncode, 137)
            self.assertFalse(any("command" in r for r in self.records()))
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
            if child_pid is not None:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == "__main__":
    unittest.main()
