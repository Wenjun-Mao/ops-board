# 007. Scoped Maintenance and Recovery

## Status

Accepted for the source/tooling contract. Real HP-15 cold checkpoints and isolated
baseline restores are recorded in the [execution receipts](../monitoring/maintenance-receipts/2026-10-07.md).
Plane/SigNoz restored normal login and every stateful release stage remain separate
deployment gates, not outcomes certified by this decision.

## Context

HP-15 runs all services under root Compose project `ops-board`, but old `--stack`
wrappers selected standalone projects. Fixed container/volume names make that
silently changed identity unsafe. Existing PowerShell backups preserve sanitized
repository configuration, not runtime data, ignored environments or credentials.
Cold state contains anonymous mounts and broker node identity as well as named
volumes; image tags and database formats are not interchangeable recovery inputs.

## Decision

Maintenance uses explicit `root` (default service groups in `ops-board`) or
`standalone` deployment context, backed by one shared Python standard-library
contract. Live checkout/project labels, fixed names, mounts/volume ownership and
outside consumers are verified before mutation; no implicit adoption or orphan
removal. Generic pull/up does not recreate containers, change image IDs, run
migrations, or restart stopped writers. Actual migrations are separately staged.

Reviewed stages can change collector config/OpAMP binds, jobs and images while
retaining root deployment identity. Resolving only the baseline cannot capture
that source contract and falsely rejects real stage mounts. Repeatable ordered
`--compose-overlay` inputs therefore belong to shared Deployment resolution,
limited to root Plane/SigNoz maintenance files. Every cumulative prefix is
compared with baseline before mutation: unselected services, service membership,
public ports, volume/network/secret identities and security fields remain fixed.
Only selected stage image/arguments/env/health/profiles, job retries, preserved
Plane broker hostname, and removal of existing ClickHouse dependencies may vary.
Named repository credential presence/values and explicit secret/storage provider
identities cannot rotate; overlay credentials must also match live container env.
Absent approved SigNoz provider flags may become explicit. Storage endpoint address
changes cannot alter embedded credentials. Entrypoints, SigNoz server arguments,
secret/launcher binds stay fixed: only the collector YAML/OpAMP targets allow scoped
read-only config replacements with retained target/options. Strengthening writable
config to read-only is allowed. Explicit Rabbit hostname/nodename/longname must
match the actual selected broker, with or without overlays; captured node identity
cannot be recaptured during maintenance. Inert `x-` metadata is not
runtime topology. No runtime mount/label/sharing/image/job/state guard is relaxed.

Config renders include all profiles without starting them; overlay dry-runs are
daemon-free source validation, not live acceptance. Ordered relative input paths
and hashes audit exact layer bytes in `config.tar`, alongside actual resolved
stage config/runtime. Restore validates captured inputs when present and remaps
captured binds into fresh isolation, without consulting current overlay source.
Old format-1 bundles remain supported. Baseline checkpoints have no layers;
current-stage checkpoints explicitly include all applied layers, never infer the
next candidate. Generic update is still not a stage installer or recovery runner.

Compose's config output drops unused resource declarations, so resolved-only
comparison cannot reject every raw layer's resource additions. Overlay-only
source parsing therefore requires PyYAML SafeLoader, with duplicate-key rejection
and Compose tags treated as data. Only selected service definitions and inert
`x-` metadata are permitted; top-level project/resources/imports and indirect
service env/label/extends files are refused. Baseline and captured-bundle restore
remain standard-library-only; unavailable PyYAML fails closed before rendering
or mutation. Ad hoc YAML scanning and trusting pruned config output are rejected.

Linux runtime checkpoints are consistent cold snapshots of the scoped family,
including every persistent mount, actual config/env/secrets, runtime identities,
and matched immutable images. Checksum manifests and restricted external-to-repo
directories distinguish complete checkpoints from failed captures. Only backup
cleanup may restart the exact prior running-container set; migration failure has
no generic automatic resume. Locks and bounded waits are required.

Checkpoint identity compares Docker's top-level `Mounts` sorted only by
`Destination`, retaining every mount field and rejecting duplicate destinations.
Twelve manager-observed inspect probes showed MinIO/proxy mount arrays reorder
while destination mappings, images, container config and Compose config stayed
equal. Array order is not mount identity; raw ordered comparison falsely refused
a clean stopped checkpoint. No recursive/list-wide normalization is allowed:
Compose lists, container config, nested mount values and running-state guards
retain their existing strict comparisons. Missing mounts or changed fields remain
refusals. Regression tests cover permutations and adversarial identity changes;
the subsequent real Plane cold checkpoint completed. Release-specific recovery
and application acceptance still require separate evidence.

