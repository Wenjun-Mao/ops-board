"""Evidence-bound coordinator stops, without translating application exit codes."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import shlex

from common import MaintenanceError, run


# Capability is bound to this inspected Linux/amd64 image, not a mutable tag.
ZOOKEEPER_IMAGE = "sha256:3ab0e8f032ab58f14ac1e929ac40305a4a464cf320bdfe4151d62d6922729ba0"
CONTRACT = "zookeeper-3.7.1-jdk11-quiesced-sigterm-v1"
CLIENTS = {"otel-collector", "signoz", "clickhouse", "init-clickhouse",
           "signoz-telemetrystore-migrator"}
MONITOR_FIELDS = {"zk_version", "zk_server_state", "zk_num_alive_connections",
                  "zk_outstanding_requests"}
MONITOR_COMMAND = ["sh", "-c", "printf 'mntr' | nc -w 5 127.0.0.1 2181"]


def service(container):
    return container.get("Config", {}).get("Labels", {}).get("com.docker.compose.service")


def config_hash(container):
    data = json.dumps(container["Config"], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


def monitor_state(output):
    fields = {}
    for line in output.splitlines():
        key, separator, value = line.partition("\t")
        if key in MONITOR_FIELDS and separator:
            if key in fields:
                raise MaintenanceError("Ambiguous ZooKeeper quiescence response")
            fields[key] = value
    if fields.keys() != MONITOR_FIELDS:
        raise MaintenanceError("Incomplete ZooKeeper quiescence response")
    try:
        for key in ["zk_num_alive_connections", "zk_outstanding_requests"]:
            value = Decimal(fields[key])
            if not value.is_finite() or value != value.to_integral_value():
                raise ValueError
            fields[key] = int(value)
    except (InvalidOperation, ValueError, OverflowError) as error:
        raise MaintenanceError("Invalid ZooKeeper quiescence response") from error
    # The four-letter probe itself accounts for the one live connection.
    if (not fields["zk_version"].startswith("3.7.1-")
            or fields["zk_server_state"] != "standalone"
            or fields["zk_num_alive_connections"] != 1
            or fields["zk_outstanding_requests"] != 0):
        raise MaintenanceError("ZooKeeper is not the supported quiescent standalone coordinator")
    return fields


def prepare_stop(container, cohort, timeout):
    """Return intent only for the inspected image after its scoped clients stop."""
    if service(container) != "zookeeper-1" or container.get("Image") != ZOOKEEPER_IMAGE:
        return None
    config, state = container["Config"], container["State"]
    if (config.get("Entrypoint") != ["/opt/bitnami/scripts/zookeeper/entrypoint.sh"]
            or config.get("Cmd") != ["/opt/bitnami/scripts/zookeeper/run.sh"]
            or config.get("StopSignal") not in {None, "", "SIGTERM", "15"}
            or not state.get("Running") or state.get("OOMKilled")
            or state.get("Health", {}).get("Status") != "healthy"):
        raise MaintenanceError("Unsupported ZooKeeper runtime shutdown contract")
    project = config["Labels"].get("com.docker.compose.project")
    clients = [c for c in cohort if service(c) in CLIENTS]
    if (not project or not {"signoz", "clickhouse"} <= {service(c) for c in clients}
            or any(c["Config"]["Labels"].get("com.docker.compose.project") != project
                   or c["State"].get("Running") or c["State"].get("ExitCode") != 0
                   or c["State"].get("Status") != "exited"
                   or c["State"].get("OOMKilled") for c in clients)):
        raise MaintenanceError("ZooKeeper clients must be stopped cleanly before coordinator stop")
    cmdline = run(["docker", "exec", container["Id"], "cat", "/proc/1/cmdline"], timeout=timeout)
    arguments = cmdline.rstrip("\0").split("\0")
    environment = dict(item.split("=", 1) for item in config.get("Env", []) if "=" in item)
    try:
        options = arguments + [option for name in ["JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"]
                               for option in shlex.split(environment.get(name, ""))]
    except ValueError as error:
        raise MaintenanceError("Unparseable ZooKeeper JVM options") from error
    if (Path(arguments[0]).name != "java"
            or "org.apache.zookeeper.server.quorum.QuorumPeerMain" not in arguments
            or any(option in {"-Xrs", "-Dzookeeper.forceSync=no"} for option in options)):
        raise MaintenanceError("ZooKeeper requires the inspected PID-1 JVM and durable WAL defaults")
    monitor = monitor_state(run(["docker", "exec", container["Id"], *MONITOR_COMMAND], timeout=timeout))
    return {"contract": CONTRACT, "container_id": container["Id"], "image": container["Image"],
            "project": project, "started_at": state["StartedAt"], "config_sha256": config_hash(container),
            "pid1_cmdline_sha256": hashlib.sha256(cmdline.encode()).hexdigest(),
            "monitor": monitor, "clients": [c["Id"] for c in clients],
            "requested_at": datetime.now(timezone.utc).isoformat(), "signal": "SIGTERM"}


def finish_stop(intent, state, elapsed):
    if intent is None:
        return None
    return {**intent, "docker_stop_completed": True, "elapsed_seconds": elapsed,
            "finished_at": state.get("FinishedAt"), "exit_code": state.get("ExitCode")}


def checkpoint_stopped(container, evidence=None):
    state = container["State"]
    if state.get("Running") or state.get("OOMKilled"):
        return False
    if state.get("ExitCode") == 0:
        return True
    if not evidence or service(container) != "zookeeper-1" or container.get("Image") != ZOOKEEPER_IMAGE:
        return False
    try:
        elapsed = evidence["elapsed_seconds"]
        requested = datetime.fromisoformat(evidence["requested_at"])
        finished = datetime.fromisoformat(state["FinishedAt"].replace("Z", "+00:00"))
        return (evidence["contract"] == CONTRACT and evidence["container_id"] == container["Id"]
                and evidence["image"] == container["Image"]
                and evidence["project"] == container["Config"]["Labels"]["com.docker.compose.project"]
                and evidence["config_sha256"] == config_hash(container)
                and re.fullmatch(r"[a-f0-9]{64}", evidence["pid1_cmdline_sha256"]) is not None
                and isinstance(evidence["clients"], list)
                and all(isinstance(client, str) and client for client in evidence["clients"])
                and len(set(evidence["clients"])) == len(evidence["clients"]) >= 2
                and evidence["started_at"] == state["StartedAt"]
                and evidence["signal"] == "SIGTERM" and evidence["docker_stop_completed"] is True
                and evidence["exit_code"] == state["ExitCode"] == 143
                and evidence["finished_at"] == state["FinishedAt"]
                and state.get("Status") == "exited"
                and type(elapsed) in {int, float} and 0 <= elapsed < 60
                and 0 <= (finished - requested).total_seconds() < 60
                and monitor_state("\n".join(f"{key}\t{value}" for key, value in evidence["monitor"].items()))
                == evidence["monitor"])
    except (AttributeError, KeyError, TypeError, ValueError, MaintenanceError):
        return False
