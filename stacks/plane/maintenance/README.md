# Plane Staged Release

Prepared configuration only. No live deployment, compatibility acceptance, or
storage decision is certified here. Start with [release.json](release.json) and
the [maintenance foundation](../../../scripts/maintenance/README.md).

## Inputs and Adaptation

Official Plane v1.4.2 [Compose asset](https://github.com/makeplane/plane/releases/download/v1.4.2/docker-compose.yml)
and [variables asset](https://github.com/makeplane/plane/releases/download/v1.4.2/variables.env)
were downloaded and compared on 2026-10-07. SHA-256 values are in the manifest;
retain the exact downloaded bytes in restricted release evidence. These are
locally computed provenance checksums, not upstream signatures.

Compared with the repository baseline, upstream changes app tags to v1.4.2,
removes `SECRET_KEY`/`LIVE_SERVER_SECRET_KEY` fallbacks, uses `DEBUG`, and replaces
original MinIO with August PGSTY MinIO. Its variables file uses mutable `stable`,
default passwords, and placeholder secrets; do not install it over existing env.
The prepared overlay instead requires existing secrets/credential URLs, retains
the repository's `PLANE_DEBUG` mapping, ports, URLs, named volumes and commands,
and passes the variables asset's authentication rate limit to backend services.
Worker/beat inherit the [exec launcher](../lifecycle/README.md); API and migrator
remain official. Verify graceful runtime stops before the next cold checkpoint.
September Silo is a separate **unaccepted** stage, not bundled with the app.

Baseline Compose/example defaults remain v1.3.1, PostgreSQL 15.7, Valkey 7.2.11,
RabbitMQ 3.13.6 and the unchanged original Quay MinIO bytes pinned at
`quay.io/minio/minio@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e`.
Manager-supplied HP evidence records RELEASE.2025-09-07 and local image ID
`sha256:69b2ec208575b69597784255eec6fa6a2985ee9e1a47f4411a51f7f5fdd193a9`.
This reproducibility correction is not storage replacement acceptance or a
recreation instruction. Keep existing ignored env; the manager selectively
converges its pin without recreation. Refresh actual IDs before any change.
Independent baseline variables
allow accepted pins to converge later; none automatically activates a target.
Never regenerate env, rotate secrets, or change another stack for these stages.

## Resolve and Freeze Each Stage

On HP-15, use the retained checkout and project, not standalone `plane`:

```bash
cd ~/projects/ops-board
umask 077
dc=(docker compose --env-file .env --env-file stacks/plane/plane.env -f compose.yaml)
accepted=() # append only already-accepted overlays, in stage order
stage=("${dc[@]}" "${accepted[@]}" -f stacks/plane/maintenance/stage3-db.yaml)
```

The second env file supplies existing Plane values to root overrides; shell
variables override env files. Clear unintended `APP_RELEASE`, `PLANE_*` and
`COMPOSE_*` shell overrides, then set only the manifest's intended target values.
Each overlay changes only its service family; retain accepted overlays in all
later commands. Example after stage 3 acceptance:

```bash
accepted=(-f stacks/plane/maintenance/stage3-db.yaml \
          -f stacks/plane/maintenance/stage3-cache.yaml)
stage=("${dc[@]}" "${accepted[@]}" -f stacks/plane/maintenance/stage4-app.yaml)
```

Do not substitute a stage-only Compose file or drop accepted layers. Freeze the
resolved config (with `--profile '*' config --format json`), source/asset hashes,
actual image IDs/digests, architecture, commands, mounts, ports and hostname in
restricted evidence outside the repo; resolved config contains secrets. Compare
with actual live containers, not just baseline source. Pre-pull approved images
separately and inspect them; all mutation commands below use `--pull never`.
The manifest records candidates/observations, not verified local image IDs.

Generic `update-stack.sh` intentionally refuses changed images and stopped
writers. Do not weaken it or use it for a stage. Use explicit scoped
`up --no-deps --pull never SERVICE...`. No orphan removal, blanket `up`, volume
deletion, or automatic migration/rollback. Never operate concurrently with the
manager; raw Docker commands do not acquire the foundation's advisory lock.
Use the shared lock for raw mutation blocks, releasing it before the backup CLI
acquires the same lock itself; keep exclusive operator ownership across blocks.

## Cold Quiesce and Checkpoint Gate

Every stage needs matched prior images/config and a real isolated restore test.
Record the exact prior running IDs; restore only that set after acceptance.

1. Close request ingress and stop `proxy`, `web`, `space`, `admin`, `live`, `api`
   and `beat-worker`. Drain safe outstanding tasks with existing workers; then
   stop workers gracefully. Check Rabbit ready/unacknowledged counts again. Never
   discard messages or use force-stop as proof of a clean checkpoint.
2. Require migrator inactive and its prior run successful. Stop storage/cache/DB
   and broker cleanly, check stop exits/OOM state, and record all mounts, Rabbit
   identity/cookie/definitions/flags and any external key material beforehand.
3. Back up the **already stopped family** for the final coherent checkpoint.
   `backup-stack.sh` always resumes containers it stopped, on success or failure;
   taking an ordinary running-family backup is not a held-writer checkpoint.
   Verify `resume_container_ids` is empty and every writer remains stopped.
4. No resumed writers between final checkpoint and schema/storage migration.
   If any write occurs, invalidate the final checkpoint and repeat quiescence.

Already stopped Rabbit brokers are captured offline: manifest records actual
hostname/State, optional configured nodename and explicit unavailable live audits.
Complete cold volumes preserve definitions/messages/cookie; no broker is resumed
for metadata. With matched images on isolated restore, verify these and export
definitions before accepting recovery. Running brokers still get live audits.
Every pre-stopped or newly stopped long-lived service requires exit zero/no OOM;
any nonzero stop (including exit 1/2) refuses the checkpoint.

```bash
# Baseline checkpoint, before any release layers are applied:
./scripts/backup-stack.sh --stack plane --context root --archive-image "$archive_image"

# Example current state AFTER separate DB/cache acceptance, BEFORE app stage:
current_layers=(--compose-overlay stacks/plane/maintenance/stage3-db.yaml \
                --compose-overlay stacks/plane/maintenance/stage3-cache.yaml)
./scripts/status.sh --stack plane --context root "${current_layers[@]}"
./scripts/backup-stack.sh --stack plane --context root \
  "${current_layers[@]}" --archive-image "$archive_image"
```

Maintain `current_layers` explicitly from actual installed/accepted state in
stage order; include every applied app/storage/broker layer when present. Do not
infer it from the next candidate `stage` array or put unapplied layers into a
prior-state checkpoint. After each accepted stage, capture a new held-writer
checkpoint with **all** its current layers before proceeding. Keep corresponding
target variables at current values (especially Rabbit bridge versus final).
Use the same array for `verify-stack.sh` after explicitly starting the accepted
cohort; verify does not start held writers. Ordered layer bytes and stage bind
config are captured by the foundation; isolated restore needs no current source
layers and starts no jobs/writers. Empty `resume_container_ids` and real matched
restore/application gates remain mandatory, not inferred from a source render.

Retain the complete bundle, old images and failed/new state. At each stage, start
only infrastructure needed for checks. Do not reopen ingress or producers until
the manager accepts migration/readiness gates. Real acceptance writes are explicit
and invalidate a no-loss return to the checkpoint; never automatically roll back
or resume after migration failure. Restore old **data/config/images together**
into isolated resources, then review any live recovery and subsequent-write loss.

## Stage 3: PostgreSQL and Valkey Separately

- `stage3-db.yaml`: PostgreSQL **15.19-alpine**, same major 15. Review every patch
  note since 15.7, index/collation follow-ups, and test copied data before live.
- Pinned container images can change ICU/libc behavior even within one database
  major. Audit actual collation versions, database defaults, dependencies, columns
  and indexes before proceeding. A mismatch fails the stage until its required
  rebuild or explicitly proved unused-metadata repair is complete; version refresh
  alone is not index repair. Retain complete before/after catalog proof and recheck
  after restart and cold restoration. See the
  [database-only kickoff](../../../docs/monitoring/maintenance-receipts/2026-10-11-plane-postgresql.md)
  and [PostgreSQL's guidance](https://www.postgresql.org/docs/15/sql-altercollation.html).
  Its unused-collation finding is not a waiver for a different/live catalog.
  A null libc version is not proof of unchanged sorting; application ordering
  behavior still needs verification.
- Quiesce/checkpoint; select only DB, then verify readiness and required repairs:
  `"${stage[@]}" up -d --no-deps --pull never plane-db`.
- Explicitly start required unchanged infrastructure and the prior app cohort,
  excluding migrator, only when DB checks pass. Verify existing login/workspace,
  queries and data counts. Accept DB before advancing.
- `stage3-cache.yaml`: take a **new** checkpoint; target **7.2.14-alpine** within
  Valkey 7.2. Select only `plane-redis` with the same scoped `up` flags. Verify
  persisted state, sessions/cache, pub/sub and live collaboration, not only PING.
- Keep unrelated stacks running. Same-major upgrades still require matched-state
  recovery and manager acceptance, not automatic downgrade on target-written data.

## Stage 4: Application Set and Explicit Schema Job

Keep accepted DB/cache pins and original storage/broker. Every application image,
including proxy and migrator, must resolve to **v1.4.2** via the single
`PLANE_APP_TARGET_RELEASE`; do not stage independently versioned app containers.
All existing credential values must be nonempty. Missing values fail config
resolution; nonempty placeholders are not evidence of valid credentials.

After the final held-writer checkpoint, explicitly start infrastructure only.
Run the profiled one-shot migrator with a bounded wait and require exit zero:

```bash
timeout 600 "${stage[@]}" --profile manual-jobs up --no-deps --pull never \
  --abort-on-container-exit --exit-code-from migrator migrator
```

Check the actual container exit and migration logs too, especially on timeout.
The target migrator has no restart retry and is excluded from default service
selection. Never start app writers after a failed/unfinished job. After success:

```bash
"${stage[@]}" up -d --no-deps --pull never api worker web space admin live proxy
# Start scheduling only after an explicitly safe task is consumed/acknowledged:
"${stage[@]}" up -d --no-deps --pull never beat-worker
```

Restore only previously running replicas. Verify old login/workspace, create/edit
test records, safe background work, live updates, old attachment downloads and
new uploads. Clean up only test-owned records. A tag reversal is not schema rollback.

## Stage 5: Copied Full Storage State First

Target **pgsty/silo:RELEASE.2026-09-16T00-00-00Z**. Verify registry digest against
the manifest and platform-specific local image identity. The image entrypoint
`/usr/bin/docker-entrypoint.sh` dispatches `silo` (the image default Cmd is `silo`);
there is no `minio` executable alias. The stage command remains
`server /export --console-address :9090`, never `minio server ...`.
Keep volume/endpoint/bucket names and actual credentials;
there is no new console/public port or optional storage mode.

Rehearse on a separate full cold copy of **every** storage mount, including
`.minio.sys` metadata/IAM and any anonymous image volume. Never run old and new
servers against the same volume concurrently. Compare object references/keys,
counts, byte totals, metadata/content types and content hashes; multipart ETags
are not universal hashes. Verify users/policies/encryption keys and denied access.
Test real Plane/proxy presigned POST/GET, uploads/downloads/deletes, spaces/non-ASCII
names, avatars/covers/attachments and used copy/multipart operations, then restart
and repeat. Startup/health alone is insufficient. Review release security/TLS/IAM
and old-format rollback constraints before accepting any backend decision.

Only after copied-state/behavior acceptance: quiesce again, take the final coherent
checkpoint, apply `stage5-storage.yaml` to **plane-minio only**, and rerun the same
set. Retain old full state and image. ADR 008 remains unaccepted/uncreated here;
failed compatibility stops this stage, not a silent alternative engine selection.

## Stage 6: Rabbit Bridge, Flags, Preserved Node

Refresh the observed hostname **3bb3429c1ce3** and node
**rabbit@3bb3429c1ce3**. Set `PLANE_RABBITMQ_HOSTNAME` to the actual existing host
**before** broker recreation, and preserve cookie, vhost, users, permissions,
bindings, queue types, messages and flags. Absent optional hostname keeps baseline
Docker behavior, not existing-node preservation on recreation. Never invent a
stable node for old state. Fresh-deployment node naming is a separate future decision.
Maintenance refuses an explicit hostname/nodename that differs from the actual
selected broker and keeps the captured node identity fixed through the invocation.

Follow [RabbitMQ's supported path](https://www.rabbitmq.com/docs/upgrade): review
3.13 patch prerequisites, enable required stable flags while still on the supported
old release, review Khepri/Erlang exceptions, and rehearse the complete sequence.
Stop producers/scheduling, drain safe work, stop consumers and checkpoint messages
with definitions; definitions alone are insufficient. Empty queue observations
are not permission to erase message state. If work cannot drain, stop and design a
message-preserving migration. Never enable experimental flags.

```bash
export PLANE_RABBITMQ_HOSTNAME=3bb3429c1ce3 # only after refreshed identity agrees
export PLANE_RABBITMQ_TARGET_VERSION=4.2.9-management-alpine
# stage contains accepted earlier layers plus stage6-rabbit.yaml
"${stage[@]}" up -d --no-deps --pull never plane-mq
```

Require correct node, healthy diagnostics, no alarms, queue/message/permission
recovery and stable required feature flags before accepting the bridge. Take a
separate checkpoint before setting **4.3.6-management-alpine** and repeating the
scoped broker upgrade; never jump 3.13 directly to 4.3. Demonstrate real Celery
publish/consume/ack before normal producers/scheduling resume. Feature flags/data
formats can prevent downgrade: use old matched checkpoint recovery, accounting
for subsequent jobs, never old images on migrated broker state.

## Source Checks and Remaining Acceptance

```bash
python3 -m unittest discover -s scripts/tests -p 'test_plane_release.py' -v
bash scripts/tests/test-linux-operator-scripts.sh
git diff --check
```

Tests render root include/overrides with the actual Compose CLI and dummy env;
no daemon or live data is accessed. Missing Compose skips rendering tests and must
be reported as a verification gap. Manager-owned gates remain: graceful launcher
stops and real full stopped-family checkpoint/restore, Plane access/data, PostgreSQL follow-ups, cache
behavior, app image availability/migration, full-copy Silo compatibility/security,
Rabbit flags/node/Erlang transitions and real application/job acceptance. After
all gates, selectively reconcile actual env/default pins and retain the strict app
contract; removing overlays without that promotion would revert accepted images.
