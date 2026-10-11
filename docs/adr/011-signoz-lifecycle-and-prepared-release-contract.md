# 011. SigNoz Lifecycle and Prepared Release Contract

## Status

Accepted for the lifecycle and prepared-source contract. HP-15's unchanged
collector passed readiness-qualified ordinary Docker stop, and coordinated cold
state was restored and compared in isolation on October 8 UTC. Restored normal
account login, historical metric queries and saved dashboard/view persistence
have since passed. The copy's ZooKeeper returned 143 during ordinary Docker stop;
[ADR 012](012-evidence-bound-zookeeper-checkpoints.md) defines its inspected JVM
shutdown contract, with native cold-restore acceptance recorded in the maintenance
receipt rather than inferred from a passing restart. That baseline gate passed
on October 8 UTC with fresh-volume restoration and signed-in application queries.
The first isolated v0.131.1/v0.144.5 stop has now passed its native migration,
five-volume cold restore, existing-session/saved-query and fresh-ingestion gates;
see the [October 8 receipt](../monitoring/maintenance-receipts/2026-10-08-signoz-0.131.1.md).
The separately authorized v0.135.0/v0.144.6 copy now passes migration, semantic
dashboard conversion, authenticated API checks, coordinated full stop/restart,
five-volume cold restoration and restored normal-session/ingestion checks.
Its [stage receipt](../monitoring/maintenance-receipts/2026-10-08-signoz-0.135.0.md)
records completed technical gates and the owner's October 10 continuation approval.
The [v0.143 receipt](../monitoring/maintenance-receipts/2026-10-10-signoz-0.143.0.md)
records completed v0.143 technical gates, including fresh cold restoration and
post-restore browser/API/ingestion/AI checks and owner acceptance. The final
[v0.145 rehearsal](../monitoring/maintenance-receipts/2026-10-10-signoz-0.145.0.md)
now also passes its own five-volume cold restore and post-restore browser/API,
three-signal ingestion and AI mapping/pricing checks. The owner subsequently
accepted that candidate and separately authorized the live sequence. All four
live stops and normal-source promotion now passed; see the
[live receipt](../monitoring/maintenance-receipts/2026-10-10-signoz-live.md).
Source files alone do not authorize or certify a live release.

## Context

The HP-15 v0.125.1 checkpoint was refused before stateful stops: collector Docker
stop exhausted 60 seconds and exited 137. The manager confirmed with `docker top`
that `/bin/sh -c '... migrate sync check && ... --config=...'` was PID 1 and the
collector its child. This is a launcher signal-delivery failure, not evidence
that ClickHouse, SQLite or ZooKeeper tolerate an unclean checkpoint.

## Decision

Use a tiny owned POSIX launcher bound read-only. Preserve `migrate sync check`,
its failure status and the collector arguments, then `exec` the collector so it
owns PID 1. During the check, TERM/INT forwards only to the owned child, waits
at most five one-second intervals and reaps it. Cancellation exits 143/130;
an unresponsive child is killed/reaped and exits 137, still an unclean refusal.
No backup-side PID discovery/signaling, longer Docker grace or 137 tolerance.
During installation, keep default images and baseline collector YAML unchanged.
Promote defaults only after accepted native live-release gates; the historical
collector YAML remains unchanged even after its active bind is superseded.

The application launcher must read the existing mounted JWT secret successfully
and refuse empty contents before `exec ./signoz server`. It never prints the
secret. No credential rotation, SQLite replacement or baseline provider change.

The installation used a one-time warm stop
of that old collector child, after ingestion quiescence and manager-reviewed
process identity, is an installation mitigation only. A manager-observed Plane
transition showed a child TERM exit zero followed by Docker restart one second
later under its old policy; failure to stay stopped was not a child hang. Thus
the proposed collector transition captures its exact original restart policy,
temporarily sets no-restart on ONLY that old container, proves warm clean exit,
then recreates ONLY the baseline collector with identical image/config/environment
and the proper exec launcher. Assert Compose restores `unless-stopped`, then
prove ordinary Docker TERM stop, clean stopped state and restart health. No actual
version upgrade is claimed here. The ordinary stop gate retires the
mitigation; no PID signaling or permanent no-restart enters baseline source or
backup. A failed transition needs explicit manager recovery, never auto-resume.

Both baseline launchers are now installed with unchanged app/collector image IDs
and JWT secret. The first operational probe stopped immediately after `exec`,
before collector initialization completed, yielding exit 2. PID 1 ownership is
not readiness. Repeated acceptance required HTTP health plus the collector's
completed-startup log before ordinary Docker stop; it exited zero without OOM.
Both original `unless-stopped` policies were restored. Cold-checkpoint capture now
requires exit zero/no OOM by default; exit 2 is also refused. The separately
evidence-bound ZooKeeper TERM exception is defined in ADR 012, not in a launcher
or broad nonzero-exit waiver.

