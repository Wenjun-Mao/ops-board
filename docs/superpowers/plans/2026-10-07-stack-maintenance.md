# Full-Stack Maintenance on HP-15

Status: Implementation in progress. Kuma and Homepage are accepted. The owner
accepted the final SigNoz rehearsal and authorized its live rollout. All four
live stops through v0.145.0 passed restart, cold recovery, native preservation and
existing-session browser checks. Normal-source/ignored-env convergence passed; see the
[live receipt](../../monitoring/maintenance-receipts/2026-10-10-signoz-live.md).
Plane remains gated by restored upload/application acceptance.
Tooling is deployed; copied Rabbit/Silo feasibility passed without
production version changes. See [execution receipts](../../monitoring/maintenance-receipts/2026-10-07.md).
Research date: 2026-10-07, America/Toronto. HP-15 observations span October 7-8 UTC.
Execution: Serial work in the existing checkout, followed by staged HP-15 deployment.

## Outcome

Bring every Ops Board component onto a reviewed, explicitly pinned maintenance
baseline without losing accounts, workspaces, attachments, monitor history, or
retained telemetry. Establish repeatable Linux backup, recovery, and upgrade workflows so
future maintenance is smaller and safer.

The storage direction agreed with the user is to evaluate Plane's maintained
MinIO fork first. A different storage engine is a fallback, not the default plan.

## Scope and Permissions

- Includes Uptime Kuma, Homepage, the complete Plane application set and its
  PostgreSQL/Valkey/RabbitMQ/object-storage dependencies, and SigNoz with its
  collector, migrators, ClickHouse, ZooKeeper, and initialization job.
- Production-shaped runtime is `hp-15:~/projects/ops-board`, Docker project
  `ops-board`. The Mac checkout is for source changes and suitable isolated tests.
- Preserve existing host URLs, published ports, private dashboard access, secrets,
  agentless monitoring, and optional `ops-board-observe` onboarding.
- Excludes other HP-15 workloads, host OS/Docker upgrades, cloud storage, paid
  editions, HA redesign, automatic update schedules, and routine secret rotation.
- No factory reset, `down -v`, unscoped prune, `init-local-config.sh --force`,
  deletion/adoption of manual monitors, or replacement of existing user accounts.
- Implementation was authorized. Covered work includes repository edits, targeted
  ignored-env
  changes on HP-15, image pulls, isolated restore rehearsals, brief component
  outages, staged migrations, and the recovery actions described below.
- Commit/push, deleting retained backups/old volumes, adding external services,
  and accepting unrecoverable post-backup writes require separate authorization.
- Do not ask again at each covered stage. Stop for a material scope/risk change,
  failed feasibility gate, uncovered destructive action, or native approval.

Brief ingestion outages can leave gaps in new samples. Check existing exporter
buffer/retry behavior and record outage windows; do not promise zero-loss ingestion.
A requirement for uninterrupted ingestion would need a separate availability design.

## Verified Baseline and Candidate Targets

These are research candidates, not a declaration that the whole combination is
compatible. Revalidate releases, image availability, architecture, migration
requirements, and security notes before freezing the implementation manifest.
Observed baselines record the initial audit, not today's accepted runtime;
the execution receipts track applied changes and remaining gates.

| Component | Observed baseline | Proposed target or gate |
| --- | --- | --- |
| Uptime Kuma | 2.5.5 live; source still floats on `:2` | Pin 2.5.5; avoid an unnecessary restart |
| Homepage | v1.13.1 | v2.4.0; preserve private access without a new login gate |
| Plane applications | v1.3.1 | v1.4.2; all application images and migrator together |
| PostgreSQL | 15.7 | 15.19, same major; review intervening patch notes |
| Valkey | 7.2.11 | 7.2.14, same release series |
| RabbitMQ | 3.13.6 | Reviewed 3.13 patch if required, then 4.2.x, then 4.3.x |
| Plane object storage | Original MinIO RELEASE.2025-09-07, Quay `:latest` | PGSTY fork/Silo after release and copied-volume testing |
| SigNoz | v0.125.1 | Required intermediate stops, then v0.145.0 |
| Collector and telemetry-store migrator | v0.144.4 | Compatible pairs at each stop; final candidate v0.144.12 |
| ClickHouse | 25.5.6.14 | Official compatible SigNoz deployment version; not independent `latest` |
| ZooKeeper | signoz/zookeeper:3.7.1 | Review with the selected SigNoz storage layout |
| Initialization jobs | Existing pinned helper and release-selected jobs | Review alongside their owning stack; record exact images/artifacts |

