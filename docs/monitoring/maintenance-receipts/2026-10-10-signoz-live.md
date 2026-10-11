# SigNoz Live Rollout on HP-15

## Status and Authority

**Accepted live v0.145.0; normal source and HP-15 version keys converged.**
The owner replied "yes go ahead" to the explicit request for the live SigNoz
upgrade with a fresh backup and rollback checkpoint. This accepted the final
isolated candidate and separately authorized the live sequence. It did not
authorize a Plane cutover, credential expansion, commit/push or artifact cleanup.
Evidence timestamps are October 11 UTC; the work began October 10 in Toronto.

## Coupled Sequence

| App | Collector / Migrator | ClickHouse / Init | Live Gates |
|---|---|---|---|
| v0.125.1 baseline | v0.144.4 | 25.5.6.14 | Fresh matched cold restore passed before changing versions |
| v0.131.1 | v0.144.5 | 25.12.5.44 | Migration, native preservation, full restart and own cold restore passed |
| v0.135.0 | v0.144.6 | 25.12.5.44 | Migration, native preservation, full restart and own cold restore passed |
| v0.143.0 | v0.144.11 | 25.12.5.44 | JWT/AI reconciliation, full restart and own cold restore passed |
| v0.145.0 | v0.144.12 | 25.12.5.44 | Migration, reconciliation, full restart, own cold restore and post-restore checks passed |

ZooKeeper remains the reviewed `signoz/zookeeper:3.7.1` legacy coordinator.
Every init and telemetry migration job ran explicitly and exited zero. App,
collector and ClickHouse ordinary stops exited zero without OOM/KILL; coordinator
143 was accepted only with fresh inspected [ADR 012](../../adr/012-evidence-bound-zookeeper-checkpoints.md)
proof after its clients stopped. Manual or stale 143 was not accepted.

## Preservation and Recovery

The actual live inventory had one user, one organization and one user-role row,
with no user dashboards, saved views or rehearsal service account. No copied
Editor key, custom mapper, pricing rule or disposable dashboard was introduced.
Whole account/credential fingerprints remain exact through each completed
migration and restart/recovery gate.

The original three named volumes and the init image's anonymous volume are
retained. Each cold restore compares **all four** volumes' file contents and
metadata before startup. Native SQLite and complete primary-table row counts/hashes
(`samples_v4`, `logs_v2`, `signoz_index_v3`), plus metric time bounds, are then
checked separately before new ingestion. These are not an exhaustive comparison
of every derived telemetry table. Restored
jobs are not rerun. Fresh trace/log/metric canaries prove post-restore ingestion.
The five-volume isolated rehearsal inventory is not substituted for live mounts.

Only vendor-owned AI dashboard/template and default message mapping transitions
may reconcile, using frozen old/new definitions and exact named deltas. Persistent
restart comparisons permit only the source-bound alert snapshot clock advance
defined by [ADR 014](../../adr/014-native-maintenance-measurements.md).

## Retained Failed Checks

The first baseline restore harness required a complete service set during
coordinator-only construction. A fresh second restore and scoped continuation
proved recovery; failed evidence and stopped containers remain retained.
The first storage comparison rejected quoted versus numeric UInt64 values,
despite identical counts/hashes/bounds. The typed contract corrected that
measurement without changing stored data. A first warm comparison rejected only
the vendor-maintained alert snapshot timestamp; persistent contents stayed exact.

