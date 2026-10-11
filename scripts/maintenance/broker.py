"""Rabbit evidence supplements authoritative full cold state, never replaces it."""

import copy

from common import MaintenanceError, run


def capture_broker_evidence(bundle, containers, manifest, timeout):
    for container in containers:
        if container["Config"]["Labels"]["com.docker.compose.service"] != "plane-mq":
            continue
        mounts = [m for m in container["Mounts"]
                  if m["Type"] == "volume" and m["Destination"] == "/var/lib/rabbitmq"]
        if len(mounts) != 1:
            raise MaintenanceError("RabbitMQ evidence requires its complete declared state volume")
        keys = [key for key, value in manifest["volumes"].items() if value["name"] == mounts[0]["Name"]]
        if len(keys) != 1:
            raise MaintenanceError("RabbitMQ state volume lacks a unique checkpoint identity")
        runtime = container["Config"]
        nodename = next((item.split("=", 1)[1] for item in runtime.get("Env", [])
                         if item.startswith("RABBITMQ_NODENAME=")), None)
        running = container["State"].get("Running", False)
        evidence = {"hostname": runtime["Hostname"], "configured_nodename": nodename,
                    "recorded_state": copy.deepcopy(container["State"]),
                    "cold_volume_keys": keys, "node_status": None, "definitions": None,
                    "live_diagnostics": {"available": running,
                                         "reason": "running broker" if running else "broker already stopped"},
                    "state_authority": "complete cold volume archives when manifest.complete is true",
                    "message_storage": "full cold state includes definitions, messages and cookie; exports alone do not",
                    "isolated_restore_verification": {"required": True, "passed": False,
                        "checks": ["matched image boots full cold state", "preserved node and cookie",
                                   "verify users, permissions, queues and messages", "export and verify definitions"]}}
        if running:
            (bundle / "rabbitmq-status.txt").write_text(run(
                ["docker", "exec", container["Id"], "rabbitmq-diagnostics", "-q", "status"], timeout=timeout))
            (bundle / "rabbitmq-definitions.json").write_text(run(
                ["docker", "exec", container["Id"], "rabbitmqctl", "-q", "export_definitions", "/dev/stdout"], timeout=timeout))
            evidence.update(node_status="rabbitmq-status.txt", definitions="rabbitmq-definitions.json")
        manifest["rabbitmq_identity"] = evidence
