"""Stage matched old images/state in fresh isolated resources; never start writers."""

import copy
import json
from pathlib import Path
import re
import shutil
import tarfile

from archives import safe_tar, validate_bundle
from backup import helper, helper_run
from common import MaintenanceError, docker_json, run, write_json
from deployment import GROUPS, JOBS


def compose_literals(value):
    # Runtime values have already been expanded. Compose must not expand them again.
    if isinstance(value, str):
        return value.replace("$", "$$")
    if isinstance(value, dict):
        return {key: compose_literals(item) for key, item in value.items()}
    if isinstance(value, list):
        return [compose_literals(item) for item in value]
    return value


def isolated_config(config, containers, manifest, target, project):
    restored = {"name": project, "services": {}, "volumes": {},
                "networks": {"recovery": {"internal": True, "driver": "bridge", "driver_opts": {
                    "com.docker.network.bridge.gateway_mode_ipv4": "isolated",
                    "com.docker.network.bridge.gateway_mode_ipv6": "isolated"}}}, "secrets": {}}
    by_service = {}
    for container in containers:
        service = container["Config"]["Labels"]["com.docker.compose.service"]
        if service in by_service:
            raise MaintenanceError("Replicated service needs an explicit isolated recovery design")
        by_service[service] = container
    root = Path(manifest["source_root"])

    def recovered_path(source):
        path = Path(source)
        if not path.is_absolute() or root not in path.parents or ".." in path.parts:
            raise MaintenanceError("External/path-traversing recovery bind refused")
        result = target / "config" / path.relative_to(root)
        if not result.exists() or result.is_symlink():
            raise MaintenanceError("Recovery bind/secret was not captured")
        return str(result)

    for name, secret in config.get("secrets", {}).items():
        restored["secrets"][name] = {"file": recovered_path(secret["file"])}
    for key in manifest["volumes"]:
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", key):
            raise MaintenanceError("Invalid recovery volume key")
        restored["volumes"][key] = {"name": f"{project}-{key}", "external": True}
    for service in manifest["services"]:
        if service not in by_service:
            if service in JOBS:
                continue
            raise MaintenanceError("Missing long-running container identity")
        original = config["services"][service]
        container = by_service[service]
        runtime = container["Config"]
        # Build from an allowlist, not an override: aliases, host mappings, devices,
        # published ports, privileged modes and external networks must not survive.
        definition = {"image": container["Image"], "pull_policy": "never",
                      "container_name": f"{project}-{service}", "hostname": runtime["Hostname"],
                      "environment": runtime.get("Env", []), "restart": "no",
                      "entrypoint": runtime.get("Entrypoint") or [],
                      "command": runtime.get("Cmd") or [], "user": runtime.get("User") or "0",
                      "working_dir": runtime.get("WorkingDir") or "/",
                      "networks": {"recovery": {"aliases": [service]}}, "volumes": []}
        if original.get("healthcheck"):
            definition["healthcheck"] = copy.deepcopy(original["healthcheck"])
        if original.get("ulimits"):
            definition["ulimits"] = copy.deepcopy(original["ulimits"])
        if original.get("secrets"):
            definition["secrets"] = copy.deepcopy(original["secrets"])
        for mount in container.get("Mounts", []):
            if mount["Type"] == "volume":
                keys = [k for k, v in manifest["volumes"].items() if v["name"] == mount["Name"]]
                if len(keys) != 1:
                    raise MaintenanceError("Recovery mount lacks one captured volume identity")
                definition["volumes"].append({"type": "volume", "source": keys[0],
                    "target": mount["Destination"], "read_only": not mount.get("RW", True)})
            elif mount["Type"] == "bind":
                # Compose mounts secrets itself; don't duplicate its generated secret bind.
                if mount["Destination"].startswith("/run/secrets/"):
                    continue
                definition["volumes"].append({"type": "bind", "source": recovered_path(mount["Source"]),
                    "target": mount["Destination"], "read_only": not mount.get("RW", True)})
            elif mount["Type"] != "tmpfs":
                raise MaintenanceError("Unsupported persistent recovery mount")
        if service in JOBS or service in {"worker", "beat-worker"}:
            definition["profiles"] = ["manual-jobs"]
        restored["services"][service] = definition
    return restored


