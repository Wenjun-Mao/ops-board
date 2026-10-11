# 014. Native Maintenance Measurements

## Status

Accepted for evidence interpretation. This record does not certify completion
of a live release; each version still needs its own migration, restart, recovery
and ingestion receipt.

## Context

The owner-authorized HP-15 SigNoz rollout exposed assumptions in its new
measurement adapter. Rehearsal-only demo objects were not present in the live
inventory. ClickHouse 25.5 and 25.12 returned identical UInt64 row counts, bounds
and row hashes as JSON strings and numbers respectively. Finally, whole-SQLite
equality after restart rejected a changed alert snapshot `updated_at`, despite
unchanged accounts, settings, notification contents and telemetry.
An AI canary also expected costs from a rehearsal pricing rule that did not exist
live. Actual OpAMP pricing had exactly zero rules; mapping and token ingestion
worked, but cost attributes were correctly absent.

These are measurement-contract problems, not permission to modify live data or
skip preservation gates. Failed attempts remain failed and are retained.

## Decision

- Bind checks to the actual captured live inventory. An empty user-dashboard or
  saved-view inventory is valid; never copy rehearsal accounts, API keys, custom
  mappings or pricing into the live instance to satisfy a fixture assumption.
- Bind cost expectations to actual configured pricing rules. With exactly zero
  rules, require missing cost attributes, not a positive or fabricated zero cost.
  Validate provider/model identity, token counts and canonical message mapping
  independently. A configured rule needs its own exact price expectation; do not
  silently skip costs when a rule exists.
- Parse named count, hash and time-bound fields as unsigned 64-bit integers.
  Accept only integers or ASCII decimal strings in range; reject booleans,
  missing/extra fields and invalid numbers. Compare values, not JSON encoding.
- Require exact cold-restored file contents and metadata before startup. Native
  post-startup checks are a separate gate, not a replacement for this equality.
- Persistent metastore contents remain exact across restart. Only
  `alertmanager_state.updated_at` may advance within the measured restart window.
  Keep its columns, row count, IDs, organization, creation time, silences and
  notification log exact. Every other table stays exact. Do not ignore timestamps
  globally, exclude an entire table, rewrite its rows or disable the component.
- Version migrations may reconcile only named vendor-owned defaults against
  frozen old/new definitions. Preserve every user-owned row, including arbitrary
  custom-group names or user rows whose names resemble system defaults.
- Refresh inspected container states before every stop. Partial startup is valid
  only inside an explicitly owned isolated restore; live preflight still requires
  the full scoped deployment. Never treat startup construction as readiness.
- Bind diagnostic merge evidence to actual output part format. The pinned
  selector uses horizontal merges for compact output, even with vertical merging
  enabled. Require bounded naturally completed merges, matching output geometry,
  unchanged diagnostic UUIDs/row lower bounds and no new error 241. Do not force
  wide parts or `OPTIMIZE` just to make a rehearsal-specific expectation pass.
  Record when the live wide-output branch was not observed; isolated evidence is
  not evidence that a live wide merge occurred.

The alert-state boundary is backed by the versioned
[SigNoz state store](https://github.com/SigNoz/signoz/blob/v0.131.1/pkg/alertmanager/alertmanagerstore/sqlalertmanagerstore/state.go):
its upsert persists silences, notification log and snapshot update time. The
same file in v0.131.1, v0.135.0, v0.143.0 and v0.145.0 has SHA256
`00620c547036d1d5c594a28fa459af4e17836c86b438b828bb67b067215b201d`.
The contract permits only the clock change, not arbitrary upsert changes.

The pinned [v0.144.11 pricing processor](https://github.com/SigNoz/signoz-otel-collector/blob/v0.144.11/processor/signozllmpricingprocessor/processor.go)
returns without writing cost attributes when no model rule matches. The matching
v0.144.12 contract is also frozen and checked. A processor in the pipeline is not
evidence that a model catalog or price rule has been configured.

The pinned [ClickHouse merge selector](https://github.com/ClickHouse/ClickHouse/blob/v25.12.5.44-stable/src/Storages/MergeTree/MergeTask.cpp)
checks the resulting part format before the vertical row/byte thresholds.

## Alternatives and Guardrails

Broad tolerance of changed rows or operational tables would hide real loss.
Byte-identical database contents after a running component snapshots its state
would conflate cold recovery with ordinary lifecycle behavior. Both are rejected.

Regression checks cover empty inventories, arbitrary custom names, credential
drift, exact vendor mapping changes, UInt64 encoding, fresh client-state reads,
partial isolated startup, metric resource identity, exact unconfigured pricing,
and rejection of changed alert notification contents.
Joined SQL measurements must alias projected fields explicitly at the query
boundary; qualified result keys are not missing native data. Receipt version
fields must retain their own verified engine value, not a later loop's app stop.
An unexplained difference stops advancement; preserve its evidence, diagnose
the originating layer, and rerun the relevant gate after correcting its contract.
