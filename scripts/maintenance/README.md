# Maintenance and Recovery

This is the Linux operator entrypoint for scoped runtime checkpoints and isolated
restore preparation. Python 3.9+, Docker Engine, Compose v2 with `config --format
json` and root `include` support, and enough local disk are required. Baseline and
restore need no additional Python package. These tools do not implement database/application
migrations or certify restored application behavior.

Only optional stage-overlay validation additionally requires PyYAML in the
operator's Python runtime. Baseline operations and restoration of old/new
captured bundles remain standard-library-only. Missing PyYAML refuses overlay
validation before any Docker mutation; the scripts do not install dependencies.

## Target the Existing Deployment

On HP-15, run from `~/projects/ops-board`:

```bash
./scripts/status.sh --stack plane --context root
./scripts/verify-stack.sh --stack plane --context root
./scripts/update-stack.sh --stack plane --context root --dry-run
```

`root` is the default: `--stack plane` selects only Plane services in project
`ops-board`. `--stack ops-board` selects all four groups. Intentionally standalone
deployments require `--context standalone --stack NAME`; this is not how HP-15
is deployed. Ownership/checkout labels, fixed names, volume identities, unexpected
mounts and outside consumers are checked before mutation. Pre-existing volumes
with different labels require an explicit reviewed adoption/recovery decision;
the tools never silently relabel/adopt them.

Status is passive and includes one-shot jobs. Verify additionally checks bounded
container readiness, completed job exits, PostgreSQL/Valkey/RabbitMQ/ClickHouse
readiness, and local published HTTP health endpoints for the selected group. It
does not bootstrap Kuma, onboard examples, create users, reconcile monitors, or
prove upload/data-history correctness. By contrast, `smoke-day1.sh` still performs
Kuma reconciliation and optional onboarding actions.

## Reviewed Stage Inputs

`status`, `verify`, `backup`, and generic `update` accept repeatable
`--compose-overlay FILE` in the exact applied order, after the root aggregator.
Only `--context root --stack plane` or `signoz` permits layers. Each input must
be a regular non-symlink file inside `stacks/<selected-stack>/maintenance`;
caller-relative and absolute paths are accepted, traversal and outside paths are
not. Restore, standalone, full-stack, Homepage and Kuma contexts refuse layers.
No argument means the unchanged baseline contract; old format-1 bundles remain
restorable without these new audit fields.

For Plane layers, the root `.env` is followed by existing `stacks/plane/plane.env`
for override interpolation, matching the release operator commands. Shell values
still win: clear unintended overrides, especially `COMPOSE_PROJECT_NAME` (refused
for layer validation). Each cumulative prefix is rendered and checked against
the same resolved baseline **before runtime queries or mutation**. Config uses
`--profile '*'` to see jobs and manual writers; that does not activate profiles
in any startup command. The project name is validated without `--project-name`
masking it, while actual operations retain explicit project `ops-board`.

Before rendering, safe YAML source parsing permits only selected service
declarations and inert `x-` metadata. Top-level project/resources/imports and
service `extends`/`env_file`/`label_file` are refused, even if unused or unchanged:
Compose drops unused volume/network definitions from its resolved output.
Duplicate mapping keys are rejected; Compose `!override`/`!reset` tags are parsed
as data and their effective behavior still passes the resolved contract guard.

