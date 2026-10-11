"""Print one manager-reviewed phase; never execute Docker or modify state."""

import argparse
import json
from pathlib import Path
import shlex

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MANIFEST = json.loads((HERE / "release.json").read_text())
SERVICES = ["init-clickhouse", "zookeeper-1", "clickhouse",
            "signoz-telemetrystore-migrator", "signoz", "otel-collector"]
PHASES = ["render", "pull", "stop-writers", "stop-store", "init", "coordinator",
          "store", "migrate", "server", "collector", "status"]
MAINTENANCE_PHASES = ["maintenance-status", "verify", "checkpoint"]


def command(stage_id, phase, root=ROOT, archive_image=None):
    if phase == "stop-coordinator":
        raise ValueError("Use the current-layer checkpoint to own the evidenced coordinator stop")
    stage = next(stage for stage in MANIFEST["stages"] if stage["id"] == stage_id)
    root = Path(root).resolve()
    directory = root / "stacks/signoz/maintenance"
    if phase in MAINTENANCE_PHASES:
        if phase == "checkpoint" and not archive_image:
            raise ValueError("checkpoint requires an explicitly selected --archive-image")
        script = {"maintenance-status": "status.sh", "verify": "verify-stack.sh",
                  "checkpoint": "backup-stack.sh"}[phase]
        args = [str(root / "scripts" / script), "--stack", "signoz", "--context", "root"]
        for overlay in [MANIFEST["common_overlay"], stage["overlay"]]:
            args += ["--compose-overlay", str(directory / overlay)]
        if phase == "checkpoint":
            args += ["--archive-image", archive_image]
        return args
    base = ["docker", "compose", "--project-name", "ops-board", "--env-file", str(root / ".env"),
            "-f", str(root / "compose.yaml"), "-f", str(directory / MANIFEST["common_overlay"]),
            "-f", str(directory / stage["overlay"])]
    if phase == "render":
        return base + ["--profile", "*", "config", "--format", "json"]
    if phase == "pull":
        return base + ["--profile", "*", "pull", *SERVICES]
    if phase == "status":
        return base + ["--profile", "*", "ps", "-a", *SERVICES]
    if phase == "stop-writers":
        return base + ["--profile", "manual-writers", "stop", "--timeout", "60", "otel-collector", "signoz"]
    if phase == "stop-store":
        return base + ["stop", "--timeout", "60", "clickhouse"]
    if phase in {"init", "migrate"}:
        service = "init-clickhouse" if phase == "init" else "signoz-telemetrystore-migrator"
        return base + ["--profile", "manual-jobs", "up", "--no-deps", "--pull", "never",
                       "--force-recreate", "--abort-on-container-exit", "--exit-code-from", service, service]
    service = {"coordinator": "zookeeper-1", "store": "clickhouse", "server": "signoz",
               "collector": "otel-collector"}[phase]
    return base + ["up", "-d", "--no-deps", "--pull", "never", service]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=[s["id"] for s in MANIFEST["stages"]])
    parser.add_argument("--phase", required=True, choices=PHASES + MAINTENANCE_PHASES)
    parser.add_argument("--archive-image", help="explicit local helper image ID for checkpoint printing")
    args = parser.parse_args()
    if args.phase == "checkpoint" and not args.archive_image:
        parser.error("checkpoint requires --archive-image")
    print(shlex.join(command(args.stage, args.phase, archive_image=args.archive_image)))


if __name__ == "__main__":
    main()