The first v0.143 AI cost check incorrectly assumed the rehearsal pricing rule
also existed live. Actual OpAMP configuration had **exactly zero rules**. The
pinned vendor processor consequently emits no cost attributes. The corrected
contract requires that exact absence, while independently checking provider,
model, token counts, canonical messages and metric service identity. A configured
rule cannot silently bypass a cost check. No pricing setting was added or changed.
See the [pinned processor](https://github.com/SigNoz/signoz-otel-collector/blob/v0.144.11/processor/signozllmpricingprocessor/processor.go).

The first final diagnostic check incorrectly required Vertical merges for live
Compact outputs. The pinned selector uses Horizontal for that format; the gate
now checks actual retained output geometry and whole-window memory/error bounds.
No parts, limits or data were changed to obtain a pass. A second query projection
used qualified output keys; explicit SQL aliases corrected that adapter boundary.
The receipt's engine version variable was separated from its app-stop loop.
Earlier failed checks remain retained, not rewritten as passes.

The first source-promotion check stopped after the two version keys were updated:
Compose's null entrypoint inherits the pinned image default, while the verifier
compared null literally to Docker's entrypoint. No runtime was recreated. The
continuation validates the sealed baseline and every other original `.env` line,
then resolves image defaults and rendered command escapes at that boundary.
Regression tests also now require old provider-removing overlays to be refused
against promoted source; the credential guard was not weakened.

## Final Live Readback

All four live-stop canaries remain queryable; the latest collector has actual
OpAMP configuration, owns PID 1, and reports healthy. Targeted migration-1017
checks passed 28 value/existence contracts across two trace tables and seven AI
fields, plus three named indexes. Both retained and fresh AI spans preserve
provider/model/tokens and moved message attributes. Zero live pricing rules means
cost attributes remain absent, not a copied rehearsal price or an invented zero bill.

The diagnostic policy and every preceding log UUID/row lower bound remain intact.
Natural Compact horizontal merges stayed below 70 MB during the checked window
beginning `2026-10-11T02:39:32.785905Z`; query/part logs had no error 241 in that
window. Rotated Wide parts remain retained, but no live Wide vertical merge was
observed. The isolated 125,476-row Wide proof is independent, not live evidence.
See [ADR 013](../../adr/013-bounded-clickhouse-diagnostic-merges.md).

Safari's existing normal-user session freshly loaded the actual live home at
03:35:51 UTC, showing logs, traces and metrics ingestion active, both live AI-stop
canary services, and the correctly empty user dashboard/view/alert inventory.
No signup, key copying or permission change was needed. The owned Mac
`localhost:18081` relay now targets HP-15 **8080**, not the isolated copy. Normal
access is [http://hp-15:8080/home](http://hp-15:8080/home). Accessibility and pixels
were observed; no exported screenshot or hash is claimed.

Normal-root source now selects the tested app/collector pair, manager pipeline,
explicit JWT/SQLite providers, diagnostic policy and no-retry jobs. HP-15's ignored
`.env` changed only `SIGNOZ_VERSION` and `SIGNOZ_OTELCOL_TAG`; every other line
matches the sealed baseline archive. Source/runtime image, process command,
environment, read-only-bind and restart-policy parity passed without another
container recreation. Historical early layers are not downgrade recipes: the
credential guard refuses removing the current explicit JWT provider.

## Evidence and Boundaries

Restricted audit root on HP-15:
`/home/wjmao/ops-board-maintenance/signoz-live-20261011T023500Z`.
Its `state.json` identifies current/completed stops and immutable image IDs;
each version directory contains migration, semantic, canary, restart and cold
recovery proofs. Each `cold-result.json` names its sealed bundle and fresh matched
restore. Backups, original images, failed attempts and stopped restored copies
are retained; none were cleaned up.

Plane, Kuma, Homepage and unrelated containers retain their original IDs, image
IDs and start times at every completed live stop. This receipt does not complete
Plane or the parent full-stack maintenance plan. SigNoz ingestion is interrupted
during coordinated checkpoint windows; retained data preservation does not
promise zero loss for new senders that exhaust buffering or retries.

Never repin old binaries onto migrated stores as rollback. Use the preceding
sealed full-family checkpoint with its matched images, secrets and configuration,
and pass isolated restoration before a separately managed recovery cutover.

## Final Verification

The repository suite ran 166 tests: 165 passed and the optional Foundry check
was skipped. All 68 focused live/rehearsal checks passed. HP-15's Linux operator
suite passed 124 tests and shell checks in temporary fixtures; it did not reset
production configuration. `verify-stack.sh --stack ops-board --context root`
passed passive readiness for the full stack, including completed jobs. Direct Mac
checks reached collector health, SigNoz health, Homepage and Plane; Kuma returned
its normal login redirect. No real day-one bootstrap was rerun.

No further SigNoz rollout gate remains. Plane application/storage/broker upgrades
remain gated separately. No commit, push or retained-artifact cleanup was performed.