Layers cannot add/remove services, alter unselected services, change ports,
container/network/volume/secret identities, or introduce host networking,
privilege, devices or external volumes. Selected image/arguments/env/health/profile
changes are deliberate stage inputs, not acceptance. Named repository credential
keys retain exact presence/value; explicit credentials also match the live runtime
for overlay operations. Existing secret/storage provider identities cannot rotate;
absent SigNoz provider flags may only become the approved sqlite/clickhouse/jwt
values. Plane storage endpoint addresses may change, not embedded credentials.
Entrypoints and SigNoz server arguments retain the owned JWT launcher contract.
Only job retry policy,
preserved Plane broker hostname, and removal of existing ClickHouse dependencies
have reviewed lifecycle exceptions. Inert Compose `x-` metadata is not a resource.
Existing persistent mounts remain required. Only collector config targets
`/etc/otel-collector-config.yaml` and `/etc/opamp-config.yaml` permit scoped
maintenance read-only config binds with unchanged target/options (a writable
baseline config bind may become read-only). Prepared SigNoz also permits one new
read-only ClickHouse bind, from `stacks/signoz/maintenance/metric-log-merges.xml`
to `/etc/clickhouse-server/config.d/metric-log-merges.xml`, under
[ADR 013](../../docs/adr/013-bounded-clickhouse-diagnostic-merges.md). It cannot
replace an existing mount or accept an arbitrary source/target. Baseline config
and storage identities remain unchanged. Secret and launcher mounts cannot be
replaced or shadowed. Explicit Rabbit hostname/nodename/longname must match the
actual selected broker, even without layers; captured node identity stays frozen
through the invocation. Actual mount/label/sharing/job/state
and image guards remain in force. This is not a raw-Docker backup bypass.

```bash
./scripts/status.sh --stack signoz --context root \
  --compose-overlay stacks/signoz/maintenance/prepared.yaml \
  --compose-overlay stacks/signoz/maintenance/stop-0.131.1.yaml --dry-run
```

That example validates candidate source only, without the daemon. Actual status,
verify and backup must receive **all current applied layers**, not the next
unapplied candidate. Stage dry-runs require the Compose CLI and valid source/env;
they do not prove live identities/readiness. Generic update retains all existing
guards and never installs a stage, executes jobs, or resumes stopped writers.

## Generic Update Is Not a Migration

`update-stack.sh` pulls only selected long-running service images. It refuses
changed image IDs, stopped writers, and active/failed migration jobs, then uses
`up --no-deps --no-recreate --pull never` without initialization/migrator jobs.
Existing containers are retained; pending config changes are not applied. This
deliberately replaces the old unsafe blanket pull/up behavior. `--remove-orphans`
is not supported. Actual release upgrades/config changes require a reviewed stage
with checkpoints and explicit migration/writer sequencing; do not bypass these
guards to resume an interrupted migration.

## Cold Checkpoint

Choose an already-local immutable helper image containing `sh`, `tar`, and `du`.
The currently deployed ClickHouse image is a candidate; the script checks tools
before stopping anything. It does not pull helpers or rely on mutable helper tags.

```bash
archive_image="$(docker image inspect clickhouse/clickhouse-server:25.5.6 --format '{{.Id}}')"
./scripts/backup-stack.sh --stack plane --context root \
  --archive-image "$archive_image" --dry-run
./scripts/backup-stack.sh --stack plane --context root \
  --archive-image "$archive_image"
```

Destination defaults to `OPS_BOARD_BACKUP_ROOT` from environment/root `.env`, then
`~/ops-board-backups`; override with `--backup-root DIR`. Destinations must be
outside the checkout. Bundles have unique names, directories mode 700, and files
mode 600; neither checkpoints nor rollback images are pruned. Bundle contents are
secret-bearing. Do not commit, paste, or expose them through a web server.

Before stopping, the tool validates resource ownership, local configuration,
helper availability, and disk capacity (2x estimated allocated state/image/config
size plus 512 MiB). Sparse files or concurrent growth can exceed the estimate;
out-of-space failures retain an incomplete bundle and run backup-only cleanup.
Matched immutable images are exported before quiescing, then container/config
identities and running states are revalidated. All selected running services are
stopped gracefully in writer-before-storage
order. Nonzero/missing exit codes, OOM, or a service still running refuse the
checkpoint by default. The sole exception is the exact-image, invocation-bound
ZooKeeper TERM contract in [ADR 012](../../docs/adr/012-evidence-bound-zookeeper-checkpoints.md):
healthy PID-1 JVM, durable defaults, cleanly stopped scoped clients, standalone
quiescence, managed stop under 60 seconds and matching identity/timing evidence.
It retains actual exit 143; it does not accept unexplained or pre-stopped 143.
Other images, topologies and architectures retain the strict default. Failed
initialization or migration must be resolved separately; an active job blocks
backup and any present job must be nonrunning, `exited`, exit zero/no OOM.
`created` with exit zero has never run and is refused by backup/verify/update;
missing one-shot containers retain the existing optional contract. Pre-stopped
long-running state must have exit zero/no OOM before helper/image/export/bundle work;
the same state/job gate is rechecked before stopping and before cold archival.
Expected previously stopped services are not started by backup cleanup.