def validate_target(bundle, manifest, target, project, stack, context):
    if manifest["project"] != ("ops-board" if context == "root" else stack) or manifest["context"] != context or manifest["stack"] != stack:
        raise MaintenanceError("Backup source identity differs from requested context/stack")
    expected = set(s for group in GROUPS.values() for s in group) if stack == "ops-board" else set(GROUPS[stack])
    if set(manifest["services"]) != expected:
        raise MaintenanceError("Backup service scope mismatch")
    if not re.fullmatch(r"ops-board-rehearsal-[a-z0-9][a-z0-9-]{0,30}", project):
        raise MaintenanceError("Target project must be ops-board-rehearsal-<unique-name>")
    if target.exists() or target.is_symlink() or target == bundle or bundle in target.parents:
        raise MaintenanceError("Restore requires a fresh target directory outside the backup")
    info = docker_json("info")
    if info["Architecture"] != manifest["architecture"]:
        raise MaintenanceError("Image/data restore architecture differs from source")
    if run(["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"]).strip():
        raise MaintenanceError("Restore project already has containers")
    container_names = set(run(["docker", "ps", "-a", "--format", "{{.Names}}"]).split())
    if any(f"{project}-{service}" in container_names for service in manifest["services"]):
        raise MaintenanceError("Restore fixed container name is already in use")
    names = set(run(["docker", "volume", "ls", "-q"]).split())
    if any(f"{project}-{key}" in names for key in manifest["volumes"]):
        raise MaintenanceError("Restore would reuse an existing volume")
    if run(["docker", "network", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"]).strip():
        raise MaintenanceError("Restore would reuse an existing network")
    if f"{project}_recovery" in run(["docker", "network", "ls", "--format", "{{.Name}}"]).split():
        raise MaintenanceError("Restore network name is already in use")


def restore(bundle, target, project, stack, context, timeout, *, dry_run=False):
    manifest = validate_bundle(bundle)
    validate_target(bundle, manifest, target, project, stack, context)
    if dry_run:
        print(f"Validated checkpoint. Would stage fresh isolated project {project}; no containers will start.")
        return
    # Space for extracted config, images, and data plus tar overhead/headroom.
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    estimate = sum(f["bytes"] for f in manifest["files"].values()) * 2 + 512 * 1024 * 1024
    if shutil.disk_usage(target.parent).free < estimate:
        raise MaintenanceError("Insufficient restore capacity")
    created = []
    target.mkdir(mode=0o700)
    try:
        (target / "config").mkdir(mode=0o700)
        safe_tar(bundle / "config.tar")
        with tarfile.open(bundle / "config.tar") as archive:
            # safe_tar rejects links through parents and escapes; extraction is fresh/private.
            archive.extractall(target / "config", members=safe_tar(bundle / "config.tar"))
        config = json.loads((bundle / "compose.json").read_text())
        containers = json.loads((bundle / "containers.json").read_text())
        config = isolated_config(config, containers, manifest, target, project)
        # Validate topology before importing images or creating any volumes.
        write_json(target / "compose.json", compose_literals(config))
        run(["docker", "compose", "-f", str(target / "compose.json"), "config", "--quiet"])
        run(["docker", "image", "load", "-i", str(bundle / "images.tar")], timeout=timeout)
        for image in manifest["images"]:
            info = docker_json("image", "inspect", image["id"])[0]
            if info["Id"] != image["id"] or info["Architecture"] != image["architecture"] or info["Os"] != image["os"]:
                raise MaintenanceError("Recovery image identity/architecture mismatch")
        helper(manifest["archive_image"])
        for key, volume in manifest["volumes"].items():
            name = f"{project}-{key}"
            # Recheck after slow validation/import and never use volume-create's reuse behavior.
            if name in run(["docker", "volume", "ls", "-q"]).split():
                raise MaintenanceError("Fresh restore volume appeared concurrently")
            run(["docker", "volume", "create", "--label", f"ops-board.recovery={project}", name])
            created.append(name)
            with (bundle / volume["archive"]).open("rb") as source:
                helper_run(manifest["archive_image"], ["tar", "-C", "/volume", "-xpf", "-"], name,
                           writable=True, timeout=timeout, input_file=source)
        write_json(target / "recovery.json", {"source": str(bundle), "project": project,
                   "volumes": created, "started": False, "application_rehearsal_passed": False})
    except BaseException:
        # Only our newly-created volumes; never remove source state or an existing target.
        failed = []
        for name in reversed(created):
            try:
                run(["docker", "volume", "rm", name])
            except MaintenanceError:
                failed.append(name)
        write_json(target / "failure.json", {"incomplete": True, "remaining_new_volumes": failed})
        raise
    print(f"Isolated restore staged: {target / 'compose.json'}")
    print("No containers started; no published ports or external network. Test accounts/data manually.")