The original Plane storage is responding; this is a maintenance/security issue,
not evidence of current attachment corruption. Plane's current v1.4.2 release
asset uses `docker.io/pgsty/minio:RELEASE.2026-08-04T00-00-00Z`. That project is now
PGSTY Silo, with a newer September 16 security release. Decide the tested target
from release notes and actual compatibility, not from an image name alone.

Uptime Kuma was already updated separately from 2.5.4 to 2.5.5. All nine monitors
were preserved and healthy at verification. The advertised leak fix concerns TCP
monitors; the nine existing monitors are HTTP, so no live TCP leak was established.

Other audit observations: one Plane workspace; RabbitMQ classic queues with zero
ready/unacknowledged messages and `khepri_db` disabled at inspection. Refresh all
of these before cutover. An empty queue snapshot is not permission to discard jobs.

## Maintenance Contract

Before this maintenance work, `--stack` wrappers selected standalone Compose files, whereas the live
services belong to the root `ops-board` project. Changing images through a
standalone file can address the wrong project or conflict with fixed names. Fix
deployment identity and service-group targeting at the shared helper layer before
using those wrappers for maintenance; do not work around it in individual callers.

The existing PowerShell backup archives repository configuration, not runtime
data, ignored environments, or secrets. Add a separate Linux runtime-data workflow
and make that distinction explicit in operator documentation.

For every stateful stage: resolve and retain old images/configuration, capture a
consistent checkpoint, rehearse recovery, execute only the intended service group,
and verify application behavior. Stop later stages on failure. Do not call an HTTP
200 or a successful image pull proof that a migration or restore succeeded.

Record durable deployment/version/recovery behavior in proposed ADR 007 during
implementation. Record the selected storage backend and its tested compatibility
boundaries in proposed ADR 008 only after the feasibility result is known. Follow
the concise format in `docs/adr/`; do not mark untested choices Accepted.

## Ordered Deliverables

### 0. Freeze Inputs and Resolve Feasibility

- [x] Audit the live stack and verify the current Plane CE storage release asset.
- [x] Agree on evaluating the maintained MinIO fork before other storage engines.
- [x] Refresh live images/digests, project labels, mount paths, node identities,
  disk/RAM capacity, service health, queues, monitor definitions, and data counts.
- [x] Obtain exact official release assets, not guessed raw-file paths. Retain
  provenance/checksums and minimally adapt Plane v1.4.2 Compose/environment files.
- [x] Resolve SigNoz's complete required-stop list from v0.125.1, with compatible
  collector/migrator pairs and storage versions. Include every applicable guide.
- [ ] Compare Plane's August PGSTY pin with the September Silo release, including
  security coverage, signed/reproducible artifacts, credentials, IAM, command and
  health-check changes, data-format compatibility, and documented rollback limits.
- [ ] Resolve RabbitMQ exact bridge/final images, Erlang requirements, feature
  flags, and Plane/Celery compatibility. The published path is 3.13 -> 4.2 -> 4.3;
  direct 3.13 -> 4.3 is not supported. Recheck the Khepri exception.
- [ ] Produce a local restricted manifest of tested versions, migration actions,
  checkpoints, service scope, and expected outages. Do not expose secret values.

Gate: No dependent live upgrade until its exact migration/recovery path is written
and the relevant rehearsal passes. Independent stages may proceed if another
component's feasibility remains unresolved; report that scope as incomplete.

### 1. Make Maintenance Targeting and Recovery Reliable

