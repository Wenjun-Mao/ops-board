"""Passive readiness checks, deliberately separate from bootstrap and migrations."""

from urllib.error import URLError
from urllib.request import urlopen

from common import MaintenanceError, run, wait_containers
from deployment import JOBS, job_completed


PROBES = {
    "plane-db": ["pg_isready", "-h", "/var/run/postgresql", "-U", "plane"],
    "plane-redis": ["valkey-cli", "ping"],
    "plane-mq": ["rabbitmq-diagnostics", "-q", "check_running"],
    "clickhouse": ["clickhouse-client", "--query", "SELECT 1"],
}
HTTP = {"homepage": (3000, "/"), "uptime-kuma": (3001, "/"),
        "signoz": (8080, "/api/v1/health"), "otel-collector": (13133, "/"), "proxy": (80, "/")}


def verify(deployment, timeout):
    deployment.inspect()
    ids = []
    for container in deployment.containers:
        service = container["Config"]["Labels"]["com.docker.compose.service"]
        if service in JOBS:
            if not job_completed(container["State"]):
                raise MaintenanceError("One-shot initialization/migration job is not successfully completed")
        else:
            ids.append(container["Id"])
    wait_containers(ids, timeout)
    for container in deployment.containers:
        service = container["Config"]["Labels"]["com.docker.compose.service"]
        if service in PROBES:
            run(["docker", "exec", container["Id"], *PROBES[service]], timeout=timeout)
        if service in HTTP:
            target, path = HTTP[service]
            ports = container["NetworkSettings"].get("Ports", {}).get(f"{target}/tcp") or []
            if not ports:
                raise MaintenanceError("Expected health endpoint has no published port")
            host = ports[0].get("HostIp", "0.0.0.0")
            host = "127.0.0.1" if host in {"", "0.0.0.0"} else ("[::1]" if host == "::" else host)
            try:
                with urlopen(f"http://{host}:{ports[0]['HostPort']}{path}", timeout=min(timeout, 20)) as response:
                    if not 200 <= response.status < 400:
                        raise MaintenanceError("HTTP health check failed")
            except (OSError, URLError) as error:
                raise MaintenanceError("HTTP health check failed (no credential or body output)") from error
    deployment.summary()
    print("Passive readiness passed. This does not certify data restoration or migration compatibility.")
