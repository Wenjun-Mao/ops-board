# Ops Board Observe Package Design

## Purpose

Onboarding a colleague's Python project should not require copying helper files or manually tracking transitive observability dependencies. Ops Board needs a small internal Python package that a project can add, import, validate, and remove cleanly.

The normal colleague path assumes the project runs somewhere other than `hp-15` on the same tailnet. For the current deployment, the default OTLP endpoint is `http://hp-15:4318`. `localhost:4318` is only valid for code running directly on the Ops Board host.

## Decision

Create a package under `packages/ops-board-observe/` with distribution name `ops-board-observe` and import package `ops_board_observe`.

The package will expose:

```python
from ops_board_observe import OpsBoardSettings, bootstrap_observability, load_settings, observe
```

The package will own these dependencies:

- `pydantic-settings`
- `pyyaml`
- `opentelemetry-api`
- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp-proto-http`
- `tenacity`

Projects will install from the Ops Board repository until the package has a release channel:

```bash
uv add "ops-board-observe @ git+https://github.com/Wenjun-Mao/ops-board.git#subdirectory=packages/ops-board-observe"
```

Projects can offboard cleanly:

```bash
uv remove ops-board-observe
```

## Package Behavior

`OpsBoardSettings` loads config in this order:

1. Explicit function arguments
2. Docker secret files from `OPS_BOARD_SECRETS_DIR` or `/run/secrets`
3. `OPS_BOARD_*` environment variables
4. YAML config file
5. Defaults

Defaults should remain safe for local tests, but docs must not present localhost as the normal colleague endpoint. Reader-facing examples should use `OPS_BOARD_OTLP_ENDPOINT=http://hp-15:4318` unless they are explicitly playground-local or Ops Board host-local.

`bootstrap_observability()` configures OpenTelemetry resources, traces, and logs. `observe()` wraps sync or async callables, records success/failure status, and keeps existing behavior from the playground helper.

The package should not configure web framework middleware yet. FastAPI integration can stay as manual `@observe(...)` examples for v1.

## Repository Changes

Add:

```text
packages/
  ops-board-observe/
    pyproject.toml
    src/
      ops_board_observe/
        __init__.py
        settings.py
        instrumentation.py
    tests/
      test_settings.py
      test_observe.py
```

Refactor the current playground helper from `examples/onboarding/shared/ops_observe.py` into the package. The playground should consume the package through a local path dependency, so the example exercises the same import path colleagues will use.

The old `examples/onboarding/shared/` package should be removed after the playground imports from `ops_board_observe`.

## Documentation Changes

Update onboarding docs around the package-first path:

- `docs/onboarding/human-guide.md` should say "install this package" before showing imports.
- `docs/onboarding/codex-guide.md` should instruct Codex sessions to add the package dependency to the target repo, not copy helper files.
- `docs/onboarding/onboarding-contract.md` should describe the package as the v1 Python integration contract.
- `examples/onboarding/README.md` should explain that the playground uses the package through a local path dependency.
- Endpoint guidance should be colleague-first: `http://hp-15:4318` by default, `localhost:4318` only on the Ops Board host.

## Testing

Package tests should cover:

- config precedence: explicit args > secrets > env > YAML > defaults
- OTLP signal endpoint suffix handling for traces and logs
- `observe()` success and failure behavior
- sync and async wrapped functions

Existing playground tests should continue to pass after switching imports.

Verification commands:

```bash
uv run --project packages/ops-board-observe pytest packages/ops-board-observe/tests -q
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -q
docker compose -f examples/onboarding/compose.yaml config --quiet
```

## Out Of Scope

- Publishing to PyPI or a private package index.
- Auto-creating Uptime Kuma monitors for external projects.
- FastAPI middleware or framework-specific integrations.
- Non-Python project integrations.
- Changing SigNoz or Plane first-run account boundaries.

## Acceptance Criteria

- A colleague can add one package dependency and import `ops_board_observe`.
- A colleague can remove one package dependency to offboard the Python helper.
- Onboarding docs no longer tell colleagues to copy helper files or manually install transitive observability dependencies.
- Reader-facing docs make `http://hp-15:4318` the default for projects not running on the Ops Board host.
- The playground uses the package as a real consumer and all package/playground tests pass.
