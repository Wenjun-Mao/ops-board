# 004. Linux-First Operator Workflow

## Status

Accepted

## Context

Ops Board is intended to run long term on Linux hosts, not on a local Windows workstation. The first target host is `HP-15`, an Ubuntu machine reachable over Tailscale with the repo cloned at `~/projects/ops-board`.

The current repo setup and operator docs are PowerShell-first. That worked for local Windows development, but it makes Linux deployment depend on installing PowerShell or translating commands by hand. The repo also contains committed screenshots that describe expected UI states after setup.

## Decision

Ops Board will become Linux-first for operator workflows. Native shell scripts under `scripts/` will be the documented default path for setup, status, update, Uptime Kuma bootstrap, and Day-1 smoke validation.

The existing PowerShell scripts may remain temporarily for compatibility, but they are no longer the primary contract. Future workflow changes should update the Linux path first.

Committed screenshots remain reference screenshots for stable UI expectations. They do not need to be recaptured solely because the runtime host changes from Windows to Linux. Host-specific deployment proof screenshots should stay in ignored local scratch space unless they reveal a real documentation or product mismatch.

## Consequences

- Linux hosts can bootstrap Ops Board without installing PowerShell.
- Documentation should prefer `./scripts/*.sh` and Tailscale-facing URLs such as `http://hp-15:3000`.
- `localhost` examples remain valid only for commands run directly on the deployment host.
- If screenshots show the same application state, they should not be churned for host changes.
- Windows support can break during this transition if preserving it would slow the Linux-first path.

## Guardrails

- Do not store deployment secrets in tracked files.
- Keep `.env` and generated stack env files ignored.
- Keep Linux script validation on `HP-15` as the acceptance check for workflow changes.
- Keep Day-1 smoke as the acceptance gate for the board runtime.
