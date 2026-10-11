"""Owned credential and node identities are not release-stage selectors."""

from common import MaintenanceError
from urllib.parse import urlsplit


PLANE_CREDENTIALS = {
    "SECRET_KEY", "LIVE_SERVER_SECRET_KEY", "DATABASE_URL", "POSTGRES_USER",
    "POSTGRES_PASSWORD", "POSTGRES_DB", "PGDATABASE", "REDIS_URL", "REDIS_PASSWORD",
    "AMQP_URL", "RABBITMQ_DEFAULT_USER", "RABBITMQ_DEFAULT_PASS",
    "RABBITMQ_DEFAULT_VHOST", "RABBITMQ_VHOST", "RABBITMQ_NODENAME",
    "RABBITMQ_ERLANG_COOKIE", "RABBITMQ_USE_LONGNAME", "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD",
}
SIGNOZ_CREDENTIALS = {
    "SIGNOZ_TOKENIZER_JWT_SECRET", "SIGNOZ_JWT_SECRET_FILE",
    "SIGNOZ_TELEMETRYSTORE_CLICKHOUSE_DSN", "SIGNOZ_OTEL_COLLECTOR_CLICKHOUSE_DSN",
    "SIGNOZ_SQLSTORE_SQLITE_PATH", "SIGNOZ_ALERTMANAGER_PROVIDER",
}
CREDENTIALS = {"plane": PLANE_CREDENTIALS, "signoz": SIGNOZ_CREDENTIALS}
# These approved provider flags may be made explicit, never redirected/rotated.
SIGNOZ_PROVIDERS = {"SIGNOZ_SQLSTORE_PROVIDER": "sqlite",
                    "SIGNOZ_TELEMETRYSTORE_PROVIDER": "clickhouse",
                    "SIGNOZ_TOKENIZER_PROVIDER": "jwt"}


def environment_values(value):
    if isinstance(value, dict):
        return value
    result = {}
    for item in value or []:
        key, separator, contents = item.partition("=")
        if not separator or key in result:
            raise MaintenanceError("Ambiguous credential environment metadata")
        result[key] = contents
    return result


def validate_environment(stack, before, after):
    original = environment_values(before.get("environment"))
    changed = environment_values(after.get("environment"))
    for key in CREDENTIALS.get(stack, set()):
        if (key in original) != (key in changed) or original.get(key) != changed.get(key):
            raise MaintenanceError("Compose overlay credential identity/value change refused")
    if stack == "plane":
        old_endpoint = urlsplit(original.get("AWS_S3_ENDPOINT_URL") or "")
        new_endpoint = urlsplit(changed.get("AWS_S3_ENDPOINT_URL") or "")
        if (old_endpoint.username, old_endpoint.password) != (new_endpoint.username, new_endpoint.password):
            raise MaintenanceError("Compose overlay storage endpoint credential change refused")
    if stack == "signoz":
        for key, provider in SIGNOZ_PROVIDERS.items():
            if key in original:
                valid = key in changed and changed[key] == original[key]
            else:
                valid = key not in changed or changed[key] == provider
            if not valid:
                raise MaintenanceError("Compose overlay secret/storage provider identity change refused")


def validate_runtime(deployment, containers):
    for container in containers:
        runtime = container["Config"]
        service = runtime["Labels"]["com.docker.compose.service"]
        configured = deployment.config["services"][service]
        expected = environment_values(configured.get("environment"))
        actual = environment_values(runtime.get("Env"))
        protected = CREDENTIALS.get(deployment.stack, set()) if deployment.overlays else set()
        for key in protected & expected.keys():
            if key not in actual or expected[key] != actual[key]:
                raise MaintenanceError("Configured/live credential identity/value mismatch")
        if service == "plane-mq":
            hostname = runtime.get("Hostname")
            if configured.get("hostname") and configured["hostname"] != hostname:
                raise MaintenanceError("Configured Rabbit hostname differs from captured live node identity")
            for key in ["RABBITMQ_NODENAME", "RABBITMQ_USE_LONGNAME"]:
                if key in expected and (key not in actual or expected[key] != actual[key]):
                    raise MaintenanceError("Configured Rabbit nodename/longname differs from captured live node identity")
            identity = {"hostname": hostname, "nodename": actual.get("RABBITMQ_NODENAME"),
                        "longname": actual.get("RABBITMQ_USE_LONGNAME")}
            if not hostname or getattr(deployment, "broker_identity", identity) != identity:
                raise MaintenanceError("Captured Rabbit node identity changed during maintenance")
            deployment.broker_identity = identity
