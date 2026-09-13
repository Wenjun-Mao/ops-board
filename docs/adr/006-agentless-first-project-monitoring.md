# 006. Agentless-First Project Monitoring

## Status

Accepted

## Context

Requiring every project to install `ops-board-observe`, configure OpenTelemetry, and edit application code before it appears in Ops Board made the smallest useful onboarding path too expensive. Many existing APIs already expose health endpoints that Uptime Kuma can check without changing the target project. Some targets are private tailnet services while others are public HTTPS endpoints; neither case requires public access to Ops Board itself.

The existing Uptime Kuma bootstrap only created monitors by display name and included every configured monitor on the `ops-board` status page. That could not safely reconcile Git changes and would allow a project incident to make the Homepage-backed Ops Board status page look unhealthy.

## Decision

Ops Board project onboarding starts with Git-managed HTTP health monitors. The registry lives in `stacks/uptime-kuma/bootstrap/monitors.yaml` under `project_monitors`. Each entry has a stable ID, display name, URL, expected status codes, and code-backed monitor settings.

The bootstrap marks each project monitor with its registry ID, creates missing owned monitors, and updates owned monitors when their registry settings change. It does not delete monitors removed from the registry and does not take ownership of manually created monitors with matching names. Project monitors stay in the private Uptime Kuma dashboard and are excluded from the core `ops-board` status page and Homepage widget.

`ops-board-observe` remains an optional second tier for traces, logs, and execution-level evidence. It is the appropriate route for one-shot jobs, because an HTTP health probe cannot establish that a scheduled job ran successfully.

Target URLs may be reachable over Tailscale/private HTTP or public HTTPS. Uptime Kuma continues to run privately on Ops Board; public target reachability does not publish any Ops Board dashboard. TLS verification is enabled by default. Notification providers and authenticated health endpoints are deferred until their credentials and escalation policy have a dedicated design.

## Rejected Alternatives

- Require package instrumentation before any monitoring: rejected because it delays the first useful signal and forces changes in projects that already have health endpoints.
- Configure project monitors only in the Uptime Kuma UI: rejected because monitor configuration would drift from Git and be harder to review or reproduce.
- Put project monitors on the `ops-board` status page: rejected because that page represents the monitoring platform itself, not every monitored project.
- Exact deletion reconciliation: rejected because removing a registry entry could erase useful monitor history or hide an accidental configuration change.

## Consequences

- A project can be visible in Ops Board without a dependency or source-code change.
- Registry IDs, rather than display names, are the durable reconciliation key.
- Removing a project monitor remains an explicit maintainer action in Uptime Kuma until a lifecycle/archive contract is designed.
- Package configuration may retain `health_url` compatibility metadata, but it is not the source of truth for Uptime Kuma monitor provisioning.

## Guardrails

- Project monitor tests cover creation, owned-monitor updates, no-delete behavior, manual-monitor collisions, and exclusion from the core status page.
- Docs distinguish colleague work from Ops Board maintainer/admin work and make the agentless path the first path.
- Do not store monitor authentication or notification credentials in Git.
