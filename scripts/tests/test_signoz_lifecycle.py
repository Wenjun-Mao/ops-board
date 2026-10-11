"""Real launcher processes; no Docker daemon or application startup."""

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
LIFECYCLE = ROOT / "stacks/signoz/lifecycle"


class SigNozLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.trace = self.root / "trace"
        self.env = dict(os.environ, TRACE=str(self.trace))
        self.binary = self.root / "collector"
        self.binary.write_text(f"#!{sys.executable}\n" + '''import json, os, signal, sys
def record(value):
    with open(os.environ["TRACE"], "a") as f:
        f.write(json.dumps(value) + "\\n")
def stop(signum, frame):
    record({"signal": signum, "pid": os.getpid()})
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
checking = sys.argv[1:] == ["migrate", "sync", "check"]
if checking and os.environ.get("IGNORE"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
record({"check" if checking else "exec": sys.argv[1:], "pid": os.getpid(),
        "secret": os.environ.get("SIGNOZ_TOKENIZER_JWT_SECRET"),
        "provider": os.environ.get("SIGNOZ_TOKENIZER_PROVIDER")})
if checking and not os.environ.get("BLOCK"):
    sys.exit(int(os.environ.get("FAIL", "0")))
while True:
    signal.pause()
''')
        self.binary.chmod(0o700)

    def records(self):
        if not self.trace.exists():
            return []
        content = self.trace.read_text()
        return [json.loads(line) for line in content.splitlines()] if content.endswith("\n") else []

    def start(self, launcher, args, **environment):
        process = subprocess.Popen(["/bin/sh", str(LIFECYCLE / launcher), *map(str, args)],
                                   env=dict(self.env, **environment),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.finish, process)
        return process

    def finish(self, process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)

    def await_record(self, process, key):
        deadline = time.monotonic() + 5
        while True:
            record = next((r for r in self.records() if key in r), None)
            if record:
                return record
            if process.poll() is not None or time.monotonic() > deadline:
                self.fail(f"Fixture did not reach {key}")
            time.sleep(0.01)

    def collector(self, **environment):
        return self.start("launch-collector.sh", [self.binary, "--config=/etc/otel-collector-config.yaml"],
                          **environment)

    def test_collector_exec_pid_arguments_and_term(self):
        process = self.collector()
        running = self.await_record(process, "exec")
        self.assertEqual(running["pid"], process.pid)
        self.assertEqual(running["exec"], ["--config=/etc/otel-collector-config.yaml"])
        self.assertEqual(self.records()[0]["check"], ["migrate", "sync", "check"])
        process.send_signal(signal.SIGTERM)
        self.assertEqual(process.communicate(timeout=5), (b"", b""))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(self.records()[-1], {"signal": signal.SIGTERM, "pid": process.pid})

    def test_check_failure_preserved_without_collector(self):
        process = self.collector(FAIL="23")
        self.assertEqual(process.communicate(timeout=5), (b"", b""))
        self.assertEqual(process.returncode, 23)
        self.assertEqual(len(self.records()), 1)

    def test_initializer_forwards_term_and_int_and_reaps(self):
        for signum, expected in [(signal.SIGTERM, 143), (signal.SIGINT, 130)]:
            with self.subTest(signal=signum):
                self.trace.unlink(missing_ok=True)
                process = self.collector(BLOCK="1")
                child = self.await_record(process, "check")["pid"]
                process.send_signal(signum)
                process.communicate(timeout=8)
                self.assertEqual(process.returncode, expected)
                self.assertIn({"signal": signum, "pid": child}, self.records())
                self.assertFalse(any("exec" in r for r in self.records()))
                with self.assertRaises(ProcessLookupError):
                    os.kill(child, 0)

    def test_unresponsive_initializer_remains_unclean_137(self):
        process = self.collector(BLOCK="1", IGNORE="1")
        child = self.await_record(process, "check")["pid"]
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=8)
        self.assertEqual(process.returncode, 137)
        self.assertFalse(any("exec" in r for r in self.records()))
        with self.assertRaises(ProcessLookupError):
            os.kill(child, 0)

    def test_server_missing_empty_or_unreadable_secret_refuses_exec(self):
        for contents in [None, "", "\n", "directory"]:
            with self.subTest(contents=contents):
                secret = self.root / "secret"
                if secret.exists():
                    secret.unlink()
                if contents == "directory":
                    secret.mkdir()
                elif contents is not None:
                    secret.write_text(contents)
                process = self.start("launch-server.sh", [secret, self.binary, "server"],
                                     SIGNOZ_TOKENIZER_JWT_SECRET="must-not-fallback")
                out, err = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 78)
                self.assertEqual(out, b"")
                self.assertNotIn(b"must-not-fallback", err)
                self.assertEqual(self.records(), [])
                if secret.is_dir():
                    secret.rmdir()

    def test_server_exec_preserves_existing_secret_and_explicit_provider(self):
        secret = self.root / "secret"
        secret.write_text("existing-test-secret\n")
        process = self.start("launch-server.sh", [secret, self.binary, "server"],
                             SIGNOZ_TOKENIZER_PROVIDER="jwt")
        running = self.await_record(process, "exec")
        self.assertEqual(running, {"exec": ["server"], "pid": process.pid,
                                  "secret": "existing-test-secret", "provider": "jwt"})
        process.send_signal(signal.SIGTERM)
        out, err = process.communicate(timeout=5)
        self.assertEqual(out + err, b"")
        self.assertEqual(process.returncode, 0)

    def test_argument_refusal(self):
        for launcher in ["launch-server.sh", "launch-collector.sh"]:
            for args in [[], [str(self.binary)]]:
                process = self.start(launcher, args)
                process.communicate(timeout=5)
                self.assertEqual(process.returncode, 64)
                self.assertEqual(self.records(), [])


if __name__ == "__main__":
    unittest.main()
