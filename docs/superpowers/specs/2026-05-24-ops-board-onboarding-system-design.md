# Ops Board Onboarding System Design

Date: 2026-05-24

## Purpose

Ops Board should become the private operating center for projects that run across local machines, VPSs, and cloud providers. It should help the team answer basic operating questions quickly:

- Is the project alive right now?
- If something failed, where did it fail and why?
- Which host, environment, or owner is involved?
- Where should a teammate start when they need to monitor or onboard a project?

The immediate goal is not to publish a reusable package or automate every integration. The goal is to create a small, working onboarding playground, a stable onboarding contract, and clear manuals that make future project onboarding repeatable.

## Current Network Assumption

Ops Board is a private hub reached through Tailscale. Monitored projects may run on the same machine as Ops Board, on another local computer, or on a remote VPS/cloud host. V1 documentation and examples should not assume all projects are local.

Tailscale replaces a public reverse proxy for now. Dashboards and collectors are expected to be reachable privately by tailnet name, tailnet IP, or another internal address chosen by the operator.

## Deliverables

V1 should produce five related deliverables:

1. Onboarding contract
2. Dummy onboarding playground
3. Tiny local Python helper module
4. Operator and onboarding manuals
5. Screenshot/image asset structure

These pieces should live in this repo for v1 so they can evolve together with the stack.

## Repository Shape

The target structure is:

```text
examples/
  onboarding/
    README.md
    compose.yaml

    config/
      ops-board.example.yaml

    shared/
      ops_observe.py

    dummy-job/
      Dockerfile
      pyproject.toml
      job.py
      README.md

    dummy-api/
      Dockerfile
      pyproject.toml
      app.py
      README.md

docs/
  monitoring/
    ops-board-user-manual.md
    images/

  onboarding/
    human-guide.md
    codex-guide.md
    onboarding-contract.md
    images/
```

The `examples/onboarding/shared/ops_observe.py` module is a prototype of a future Python onboarding package. It should be easy to copy and inspect, but it should not be treated as a published library yet.

The `dummy-job` and `dummy-api` examples are consumers of that helper. This keeps the helper honest: it has to serve real example workflows without over-designing packaging too early.

## Onboarding Contract

Every onboarded project should identify:

- Service name
- Namespace or project group
- Environment
- Owner or team
- Runtime location
- Tailscale hostname or private address where relevant
- Provider, country, or region when useful
- OTLP endpoint for SigNoz telemetry
- Health endpoint for Uptime Kuma
- Links or notes useful for Homepage and future Plane follow-up

An app is considered onboarded when the operator can:

- See or configure its health check in Uptime Kuma
- See useful traces, logs, or metrics in SigNoz where practical
- Understand who owns it and where it runs
- Reproduce the onboarding steps from documentation

## Data Flow

The basic flow is:

```text
Project/App
  -> health check endpoint
      -> Uptime Kuma

  -> traces / metrics / logs
      -> SigNoz OpenTelemetry collector

  -> project metadata / operator links
      -> Homepage / docs / eventually Plane
```

Homepage is the starting surface: what exists and where to click.

Uptime Kuma answers whether a service is alive right now.

SigNoz answers what happened inside the service, job, or request.

Plane is for follow-up work once an issue becomes an operational task.

## App Configuration

The app-side config should be explicit and portable. A representative config shape is:

```yaml
service:
  name: dummy-api
  namespace: ops-board.examples
  environment: local
  owner: mk

ops_board:
  otlp_endpoint: http://ops-board-tailnet-name:4318
  health_url: http://dummy-api-tailnet-name:8000/health
```

The helper should load config in this precedence order:

1. Explicit function arguments
2. Environment variables
3. Config file
4. Defaults

This supports Docker Compose, remote VPS services, CI jobs, scheduled scripts, and local development without forcing one deployment style.

## Dummy Playground

The onboarding playground should cover two common project shapes.

### Dummy Job

`dummy-job` represents scheduled scripts, batch work, cron jobs, one-off workers, and other non-web workloads.

Success means a single script run creates:

- A named trace/span
- Duration information
- Success or failure status
- Structured logs with enough context to identify host, service, and environment

The operator should be able to answer:

