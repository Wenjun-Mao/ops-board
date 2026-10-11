# 012. Evidence-Bound ZooKeeper Checkpoints

## Status

Accepted contract; native cold-capture and fresh-volume restore acceptance is
recorded separately in the maintenance receipt. No version upgrade is authorized
by this decision.

## Context

The restored SigNoz baseline's ZooKeeper returned 143 after ordinary Docker TERM
stop, without OOM. Its existing Bitnami launcher already execs Java as PID 1.
Inspection of this image's Java 11.0.20 runtime (`javap java.lang.Terminator`)
confirmed the JVM registers TERM and exits with `128 + signal`: 143 for TERM.
The failure belongs to the universal exit-zero checkpoint model, not its launcher.
[OpenJDK's Unix signal handler](https://raw.githubusercontent.com/openjdk/jdk11u/master/src/java.base/unix/classes/java/lang/Terminator.java)
corroborates the inspected bytecode. ZooKeeper's transaction log defaults to
[durable forceSync](https://raw.githubusercontent.com/apache/zookeeper/release-3.7.1/zookeeper-server/src/main/java/org/apache/zookeeper/server/persistence/FileTxnLog.java).

## Decision

Keep strict exit-zero/no-OOM checkpointing as the default. Add the named contract
`zookeeper-3.7.1-jdk11-quiesced-sigterm-v1` for service `zookeeper-1`, exclusively
for inspected Linux/amd64 image
`sha256:3ab0e8f032ab58f14ac1e929ac40305a4a464cf320bdfe4151d62d6922729ba0`.
Tags, other architectures and unverified images confer no such capability.

Require healthy running state, the original entrypoint/command, TERM stop signal,
PID-1 `QuorumPeerMain` JVM, no reduced signal handling or disabled WAL sync, and
cleanly stopped same-project clients (including SigNoz and ClickHouse). The `mntr`
probe must report the supported standalone version, zero outstanding requests
and only its own connection. Record sanitized intent before ordinary Docker stop.

An actual 143 is accepted only when that invocation completed its managed stop
in less than the 60-second kill deadline. Evidence binds container/image/project,
configuration and PID-1 hashes, startup and finish times, client IDs, quiescence,
the requested signal, completed stop and unchanged exit status. Capture it in the
checksummed bundle. Revalidate the complete cold cohort before archival.

Pre-stopped unexplained 143, stale/restarted or changed containers, active clients,
OOM, 137, other nonzero statuses, unsupported topology and incomplete evidence
remain refused. Existing stopped-state evidence cannot be reused on a later run.
All storage is archived cold; fresh matched-image/config/state restoration and
application checks remain separate mandatory gates at each upgrade stop.

The release printer no longer offers a standalone `stop-coordinator` phase.
Final held-writer captures leave the coordinator healthy for the current-layer
checkpoint to stop with evidence. Backup-only cleanup may resume that coordinator,
but must not start already held app/collector/store roles. Record the actual resume
set; requiring it always to be empty would contradict this managed-stop contract.

## Alternatives and Consequences

- Exit-143-to-zero translation would hide the real state; rejected.
- Allowing 143 for every container, image or pre-stopped service would accept
  unknown failures; rejected.
- Changing ZooKeeper or its JVM just to satisfy a numeric gate couples checkpoint
  repair to another migration; rejected.
- The isolated rehearsal has no running collector/jobs, so its client cohort is
  smaller. Live capture still checks every present scoped client and job.
- This capability is deliberately image-specific. A different coordinator image
  needs fresh process, durability and cold-restore evidence before expansion.

## Guardrails

Focused tests cover owned probes, runtime identity, durable defaults, quiescence,
failed clients, stale/malformed evidence, forced stops, sealed receipts and cleanup.
Native acceptance must preserve account/dashboard/view fingerprints, historical
ClickHouse data and coherent ZooKeeper state through cold capture and restoration
into fresh private volumes. No changed images, public ports, live writers or
credential rotation are part of this fix.
