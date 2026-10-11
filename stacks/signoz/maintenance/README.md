# Prepared SigNoz Maintenance

**Accepted live target: v0.145.0 / collector v0.144.12 / ClickHouse 25.12.5.44.**
The ordered live sequence and repository-default promotion are recorded in the
[live receipt](../../../docs/monitoring/maintenance-receipts/2026-10-10-signoz-live.md).
Rendering these files alone proves no stop, upgrade, restore or acceptance.
Use [ADR 011](../../../docs/adr/011-signoz-lifecycle-and-prepared-release-contract.md)
and [provenance](provenance.md) before any manager-authorized rehearsal.

## Baseline Launcher Installation Gate

The baseline source launches `migrate sync check` under a tiny owned POSIX
initializer, then execs the final collector with unchanged arguments. During the
check, TERM/INT forwards only to that child and reaps it; five one-second polling
intervals bound cancellation. Forced KILL remains exit 137 and a refused backup.
The server reads the exact existing Docker JWT secret and refuses missing/empty
contents before exec. No baseline provider change, rotation or config change.

HP-15 completed this one-time transition at the old baseline, then passed ordinary
stop/restart and cold restoration. The mitigation is retired. The following is a
historical installation procedure for an old shell-PID-1 collector, not the
current backup path. The manager owns process identity and all live actions:

1. Quiesce incoming OTLP clients/agents and capture the old collector container ID,
   image ID, complete command/process tree, environment/config hashes and exact
   original `HostConfig.RestartPolicy` (including retry count). Scope to ONLY that
   old `ops-board/otel-collector` container; leave app, storage and other stacks alone.
2. Temporarily disable restart ONLY on that old container and assert the changed
   runtime policy. Otherwise a clean warm child exit may immediately restart it:
   the manager's Plane transition recorded exit zero followed by start one second
   later and RestartCount 1. A stopped-state timeout is not proof of a child hang.
3. After verifying the actual collector child identity, deliver its one-time warm
   TERM and retain evidence of graceful shutdown, parent/container exit zero, no
   OOM and stable stopped state without a subsequent start event. No broad PID
   search, guessing, signal escalation or tolerance of 137. If unproved, stop here.
4. Recreate ONLY the collector using the baseline Compose exec launcher, identical
   image and environment, original collector YAML and published binds. Assert
   actual collector PID 1 and restored Compose `unless-stopped` restart policy.
   The runtime policy exception must not leak into source or other containers.
5. Prove an ordinary scoped Docker/Compose stop with the existing 60-second grace
   completes cleanly, with no OOM/KILL/restart; restart the collector, assert health
   and policy, then prove ingestion. Retire warm-child signaling at this gate.

Record every transition and the original policy for explicit manager recovery if
installation fails. Never auto-resume writers after a failed step. The later
coordinated cold backup must use ordinary Docker stop, never this mitigation.

## Exact Required Stops

| Stop | App | Collector and Migrator | ClickHouse and Init | Collector Config |
|---|---|---|---|---|
| First | v0.131.1 | v0.144.5 | 25.12.5 | collector-v0.144.5.yaml |
| Dashboards | v0.135.0 | v0.144.6 | 25.12.5 | collector-v0.144.6-plus.yaml |
| JWT/AI | v0.143.0 | v0.144.11 | 25.12.5 | collector-v0.144.6-plus.yaml |
| Target | v0.145.0 | v0.144.12 | 25.12.5 | collector-v0.144.6-plus.yaml |

Apply `prepared.yaml` plus **exactly one** stop layer over the root Compose file.
Each stop reasserts both image pairs; they are not cumulative overlays. Do not
apply `prepared.yaml` alone. Requires Compose supporting `!override` (2.24.4+).
The real project stays `ops-board`; never deploy standalone project `signoz` or
Foundry's generated names. No root-wide `up`, `down`, `-v` or remove-orphans.
No `latest`, independent ClickHouse bump, or skipped required stop.

HP-15 is already at the target: **do not apply an earlier stop layer to its
migrated stores**. Earlier layers remain historical render/rehearsal contracts,
not downgrade commands. The v0.131/v0.135 environment replaces the app environment
with its exact old five-value contract; it must not retain the later JWT selector.
The credential guard still refuses removing an explicit provider from a current
deployment. Recovery uses sealed preceding-source bytes and matched stores/images,
not an old overlay over today's source.

### Diagnostic Merge Policy

