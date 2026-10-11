"""Checksummed recovery bundles and conservative tar validation."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

from common import MaintenanceError, write_json


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_tar(path):
    try:
        with tarfile.open(path) as archive:
            members = archive.getmembers()
            links = {PurePosixPath(m.name).parts: m for m in members if m.issym() or m.islnk()}
            seen = set()
            for member in members:
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts or member.isdev() or member.isfifo():
                    raise MaintenanceError("Unsafe archive member")
                if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                    raise MaintenanceError("Unsupported archive member")
                if name.parts in seen:
                    raise MaintenanceError("Duplicate archive member path")
                seen.add(name.parts)
                if not name.parts and not member.isdir():
                    raise MaintenanceError("Archive root must be a directory")
                if (member.issym() or member.islnk()) and not name.parts:
                    raise MaintenanceError("Archive root cannot be a link")
                if any(parent.parts in links for parent in name.parents):
                    raise MaintenanceError("Archive writes through a link")
            for name, member in links.items():
                target = PurePosixPath(member.linkname)
                # Symlinks are parent-relative; tar hardlink names are root-relative.
                base = name[:-1] if member.issym() else ()
                resolve_link(target, base, links, frozenset({name}))
            return members
    except (tarfile.TarError, OSError) as error:
        raise MaintenanceError("Unreadable recovery archive") from error


def resolve_link(path, base, links, active):
    """Resolve a virtual archive path in filesystem order, without touching disk."""
    if path.is_absolute():
        raise MaintenanceError("Absolute archive link")
    if len(active) > 128:
        raise MaintenanceError("Archive link chain is too deep")
    resolved = list(base)
    for part in path.parts:
        if part == "..":
            if not resolved:
                raise MaintenanceError("Archive link escapes its root")
            resolved.pop()
            continue
        name = (*resolved, part)
        if name in links:
            if name in active:
                raise MaintenanceError("Cyclic archive link")
            member = links[name]
            parent = tuple(resolved) if member.issym() else ()
            resolved = list(resolve_link(PurePosixPath(member.linkname), parent, links, active | {name}))
        else:
            resolved.append(part)
    return tuple(resolved)


def seal(bundle, manifest):
    manifest["files"] = {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size}
                         for p in bundle.iterdir() if p.is_file() and p.name != "manifest.json"}
    write_json(bundle / "manifest.json", manifest)


def validate_bundle(bundle):
    try:
        if bundle.is_symlink() or not bundle.is_dir():
            raise MaintenanceError("Backup must be a real directory")
        manifest_path = bundle / "manifest.json"
        if manifest_path.is_symlink():
            raise MaintenanceError("Manifest must not be a link")
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("format") != 1 or manifest.get("complete") is not True:
            raise MaintenanceError("Incomplete or unsupported checkpoint")
        files = manifest["files"]
        required = {"config.tar", "compose.json", "containers.json", "images.tar"}
        required |= {v["archive"] for v in manifest["volumes"].values()}
        if not required <= files.keys():
            raise MaintenanceError("Required recovery artifacts missing from manifest")
        if set(p.name for p in bundle.iterdir()) != set(files) | {"manifest.json"}:
            raise MaintenanceError("Unexpected/missing recovery artifacts")
        for name, info in files.items():
            if Path(name).name != name or name in {".", ".."}:
                raise MaintenanceError("Unsafe manifest path")
            path = bundle / name
            if path.is_symlink() or not path.is_file() or path.stat().st_size != info["bytes"] or sha256(path) != info["sha256"]:
                raise MaintenanceError("Recovery artifact checksum/size mismatch")
            if name.endswith(".tar") and name != "images.tar":
                safe_tar(path)
        validate_compose_inputs(bundle, manifest)
        return manifest
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        raise MaintenanceError("Invalid recovery manifest") from error


def validate_compose_inputs(bundle, manifest):
    # Optional for format-1 bundles created before ordered stage capture existed.
    inputs = manifest.get("compose_inputs", [])
    if not inputs:
        if manifest.get("compose_overlays"):
            raise MaintenanceError("Overlay audit lacks captured Compose inputs")
        return
    paths = [item["path"] for item in inputs]
    for path in paths:
        value = PurePosixPath(path)
        if value.is_absolute() or ".." in value.parts or str(value) != path:
            raise MaintenanceError("Unsafe captured Compose input path")
    if manifest.get("compose_overlays", []) != paths[1:]:
        raise MaintenanceError("Captured Compose layer order mismatch")
    with tarfile.open(bundle / "config.tar") as archive:
        for item in inputs:
            member = archive.getmember(item["path"])
            if not member.isfile():
                raise MaintenanceError("Captured Compose input is not a regular file")
            digest = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
            if digest != item["sha256"]:
                raise MaintenanceError("Captured Compose input checksum mismatch")