Every named and declared image-created anonymous volume attached to scoped
containers is captured. For example, Plane MinIO includes `plane_uploads` at
`/export` and its anonymous `/data` mount. Additional persistent mount types,
outside-checkout binds/secrets, symlink configuration, non-local volume drivers,
or shared outside consumers are refused rather than silently omitted.

The bundle contains:

- `config.tar`: Compose files, exact ordered raw layer inputs, examples, actual env files, secrets, and all scoped
  repository-local bind sources, including runtime/custom config.
- `compose.json` and `containers.json`: restricted resolved configuration and
  actual runtime image/env/command/hostname/mount identities.
- `images.tar`: matched pre-checkpoint images plus the immutable archive helper.
- `volume-N.tar`: complete cold filesystems, preserving ownership/modes, internal
  metadata such as `.minio.sys`, SQLite/MariaDB/PostgreSQL/ClickHouse/ZooKeeper state,
  persisted Valkey data, and RabbitMQ cookie/message storage.
- Plane checkpoints additionally record RabbitMQ diagnostic node status and
  definitions when the broker is running. An already stopped broker is recorded
  offline with actual hostname/State, optional configured nodename, explicit
  unavailable diagnostic paths and mandatory isolated full-state verification.
  Complete cold RabbitMQ volume state preserves definitions/messages/cookie;
  verify these and export definitions after isolated matched-image startup.
  RabbitMQ and other long-lived services require exit zero/no OOM; the guarded
  ZooKeeper exception above never applies to the broker.
  Definitions do not replace message storage. The observed HP-15
  node is `rabbit@3bb3429c1ce3` (OTP 26); refresh at the checkpoint, and preserve
  its hostname/node configuration with its original data when recreating it.
- `manifest.json`: completion status, UTC time, revision, source scope/daemon/
  architecture, image IDs/digests, volume metadata, exact resume set, SHA-256 and
  byte counts for every artifact. Checksums detect corruption, not malicious
  replacement of the manifest and artifacts; trust only restricted local bundles.
- `cleanup.json`: complete prior running IDs, this invocation's stop attempts,
  unsettled stops, resume failures, and final readiness outcome, including failures.
- When the known ZooKeeper runtime is present, `shutdown-intent.json` records its
  sanitized pre-stop identity/quiescence and `shutdown-evidence.json` the completed
  managed stop, actual exit code and bounded duration. Both are checksummed with
  the bundle. Evidence from a prior invocation cannot waive a pre-stopped failure.

`manifest.json` additionally audits ordered `compose_inputs` (repository-relative
path plus SHA-256, root first) and `compose_overlays`. Inputs are rechecked during
capture and against the archived bytes; restore verifies this audit when present.
Resolved stage `compose.json` and actual Docker `containers.json` remain the
runtime authorities. Restore never consults current overlay files: captured bind
paths are remapped into the fresh private config tree with matched old images.

State archives allow contained relative links, including ClickHouse Atomic
`data/signoz_traces/signoz_index_v3 -> ../../store/<prefix>/<uuid>` and metadata
links. Link chains are resolved in filesystem order within the archive root;
absolute/escaping targets, cycles, duplicate paths and archive writes through a
link remain refused. This is a general containment contract, not a ClickHouse bypass.

Only this backup invocation's stop-attempted originally-running container IDs are
restarted in reverse order on success or failure. An interrupted Docker client
does not certify daemon stop completion: cleanup reissues/waits for outstanding
stops before any restart. Unsettled stops block all resumes. Final readiness checks
cover the full original running cohort even on the error path, and cleanup failure
is nonzero with retained evidence; later migration stages must not proceed.
Failed helpers are removed by their unique
names; failed resume is reported. An incomplete bundle is not restorable. SIGINT/
SIGTERM invoke cleanup; SIGKILL, host failure, or Docker daemon loss cannot. Inspect
status and the restricted checkpoint metadata after such failures. Never use the
backup resume logic as recovery from failed migrations.