Stop intent, daemon completion and post-cleanup readiness are distinct states.
Every pre-stopped long-lived service requires exit zero/no OOM before capture.
Newly stopped services use the same default; [ADR 012](012-evidence-bound-zookeeper-checkpoints.md)
defines the sole evidence-bound, exact-image ZooKeeper TERM exception. Unexplained
143, exit 1/2, OOM and forced kills remain refusals, not clean checkpoints.
Interrupted stop clients must settle via a bounded daemon stop/wait before any
restart, not a one-time `Running` snapshot. Cleanup restarts only attempted prior
IDs, checks the complete original running cohort on both success/error paths, and
retains a restricted result report; unsettled cleanup blocks subsequent work.
Writers held stopped before invocation are never resumed, including on refusal.

Archive safety uses root containment through resolved link chains, not a ban on
relative `..` targets. ClickHouse Atomic uses these legitimate data/metadata links.
Absolute/escaping links, cycles, duplicate member paths and archive writes through
link parents remain invalid independent of member order.

Restores stage fresh isolated resources only, with matched old image/data pairs,
recorded broker identity, no public ports, no external/host bridge access, and no
automatic application/job startup. Docker internal plus isolated gateway mode is
required. Restore preparation and read-only readiness do not substitute for actual
account/data/application tests. New writes preclude an automatic lossy rollback.

Interactive recovery access may use an explicitly scoped host-loopback bridge
and SSH forwarding without publishing Docker ports or changing isolated networks.
Ordinary HTTP keepalives and WebSockets must not consume a shared SSH exec-session
quota that queues new browser connections indefinitely. Use standard SSH forwarded
TCP streams; test multiple idle connections, fresh requests, binary bodies and
half-close behavior. Retain listener/process identities for scoped cleanup, recheck
egress denial, and distinguish access failures from restored-application failures.
Before a browser handoff after startup/restart, require a successful application
API probe, not just a running container or HTTP 200 from the static frontend.
The current bridge is an ephemeral rehearsal artifact, not an automatic startup
feature of `restore-stack.sh`.

Rehearsal containers deliberately retain `restart: no`: a host reboot must not
resume unaccepted writers or completed jobs. An authorized recovery can resume
the exact existing cohort in dependency order and recreate its loopback access
after verifying identity, isolation and retained state. Record the new boot and
pre-recovery live snapshot without rewriting historical evidence. Host shutdown
is not a coordinated checkpoint; forced exits or unproved coordinator TERM
statuses remain refused even when recovery health/data queries subsequently pass.

Fresh Plane configuration takes its release from the checked-in example; Compose
fallbacks agree by regression tests. Existing env values and secrets are retained.
Kuma's already-applied 2.5.5 is pinned in source, without a deployment/restart here.

The original Plane MinIO baseline is pinned to the manager-observed Quay digest
for unchanged RELEASE.2025-09-07 bytes, not promoted to the untested Silo target.
This closes reproducibility drift only; storage compatibility acceptance remains
a separate gate and existing ignored env is not automatically rewritten.

## Alternatives and Consequences

- Keeping implicit standalone selection or blanket `up` obscures ownership and
  migration sequencing; rejected even though it is more convenient.
- Online filesystem tar or config-only backups cannot certify database/broker
  consistency; rejected. Family-scoped orderly downtime is accepted.
- In-place restoration or old binaries on upgraded volumes risks data loss and
  irreversible format changes; rejected as a default recovery interface.
- Live deployment may expose unsupported external binds, symlinks, volume
  drivers, or isolation capabilities. These block maintenance until explicitly
  designed/rehearsed; no silent partial backup or weakened isolation.
- Local backups are not host-loss recovery. Multi-user operators must share the
  advisory lock; raw Docker actions remain outside its protection.
- Raw-Docker stage backup bypasses and relaxed mount guards hide the resolved
  source mismatch; rejected. Explicit source layers preserve the shared contract.

## Guardrails

Contract tests cover scope/identity, anonymous mounts, checksums/path safety,
secret-safe failures, lock exclusion, exact backup cleanup, fresh-restore cleanup,
configuration preservation and version default agreement. Real HP-15 restore and
egress-denial/application evidence remain required for stateful release stages.
Never rotate config with `init --force`, prune recovery artifacts, or recreate
accounts as an upgrade workaround. Capture actual release-specific compatibility
and migration decisions before advancing other version pins.

Representative ClickHouse link roundtrips and adversarial link chains guard the
containment model. Interrupted-stop, settlement-timeout and error-path readiness
regressions guard the cleanup state machine; successful client termination alone
is neither a consistent checkpoint nor evidence that the original services resumed.
