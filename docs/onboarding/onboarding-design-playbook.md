# Onboarding Design Playbook

Use this playbook when designing or reviewing a workflow that helps another project connect to Ops Board. It captures the lessons from the first onboarding-doc and `ops-board-observe` package pass.

This is not an ADR. Use it for repeatable product and docs practice. If a future change alters a durable runtime, package, deployment, or ownership contract, write or update an ADR too.

## Start With The User Path

Write the workflow as if a colleague is following it from a different machine and a different repository.

- Assume the project does not run on `hp-15`.
- Assume imports from this repo do not work unless a package or explicit path dependency makes them work.
- Assume `localhost` means the reader's current machine, not Ops Board.
- State which commands run on the project host, the Ops Board host, or a local playground.
- Put the first useful success check before the first code edit.

Read the draft once as the colleague and once as the Ops Board maintainer/admin. If either role has to infer ownership, location, credentials, defaults, or next action, the doc is not obvious enough yet.

## Separate Roles

Keep project-owner work separate from Ops Board maintainer/admin work.

Project owner or colleague owns:

- package install or app dependency changes
- `ops-board.yaml`, `OPS_BOARD_*`, or deployment config
- health endpoint implementation
- app/job telemetry
- project docs for owner, runtime host, and health URL

Ops Board maintainer/admin owns:

- Uptime Kuma monitor creation and placement
- Homepage entries and Ops Board-side links
- SigNoz and Plane first admin/workspace setup
- Ops Board credentials and local stack secrets
- monitor naming and status-page placement

When a person wears both hats, keep the labels anyway. The labels make handoff and future automation boundaries visible.

## Put Preflights Before Code Changes

A preflight should answer, "Can this environment even work?" before the reader installs packages or edits code.

For current HP-15 onboarding, the project runtime host should pass:

```bash
curl -fsS --max-time 20 http://hp-15:13133/
```

This proves the project host can reach the collector health endpoint. It does not prove telemetry export. The later success test must still run one request or job and confirm SigNoz sees the expected service.

Use exact commands for:

- Ops Board collector reachability from the project host
- project health endpoint reachability from a tailnet machine
- package config loading from the same working directory or environment the app uses
- final trace or log evidence in SigNoz

## Explain Every Config Field

For each required config field, document:

- whether it is required for real onboarding
- the package or tool default
- how the value is used
- examples and accepted conventions
- how to discover the value
- whether it is sent as telemetry or only used for handoff

Avoid examples that look like magic constants. If a value is only a convention, say so. For example, `environment` accepts strings; Ops Board recommends short labels such as `local`, `dev`, `test`, `staging`, and `prod`.

For host fields, explain Tailscale clearly:

- `runtime.host` identifies where the project runs.
- `runtime.tailscale_host` is the Tailscale MagicDNS name or Tailscale IP when available.
- The project owner can find it in the Tailscale app or Machines page.
- If MagicDNS is unclear, the project owner can share the Tailscale IP and let the maintainer/admin decide what to monitor.

## When To Build A Package

Build a package when shared onboarding behavior crosses repository boundaries and would otherwise be copied into each project.

Package the behavior when at least two of these are true:

- the consumer would copy helper files from Ops Board
- the consumer would manually install several dependencies only for Ops Board
- imports would otherwise point at repo-local paths that do not exist in the target project
- config precedence, defaults, or secrets need one stable contract
- removal should be one dependency removal plus small app edits
- tests need a reusable no-export path
- the helper owns tricky runtime behavior, such as OpenTelemetry provider setup

Do not package one-off docs, project-specific monitors, credentials, or Ops Board-side admin actions.

## Package Design Checklist

For a package-backed onboarding path:

- Give the package one stable import path.
- Expose a small public API and document it.
- Own transitive helper dependencies inside the package.
- Use `pydantic-settings` for config and document precedence.
- Prefer Docker secrets over environment variables over defaults when secrets are involved.
- Make defaults safe for local tests but too obvious to leave in real onboarding.
- Provide a no-export test path so unit tests do not need live Ops Board.
- Define how bootstrap behaves if called twice in one process.
- Reject hidden runtime divergence instead of silently composing incompatible setup.
- Keep playground examples consuming the package, not copied helper code.
- Document the current install source and the future publishing path.

For `ops-board-observe`, ADR 005 is the durable package contract. Update that ADR or add a replacement ADR before changing package bootstrap semantics, provider ownership, config precedence, or install strategy.

## Install And Removal Checklist

A good onboarding package should be easy to add and easy to remove.

Install docs should include:

- one command to add the package
- the expected import statement
- the minimum config file or environment block
- a command that proves config loads
- the first app or job code edit
- the first telemetry success test

Removal docs should include:

- imports to remove
- decorators or bootstrap calls to remove
- config fields or environment variables to remove
- package removal command
- Ops Board maintainer/admin handoff for monitors and links
- project tests or startup checks to run afterward

If removal takes more than a short checklist, the package has leaked too much surface area into the target project.

## Docs Review Checklist

Before treating onboarding docs as ready, check:

- The first page says who it is for.
- The endpoint examples distinguish `hp-15`, `localhost`, and playground-local usage.
- Every command says where to run it when location matters.
- Project-owner steps and maintainer/admin steps are visually distinct.
- Required fields include defaults, usage, examples, and discovery instructions.
- A reader can install the package without manually adding transitive dependencies.
- A reader can remove the package without hunting through chat history.
- Screenshots are refreshed only when the UI state or documented workflow changes.
- Historical plans are not used as current runbooks.
- The final success test produces evidence, not just "it started."

## Verification Checklist

Use checks that prove the docs match the repo:

```bash
rg -n "shared[.]ops_observe|copy[ ]or[ ]adapt|manual[ ]dependency|Before[ ]calling|minimum[ ]service[ ]identity" README.md docs access scripts stacks examples -g "*.md" -g "!docs/superpowers/**"
docker compose --env-file .env.example -f compose.yaml config --quiet
docker compose -f examples/onboarding/compose.yaml config --quiet
uv run --project packages/ops-board-observe pytest packages/ops-board-observe/tests -q
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -q
git diff --check
```

Add more checks when the workflow touches more code. Do not claim the docs are current until the commands that prove the claim have passed.

## What To Promote

Use the right home for each lesson:

- ADR: durable architecture, runtime, package, deployment, or ownership contract.
- Playbook: reusable review practice or product taste.
- Contract doc: current onboarding requirements and acceptance evidence.
- Human guide: colleague-facing steps.
- Codex guide: machine-friendly implementation instructions.
- Temporary note: unstable ideas that still need review.

When a manual review or real onboarding reveals a repeated issue, capture it first, review the wording and boundary, then promote it to the right home.
