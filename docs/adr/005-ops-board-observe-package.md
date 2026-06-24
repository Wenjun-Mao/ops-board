# 005. Ops Board Observe Package

## Status

Accepted

## Context

Colleague project onboarding was too manual. The original observability helper was copied from this repo, so imports, dependency installation, and configuration drifted when used from separate projects. That made the onboarding path fragile and required each consuming project to rediscover the same setup details.

## Decision

Ops Board observability will live in the `ops-board-observe` Python package and be imported as `ops_board_observe`. Until it is published to a package index, consuming projects install it from the repo git subdirectory. The package owns its OpenTelemetry, settings, YAML, and retry dependencies instead of asking each consumer to copy helper code or dependency lists.

The public helper API is:

- `OpsBoardSettings`
- `load_settings`
- `bootstrap_observability`
- `observe`

Runtime docs use `http://hp-15:4318` as the default colleague endpoint. `localhost` is only for commands running directly on HP-15 or in a local playground.

`bootstrap_observability` is first-call-wins inside a process. Repeated calls with identical effective settings and the same `export` flag return the active settings without reinstalling providers or duplicate handlers. Repeated calls with different settings or a different `export` flag raise `RuntimeError`. Bootstrap also rejects preconfigured process-global OpenTelemetry tracer or logger providers so it does not claim success while another provider remains active.

`export=False` is the no-export/test path and avoids OTLP exporters, OTel logging handlers, and root logging level changes. `export=True` configures OTLP traces and logs, attaches the OTel logging handler once, and enables INFO-level application logs for that handler.

Resource metadata includes standard service fields plus `service.owner`.

## Rejected Alternatives

- Keep the copied playground helper: rejected because it preserves manual onboarding, dependency drift, and broken imports in separate projects.
- Silently compose with pre-existing host OpenTelemetry providers: rejected because OTel providers are process-global and set-once, so silent composition can claim success while another provider owns export behavior.
- Allow in-process reconfiguration: rejected because changing settings, exporters, providers, or logging handlers after bootstrap can leave traces and logs using different runtime contracts. Hosts should restart the process, and tests should use the explicit reset helper.

## Guardrails

- Package tests cover settings precedence, bootstrap conflict and reconfiguration behavior, provider rollback and cleanup, `export=False` side effects, OTel logging handler wiring, and span emission.
- Docs and playground workflows should import and install `ops-board-observe` instead of copying helper code.
- Any future host-provider composition must update this ADR or add a replacement ADR before relaxing the first-call-wins/provider-conflict contract.

## Consequences

- Separate projects can depend on one package contract instead of copying helpers.
- The package can later be published and versioned without changing import paths.
- Host applications that already configure OpenTelemetry must coordinate bootstrap order with Ops Board observability.
- First-call-wins avoids hidden in-process divergence, but it means tests and long-running hosts must reset or restart before changing observability settings.
- Docs and playground examples must be explicit about when `hp-15` versus `localhost` applies.

## Follow-ups

- Publish and version `ops-board-observe` when the package contract settles.
- Keep docs and the playground consuming the package rather than copied helper code.
- Add compatibility guidance for host apps that need to compose their own OpenTelemetry providers with Ops Board telemetry.
