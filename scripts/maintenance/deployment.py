"""Bind operator scope to an explicit Compose project and its existing resources."""

from pathlib import Path
import hashlib
import os
import re

from common import MaintenanceError, docker_json, run
from overlays import assert_inputs, input_records, overlay_paths, validate_contract
from overlay_sources import validate_source
from credentials import validate_runtime


GROUPS = {
    "uptime-kuma": ["uptime-kuma"],
    "homepage": ["homepage"],
    "plane": ["proxy", "web", "space", "admin", "beat-worker", "live", "api", "worker",
              "migrator", "plane-minio", "plane-mq", "plane-redis", "plane-db"],
    "signoz": ["otel-collector", "signoz", "signoz-telemetrystore-migrator",
               "clickhouse", "zookeeper-1", "init-clickhouse"],
}
JOBS = {"migrator", "init-clickhouse", "signoz-telemetrystore-migrator"}


def job_completed(state):
    return (state.get("Status") == "exited" and not state.get("Running")
            and state.get("ExitCode") == 0 and not state.get("OOMKilled"))


class Deployment:
    def __init__(self, root, stack="ops-board", context="root", overlays=()):
        self.root = Path(root).resolve()
        if stack != "ops-board" and stack not in GROUPS:
            raise MaintenanceError("Unknown stack")
        if context not in {"root", "standalone"} or (context == "standalone" and stack == "ops-board"):
            raise MaintenanceError("Standalone context requires a named stack")
        self.stack, self.context = stack, context
        self.overlays = overlay_paths(self.root, stack, context, overlays)
        self.project = "ops-board" if context == "root" else stack
        self.services = [s for group in GROUPS.values() for s in group] if stack == "ops-board" else GROUPS[stack]
        self.compose = ["docker", "compose", "--project-name", self.project]
        if (self.root / ".env").is_file():
            self.compose += ["--env-file", str(self.root / ".env")]
        if self.overlays and stack == "plane":
            env = self.root / "stacks/plane/plane.env"
            if env.is_file():
                self.compose += ["--env-file", str(env)]
        if context == "standalone":
            for name in (".env", f"{stack}.env"):
                env = self.root / "stacks" / stack / name
                if env.is_file():
                    self.compose += ["--env-file", str(env)]
        file = self.root / ("compose.yaml" if context == "root" else f"stacks/{stack}/compose.yaml")
        self.compose += ["-f", str(file)]
        self.base_compose = self.compose.copy()
        self.compose_inputs = [file, *self.overlays]
        for overlay in self.overlays:
            self.compose += ["-f", str(overlay)]

    def resolve_config(self):
        if not self.overlays:
            return docker_json(*self.compose[1:], "--profile", "*", "config", "--format", "json")
        records = input_records(self)
        for overlay in self.overlays:
            validate_source(overlay, self.services)
        # Omit -p during source validation so a layer cannot hide a changed name.
        command = self.base_compose[1:]
        project_flag = command.index("--project-name")
        del command[project_flag:project_flag + 2]
        # A later env file must not override the YAML name either.
        environment = dict(os.environ, COMPOSE_PROJECT_NAME="")
        baseline = docker_json(*command, "--profile", "*", "config", "--format", "json", env=environment)
        for overlay in self.overlays:
            command += ["-f", str(overlay)]
            candidate = docker_json(*command, "--profile", "*", "config", "--format", "json", env=environment)
            validate_contract(baseline, candidate, self)
        assert_inputs(self, records)
        return candidate

    def inspect(self, *, require_all=True):
        self.config = self.resolve_config()
        configured = self.config["services"]
        if self.config.get("name") != self.project or not set(self.services) <= configured.keys():
            raise MaintenanceError("Compose project/service contract mismatch")
        ids = run(["docker", "ps", "-aq"]).split()
        all_containers = docker_json("inspect", *ids) if ids else []
        selected = []
        for container in all_containers:
            labels = container["Config"].get("Labels") or {}
            service = labels.get("com.docker.compose.service")
            project = labels.get("com.docker.compose.project")
            fixed = {configured[s].get("container_name") for s in self.services}
            if container["Name"].lstrip("/") in fixed and project != self.project:
                raise MaintenanceError("Fixed container name belongs to another project")
            owners = [s for s in self.services if configured[s].get("container_name") == container["Name"].lstrip("/")]
            if owners and service not in owners:
                raise MaintenanceError("Fixed container name has the wrong service identity")
            if project == self.project and service in self.services:
                if labels.get("com.docker.compose.oneoff", "False").lower() == "true":
                    raise MaintenanceError("One-off container in maintenance scope")
                workdir = labels.get("com.docker.compose.project.working_dir")
                expected = self.root if self.context == "root" else self.root / "stacks" / self.stack
                if not workdir or Path(workdir).resolve() != expected:
                    raise MaintenanceError("Container belongs to a different checkout/deployment context")
                selected.append(container)
        present = {c["Config"]["Labels"]["com.docker.compose.service"] for c in selected}
        if require_all and set(self.services) - JOBS - present:
            raise MaintenanceError("Expected long-running services are missing; refusing partial checkpoint")
        if require_all:
            for service in set(self.services) - JOBS:
                expected = configured[service].get("scale", configured[service].get("deploy", {}).get("replicas", 1))
                actual = sum(c["Config"]["Labels"]["com.docker.compose.service"] == service for c in selected)
                if actual != expected:
                    raise MaintenanceError("Configured/live replica count mismatch; refuse implicit scaling")
        self.containers = selected
        validate_runtime(self, selected)
        self.volumes = {}
        self.anonymous = {}
        for service in self.services:
            for mount in configured[service].get("volumes", []):
                if mount["type"] == "volume":
                    key = mount.get("source")
                    definition = self.config.get("volumes", {}).get(key, {})
                    name = definition.get("name")
                    if not key or not name or definition.get("external"):
                        raise MaintenanceError("Anonymous/external volume requires a separate recovery design")
                    self.volumes[key] = name
        if len(set(self.volumes.values())) != len(self.volumes):
            raise MaintenanceError("Ambiguous volume aliases")
        for container in selected:
            service = container["Config"]["Labels"]["com.docker.compose.service"]
            mounts = {m["Destination"]: m for m in container.get("Mounts", [])}
            expected_mounts = {}
            for mount in configured[service].get("volumes", []):
                if mount["type"] == "volume":
                    source = self.config["volumes"][mount["source"]]["name"]
                elif mount["type"] == "bind":
                    source = str(Path(mount["source"]).resolve())
                elif mount["type"] == "tmpfs":
                    continue
                else:
                    raise MaintenanceError("Unsupported configured mount type")
                expected_mounts[mount["target"]] = (mount["type"], source)
            for secret in configured[service].get("secrets", []):
                secret = {"source": secret} if isinstance(secret, str) else secret
                definition = self.config.get("secrets", {}).get(secret["source"], {})
                if not definition.get("file"):
                    raise MaintenanceError("External secret has no recoverable local source")
                target = secret.get("target", secret["source"])
                target = target if target.startswith("/") else "/run/secrets/" + target
                expected_mounts[target] = ("bind", str(Path(definition["file"]).resolve()))
            for target, (kind, source) in expected_mounts.items():
                live = mounts.get(target, {})
                actual = live.get("Name") if kind == "volume" else str(Path(live.get("Source", "/")).resolve())
                if live.get("Type") != kind or actual != source:
                    raise MaintenanceError("Configured/live mount target-to-source mismatch")
            image_volumes = None
            for mount in container.get("Mounts", []):
                if mount["Destination"] in expected_mounts or mount["Type"] == "tmpfs":
                    continue
                if mount["Type"] == "volume":
                    if image_volumes is None:
                        image_volumes = docker_json("image", "inspect", container["Image"])[0]["Config"].get("Volumes") or {}
                    if mount["Destination"] not in image_volumes or not re.fullmatch(r"[a-f0-9]{64}", mount["Name"]):
                        raise MaintenanceError("Undeclared live volume mount")
                    key = "anonymous-" + hashlib.sha256(mount["Name"].encode()).hexdigest()[:16]
                    self.volumes[key] = mount["Name"]
                    self.anonymous[key] = {"service": container["Config"]["Labels"]["com.docker.compose.service"],
                                           "target": mount["Destination"]}
                else:
                    raise MaintenanceError("Unexpected persistent bind mount")
        for key, name in self.volumes.items():
            info = docker_json("volume", "inspect", name)[0]
            if info.get("Driver", "local") != "local" or info.get("Options"):
                raise MaintenanceError("Non-local/configured volume needs an explicit recovery design")
            labels = info.get("Labels") or {}
            if key in self.anonymous:
                if labels.get("com.docker.compose.project") not in {None, self.project}:
                    raise MaintenanceError("Anonymous volume belongs to a different project")
            elif labels.get("com.docker.compose.project") != self.project or labels.get("com.docker.compose.volume") != key:
                raise MaintenanceError("Volume ownership does not match the selected deployment")
        selected_ids = {c["Id"] for c in selected}
        selected_binds = {m["Source"] for c in selected for m in c.get("Mounts", []) if m["Type"] == "bind" and m.get("RW")}
        for container in all_containers:
            for mount in container.get("Mounts", []):
                if container["Id"] in selected_ids:
                    if mount["Type"] == "volume" and mount["Name"] not in self.volumes.values():
                        raise MaintenanceError("Unexpected live volume mount")
                elif mount["Type"] == "volume" and mount["Name"] in self.volumes.values():
                    raise MaintenanceError("Scoped volume is also attached outside the selected group")
                elif container["State"].get("Running") and mount["Type"] == "bind" and mount.get("RW"):
                    source = Path(mount["Source"]).resolve()
                    if any(source == Path(bind).resolve() or source in Path(bind).resolve().parents
                           or Path(bind).resolve() in source.parents for bind in selected_binds):
                        raise MaintenanceError("Scoped writable bind overlaps a running outside writer")
        return self

    def ordered_running(self):
        return [c for service in self.services for c in self.containers
                if c["Config"]["Labels"]["com.docker.compose.service"] == service and c["State"].get("Running")]

    def summary(self):
        for container in self.containers:
            service = container["Config"]["Labels"]["com.docker.compose.service"]
            state = container["State"]
            health = state.get("Health", {}).get("Status", "no healthcheck")
            print(f"{self.project}/{service}: {state['Status']} ({health}), restarts={container.get('RestartCount', 0)}")
