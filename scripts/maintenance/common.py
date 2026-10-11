"""Restricted process execution and host-local maintenance locking."""

import contextlib
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time


class MaintenanceError(Exception):
    pass


def run(args, *, timeout=120, output=None, input_file=None, env=None):
    # Docker errors can contain expanded env values; never echo them or commands.
    try:
        result = subprocess.run(args, stdin=input_file, stdout=output or subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout, check=True, env=env)
    except (OSError, subprocess.SubprocessError) as error:
        raise MaintenanceError(f"{args[0]} operation failed; details suppressed to protect secrets") from error
    return result.stdout.decode() if output is None else ""


def docker_json(*args, timeout=120, env=None):
    # Unlike inspect/config, info defaults to human-readable text.
    command = ["docker", *args]
    if args and args[0] == "info":
        command.extend(["--format", "{{json .}}"])
    try:
        return json.loads(run(command, timeout=timeout, env=env))
    except ValueError as error:
        raise MaintenanceError("Invalid Docker JSON response") from error


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    Path(path).chmod(0o600)


def env_value(root, key, default):
    if key in os.environ:
        return os.environ[key]
    path = root / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return default


def outside_repo(path, root):
    path = Path(path).expanduser().resolve()
    if path == root or root in path.parents:
        raise MaintenanceError("Recovery artifacts must be outside the checkout")
    return path


@contextlib.contextmanager
def lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Do not unlink lock files: a second process could lock a different inode.
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise MaintenanceError("Another maintenance operation holds the lock") from error
        yield
    finally:
        os.close(fd)


def wait_containers(ids, timeout):
    deadline = time.monotonic() + timeout
    while True:
        containers = docker_json("inspect", *ids) if ids else []
        pending = False
        for container in containers:
            state = container["State"]
            health = state.get("Health", {}).get("Status")
            if not state.get("Running") or health == "unhealthy" or state.get("OOMKilled"):
                raise MaintenanceError("Container stopped, unhealthy, or OOM-killed")
            pending |= health == "starting"
        if not pending:
            return
        if time.monotonic() >= deadline:
            raise MaintenanceError("Bounded readiness wait expired")
        time.sleep(min(2, max(0, deadline - time.monotonic())))
