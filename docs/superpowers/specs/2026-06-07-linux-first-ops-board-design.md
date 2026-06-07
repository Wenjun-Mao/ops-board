# Linux-First Ops Board Workflow Design

## Purpose

Move Ops Board from a Windows-development workflow to a Linux-first operator workflow, with `HP-15` as the immediate deployment target.

## Current State

- The repo is clean on `main`.
- `HP-15` has the repo at `~/projects/ops-board`.
- `HP-15` is Ubuntu, has Docker Compose, and has `uv` in the login shell path.
- The repo's operator scripts are currently PowerShell-first.
- The committed screenshots document expected UI states and are not host-specific deployment proof.

## Design

Add native shell scripts as the primary operator entrypoints:

- `scripts/init-local-config.sh`
- `scripts/bootstrap-uptime-kuma.sh`
- `scripts/status.sh`
- `scripts/update-stack.sh`
- `scripts/smoke-day1.sh`

The shell scripts should follow the current PowerShell behavior closely enough that the workflow remains familiar:

1. Generate ignored local config from `.env.example`.
2. Generate ignored secret files under `secrets/`.
3. Generate `stacks/plane/plane.env` from `stacks/plane/plane.env.example`.
4. Start the board through the root Compose aggregator.
5. Bootstrap Uptime Kuma with the existing Python helper through `uv`.
6. Run the Day-1 smoke from Linux.

The Linux scripts become the documented default. PowerShell scripts may stay during the transition, but they are no longer the primary contract.

## HP-15 Runtime Shape

`HP-15` should use host-facing URLs in `.env`:

- `HOMEPAGE_PUBLIC_URL=http://hp-15:3000`
- `UPTIME_KUMA_PUBLIC_URL=http://hp-15:3001`
- `SIGNOZ_PUBLIC_URL=http://hp-15:8080`
- `PLANE_PUBLIC_URL=http://hp-15:8082`
- `PLANE_WEB_URL=http://hp-15:8082`

Container-internal URLs such as `UPTIME_KUMA_INTERNAL_URL=http://host.docker.internal:3001` can remain as internal wiring when the compose files map `host.docker.internal` to the Docker host gateway.

## Screenshots

Existing committed screenshots remain reference screenshots. They show expected UI states, not proof of a particular host. Do not recapture them just because the deployment target changed.

After HP-15 is live, capture deployment proof screenshots into ignored scratch space only if they help the current handoff. Commit new screenshots only when the UI state or documented workflow differs.

## Testing

Validation should happen in layers:

1. Run shell script help/no-op checks locally where possible.
2. Run the Linux scripts on `HP-15`.
3. Run `./scripts/smoke-day1.sh` on `HP-15`.
4. Confirm the board is reachable from this workstation through Tailscale-facing URLs.

The Day-1 smoke remains the acceptance gate for a healthy board runtime.

## Documentation Impact

Update operator docs to make Linux the default:

- `README.md`
- `scripts/README.md`
- `docs/monitoring/ops-board-user-manual.md`
- onboarding docs that currently show only PowerShell commands

Docs should explain when to use `localhost` versus the Tailscale hostname.