Source checkpoint: interfaces implemented under `scripts/maintenance/` with
`status`, `update`, `backup`, `restore`, and passive `verify` shell entrypoints.
ADR 007 records the implemented contract. The checklist below remains open for
live verification/rehearsal; source tests alone do not close these operational gates.
See `scripts/maintenance/README.md` for commands, lock and helper requirements,
anonymous-volume preservation, isolated networking, and explicit limitations.

Files: `scripts/lib/ops-board.sh`, `scripts/{status,update-stack}.sh`, proposed
focused deployment/backup helpers, `scripts/{backup-stack,restore-stack,verify-stack}.sh`,
`scripts/tests/test-linux-operator-scripts.sh`, and `scripts/README.md`.

- [x] Introduce an explicit deployment context separating root-project service
  groups from intentionally standalone deployments. Validate live project labels,
  service membership, fixed names, and volumes; fail on mismatches before mutation.
- [x] Preserve intentional standalone use. Document changed flags/semantics and
  update all affected callers/tests; never silently adopt another project.
- [x] Add dry-run plans, bounded health waits, stage failure reporting, and a
  maintenance lock. Keep generic pull/up clearly separate from migration logic.
- [x] Store runtime backups outside the checkout, defaulting to
  `~/ops-board-backups`, with restricted permissions and configurable destination.
  Capture configuration, ignored env files, secrets, images, identities, and state.
- [x] Manifest backups with checksums, scope, timestamps, source revision, resolved
  versions, volume identities, and recovery commands. Preserve the previous Kuma
  backup and rollback image; do not overwrite or prune retained checkpoints.
- [x] Validate capacity and required tools before pausing anything. Keep the exact
  prior running-service set; on backup-only failure, resume only services paused
  by that invocation. Do not blindly resume writers after a failed migration.
- [x] Restore into fresh, explicitly isolated volumes/names/networks. Validate
  archive integrity, image/data compatibility, target identity, and path safety;
  never overwrite a live volume as the default restore behavior.
- [ ] Rehearse one stack family at a time within HP-15 capacity. Restored workers,
  webhooks, notifications, and scheduled jobs must not contact real destinations.
  Use isolated internal networks and loopback-only test ports where necessary.

Consistency requirements:

| State family | Checkpoint requirements |
| --- | --- |
| Kuma | Gracefully stop Kuma; archive its complete data volume, including embedded MariaDB, users, history, settings, and status pages |
| Plane | Quiesce API/live/background writers; capture PostgreSQL, uploads including `.minio.sys`, Valkey persistence, RabbitMQ state/definitions, and required proxy/configuration state |
| SigNoz | Quiesce ingestion and all metadata/data writers; use a documented coordinated backup of SQLite, ClickHouse, and ZooKeeper, or cold archive after orderly shutdown |
| Homepage | Preserve tracked config plus restricted runtime environment; no equivalent application database |

RabbitMQ definitions are not a message backup. Preserve message storage and node
identity as needed; image recreation must not accidentally start a new empty node.
Include any external encryption/key material discovered by preflight. Local backups
protect an upgrade, not loss of HP-15; off-host disaster recovery is a separate scope.

Tests: root versus standalone targeting, wrong-project refusal, no unrelated
restart/removal, locking, corrupt/incomplete archives, traversal/target mismatch,
secret-safe output, backup failure cleanup, and restore into fresh isolated state.

Gate: A real restore with the pre-upgrade images must demonstrate usable accounts,
data, attachments/history, and no unwanted external side effects. Mocked CLI tests
are necessary but insufficient.
Kuma/Homepage are accepted. Plane's upload/application gate remains pending.
SigNoz's baseline and v0.131.1 copy passed native cold restore and normal account
queries. The v0.135.0 copy now passes migration/UI/ingestion, authenticated API,
coordinated full restart and current-stage five-volume cold-restore checks;
the owner authorized continuation on October 10. The v0.143.0 copy now passes its
own five-volume cold restore and post-restore browser/API/ingestion/AI checks.
The owner accepted that stop and authorized the final v0.145 rehearsal. Its own
five-volume cold restore and post-restore browser/API/ingestion/AI technical gates
also pass. The owner accepted that candidate and separately authorized the live
rollout. Follow the [live receipt](../../monitoring/maintenance-receipts/2026-10-10-signoz-live.md)
for completed stops and remaining gates, rather than treating rehearsal as cutover.
The revised shared interface captures explicit ordered root stage layers, while
retaining ownership/mount/credential/node guards and matched isolated recovery.
Independent verification passed 149 tests including all four Foundry pairs,
the Linux operator suite, and HP-15 source-only renders of every manifest stage.

