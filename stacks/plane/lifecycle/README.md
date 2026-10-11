# Celery Launch Contract

`launch-celery.sh` replaces only the worker/beat shell launch boundary. It keeps
the official waits and `celery -A plane worker|beat -l info` flags, then `exec`s
Celery to receive Docker's PID 1 TERM. API and migrator remain official/unmodified.
Compose mounts this one file read-only; no image rebuild or credentials change.
During either readiness wait, the launcher forwards TERM/INT only to its owned
Python child and reaps it without starting Celery. It allows 50 cancellation polls
at 0.1 seconds, then kills/reaps an unresponsive child and exits 137, which remains
an unclean-stop refusal. Responsive cancellation exits 143/130; wait failures keep
their original exit. This bound does not shorten normal dependency readiness waits.

Source reviewed against official [v1.3.1 worker](https://raw.githubusercontent.com/makeplane/plane/v1.3.1/apps/api/bin/docker-entrypoint-worker.sh),
[v1.3.1 beat](https://raw.githubusercontent.com/makeplane/plane/v1.3.1/apps/api/bin/docker-entrypoint-beat.sh),
[v1.4.2 worker](https://raw.githubusercontent.com/makeplane/plane/v1.4.2/apps/api/bin/docker-entrypoint-worker.sh),
[v1.4.2 beat](https://raw.githubusercontent.com/makeplane/plane/v1.4.2/apps/api/bin/docker-entrypoint-beat.sh),
and [v1.4.2 API](https://raw.githubusercontent.com/makeplane/plane/v1.4.2/apps/api/bin/docker-entrypoint-api.sh).
Re-review initialization and flags before accepting any other app release.

## One-Time Installation Mitigation

This one-time transition was verified on HP-15's unchanged v1.3.1 backend on
October 8 UTC. It is a temporary installation transition for the known broken shell-PID-1 containers,
**not a backup hook or a permanent shutdown path**. Do not encode child-PID
signaling into maintenance CLI. Source tests are not HP-15 runtime proof.

1. Freeze current immutable backend image IDs, launcher/config/credentials and
   service identities. Close ingress and API producers. Verify the old beat's
   direct Celery child and namespace/PID mapping from the actual process tree;
   record its original restart policy and temporarily disable restart only on that
   old container before delivering TERM. Otherwise `always` can immediately restart
   a cleanly exited child/container. Do not reuse observed PIDs later.
2. Drain safe work, then verify and TERM only each old worker's direct Celery
   child, recording/disabling only its old restart policy first. Bound each warm
   stop by the existing 60-second stop window; require
   child completion, old shell/container exit, no OOM and no exit 137. Preserve
   queue/message state and record exits. No Docker SIGKILL, forced cleanup or
   acceptance of an unclean stop. If identity/drain/clean exit cannot be proven,
   halt installation rather than expand this workaround or restart producers.
3. With producers held, install the read-only launcher and recreate only
   `worker beat-worker` using explicit unchanged-image-ID scope and
   `up -d --no-deps --pull never`. No app/dependency upgrades or implicit migrator.
4. Verify restored original Compose restart policies, new Celery PID 1, both initialization waits and ordinary Docker TERM
   stop/clean exit before intended scoped resume. This is the durable follow-up
   gate that retires the mitigation; all later backups use ordinary Docker stop.
   Restore scheduling/ingress only after the manager accepts readiness/job checks.

No temporary PID-signaling or restart-policy exception remains in the source path.
Both recreated roles restored `always`, owned PID 1, and exited zero under ordinary
Docker stop. The cold checkpoint captured all 11 volumes with no resumed writers;
full restore/application acceptance remains required before version upgrades.

## Runtime Acceptance

Manager-owned runtime gate: freeze actual old image IDs/config/credentials and
script evidence; deploy source in the existing root checkout; recreate only
`worker beat-worker` with `up -d --no-deps --pull never` after resolving and
confirming unchanged images. Verify Celery is PID 1 and healthy, then test a
bounded ordinary Docker stop, clean exit/no OOM and intended scoped resume.
Generic update deliberately does not recreate these containers. Do not use
`--force-recreate` on unrelated services, run implicit migration, or advance
images as part of this launch correction. Fresh stopped-family backups stay
stopped; restoring old config must also restore its matched launcher bytes.

Tests use real exec/signal processes and dummy commands, plus Compose rendering:

```bash
python3 -m unittest discover -s scripts/tests -p 'test_plane*.py' -v
```

They prove replacement PID/TERM delivery and interrupted-initializer reaping, but
do not run in Docker PID namespaces.
See [ADR 010](../../../docs/adr/010-plane-celery-process-and-cold-broker-evidence.md).
