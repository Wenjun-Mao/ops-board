# 001. V1 Status Source

Date: 2026-06-07

## Status

Accepted

## Context

Ops Board needs a clear day-1 answer for "is this service alive?" while the stack is still intentionally small. The board already includes Homepage, Uptime Kuma, SigNoz, and Plane. Healthchecks may be useful later, but adding it before Uptime Kuma has been used in real work would add another alerting surface without evidence that it is needed.

Homepage can display links and lightweight widgets, SigNoz can explain what happened inside services, and Plane can track follow-up work. None of those should become the first v1 owner for endpoint uptime.

## Decision

Uptime Kuma is the v1 status source for endpoint health and status pages.

Homepage remains the private launch board. It links to SigNoz, Uptime Kuma, Plane, Ops Board docs, and the onboarding playground. Homepage may show the Uptime Kuma status widget once the `ops-board` status page exists, but it should not become a parallel monitor configuration surface.

Homepage should use browser-facing public URLs for links and container-reachable internal URLs for server-side widgets. For Uptime Kuma, that means the link can use `UPTIME_KUMA_PUBLIC_URL`, while the widget proxy should use `UPTIME_KUMA_INTERNAL_URL`.

SigNoz remains the debugging and telemetry source. It is monitored by Uptime Kuma at both the UI health endpoint and the collector health endpoint.

Healthchecks is deferred until scheduled-job monitoring in real projects proves that Uptime Kuma's push/HTTP monitor model is insufficient.

## Consequences

- Uptime Kuma monitor setup is code-backed through `stacks/uptime-kuma/bootstrap/monitors.yaml`, with manual monitor docs kept as a fallback.
- Homepage cleanup should favor clear links and a single Uptime Kuma widget over duplicate direct status widgets.
- New project onboarding should first add an endpoint/job signal to Uptime Kuma and telemetry to SigNoz before adding more tooling.
- Local Uptime Kuma data becomes valuable after first-run setup; avoid `docker compose down -v` unless intentionally resetting the board.

## Guardrails

- Keep Uptime Kuma status page slug `ops-board` for v1.
- Do not add Caddy, Traefik, nginx, or a public reverse proxy as part of this decision.
- Do not add Healthchecks until a pilot project produces a concrete need that Uptime Kuma cannot handle cleanly.
