# 0003. First-Run Account Boundary

Date: 2026-06-07

## Status

Accepted

## Context

Ops Board now has a repo-owned first-run bootstrap path for Uptime Kuma. That bootstrap uses Uptime Kuma's Socket.IO application contract, generated local secrets, and monitor definitions committed under `stacks/uptime-kuma/bootstrap/`.

SigNoz and Plane also have first-run account or workspace flows, but Ops Board has not selected a stable, documented bootstrap contract for those products. Their first-run data includes personal admin credentials, workspace names, and product-specific state. Seeding those databases directly would couple Ops Board to private schemas and bypass application validation.

## Decision

For v1, Ops Board automates Uptime Kuma first-run setup and keeps SigNoz and Plane first admin/workspace setup manual.

Repo-owned scripts may verify that SigNoz and Plane containers are healthy, that their UIs are reachable, and that SigNoz receives telemetry from the onboarding playground. Repo-owned scripts must not create SigNoz or Plane admin credentials, workspace users, or tokens unless a future ADR selects an official application-level bootstrap contract.

## Consequences

- A fresh local setup still has manual UI work for SigNoz and Plane accounts.
- Day-1 smoke verification can pass without storing SigNoz or Plane credentials in Git.
- Screenshots may show setup, login, or dashboard states depending on the local browser session and reset timing.
- Future automation for SigNoz or Plane needs its own ADR, secret contract, and regression tests.

## Guardrails

- Do not commit SigNoz, Plane, or Uptime Kuma passwords.
- Do not seed SigNoz or Plane databases directly for first-run setup.
- Keep generated local secrets in ignored files under `secrets/`.
- Keep manual account details in a password manager or another user-controlled secret store, not in repo docs.
