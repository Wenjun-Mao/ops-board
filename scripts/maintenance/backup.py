"""Orderly cold checkpoints; backup failure cleanup never runs migration logic."""

from datetime import datetime, timezone
import os
import copy
from pathlib import Path
import re
import shutil
import tarfile
import uuid
import time

from archives import safe_tar, seal, validate_compose_inputs
from broker import capture_broker_evidence
from common import MaintenanceError, docker_json, run, wait_containers, write_json
from deployment import JOBS, job_completed
from overlays import assert_inputs, input_records
from shutdown import checkpoint_stopped, finish_stop, prepare_stop


def helper(image):
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image or ""):
        raise MaintenanceError("--archive-image must be an already-local immutable sha256 image ID")
    info = docker_json("image", "inspect", image)[0]
    helper_run(image, ["sh", "-c", "command -v tar >/dev/null && command -v du >/dev/null"])
    return info


def helper_command(image, volume=None, writable=False):
    command = ["docker", "run", "--name", "ops-board-archive-" + uuid.uuid4().hex,
               "--rm", "--pull", "never", "--network", "none", "--read-only",
               "--user", "0:0", "--cap-drop", "ALL", "--cap-add", "DAC_OVERRIDE",
               "--security-opt", "no-new-privileges", "--entrypoint", ""]
    if writable:
        command += ["--cap-add", "CHOWN", "--cap-add", "FOWNER", "-i"]
    if volume:
        command += ["--mount", f"type=volume,src={volume},dst=/volume" + ("" if writable else ",readonly")]
    return command + [image]


def helper_run(image, arguments, volume=None, writable=False, **kwargs):
    command = helper_command(image, volume, writable)
    try:
        return run(command + arguments, **kwargs)
    except BaseException:
        try:
            run(["docker", "rm", "-f", command[command.index("--name") + 1]], timeout=120)
        except MaintenanceError:
            remaining = run(["docker", "ps", "-aq", "--filter",
                             "name=^/" + command[command.index("--name") + 1] + "$"])
            if remaining.strip():
                raise MaintenanceError("Transient archive helper cleanup failed; inspect owned archive containers")
        raise


def config_paths(deployment):
    root = deployment.root
    paths = {root / "compose.yaml", root / ".env", root / ".env.example"}
    paths.update(root.glob("stacks/*/compose.yaml"))
    paths.update(root.glob("stacks/*/*.env"))
    paths.update(root.glob("stacks/*/.*env"))
    paths.update(root.glob("stacks/*/*.env.example"))
    paths.update(getattr(deployment, "compose_inputs", [root / "compose.yaml"]))
    paths.add(root / "secrets")
    for service in deployment.services:
        for mount in deployment.config["services"][service].get("volumes", []):
            if mount["type"] == "bind":
                paths.add(Path(mount["source"]))
    for secret in deployment.config.get("secrets", {}).values():
        if secret.get("external") or not secret.get("file"):
            raise MaintenanceError("External secret needs a separate recovery design")
        paths.add(Path(secret["file"]))
    for container in deployment.containers:
        for mount in container.get("Mounts", []):
            if mount["Type"] == "bind":
                paths.add(Path(mount["Source"]))
    selected = []
    for path in sorted(paths):
        if not path.exists():
            raise MaintenanceError("Required local configuration/bind is missing")
        if root not in path.absolute().parents or path.is_symlink() or path.resolve() != path.absolute():
            raise MaintenanceError("External/symlink bind or secret needs an explicit recovery design")
        for child in [path, *(path.rglob("*") if path.is_dir() else [])]:
            if child.is_symlink() or not (child.is_dir() or child.is_file()):
                raise MaintenanceError("Configuration contains links or special files")
        if not any(parent in path.parents for parent in selected):
            selected.append(path)
    return selected


def estimate(deployment, paths, image_infos, archive_image, destination):
    size = sum(i["Size"] for i in image_infos)
    for path in paths:
        size += sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() else path.stat().st_size
    for volume in deployment.volumes.values():
        value = helper_run(archive_image, ["du", "-sk", "/volume"], volume)
        size += int(value.split()[0]) * 1024
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.disk_usage(destination).free < size * 2 + 512 * 1024 * 1024:
        raise MaintenanceError("Insufficient backup capacity (2x estimate plus 512 MiB reserve required)")