- Did it run?
- Did it fail?
- How long did it take?
- Which host and environment ran it?

### Dummy API

`dummy-api` represents web/API services.

Success means:

- The app exposes `/health`
- Uptime Kuma can monitor `/health`
- API requests produce useful traces and logs in SigNoz
- Key internal functions can be wrapped with `@observe`

The API example may show a minimal middleware or framework instrumentation pattern, but v1 should avoid polished integrations for every Python framework.

## Python Helper Boundary

The helper should be intentionally small:

```python
bootstrap_observability(...)
@observe(...)
```

It should support the playground and teach the future package shape. It should not try to become a complete production SDK in v1.

The decorator-first experience is valuable for Python jobs and key functions, but it is not the whole onboarding story. Web apps still need health endpoints and request-level instrumentation. Services also need identity, config, and operational docs.

## Documentation

The docs should be split by reader intent.

### Ops Board User Manual

`docs/monitoring/ops-board-user-manual.md` is the operator manual. It should explain what Ops Board can do, where to start, and when to use each tool:

```text
Homepage      -> where do I start / what exists?
Uptime Kuma   -> is the thing alive right now?
SigNoz        -> what happened inside the app?
Plane         -> what work needs follow-up?
Tailscale     -> how do all machines privately reach each other?
```

### Human Onboarding Guide

`docs/onboarding/human-guide.md` should be written for colleagues, not only for the repo owner.

It should start with why Ops Board is worth using:

- One private place to see project health
- Faster debugging when jobs fail or APIs slow down
- Less guessing across VPSs, local machines, and cloud providers
- Shared operating language: health, traces, logs, owner, environment
- Private access through Tailscale without exposing dashboards publicly

Then it should explain how to onboard common project types:

- Python script or scheduled job
- Python web/API service
- Dockerized app
- Remote Tailscale-connected machine

### Codex Onboarding Guide

`docs/onboarding/codex-guide.md` should be precise and machine-friendly. It should include:

- Required files
- Expected config keys
- Naming conventions
- Validation commands
- Acceptance criteria
- What not to change in unrelated projects

The intent is that the guide can be pasted into another Codex session with a request like: "Onboard this project to Ops Board."

### Onboarding Contract

`docs/onboarding/onboarding-contract.md` is the stable reference that both human and Codex guides depend on. It should be less conversational and more exact.

## Screenshots And Images

Use a hybrid strategy with a bias toward local screenshots:

- Prefer screenshots from the local Ops Board stack
- Capture Homepage, Uptime Kuma, SigNoz services/traces/logs, and the dummy app appearing in the stack
- Use official screenshots or diagrams only where local screenshots cannot explain the concept well
- Avoid random stock images

Images should live beside the manuals that reference them:

```text
docs/monitoring/images/
docs/onboarding/images/
```

## Maturity Boundary

V1 is a pilot-ready onboarding system, not a production-grade monitoring platform for every project.

In scope:

- Working examples
- Clear docs
- Stable config contract
- Manual Uptime Kuma setup documented clearly
- SigNoz usage guidance based on observed dummy signals

Out of scope for v1:

- Published Python package
- Automatic discovery of all machines and services
- Automatic Uptime Kuma monitor creation
- Fully custom SigNoz dashboards
- Framework-specific integrations for every Python web framework and worker stack

## Acceptance Criteria

The implementation plan that follows this design should be considered complete when:

- Ops Board stack starts successfully
- Dummy API exposes `/health`
- Dummy API emits traces/logs that can be found in SigNoz
- Dummy job emits a run trace/log set that can be found in SigNoz
- Uptime Kuma can monitor the dummy API health endpoint
- Docs explain why Ops Board exists and how colleagues can join
- Codex guide is specific enough to reuse in another repo
- Screenshots or image assets are organized in the intended docs folders, with source notes where external official visuals are used

## Repo Hygiene Note

The stale temporary `signoz-stack` copy under `ContentShuttle/zz_external_projects` was removed before this spec was written. The canonical repo is:

```text
D:\MyDocuments\03-PythonProjects\HU\ops-board
```

The visual brainstorming companion creates `.superpowers/` artifacts. They are working artifacts and should not be committed.
