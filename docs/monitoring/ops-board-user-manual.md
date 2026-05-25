# Ops Board User Manual

Ops Board is a private operations board for projects that run across local machines, VPSs, countries, and cloud providers.

Use it when you need to answer:

- What projects exist and where do I start?
- Is a project alive right now?
- What happened inside a job, API request, or service?
- Who owns the project and where does it run?
- What follow-up work should be tracked?

Tailscale is the access layer for v1. Do not expose dashboards publicly unless the access model is intentionally changed.

## Where To Start

Start with Homepage:

```text
http://localhost:3000
http://<ops-board-tailscale-hostname>:3000
```

Homepage should link to:

- SigNoz
- Uptime Kuma
- Plane
- Ops Board docs

## Which Tool To Use

| Need | Use | Why |
|------|-----|-----|
| Find services and dashboards | Homepage | It is the launch board. |
| Check whether something is up | Uptime Kuma | It tracks health endpoints and status pages. |
| Debug a slow API or failed job | SigNoz | It stores traces, logs, and metrics. |
| Track follow-up work | Plane | It turns operational findings into tasks. |
| Reach private hosts | Tailscale | It connects local machines and VPSs privately. |

## Common Workflow: Service Looks Down

1. Open Homepage.
2. Open Uptime Kuma.
3. Check the monitor status and last failure time.
4. Open SigNoz and filter by `service.name`.
5. Look for recent traces, errors, and logs around the failure time.
6. If work is needed, create or update a Plane issue.

## Common Workflow: Job Failed Or Did Not Run

1. Open SigNoz.
2. Search for the job service name, for example `dummy-job`.
3. Look for spans named after the job run.
4. Check span status, exception events, duration, and host attributes.
5. Confirm the expected host and environment match the project docs.

## Current Local Endpoints

| Tool | Local URL | Tailnet URL Pattern |
|------|-----------|---------------------|
| Homepage | `http://localhost:3000` | `http://<host>:3000` |
| Uptime Kuma | `http://localhost:3001` | `http://<host>:3001` |
| SigNoz | `http://localhost:8080` | `http://<host>:8080` |
| Plane | `http://localhost:8082` | `http://<host>:8082` |
| OTLP HTTP | `http://localhost:4318` | `http://<host>:4318` |

## First Dashboards To Check

### Homepage

Use Homepage to confirm the board has links for the tools you expect.

Screenshot target:

```text
docs/monitoring/images/homepage-overview.png
```

### Uptime Kuma

Use Uptime Kuma for health status and status page checks.

Screenshot target:

```text
docs/monitoring/images/uptime-kuma-dashboard.png
```

### SigNoz

Use SigNoz for traces, logs, metrics, and service-level debugging.

Screenshot targets:

```text
docs/monitoring/images/signoz-services.png
docs/monitoring/images/signoz-traces.png
```

### Plane

Use Plane after a monitoring finding becomes work that someone should track.

Screenshot target:

```text
docs/monitoring/images/plane-board.png
```

## Limits Of V1

Ops Board v1 is good enough for pilot onboarding. It is not yet a fully automated monitoring platform.

Current manual steps:

- Create Uptime Kuma monitors manually.
- Capture screenshots manually after UI login where needed.
- Add project entries to Homepage manually.
- Use project docs to track ownership and runtime location.
