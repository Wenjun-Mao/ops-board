# Tailscale Access

Ops Board uses Tailscale as the first private access layer for operator-facing services.

Reverse proxy services are intentionally not part of the current architecture. Do not add a public reverse proxy or auth boundary until that design is chosen deliberately.

## Host Naming

Use the machine's Tailscale hostname when sharing private service URLs:

```text
<tailscale-hostname>
```

Set the shared hostname in `.env`:

```dotenv
OPS_BOARD_TAILSCALE_HOSTNAME=<tailscale-hostname>
```

## SigNoz Endpoints

| Service | Endpoint |
| --- | --- |
| UI | `http://<tailscale-hostname>:8080` |
| OTLP HTTP logs | `http://<tailscale-hostname>:4318/v1/logs` |
| OTLP HTTP traces | `http://<tailscale-hostname>:4318/v1/traces` |
| OTLP HTTP metrics | `http://<tailscale-hostname>:4318/v1/metrics` |
| OTLP gRPC | `<tailscale-hostname>:4317` |
| Collector health | `http://<tailscale-hostname>:13133` |

## Project Agents

Agents that emit telemetry should point at the Tailscale hostname.

Vector example:

```dotenv
VECTOR_SIGNOZ_OTLP_HTTP_URI=http://<tailscale-hostname>:4318/v1/logs
VECTOR_PROJECT_NAME=<project-name>
VECTOR_DEPLOYMENT_ENV=prod
```

## Security Notes

- Allow access only from trusted machines on the tailnet.
- After the initial SigNoz admin account is created, verify the current account-registration setting before broader rollout and document the chosen state.
- Do not expose SigNoz or telemetry ports publicly until a reverse proxy and authentication boundary are intentionally added.