Normal and prepared storage include the read-only `metric-log-merges.xml` bind defined by
[ADR 013](../../../docs/adr/013-bounded-clickhouse-diagnostic-merges.md). It enables
vertical merging of wide `system.metric_log` parts at any row/byte count, without
changing application-table policies, memory limits or logging retention. The
historical v0.125 baseline did not include this bind. This is an owned adaptation to the
pinned ClickHouse release, not a claim that upstream Foundry renders it.

Existing copies also require settings reconciliation on that table and its
numeric-suffix rotated predecessors. Record exact table UUIDs/configuration and
cleanly quiesce writers before mutation; a new config alone does not repair old
wide parts. Preserve every predecessor, including any rotation on restart.
Require low-memory natural merges appropriate to the output format and unchanged
full-data queries, then fresh lifecycle/cold-restore evidence. Wide outputs use
vertical merges; Compact outputs use horizontal merges. The isolated Wide branch
was proved independently; the live window observed Compact horizontal merges,
not a live Wide merge. Do not force geometry to manufacture that evidence or truncate diagnostic
tables, pause merges, increase limits or retry until a failed validation happens
to pass. Failed evidence remains failed.

## Operator Workflow

`commands.py` **prints only** one scoped phase; it does not execute Docker, prove
gates, advance versions or capture acceptance. For example, from the root:

```bash
python3 stacks/signoz/maintenance/commands.py --stage 0.131.1 --phase render
```

Review each printed command before running it in the separately authorized
execution environment. Render uses `--profile '*' config --format json` so jobs
and writers are visible. Restrict resolved output permissions because root
configuration may contain other stacks' credentials; never publish it in logs.

Follow this order **one gated phase at a time**, not as a batch script:

1. Before the first stop, pass the baseline installation gate. Before every stop,
   have an accepted preceding release and a complete matched coordinated cold
   SQLite/ClickHouse/ZooKeeper checkpoint with tested isolated restoration. Quiesce
   ingress and metadata writers, and prove no active init/migrator job or outside
   writer. Capture all mounts, secrets, launchers, images/digests, configuration,
   dashboards/users/alerts inventory, telemetry IDs/counts and timestamps.
2. `render`: review the candidate pins, full config, paths, project labels, named
   volumes and service scope. `pull`: explicitly acquire only the six SigNoz
   images, record exact image IDs/digests. All later ups use `--pull never`.
3. `stop-writers`: stop collector and app. Prove both cleanly stopped before
   `stop-store`; prove ClickHouse cleanly stopped, but leave ZooKeeper healthy.
   Run the **preceding/current-layer checkpoint**, not the candidate's checkpoint,
   so the tool owns the coordinator stop, cold capture and evidence. Refuse exit
   137, OOM or ambiguous state. Complete isolated matched-state restoration first.
   [ADR 012](../../../docs/adr/012-evidence-bound-zookeeper-checkpoints.md) defines
   the only guarded coordinator TERM exception; a manual or pre-stopped 143 cannot
   qualify later merely by reusing prior evidence. The standalone `stop-coordinator`
   printer phase is retired. Backup cleanup can restart its attempted coordinator;
   previously held writers and ClickHouse must remain stopped.
4. `init`: run just the init job attached, no dependencies/pulls/retries, and
   require completed exit zero. `coordinator`: start ONLY retained ZooKeeper and
   prove health. `store`: start ONLY ClickHouse and prove health, SQL version
   25.12.5, correct macros/cluster/replica paths, old data and no format errors.
5. `migrate`: attached, explicit manual job with exit-code gating. Vendor sequence
   is `migrate ready`, `bootstrap`, `sync up`, `async up`, each joined by `&&`.
   Require container Status exited, exit zero, no OOM and migration completion
   evidence. Neither jobs nor writers start automatically on failure; stop here
   and retain logs/containers/checkpoint until manager chooses recovery.
6. `server`: start ONLY app; prove health and metastore migration using existing
   users, dashboards and alerts. `collector`: start ONLY collector; prove PID 1,
   sync check, health and OpAMP connection with no unknown component or config
   parse errors. Verify new logs/traces/metrics, self-Prometheus series, metadata,
   meter records and historical data using saved resource IDs. Restore ingress
   only after explicit success, then observe late writes and restart stability.
7. `status`: inventory all six scoped services including completed jobs. Prove
   ordinary Docker stop and restart at this stop, capture a new full cold matched
   checkpoint, restore it in isolation and run the stage-specific checks below.
   The manager accepts the stop or halts. No next stop follows from rendering.