def validate_checkpoint_states(containers, shutdown_evidence=None):
    shutdown_evidence = shutdown_evidence or {}
    for container in containers:
        state = container["State"]
        service = container["Config"]["Labels"]["com.docker.compose.service"]
        if service in JOBS:
            if state.get("Running"):
                raise MaintenanceError("Initialization/migration is active; refuse a maintenance checkpoint")
            if not job_completed(state):
                raise MaintenanceError("Initialization/migration did not complete cleanly; checkpoint refused")
        elif not state.get("Running") and not checkpoint_stopped(container, shutdown_evidence.get(container.get("Id"))):
            raise MaintenanceError("Cold service state has an unclean stop; checkpoint refused")


def backup(deployment, destination, archive_image, timeout):
    deployment.inspect()
    validate_checkpoint_states(deployment.containers)
    info = docker_json("info")
    archive_info = helper(archive_image)
    paths = config_paths(deployment)
    inputs = input_records(deployment) if hasattr(deployment, "compose_inputs") else []
    images = sorted({c["Image"] for c in deployment.containers} | {archive_image})
    image_infos = docker_json("image", "inspect", *images)
    estimate(deployment, paths, image_infos, archive_image, destination)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle = destination / f"{deployment.stack}-{stamp}-{uuid.uuid4().hex[:8]}"
    bundle.mkdir(mode=0o700)
    manifest = {"format": 1, "complete": False, "created_utc": stamp,
                "source_root": str(deployment.root), "project": deployment.project,
                "context": deployment.context, "stack": deployment.stack,
                "compose_inputs": inputs,
                "compose_overlays": [str(p.relative_to(deployment.root)) for p in getattr(deployment, "overlays", [])],
                "services": deployment.services, "daemon_id": info["ID"],
                "architecture": info["Architecture"], "archive_image": archive_info["Id"],
                "images": [{"id": i["Id"], "digests": i.get("RepoDigests"),
                            "architecture": i["Architecture"], "os": i["Os"]} for i in image_infos],
                "volumes": {key: {"name": value, "archive": f"volume-{index}.tar",
                                   "anonymous": deployment.anonymous.get(key),
                                   "identity": docker_json("volume", "inspect", value)[0]}
                            for index, (key, value) in enumerate(deployment.volumes.items())}}
    try:
        manifest["revision"] = run(["git", "-C", str(deployment.root), "rev-parse", "HEAD"]).strip()
    except MaintenanceError:
        manifest["revision"] = "unavailable"
    write_json(bundle / "manifest.json", manifest)
    write_json(bundle / "containers.json", deployment.containers)
    write_json(bundle / "compose.json", deployment.config)
    original_containers = copy.deepcopy(deployment.containers)
    original_config = copy.deepcopy(deployment.config)
    capture_broker_evidence(bundle, deployment.containers, manifest, timeout)
    paused = []
    outstanding = set()
    shutdown_evidence = {}
    try:
        # Immutable images don't require database downtime. Recheck the live
        # identities/config afterward, before quiescing their matched data.
        with (bundle / "images.tar").open("wb") as output:
            run(["docker", "image", "save", *images], timeout=timeout, output=output)
        deployment.inspect()
        unchanged(deployment, original_containers, original_config)
        validate_checkpoint_states(deployment.containers)
        for container in deployment.ordered_running():
            if container["Config"]["Labels"]["com.docker.compose.service"] == "zookeeper-1":
                deployment.inspect()
                matches = [c for c in deployment.containers if c["Id"] == container["Id"]]
                if len(matches) != 1 or matches[0]["Config"] != container["Config"]:
                    raise MaintenanceError("Coordinator identity/config changed before stop")
                container = matches[0]
            intent = prepare_stop(container, deployment.containers, timeout)
            if intent:
                write_json(bundle / "shutdown-intent.json", intent)
            # Record intent first: even a timed-out stop may already have stopped it.
            paused.append(container["Id"])
            outstanding.add(container["Id"])
            started = time.monotonic()
            run(["docker", "stop", "--time", "60", container["Id"]], timeout=timeout)
            state = wait_stopped(container["Id"], timeout)
            outstanding.remove(container["Id"])
            proof = finish_stop(intent, state, time.monotonic() - started)
            if proof:
                shutdown_evidence[container["Id"]] = proof
                write_json(bundle / "shutdown-evidence.json", shutdown_evidence)
            if not checkpoint_stopped({**container, "State": state}, proof):
                raise MaintenanceError("Service did not stop cleanly; checkpoint refused")
        # Recheck resource ownership while cold before any archives are captured.
        deployment.inspect()
        unchanged(deployment, original_containers, original_config, cold=True)
        validate_checkpoint_states(deployment.containers, shutdown_evidence)
        if inputs:
            assert_inputs(deployment, inputs)
        with tarfile.open(bundle / "config.tar", "w") as archive:
            for path in paths:
                archive.add(path, arcname=str(path.relative_to(deployment.root)))
        safe_tar(bundle / "config.tar")
        validate_compose_inputs(bundle, manifest)
        if inputs:
            assert_inputs(deployment, inputs)
        for volume in manifest["volumes"].values():
            with (bundle / volume["archive"]).open("wb") as output:
                helper_run(archive_image, ["tar", "-C", "/volume", "-cpf", "-", "."], volume["name"],
                           timeout=timeout, output=output)
            safe_tar(bundle / volume["archive"])
        manifest["complete"] = True
        manifest["resume_container_ids"] = paused
    finally:
        # This is backup-only cleanup. Migration/update failures have no such resume path.
        prior_running = [c["Id"] for c in original_containers if c["State"].get("Running")]
        cleanup = resume_after_backup(paused, outstanding, timeout, prior_running=prior_running)
        write_json(bundle / "cleanup.json", cleanup)
        for path in bundle.iterdir():
            if path.is_file():
                path.chmod(0o600)
        seal(bundle, manifest)
        if not cleanup["ready"]:
            raise MaintenanceError("Backup cleanup failed; stop settlement/resume/readiness could not be certified; inspect retained cleanup.json")
        if paused:
            print("Backup-only cleanup: prior running set restored and readiness passed.")
    print(f"Cold checkpoint completed: {bundle}")
    print("Original running containers resumed." if paused else "Family remains stopped; no containers resumed.")
    print("Application recovery rehearsal is still required.")
    return bundle