Prepared release contracts live under `stacks/signoz/maintenance/`, separate
from baseline defaults. They adapt official Foundry output to the existing root
project, names, volumes, XML/macros and endpoints without installing Foundry or
deploying its Keeper/Postgres/latest defaults. Detailed provenance, version pairs,
intentional legacy-store compatibility and operator gates accompany the layers.
Stops are app/collector v0.131.1/v0.144.5, v0.135.0/v0.144.6,
v0.143.0/v0.144.11, v0.145.0/v0.144.12. Every layer pins ClickHouse/init
25.12.5 and collector/migrator together. Official forge-only pinned legacy
castings render all four pairs; this is preparation evidence, not runtime proof.

Match vendor old/new templates at the collector v0.144.6 threshold and use
vendor `signoz_health_check` in prepared configs only. Preserve every existing
ingestion setting except the named health extension and required AI processors
after spanmetrics/before batch. Adapt OpAMP to `ws://signoz:4320/v1/opamp` and
retain vendor manager-config/copy-path arguments. From app v0.143 explicitly
select JWT with the same mounted secret and SQLite/provider identity.

Prepared jobs use `manual-jobs`, no restart and exact vendor ready/bootstrap/sync/async
commands. App/collector use `manual-writers`; ClickHouse no longer automatically
runs init. The operator must prove each job before explicitly starting writers,
using scoped `--no-deps --pull never` ups. This is intentional repository
divergence from vendor automatic startup, shared by every prepared stop and
tested with no implicit jobs/writers. The command interface only prints one
phase, never executes or automatically advances after a failed migration.
Normal fresh startup retains its automatic dependency graph without those manual
profiles, using the same no-retry jobs. Existing-state upgrades never use that
fresh-start path. Earlier prepared pairs retain exact historical environments;
the credential guard refuses removing a later explicit JWT provider. Restore
sealed matching source for recovery rather than applying an old layer to promoted
source or migrated stores.

Keep SQLite/ZooKeeper and existing XML/macros because the official migration
supports the legacy layout, and render exact paired castings; changing storage
engines or replication identity would introduce independent migrations. Full
coordinated cold SQLite/ClickHouse/ZooKeeper restoration remains mandatory at
each stop. Shared stage-aware capture is now implemented under ADR 007: operators
explicitly supply the ordered common/accepted-stop overlays, including profiled
jobs/writers, and retain exact source bytes with actual resolved/runtime identities.
The current accepted stage must be stated; commands never infer or advance it.
Real isolated recovery/application checks at every stop remain manager gates.
Defaults were promoted only after the final accepted live gates. This does not
complete Plane or the parent full-stack maintenance plan.

Cold restore compares complete authentication rows exactly. Ordinary authenticated
requests legitimately update API-key usage metadata. Operational reboot resume may
accept only a proved `factor_api_key.last_observed_at` increase no later than now,
with key bytes, expiry, identity, account, role, schemas and every other column
unchanged against the sealed baseline. Retain both full hashes and the named
column-difference proof. Do not mask authentication fields in checkpoint/restore
comparisons or treat an unclean reboot as a coordinated checkpoint.

Upgrade comparisons distinguish ownership. User dashboards, accounts, custom AI
mapping and pricing must stay exact unless a separately reviewed migration names
their conversion. Vendor-owned, versioned defaults may reconcile only through
an exact predecessor/candidate template comparison with pinned source hashes,
stable identities and an explicit field/version transition. Never exempt an
entire system dashboard or mapping table, suppress arbitrary timestamps, or edit
stored values to satisfy a comparator. After reconciliation, same-version full
restart and cold restoration must preserve the resulting state exactly.

The v0.145 rehearsal names `vendor-owned-ai-overview-template-v2-to-v3` and
`vendor-owned-default-message-copy-to-move`; the
[receipt](../monitoring/maintenance-receipts/2026-10-10-signoz-0.145.0.md) records
their exact changes and retained failed checks. For mapping, the metastore/API
field `operation` becomes the collector wire field `action`; compare each
contract at its own layer. Require actual OpAMP readback, canonical message
values and removal of moved legacy sources in fresh and restored synthetic spans,
not only matching templates or simulated processing.

## Alternatives and Consequences

- A timeout increase or allowing 137 hides broken signal delivery; rejected.
- Backup-specific child signals couple recovery to an app process tree; rejected.
- Replacing storage with default Keeper/Postgres couples upgrades to independent
  data migrations; rejected for this maintenance sequence.
- Bind-mounted launchers become part of matched configuration backups.
- Local process/schema tests cannot certify container PID namespaces, application
  schema migrations, persisted dashboards, ingestion or state restoration.
- Treating vendor defaults as user-owned immutable bytes falsely rejects their
  versioned reconciliation; ignoring default tables hides unrelated drift. Both
  are rejected in favor of named, source-bound transition checks.

## Guardrails

Real-process tests cover exec identity, TERM, TERM/INT during initialization,
reaping, failed check, bounded unclean cancellation and secret refusal/preservation.
Prepared release tests constrain versions, config paths, processor order, manual
jobs, JWT provider and scoped commands. No failed job starts writers automatically.
Ownership-aware reconciliation tests reject user-data drift, wrong template
versions, unexpected query/layout changes, custom/default mapping or price drift,
and API/collector wire-format confusion. Native evidence remains a separate gate.