The maintenance lock defaults to `~/.local/state/ops-board/maintenance.lock`, shared
by these mutation commands irrespective of group or backup destination. All
operators using the same daemon must configure the same `OPS_BOARD_MAINTENANCE_LOCK`
path (and appropriate access) when using multiple accounts. It is advisory: raw
Docker commands and other checkouts that ignore the lock can still race. Do not
unlink held lock files. `--timeout-sec` bounds each subprocess/readiness wait;
default 600, allowed 70..3600 seconds. Adjust for image exports on slower storage.

## Stage a Fresh Isolated Restore

Use the exact bundle path printed by backup; choose new target/project names:

```bash
./scripts/restore-stack.sh --stack plane --context root \
  --backup "$HOME/ops-board-backups/plane-<checkpoint>" \
  --target "$HOME/ops-board-rehearsals/plane-<checkpoint>" \
  --project ops-board-rehearsal-plane-a --dry-run
```

Dry-run verifies completion, all checksums/tar safety, source scope/context,
architecture, and fresh target/resource identities. It runs read-only Docker
queries (and acquires the advisory maintenance lock); it neither extracts files
nor creates volumes/containers. Other dry-runs print plans only, without querying
Docker, except overlay dry-runs perform daemon-free source schema/contract renders,
and therefore are not live preflight acceptance.

Repeat without `--dry-run` to stage. Restore extracts configuration into the new
private target, imports matched images, creates uniquely prefixed fresh volumes,
and writes `compose.json` plus `recovery.json`. It starts no containers. Wrong
scope, existing target/volumes/project resources, traversal, unsafe links, checksum
mismatch, or unavailable/incompatible images are refused. Failed staging removes
only volumes created by that invocation, and records any cleanup failure in the
new target's `failure.json`; source/live volumes and backups are never removed.

Generated Compose uses the recorded image IDs and runtime environment/commands,
not current version defaults. It preserves RabbitMQ's original hostname inside
the isolated network. It drops production fixed names, published ports, external
networks, host mappings, privileged/device settings, and automatic restarts.
All traffic remains in a single internal bridge with `isolated` IPv4/IPv6 gateway
modes. Plain `internal` alone can still expose host bridge services; see
[Docker gateway modes](https://docs.docker.com/engine/network/port-publishing/#gateway-modes).
Do not remove the isolated gateway settings to make startup succeed. Validate
Engine support and denied host/external access before starting restored apps.

Migrators, initialization jobs, workers and beat require the `manual-jobs` profile
and are not automatically run. Start infrastructure/services explicitly with
`--no-deps --pull never`; do not run blanket `up` as a rehearsal shortcut:

```bash
docker compose -f "$HOME/ops-board-rehearsals/plane-<checkpoint>/compose.json" \
  up -d --no-deps --pull never plane-db plane-redis plane-mq plane-minio
```

Proceed with the existing release's startup/health order and use `docker exec` or
an explicitly isolated test client for checks. Browser access needs a separately
reviewed loopback proxy/binding that does not grant restored writers outbound or
host-network access. With isolated gateway mode there is no host-facing bridge
address. Record actual login, old/new attachment, workspace, monitor/history and
telemetry checks; `recovery.json` deliberately leaves application acceptance false.
Rehearse one state family at a time to fit HP-15 memory. Local checkpointing is
upgrade protection, not off-host disaster recovery.

## Checks

```bash
bash scripts/tests/test-linux-operator-scripts.sh
python3 -m unittest discover -s scripts/tests -p 'test_maintenance*.py' -v
git diff --check
```

Mocked workflow tests are not evidence of successful Linux cold restart, archive
tool fidelity, Docker network isolation, or application restoration. Those live
gates remain required before any stateful upgrade. No automatic in-place restore
or rollback after new writes is provided.