### 2. Make Version Configuration Reproducible

Files: `.env.example`, `stacks/*/compose.yaml`, `stacks/plane/plane.env.example`,
`scripts/init-local-config.sh`, relevant script tests, and proposed ADR 007.

- [ ] Use exact reviewed release pins for application and dependency images.
  Follow the existing environment-version pattern; record resolved digests too.
- [x] Remove the generator's independent hardcoded Plane v1.3.1 default; fresh
  generation, sanitized examples, and Compose fallbacks must agree by tests.
- [ ] Update existing ignored HP-15 env keys selectively at their deployment
  stage. Do not regenerate config, rotate credentials, or activate every new pin
  simply because examples changed. Stage overrides/manifests must be explicit.
- [x] Codify Kuma 2.5.5 in source without a runtime restart in this assignment.
  Live ignored-env convergence and monitor comparisons remain deployment checks.
  Preserve all nine monitors, their IDs/settings/history, and ownership.
- [x] Keep maintenance verification read-only by default. `smoke-day1.sh` still
  runs Kuma bootstrap and optional onboarding, documented separately from passive
  `verify-stack.sh`.
- [x] Confirm the live Kuma pin and compare the retained monitor identities,
  settings, histories and ownership before closing deployment acceptance.

Gate: Tests cover fresh defaults and preservation of existing env/secrets. Source
pins and live pins converge at completion, not through an unscoped `up` mid-plan.

### 3. Patch Plane's Database and Cache

Files: Plane Compose/version settings and stage verification/recovery helpers.

- [ ] Review all PostgreSQL 15 patch notes since 15.7 for required follow-ups such
  as index repair. Rehearse the target with copied data before the live patch.
- [ ] Quiesce Plane writers, checkpoint, upgrade PostgreSQL within major 15, run
  required follow-ups, and verify login, workspace data, and application queries.
- [ ] In a separate checkpointed change, patch Valkey within 7.2. Preserve sessions
  and persisted state where applicable; verify cache/pub-sub and live collaboration.
- [ ] Verify Plane stays functional between changes and unrelated stacks stay up.

Gate: Database/cache readiness plus Plane behavior, not only `pg_isready`/`PING`.
Rollback uses the matched pre-stage data/config/images if needed.

### 4. Upgrade Plane's Application Set

Files: `stacks/plane/{compose.yaml,plane.env.example,README.md}`, generator/tests,
and necessary first-run/manual references.

- [ ] Adapt the official v1.4.2 assets with minimal repository-specific changes,
  preserving ports, secret mounts, URLs, named volumes, and private networking.
- [ ] Upgrade frontend, admin, space, live, API, worker, beat-worker, migrator, and
  proxy in lockstep. Keep the current storage backend during this stage to isolate
  application changes; prepare the storage configuration separately.
- [ ] Run schema migrations in the required order and require successful exit.
  Hold application writers until migrations and readiness checks succeed.
- [ ] Test existing login/workspace, project/work-item creation, editing, a safe
  background job, live updates, existing attachment downloads, and new uploads.
  Use clearly named test records and clean up only records created by this test.

Gate: Existing accounts and data survive, migration jobs succeed, and real flows
work. Reversing an image tag alone is not a schema rollback; restore a coherent
pre-stage database/storage checkpoint with the old images when required.

### 5. Move Storage to the Tested Maintained Fork

Files: Plane storage Compose/env settings, proposed storage probe/recovery helpers
under `stacks/plane/`, operator docs, and proposed ADR 008.

- [ ] Audit actual bucket/object/IAM/encryption state and the storage calls in
  target Plane v1.4.2. Confirm browser/proxy routing and internal endpoint behavior.
- [x] Test the selected PGSTY image against an isolated full copy of the MinIO
  volume, including internal metadata. Never let old and new servers share that
  volume concurrently. Do not assume a successful startup proves compatibility.