Prepared jobs use `manual-jobs` and `restart: no`; app/collector use `manual-writers` so
an unscoped up cannot implicitly run metadata migrations or ingestion. Existing
long-running restart policies remain `unless-stopped`. Init is intentionally
removed from ClickHouse's automatic dependency graph; operator completion is the
gate. `--no-deps` ups never supply that proof. No new migration CLI is invented.
Normal fresh startup retains the existing automatic dependency graph, without
manual profiles, and uses the same no-retry jobs. It is not the existing-state
upgrade workflow. Source render tests do not certify a new empty-host installation.

### Matched Current-Layer Checkpoints

Foundation source integration now accepts exact ordered layers, validates scope
and resource/mount contracts, and archives their raw bytes plus the resolved
stage config and actual runtime identities. The promoted v0.145 normal-root
deployment now needs no overlays. During the historical rollout, after an accepted
stop, use `prepared.yaml` plus exactly its **current**
stop layer for status/verify and every final held-writer checkpoint before the
next stop. Do not capture the next unapplied candidate as preceding state.

```bash
# Current accepted normal-root v0.145 deployment: no overlays.
./scripts/backup-stack.sh --stack signoz --context root --archive-image "$archive_image"

# Historical 0.131.1 acceptance ONLY, not today's HP-15 state:
# hold writers/store stopped, ZooKeeper healthy.
# Prints only; does not execute:
python3 stacks/signoz/maintenance/commands.py --stage 0.131.1 \
  --phase checkpoint --archive-image "$archive_image"
# Explicit current-stage readiness only after manager starts the accepted cohort:
python3 stacks/signoz/maintenance/commands.py --stage 0.131.1 --phase verify
```

`checkpoint`, `verify`, and `maintenance-status` print scoped foundation commands
with both ordered `--compose-overlay` paths. The operator selects the actual
current stage explicitly; the printer never infers predecessor/acceptance gates
or runs commands. The final held-writer checkpoint's `resume_container_ids` may
contain only the previously running coordinator, or be empty if every service
already had an accepted stopped state. Require held writers/store to remain
stopped throughout. Restores use captured collector YAML/OpAMP/launcher paths
and old image/runtime bytes in fresh isolation, without current source layers or
automatic startup. Source tests prove integration only: real stage stop exits,
full cold checkpoint, egress denial, restored login/users/data, migration and
ingestion remain manager-owned gates. Source tests alone certify no upgrade.
The first isolated stop has now passed its runtime gates; see the
[v0.131.1 receipt](../../../docs/monitoring/maintenance-receipts/2026-10-08-signoz-0.131.1.md).
The authorized v0.135.0 copy passes migration, dashboard conversion, authenticated
API checks, coordinated full stop/restart and a new five-volume cold restore with
retained accounts, normal-session queries and fresh ingestion; see its
[stage receipt](../../../docs/monitoring/maintenance-receipts/2026-10-08-signoz-0.135.0.md).
The owner authorized continuation on October 10. The fresh pre-v0.143 restore
passed; [next-stage progress](../../../docs/monitoring/maintenance-receipts/2026-10-10-signoz-0.143.0.md)
is separate from completed v0.135 evidence. The v0.143 copy now passes migrations,
saved-view/API conversion, actual OpAMP default/custom mapping and synthetic token
pricing, targeted diagnostic-merge repair and full-cohort restart with exact AI
settings/spans. Its own fresh five-volume cold restore and post-restore
normal-session/API/ingestion/AI checks also pass. The owner accepted that stop and
authorized the final [v0.145 rehearsal](../../../docs/monitoring/maintenance-receipts/2026-10-10-signoz-0.145.0.md).
That candidate's own five-volume cold restore and post-restore browser/API,
three-signal ingestion and AI mapping/pricing checks also passed. The owner then
accepted the candidate and authorized the live rollout. All four live stops
passed independent restart/cold recovery and fresh ingestion; current defaults
match live v0.145. See the separate live receipt rather than substituting copied
dashboards, five-volume inventory, service keys or pricing rules for live state.

## Stage-Specific Gates

- v0.131.1: ClickHouse must reach 25.12.5 before migration. This is an on-disk
  format upgrade; image downgrade alone is not rollback. Preserve the full old
  family checkpoint and restore it with matched old images/config in isolation.
- v0.135.0: server startup automatically converts stored dashboards to the
  Perses-compatible V2 schema. Check existing dashboard IDs/panels/variables;
  Legacy rows are incomplete conversion, not successful acceptance. Review API
  callers: V1 dashboard CRUD returns 501. Scalar metric queries/persisted Number,
  Table and Pie panels need `reduceTo`; test programmatic queries explicitly.
