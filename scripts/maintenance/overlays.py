"""Source-only stage validation; runtime identity checks remain in Deployment."""

from pathlib import Path

from archives import sha256
from common import MaintenanceError, env_value
from credentials import validate_environment


def scoped_file(root, directory, value):
    path = Path(value)
    if ".." in path.parts:
        raise MaintenanceError("Compose overlay/bind traversal refused")
    path = path.absolute()
    if directory not in path.parents or path.resolve() != path or not path.is_file():
        raise MaintenanceError("Compose overlay/bind must be a regular non-symlink scoped repository file")
    if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root):
        raise MaintenanceError("Compose overlay/bind symlink refused")
    return path


def overlay_paths(root, stack, context, values):
    if not values:
        return []
    if context != "root" or stack not in {"plane", "signoz"}:
        raise MaintenanceError("Compose overlays require root context and named plane or signoz stack")
    # An environment project override would conceal a malicious YAML name during config.
    if env_value(root, "COMPOSE_PROJECT_NAME", ""):
        raise MaintenanceError("Unset COMPOSE_PROJECT_NAME before overlay validation")
    directory = root / "stacks" / stack / "maintenance"
    return [scoped_file(root, directory, value) for value in values]


def validate_contract(baseline, candidate, deployment):
    if candidate.get("name") != deployment.project or baseline.get("name") != deployment.project:
        raise MaintenanceError("Compose overlay project/name mismatch")
    for key in set(baseline) | set(candidate):
        if key != "services" and not key.startswith("x-") and baseline.get(key) != candidate.get(key):
            raise MaintenanceError("Compose overlay changes top-level resource identities")
    before, after = baseline["services"], candidate["services"]
    if set(before) != set(after) or not set(deployment.services) <= set(after):
        raise MaintenanceError("Compose overlay adds/removes services")
    for service, original in before.items():
        changed = after[service]
        if service not in deployment.services:
            if changed != original:
                raise MaintenanceError("Compose overlay changes an unselected service")
            continue
        allowed = {"image", "command", "environment", "healthcheck", "profiles", "volumes"}
        if service == "signoz" and original.get("command") != changed.get("command"):
            raise MaintenanceError("SigNoz JWT launcher/server arguments must retain the owned secret contract")
        # Only reviewed jobs may change retries; no implicit replica/security changes.
        if service in {"migrator", "init-clickhouse", "signoz-telemetrystore-migrator"}:
            allowed |= {"restart", "deploy"}
            for key in set(original.get("deploy", {})) | set(changed.get("deploy", {})):
                if key != "restart_policy" and original.get("deploy", {}).get(key) != changed.get("deploy", {}).get(key):
                    raise MaintenanceError("Compose overlay changes job deployment identity")
        if service == "plane-mq":
            allowed.add("hostname")
        if service == "clickhouse":
            allowed.add("depends_on")
            dependencies = changed.get("depends_on", {})
            if any(key not in original.get("depends_on", {}) or
                   value != original["depends_on"][key] for key, value in dependencies.items()):
                raise MaintenanceError("Compose overlay adds/changes dependencies")
        for key in set(original) | set(changed):
            if key not in allowed and original.get(key) != changed.get(key):
                raise MaintenanceError("Compose overlay changes protected service fields (ports/security/identity)")
        validate_environment(deployment.stack, original, changed)
        validate_mounts(original.get("volumes", []), changed.get("volumes", []), deployment, service)


def validate_mounts(before, after, deployment, service):
    old = {mount["target"]: mount for mount in before}
    new = {mount["target"]: mount for mount in after}
    if len(old) != len(before) or len(new) != len(after) or not old.keys() <= new.keys():
        raise MaintenanceError("Compose overlay removes/duplicates persistent mounts")
    directory = deployment.root / "stacks" / deployment.stack / "maintenance"
    for target, mount in new.items():
        original = old.get(target)
        if mount == original:
            continue
        collector_config = service == "otel-collector" and target in {
            "/etc/otel-collector-config.yaml", "/etc/opamp-config.yaml"}
        metric_log_config = deployment.stack == "signoz" and service == "clickhouse" and original is None and (
            target == "/etc/clickhouse-server/config.d/metric-log-merges.xml" and
            Path(mount.get("source", "")) == directory / "metric-log-merges.xml")
        if not (collector_config or metric_log_config):
            raise MaintenanceError("Secret/owned bind identity cannot change; only named prepared config binds may vary")
        if mount.get("type") != "bind" or (original and original.get("type") != "bind"):
            raise MaintenanceError("Compose overlay changes persistent volume identity")
        if not mount.get("read_only"):
            raise MaintenanceError("Compose overlay config binds must be read-only")
        scoped_file(deployment.root, directory, mount["source"])
        # A reviewed config replacement may strengthen writable -> read-only.
        if original and {k: v for k, v in original.items() if k not in {"source", "read_only"}} != {
                k: v for k, v in mount.items() if k not in {"source", "read_only"}}:
            raise MaintenanceError("Compose overlay changes existing bind contract")


def input_records(deployment):
    overlay_paths(deployment.root, deployment.stack, deployment.context, deployment.overlays)
    return [{"path": str(path.relative_to(deployment.root)), "sha256": sha256(path)}
            for path in deployment.compose_inputs]


def assert_inputs(deployment, records):
    if input_records(deployment) != records:
        raise MaintenanceError("Compose source inputs changed during checkpoint/validation")