- [ ] Verify existing objects and database references, bucket names, object keys,
  metadata/content types, counts, byte totals, and content hashes. Multipart ETags
  are not universal content checksums.
- [ ] Exercise real Plane presigned POST/GET via its proxy, upload/download/delete,
  filenames with spaces/non-ASCII, avatars/covers/attachments, permission denial,
  and copy/multipart operations where Plane uses them. Verify after restart too.
- [ ] Review the candidate release's IAM, TLS, and rollback changes. Keep optional
  new storage modes disabled; no new console port or public bucket exposure.
- [ ] Quiesce Plane writers, take a final coherent checkpoint, switch the image
  and only required configuration/health commands, then rerun the acceptance set.
- [ ] Keep the original backup and image. If copied-volume compatibility or
  maintenance/security review fails, stop this stage and revise this plan for a
  bounded Garage/SeaweedFS evaluation; do not silently change storage engines or
  introduce a locally maintained source build.

Gate: Demonstrated preservation and full Plane behavior on the selected released
image. Rollback follows documented format/IAM constraints; restore the old complete
checkpoint rather than assume an old binary can read newly modified state.
Copied-state feasibility passed for September Silo with nonempty old-format
fixtures and S3 presigned/copy/delete/multipart/restart checks. Real Plane v1.4.2
proxy/attachment flows and adoption remain pending; ADR 008 is not accepted.

### 6. Upgrade RabbitMQ Through Supported Stops

Files: Plane RabbitMQ configuration, focused migration/verification helpers and docs.

- [ ] Preserve current node name/hostname, cookie, vhost, users, permissions,
  bindings, queue types, messages, and enabled flags. Do not introduce a new stable
  node name on an existing volume without a documented identity migration.
- [ ] Stop beat and other producers, drain outstanding jobs with workers, then
  stop consumers gracefully and recheck ready/unacknowledged state. If jobs cannot
  drain safely, use a documented message-preserving migration instead of deletion.
- [ ] Checkpoint the stopped broker and definitions. Rehearse the exact supported
  patch/4.2/4.3 sequence and required feature-flag transitions before live execution.
- [ ] Run and verify each stop independently; require supported Erlang, no alarms,
  successful recovery of queues, and the expected identity/state before proceeding.
- [ ] Verify a real Plane task is published, consumed, and acknowledged, then
  restore normal producers and scheduling. Do not enable experimental flags.

Gate: Healthy broker plus working Celery and no lost jobs. Feature-flag/schema
changes can be irreversible; downgrade on a migrated volume is not the rollback.
Use the matched old image and pre-stage state, accounting for any subsequent jobs.
The complete copied-broker path 3.13.6 -> 4.2.9 -> 4.3.6 passed identity, durable
message and current Plane client transport checks. Production and real Plane task
acceptance remain unchanged/pending; copied feasibility is not a live cutover.

### 7. Upgrade SigNoz as a Coupled Telemetry System

Files: `.env.example`, `stacks/signoz/compose.yaml`, collector and OpAMP config,
SigNoz verification helpers/docs, and affected onboarding smoke assertions.

- [x] Resolve the restored baseline's ZooKeeper 3.7.1 Docker-stop exit 143.
  ADR 012 binds the inspected JVM TERM status to current managed-stop evidence;
  October 8 cold capture, four fresh-volume file comparisons, account/object/data
  checks and signed-in dashboard/view queries passed. The subsequent live sequence passed;
  unexplained/pre-stopped 143 and other nonzero exits remain refused.
- [x] Execute only the official stop list resolved in stage 0. Pair app, collector,
  telemetry-store migrator, storage, initialization artifacts, and configuration at
  each stop; verify migration exit codes and supported data layouts.
- [x] Rehearse the first v0.131.1/v0.144.5 stop on an isolated copy with ClickHouse
  25.12.5. October 8 migration, five-volume cold restore, retained accounts/queries,
  three fresh signals and collector restart passed; see the
  [stage receipt](../../monitoring/maintenance-receipts/2026-10-08-signoz-0.131.1.md).
  This accepts only that copy stop, not the remaining sequence or a live cutover.
