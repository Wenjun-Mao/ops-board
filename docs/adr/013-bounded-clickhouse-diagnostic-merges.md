# 013. Bounded ClickHouse Diagnostic Merges

## Status

Accepted maintenance contract; isolated native repair, full stop/restart and
fresh five-volume cold restoration verified on October 10, America/Toronto
(October 11 UTC evidence). Technical checks passed and the owner accepted the
v0.143 isolated rehearsal. The final v0.145 isolated cold restore preserves the policy,
diagnostic UUIDs and row lower bounds, with no new 241 in its observation window;
the owner subsequently accepted it and separately authorized live deployment.
All live stops now preserve this policy and diagnostic data; the normal-root
configuration includes the bind. See the
[live receipt](../monitoring/maintenance-receipts/2026-10-10-signoz-live.md).

## Context

The isolated ClickHouse 25.12.5.44 rehearsal repeatedly cancelled small full-data
validation queries with error 241. Query logs measured only 3-4 MB for those
queries. Part and metric logs identified simultaneous horizontal merges of
`system.metric_log`, with 1,552 columns, allocating about 6.6 GB. These exhausted
the unchanged 6.66 GiB server limit despite a much smaller resident footprint.
Existing wide parts had fewer than the default 131,072 rows required to activate
vertical merging. This is a diagnostic-table merge-policy problem, not permission
to skip data checks, raise memory limits or disable logging.

The [upstream issue](https://github.com/ClickHouse/ClickHouse/issues/78957)
and [subsequent default-policy improvement](https://github.com/ClickHouse/ClickHouse/pull/89811)
identify this wide-column failure class. The pinned
[25.12.5.44 merge selector](https://github.com/ClickHouse/ClickHouse/blob/v25.12.5.44-stable/src/Storages/MergeTree/MergeTask.cpp)
requires both row and byte thresholds for vertical merges, and that version's
shipped configuration predates the upstream policy change.

## Decision

Apply the named policy `metric-log-wide-vertical-v1` only to the SigNoz
ClickHouse diagnostic table: enable vertical merging and set its row and byte
activation thresholds to zero. Wide outputs gather non-key columns separately;
compact outputs continue to use their existing merge path. Keep all application
tables, memory limits, row coverage, retention and diagnostic collection intact.
Unlike merely delaying creation of new wide parts, this also handles the already
restored small wide parts. The prepared overlay adds one exact read-only config
bind, now also in accepted normal source; it cannot replace an existing bind or storage identity.

For an existing copy, reconcile the same settings on `system.metric_log` and
its numeric-suffix rotated predecessors. Record their UUIDs, settings, rows and
the exact configuration mutation. ClickHouse may rotate a system log on a config
change; retain all predecessors and verify their policy by UUID after restart.
Do not drop/truncate logs or stop merges to satisfy validation.

## Alternatives and Guardrails

- Retrying until a scan happens to pass does not resolve the ongoing failure.
- Increasing limits is unsafe on a shared 7.4 GiB host; rejected.
- Disabling logs or broad merge tuning would weaken evidence or affect telemetry;
  rejected. This narrower policy trades some small-merge overhead for bounded
  wide-column buffering.
- Do not independently upgrade ClickHouse outside the reviewed SigNoz pair.
- Require natural low-memory merges appropriate to output format: Vertical for
  Wide, Horizontal for Compact. Record an unobserved branch explicitly rather
  than forcing geometry. Require no recurring error 241 and unchanged
  full inventory/history/retained fixtures, and current-stage stop/restart and
  cold-restore checks. Historical failed checks remain failed.
- Tests protect the exact table-scoped XML, read-only normal/prepared addition
  and refusal of arbitrary ClickHouse bind changes.

## Isolated Evidence

The original diagnostic-log UUIDs and rows survived policy reconciliation and
ordinary storage restart. A naturally completed vertical merge of 125,476 rows
used 13,486,903 bytes, versus the previous approximately 6.6 GB horizontal
allocation. Repeated full inventory/history scans and retained canaries matched;
no new error 241 appeared in the bounded query/part-log observation window.
Compact diagnostic output retained its ordinary horizontal merge path.

Fresh full-cohort stop/restart checks passed, including exact account/data checks
and, in the second run, complete AI-settings fingerprints, both retained AI spans
and the OpAMP-written mapping/pricing configuration. Fresh cold restoration and
post-restore queries/ingestion passed, preserving diagnostic UUIDs/rows and the
table-scoped policy with no recurring 241 in the bounded observation window.
Historical failures were not rewritten. See the [v0.143 receipt](../monitoring/maintenance-receipts/2026-10-10-signoz-0.143.0.md)
for current-stage completion boundaries.
The [v0.145 receipt](../monitoring/maintenance-receipts/2026-10-10-signoz-0.145.0.md)
records the final candidate's independent restart, cold recovery and post-restore
checks. The later live window observed Compact horizontal merges below 70 MB,
retained the rotated Wide parts, and had no error 241 in bounded query/part logs.
It did not observe a live Wide vertical merge; the independent isolated Wide
proof above is not relabeled as live evidence. Live lifecycle/cold recovery and
source promotion are recorded separately in the live receipt.
