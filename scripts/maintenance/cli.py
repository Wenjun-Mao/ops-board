#!/usr/bin/env python3
"""Host-side maintenance; optional stage-source validation also uses PyYAML."""

import argparse
import os
from pathlib import Path
import shlex
import signal
import sys

from backup import backup
from common import MaintenanceError, docker_json, env_value, lock, outside_repo, run, wait_containers
from deployment import Deployment, JOBS, job_completed
from restore import restore
from verify import verify


def parser():
    value = argparse.ArgumentParser(description="Scoped Ops Board maintenance; no migration execution.")
    value.add_argument("operation", choices=["status", "update", "backup", "restore", "verify"])
    value.add_argument("--stack", default="ops-board", choices=["ops-board", "plane", "signoz", "homepage", "uptime-kuma"])
    value.add_argument("--context", default="root", choices=["root", "standalone"])
    value.add_argument("--dry-run", action="store_true")
    value.add_argument("--compose-overlay", action="append", default=[], metavar="FILE",
                       help="ordered reviewed stage layer (repeatable; root plane/signoz only)")
    value.add_argument("--timeout-sec", type=int, default=600, help="bounded per-operation timeout (70..3600 seconds)")
    value.add_argument("--backup-root", help="restricted directory outside checkout")
    value.add_argument("--archive-image", help="already-local sha256 image ID containing sh/tar/du")
    value.add_argument("--backup", help="completed checkpoint directory")
    value.add_argument("--target", help="fresh restore directory outside checkout")
    value.add_argument("--project", help="unique ops-board-rehearsal-<name> project")
    return value


def main():
    args = parser().parse_args()
    os.umask(0o077)
    root = Path(__file__).resolve().parents[2]
    if not 70 <= args.timeout_sec <= 3600:
        raise MaintenanceError("Timeout must be between 70 and 3600 seconds")
    if args.operation == "restore" and args.compose_overlay:
        raise MaintenanceError("Restore uses captured bytes; --compose-overlay is not allowed")
    deployment = Deployment(root, args.stack, args.context, args.compose_overlay)
    backup_root = outside_repo(args.backup_root or env_value(root, "OPS_BOARD_BACKUP_ROOT", str(Path.home() / "ops-board-backups")), root)
    if args.operation == "restore" and not all([args.backup, args.target, args.project]):
        raise MaintenanceError("Restore requires --backup, --target, and --project")
    if args.operation == "backup" and not args.archive_image:
        raise MaintenanceError("Backup requires --archive-image (local immutable helper ID)")
    if args.dry_run and args.operation != "restore":
        if deployment.overlays:
            deployment.resolve_config()
            print("Source overlay contract validated (Compose config only; no daemon preflight).")
        print(f"Plan only: context={args.context}, project={deployment.project}, group={args.stack}")
        if deployment.overlays:
            print("Compose inputs: " + ", ".join(str(p.relative_to(deployment.root)) for p in deployment.compose_inputs))
        print("Services: " + ", ".join(deployment.services))
        if args.operation == "update":
            services = [s for s in deployment.services if s not in JOBS]
            print(shlex.join(deployment.compose + ["pull", *services]))
            print(shlex.join(deployment.compose + ["up", "-d", "--no-deps", "--no-recreate", "--pull", "never", *services]))
            print("Live identity/image guards and lock precede mutation; no migration jobs.")
        elif args.operation == "status":
            print(shlex.join(deployment.compose + ["ps", "-a", *deployment.services]))
        elif args.operation == "backup":
            print(f"Cold checkpoint to {backup_root}; preflight, stop scoped services, capture images/config/state, resume only original running services.")
        else:
            print("Inspect identities/readiness; bounded passive protocol/HTTP probes. No bootstrap.")
        return
    if args.operation == "status":
        deployment.inspect(require_all=False).summary()
        return
    if args.operation == "verify":
        verify(deployment, args.timeout_sec)
        return
    lock_path = outside_repo(env_value(root, "OPS_BOARD_MAINTENANCE_LOCK", str(Path.home() / ".local/state/ops-board/maintenance.lock")), root)
    with lock(lock_path):
        if args.operation == "backup":
            backup(deployment, backup_root, args.archive_image, args.timeout_sec)
        elif args.operation == "restore":
            restore(Path(args.backup).absolute(), outside_repo(args.target, root), args.project,
                    args.stack, args.context, args.timeout_sec, dry_run=args.dry_run)
        else:
            deployment.inspect()
            services = [s for s in deployment.services if s not in JOBS]
            if any(not c["State"].get("Running") for c in deployment.containers
                   if c["Config"]["Labels"]["com.docker.compose.service"] not in JOBS):
                raise MaintenanceError("Scoped writers are stopped; generic update must not resume a failed stage")
            if any(not job_completed(c["State"]) for c in deployment.containers
                   if c["Config"]["Labels"]["com.docker.compose.service"] in JOBS):
                raise MaintenanceError("Initialization/migration job is not successfully completed; generic update refused")
            run(deployment.compose + ["pull", *services], timeout=args.timeout_sec)
            for container in deployment.containers:
                service = container["Config"]["Labels"]["com.docker.compose.service"]
                if service not in JOBS:
                    image = deployment.config["services"][service]["image"]
                    if docker_json("image", "inspect", image)[0]["Id"] != container["Image"]:
                        raise MaintenanceError("Image differs from live state; use a reviewed staged migration, not generic update")
            deployment.inspect()
            run(deployment.compose + ["up", "-d", "--no-deps", "--no-recreate", "--pull", "never", *services], timeout=args.timeout_sec)
            wait_containers([c["Id"] for c in deployment.containers if c["Config"]["Labels"]["com.docker.compose.service"] not in JOBS], args.timeout_sec)
            deployment.summary()
            print("Existing containers retained; no migration or config change executed.")


def interrupted(signum, _frame):
    raise MaintenanceError(f"Interrupted by signal {signum}; failure cleanup requested")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        main()
    except (MaintenanceError, OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR: {error if isinstance(error, MaintenanceError) else 'Maintenance validation failed; details suppressed'}", file=sys.stderr)
        sys.exit(1)