- [x] Accept the isolated v0.135.0/v0.144.6 stop. Migration, semantic V2 dashboard
  conversion, normal signed-in graph/Number/saved-view queries and ingestion/restart
  checks pass. Authenticated API compatibility, coordinated full stop/restart
  and a new v0.135.0 five-volume cold restore with restored accounts/queries and
  fresh ingestion also pass. The owner authorized continuation October 10; see the
  [stage receipt](../../monitoring/maintenance-receipts/2026-10-08-signoz-0.135.0.md).
- [x] Preserve JWT authentication deliberately with
  `SIGNOZ_TOKENIZER_PROVIDER=jwt` and the existing mounted secret. Fail on a missing
  secret; never silently rotate it or create a replacement admin account. Verify
  existing credentials, accepting re-login if the migration requires it. The live
  existing normal session remained valid; no new account/key or rotation occurred.
- [x] Promote the tested prepared pipeline only with accepted live-stage rollout.
  The historical baseline lacked `signozspanmapper` and `signozllmpricing`; preserve
  their OpAMP wiring and required pipeline order when promoting. Merely defining
  processors without using them is insufficient.
- [x] Prove the prepared v0.143 AI pipeline on the isolated copy. OpAMP delivered
  default/custom mappings and pricing; native stored spans and legitimate Editor
  API readback show the expected model, token counts and $0.0004 synthetic cost.
  Full stop/restart preserves whole AI-settings fingerprints, spans and active
  processor configuration. Fresh cold restore and post-restore native/API/browser
  readback also pass. The live pipeline now passes actual OpAMP and fresh-span
  checks; no copied custom mapping or pricing rule was introduced into live.
- [x] Resolve the isolated diagnostic-log merge failure with ADR 013's narrow
  table-scoped policy. Natural vertical merges and repeated full-data checks pass;
  no memory-limit increase, log truncation, disabled merges or reduced query scope.
- [x] Complete the isolated v0.143.0/v0.144.11 technical gates: its own fresh
  five-volume cold restore, post-restore normal-session/API queries, fresh
  three-signal ingestion and actual AI mapping/pricing readback all pass.
- [x] Obtain owner acceptance of the isolated v0.143.0/v0.144.11 stop before
  advancing to the separately gated v0.145.0/v0.144.12 rehearsal. See the
  [current-stage receipt](../../monitoring/maintenance-receipts/2026-10-10-signoz-0.143.0.md).
- [x] Complete the separately authorized final v0.145.0/v0.144.12 isolated
  technical rehearsal, including fresh predecessor and candidate cold restores
  and post-restore browser/API/ingestion/AI checks. Track its
  [stage receipt](../../monitoring/maintenance-receipts/2026-10-10-signoz-0.145.0.md).
- [x] Obtain owner acceptance of the final isolated candidate, then separately
  authorize the live checkpoint/rollout. Technical completion is not live acceptance.
- [x] Select ClickHouse/ZooKeeper versions from the official compatible deployment
  contract. Retain a compatible existing version only with evidence; do not leave
  storage unreviewed or bump it independently to upstream latest.
- [x] Verify existing dashboards, saved views, alerts, accounts, and retained
  telemetry. Actual live user dashboards/views/alerts were empty; account and
  whole primary-table fingerprints matched. Bounded OTLP trace/log/metric canaries
  passed at every live stop and after its own cold restore, with metric resource
  identity and targeted AI columns proved. No package public API was expanded.
- [x] Check known OTLP ingestion and health endpoints, actual collector OpAMP
  configuration, targeted AI attributes, and documented V1 removal/V2-V5 behavior.
  The authenticated API compatibility tests ran on the matched final copy; live
  known-session/native readbacks passed without importing its service key. No
  exhaustive audit of unknown external clients or configured pricing is claimed.
  Distinguish existing license-job warnings from migration/ingestion failures.

Gate: Required migrations and three telemetry signals succeed, old retained data
remains readable, and collector health works from Kuma and a colleague's host.
Rollback restores a coherent SQLite/ClickHouse/ZooKeeper/config/image checkpoint,
not old binaries against new schemas. Verify retained-data counts within TTL rules.