def wait_stopped(identity, timeout):
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise MaintenanceError("Outstanding stop did not settle within its bounded wait")
        state = docker_json("inspect", identity, timeout=remaining)[0]["State"]
        if not state.get("Running"):
            return state
        time.sleep(min(1, max(0, deadline - time.monotonic())))


def resume_after_backup(paused, outstanding, timeout, *, prior_running=None):
    prior_running = paused if prior_running is None else prior_running
    report = {"prior_running_ids": prior_running, "stop_attempt_ids": paused,
              "unsettled_stops": [], "resume_failures": [], "ready": False}
    # An interrupted client is not proof the daemon stopped processing its request.
    # Reissue/wait for every outstanding stop before any restart can race with it.
    for identity in paused:
        if identity in outstanding:
            try:
                run(["docker", "stop", "--time", "60", identity], timeout=timeout)
                wait_stopped(identity, timeout)
            except MaintenanceError:
                report["unsettled_stops"].append(identity)
    if not report["unsettled_stops"]:
        for identity in reversed(paused):
            try:
                if not docker_json("inspect", identity)[0]["State"].get("Running"):
                    run(["docker", "start", identity], timeout=timeout)
            except MaintenanceError:
                report["resume_failures"].append(identity)
    # Also execute/report the final check on the archive/stop-error path.
    try:
        wait_containers(prior_running, timeout)
        report["ready"] = not report["unsettled_stops"] and not report["resume_failures"]
    except MaintenanceError:
        report["readiness_failed"] = True
    return report


def unchanged(deployment, original_containers, original_config, *, cold=False):
    def identities(containers):
        result = {}
        for container in containers:
            mounts = container["Mounts"]
            destinations = [mount.get("Destination") for mount in mounts]
            if any(not isinstance(destination, str) or not destination for destination in destinations):
                raise MaintenanceError("Invalid mount destination during checkpoint identity comparison")
            if len(set(destinations)) != len(destinations):
                raise MaintenanceError("Duplicate mount destination during checkpoint identity comparison")
            # Docker inspect may reorder Mounts; only destination order is immaterial.
            result[container["Id"]] = {"Image": container["Image"], "Config": container["Config"],
                                       "Mounts": sorted(mounts, key=lambda mount: mount["Destination"])}
        return result
    if deployment.config != original_config or identities(deployment.containers) != identities(original_containers):
        raise MaintenanceError("Deployment identity/config changed during checkpoint preparation")
    original_running = {c["Id"]: c["State"].get("Running") for c in original_containers}
    if any(c["State"].get("Running") != (False if cold else original_running[c["Id"]]) for c in deployment.containers):
        raise MaintenanceError("Unexpected running-state change during checkpoint; consistent capture refused")
