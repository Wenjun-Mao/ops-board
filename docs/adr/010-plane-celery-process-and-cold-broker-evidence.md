# 010. Plane Celery Process and Cold Broker Evidence

## Status

Accepted. HP-15 baseline worker/beat recreation and ordinary Docker stops were
verified on October 8 UTC without a version change. Full-family restoration and
release-specific application acceptance remain separate runtime gates.

## Context

The live v1.3.1 Plane checkpoint stopped at beat-worker: its shell was PID 1,
Celery was a child, and Docker killed it after the existing 60-second TERM window
(exit 137). Database/broker stops had not started; cleanup restored scoped health.
Official v1.3.1 and v1.4.2 worker/beat scripts both wait for DB/migrations and then
start Celery without `exec`. API already executes Gunicorn after substantial setup.
During the one-time installation, a verified direct-child TERM exited zero but
Docker's `always` policy immediately restarted the old container. A stopped-state
timeout alone therefore did not establish a hung child. Recording then temporarily
disabling only those old restart policies allowed clean warm shutdown; recreated
containers restored the original policies from Compose. This transition is not
part of the maintenance CLI or an ongoing shutdown mechanism.

Separately, backup tried live Rabbit diagnostics even when the caller had already
stopped the entire family to hold writers through a final migration checkpoint.
Offline state is authoritative; inability to execute a diagnostic is not evidence
that the complete stopped message store cannot be captured.

## Decision

Worker and beat use a tiny repository-owned Bash launcher via a read-only bind,
preserving `python manage.py wait_for_db`, `python manage.py wait_for_migrations`
and exact upstream `celery -A plane ROLE -l info` arguments. The final command uses
`exec`, so Celery becomes PID 1 and handles Docker TERM directly. Only `worker`
and `beat` are accepted roles. During both waits, TERM/INT is forwarded only to
the owned initializer and the child is reaped; interrupted initialization never
starts Celery. Cancellation waits at most 50 polling intervals of 0.1 seconds,
then kills/reaps an unresponsive child and exits 137 (still refused as unclean).
Normal TERM/INT cancellation exits 143/130; failed waits retain their exit status.
No image rebuild, upstream file replacement, API
setup duplication, new environment values or migrator change. API/migrator keep
their official launch contracts. The bind is captured in matched config backups.

Running brokers retain live status/definitions capture. Already stopped brokers
use recorded hostname, optional configured nodename and State, with explicit null
diagnostic/export paths and an unavailable reason. A uniquely captured complete
`/var/lib/rabbitmq` volume is mandatory; all other mounts remain captured by the
existing deployment contract. Full cold archives contain definitions/messages/
cookie; a definitions export is supplementary, never a substitute for state.
Completion requires cold archive capture/checksums, not a claimed offline probe.
Metadata requires booting matched images/state in isolation and verifying node,
cookie, permissions, queues/messages and exported definitions before acceptance.

Already stopped and newly stopped containers require exit zero/no OOM; all
nonzero exits, including 1/2 as well as 137, refuse checkpoint capture.
Preflight refuses pre-stopped unclean long-running services and inactive failed
one-shot jobs before helper/image/export/bundle work; present completed jobs must
be nonrunning with Status `exited`, exit zero and no OOM. Backup, passive verify
and generic update share this completion predicate; `created` with exit zero is
not a successful run. Missing one-shot containers retain the optional contract.
Revalidation after image export and before cold capture
retains the same gate. These jobs are never restarted as checkpoint cleanup.
No backup-specific Celery PID signaling, increased grace timeout, unclean-stop
tolerance, broker restart for metadata, omitted mounts, or automatic migration
rollback/resume is introduced.

## Alternatives and Consequences

- Increasing the timeout or accepting 137 leaves the TERM delivery contract
  broken and cannot certify a clean checkpoint; rejected.
- Docker exec signaling a discovered child PID couples backup to one app process
  tree and loses ordinary Docker stop semantics; rejected.
- Copying API setup into a new launcher risks dropping registration/config/bucket/
  cache/static steps; rejected because its official final command already execs.
- Existing worker/beat containers require scoped recreation with unchanged image
  IDs and credentials before the fix reaches runtime. Coordinate with the manager.
- Offline capture loses optional live diagnostics, honestly recorded. Real
  isolated full-state verification is still required, not inferred from archives.

## Guardrails

Real-process tests prove exact initialization order, exec PID replacement and
TERM handling, TERM/INT during each blocking initializer, child reaping, bounded
unclean cancellation, unchanged arguments/secrets, initialization failure exit, and role
refusal. Compose tests constrain read-only binds to worker/beat and preserve API/
migrator commands and baseline images. Checkpoint tests retain all volumes and
launcher bytes, empty resume sets, unavailable offline audit, running diagnostics,
and wrong/missing state-volume or unclean-stop refusal. These tests are not a
Docker PID-namespace stop or application recovery certification.

HP-15 runtime evidence now establishes unchanged backend image IDs, both Celery
roles owning PID 1, ordinary 60-second Docker stops exiting zero without OOM, and
restored `always` policies. The pre-installation complete cold checkpoint captured
all 11 volumes with an empty resume set. Retain matched old launch/config bytes for
restoration; do not apply this operational result to untested future releases.