### 8. Update Homepage and Finish Acceptance

Files: Homepage Compose/config/env, stack READMEs, `scripts/README.md`, root README,
monitoring manuals, and onboarding references affected by changed instructions.

- [x] Upgrade Homepage to v2.4.0 after reviewing v2 changes. Explicitly preserve
  the current private-access model with auth disabled; retain the strict host
  allowlist. A new password/OIDC login gate is outside this maintenance scope.
- [ ] Verify every tile/link, Kuma status widget, environment substitution, normal
  browser rendering, health route, and cross-device access over the tailnet.
- [ ] Run read-only full-stack checks and the approved behavior tests. Keep day-1
  bootstrap/playground actions explicit; never infer success from a blank dashboard.
- [ ] Compare all existing monitor definitions/IDs, manual ownership, status-page
  placement, fresh checks, account/workspace/object counts, and retained histories.
  Allow explainable new checks and normal retention, not unexplained disappearance.
- [ ] Observe at least two full configured monitor intervals and a bounded synthetic
  scheduled-job cycle; inspect logs/restarts/resource usage for new failures or
  ongoing migration. Do not wait indefinitely for a real project's next cron run.
- [ ] Update current operator docs with versions, commands, backup/restore steps,
  owner/admin responsibilities, and upgrade caveats. Recapture only screenshots
  whose actual documented UI changed; leave historical plans untouched.
- [ ] Record completed stage receipts and accepted ADRs, and reconcile source/env
  pins with actual running images. Keep old recovery artifacts; report any deferred
  component honestly rather than declaring the entire stack current.

## Recovery and Completion Rules

Pause writers before irreversible transitions and verify recovery before reopening
them. Once new writes are accepted, a pre-stage restore can lose those writes. Do
not perform that rollback automatically: preserve the failed/new state, assess a
lossless repair or migration, and request authority for any unavoidable loss.

Implementation is complete only when all intended components have reviewed pins
or an explicitly reviewed compatible retention decision, each stateful stage has
restore evidence, existing data and identities remain intact, actual application
and telemetry flows pass, and current docs reflect the deployed behavior.

Use existing Bash/Python/uv verification tools. Keep helpers cohesive and under
roughly 400 lines. The Kuma bootstrap is already 594 lines: do not put general
maintenance logic there; split it first only if this scope truly requires additions.

## Primary References

- [Plane v1.4.2 release](https://github.com/makeplane/plane/releases/tag/v1.4.2)
- [Exact Plane CE Compose asset](https://github.com/makeplane/plane/releases/download/v1.4.2/docker-compose.yml)
- [Plane storage configuration](https://developers.plane.so/self-hosting/govern/database-and-storage)
- [PGSTY Silo September release](https://github.com/pgsty/silo/releases/tag/RELEASE.2026-09-16T00-00-00Z)
- [Silo migration and compatibility](https://silo.pgsty.com/compatibility/migration/)
- [PostgreSQL versioning and patch policy](https://www.postgresql.org/support/versioning/)
- [Valkey 7.2.14 release](https://github.com/valkey-io/valkey/releases/tag/7.2.14)
- [RabbitMQ supported upgrade paths](https://www.rabbitmq.com/docs/upgrade)
- [RabbitMQ release/support information](https://www.rabbitmq.com/release-information)
- [SigNoz upgrade-path tool](https://signoz.io/upgrade-path/)
- [SigNoz v0.143 migration requirements](https://signoz.io/docs/operate/migration/upgrade-0-143/)
- [SigNoz v0.145 release](https://github.com/SigNoz/signoz/releases/tag/v0.145.0)
- [Collector v0.144.12 release](https://github.com/SigNoz/signoz-otel-collector/releases/tag/v0.144.12)
- [Homepage v2.4 release](https://github.com/gethomepage/homepage/releases/tag/v2.4.0)
- [Homepage authentication options](https://gethomepage.dev/installation/)
- [Uptime Kuma 2.5.5 release](https://github.com/louislam/uptime-kuma/releases/tag/2.5.5)