- v0.143.0: explicit `SIGNOZ_TOKENIZER_PROVIDER=jwt` plus the same existing secret
  and SQLite identity. Accept one re-login, not new user onboarding or credential
  rotation. Test both AI processors after spanmetrics/before batch, OpAMP-managed
  mapping/pricing round trip, cost attributes and queries using moved AI keys.
  V1 dashboard CRUD is removed, not the earlier 501 deprecation response. This
  image's catch-all returns the HTML app shell with 200 for removed paths, including
  writes; API clients must validate JSON/media type, not only HTTP success.
  Saved views migrate to the V2 `saved_view` table; preserve IDs, ownership, query
  and display semantics while validating the vendor's new schema/name structure.
  Pricing/mapping writes require an existing Admin session; an Editor service key
  can read/test them but must not be promoted to bypass this permission boundary.
- v0.145.0: repeat JWT/users, dashboards/alerts, historical and fresh ingestion,
  resource IDs, log-body/schema behavior and restart checks before final acceptance.
  Distinguish user-owned preservation from the pinned system AI overview/default
  mapping reconciliation described in the [stage receipt](../../../docs/monitoring/maintenance-receipts/2026-10-10-signoz-0.145.0.md).
  Verify canonical message targets and removal of moved legacy source attributes,
  plus targeted AI columns and actual OpAMP `action: move` configuration. Same-version
  restart and cold restore must preserve the reconciled state exactly.

Never rollback by simply repinning older binaries onto migrated stores. Use a
matched full-family restoration; preserve the failed candidate as evidence.

## Rehearsal Measurement Boundaries

Recovery inventory comes from the sealed manifest and actual runtime mounts,
not only `docker compose config`: Compose may omit an unattached retained volume.
Capture and compare every manifested volume, even when no current service uses it.
Image-declared job volumes can add anonymous mounts. Reconcile every inspected
mount before capture; keep prior unattached state as well. A fixed volume count
from an earlier stage is not authority for a later checkpoint.

The recovery serializer accepts actual runtime strings. Rendered Compose shell
commands can still contain `$$` escapes; they are not container `Cmd` strings.
Decode that source boundary before freezing runtime literals. Do not escape a
rendered shell command twice or change the production command to accommodate an
isolated adapter. Preserve refused preflight/job evidence before retrying.

Compare ClickHouse integer counts/time bounds as typed integers: JSON quoting of
64-bit numbers can change between releases. Do not weaken the data comparison.
After restoring, compare retained rows before allowing collector self-scrapes or
new fixtures; subsequent fresh samples are not evidence of lost original data.

For offline SQLite checks, first quiesce writers and copy the complete SQLite
file set into a disposable writable scratch directory. Keep the source volume
read-only. WAL-mode reads may need scratch WAL/SHM files even after clean shutdown;
do not drop existing WAL files or use an immutable connection on changing state.

Before each version stop, capture and test a fresh preceding-stage checkpoint
including the latest accepted fixture writes. That proof does not replace the
candidate's own post-migration full cold restore. Distinguish a currently running
candidate from an accepted stage in receipts and recovery metadata.

For V2 dashboard conversion, compare the coherent before/after semantic contract:
IDs, query reducers/filters, panel geometry, variables, permissions and audit
fields. Schema/plugin structure, generated names and exact vendor preset-icon
aliases may change intentionally; require specific conversion evidence rather
than ignoring whole fields. A legacy scalar fixture with a valid existing reducer
proves preservation, not derivation of a missing reducer. Direct authenticated
API positive/negative tests remain separate from signed-in UI success.

The v0.144.5 meter flushes on graceful shutdown. Require the three fixture counts
and retained values. Its per-resource metric-size function returns zero, so a
zero byte-size row is not failed sample ingestion or a positive size measurement.
See the [exact vendor implementation](https://github.com/SigNoz/signoz-otel-collector/blob/v0.144.5/pkg/metering/v1/metrics.go).

## Local Checks

```bash
python3 -m unittest discover -s scripts/tests -p 'test_signoz*.py' -v
FOUNDRYCTL=/path/to/verified/foundryctl python3 -m unittest discover -s scripts/tests -p 'test_signoz*.py' -v
```

Tests need the installed PyYAML and Docker Compose CLI, but no Docker daemon.
The optional verified Foundry path invokes ONLY `forge --no-ledger --no-updater`
against copied casting inputs in temporary directories. Generated pours and
`casting.yaml.lock` stay there; checked-in inputs are unchanged. It never invokes
cast/install or starts an app.
