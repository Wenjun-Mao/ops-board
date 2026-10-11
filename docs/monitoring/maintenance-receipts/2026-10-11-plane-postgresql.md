# Plane PostgreSQL Kickoff on HP-15

## Status and Scope

**Database-only isolated compatibility and recovery passed. Live Plane is unchanged.**
The owner requested committing/pushing the existing maintenance work, then kicking
off Plane. Commit `e0fbed0` was pushed and HP-15 fast-forwarded before this test.
This receipt does not accept the complete Plane application/dependency release.

Live readback still selects Plane v1.3.1, PostgreSQL 15.7, Valkey 7.2.11,
RabbitMQ 3.13.6 and the original pinned MinIO bytes. Unrelated/live containers
retain their IDs, image IDs, start times and running states throughout the checks.
No live version, account, secret, monitor or restart policy changed.

## Restored Baseline

The retained `ops-board-rehearsal-plane-a` copy was started by its inspected
existing container IDs, with internal isolated networking and no published ports.
Workers, scheduler and migrator were not started. Its real instance API returned
200 through its proxy. Native reads found one user, one workspace, one test
project, one work item, two uploaded file assets and two stored objects.

The known 208-byte PNG retained SHA-256
`9e51e4eaf6428e6676868b06fc3fa1692881806a11462407aab52254ca12e7ca`
and `image/png` content type. These fixtures belong to the restored copy, not live
Plane. All ten interactive/infrastructure containers stopped with exit zero and
no OOM; all eleven retained volumes, including unmounted job logs, were archived
cold. This refreshed archive set is not a sealed full-family recovery acceptance.

## Patch Review and Actual Catalog

The PostgreSQL 15.8 through 15.19 release notes were reviewed. Relevant conditional
follow-ups include partitioned foreign keys in
[15.9](https://www.postgresql.org/docs/release/15.9/) and
[15.13](https://www.postgresql.org/docs/release/15.13/), BRIN bloom/numeric indexes
in [15.13](https://www.postgresql.org/docs/release/15.13/) and
[15.14](https://www.postgresql.org/docs/release/15.14/), and logical output plugins,
PGP cleanup and extension indexes in
[15.19](https://www.postgresql.org/docs/release/15.19/).

The inspected Plane database has only `plpgsql`, btree indexes, no partitioned or
foreign tables, no replication slots and no invalid indexes. The named extension,
BRIN and partition repair cases therefore do not apply to this inspected catalog.
The maintenance client uses `COPY TO STDOUT`, not scripted inline `COPY FROM STDIN`.
Refresh the actual live catalog before any live patch; the rehearsal is not an
assertion about every database, historical schema operation or future change.

## ICU Follow-Up

The frozen `postgres:15.19-alpine` image is linux/amd64, local image ID
`sha256:319d040b5d68e3e5b98a238f0b5d375b4b4d9c5b3a6a9afb0308a8bcf0de72a5`.
Its ICU provider reports different versions for **852 predefined collations**
copied from 15.7. The strict gate refused that mismatch rather than ignoring it.

Native `pg_depend`, column and index audits each found exactly zero references to
the mismatched collations. User columns use `default`; indexes use `default` or
`C`. Database defaults use libc, with no reported database-version mismatch.
Only the inspected Plane database's unused `pg_catalog` ICU records were refreshed
using `ALTER COLLATION ... REFRESH VERSION`. Complete before/after collation rows
matched an exact expected delta: only those 852 `collversion` fields changed to
their inspected provider versions. No indexes, owners, definitions or application
data were changed. Other databases/templates were not refreshed.

This is not permission to refresh used collations without rebuilding their
dependent objects. PostgreSQL explicitly warns that refreshing a version does
not verify a rebuild. See its
[collation maintenance guidance](https://www.postgresql.org/docs/15/sql-altercollation.html).
The guard refuses any dependent object, column, index or unexpected catalog delta.

## Preservation and Recovery

The candidate used a fresh separately owned PostgreSQL volume, never a live or
shared database volume. Restored file contents and metadata matched the cold
baseline before startup. All **110 public tables**, **13 role rows** and **13
sequence states** retained exact canonical row/state fingerprints on 15.19,
after the metadata refresh, and after an ordinary stop/restart.

A separate cold archive of the repaired 15.19 candidate was then restored into
another fresh volume/project with its exact image/config. Every PostgreSQL file
and recorded metadata field matched before startup; public data, roles, sequences
and the complete collation catalog matched after startup. Strict catalog checks
passed, and the recovered database stopped with exit zero/no OOM.

All original-copy, candidate and cold-restored test containers are now cleanly
stopped and retained. The full live stack's passive verification passed afterward.

## Failed Checks and Evidence

The first private harness inherited `PGHOST` and omitted the existing password for
its TCP client. Explicit loopback host/port and the existing runtime password
fixed the adapter, without rotating credentials. The second attempt incorrectly
treated a sequence as a composite row; a native failure established the need for
explicit `last_value`, `log_cnt`, `is_called` projection. Both failed attempts were
retained and their isolated infrastructure stopped cleanly before a fresh attempt.
The third attempt retained its genuine ICU-gate refusal and diagnostic proof;
a separately inspected continuation performed the scoped metadata repair.

Twelve focused harness tests passed on HP-15, covering client binding, complete
state fingerprints, isolation, volume consumers, strict stops and repair refusal
conditions. The committed repository suite had already run 166 tests: 165 passed,
with the optional Foundry check skipped. Private code/configuration, archives,
failed attempts and native comparisons remain outside tracked source.
All twelve Plane release/configuration tests and `git diff --check` passed after
the kickoff documentation update.

Restricted successful audit root:
`/home/wjmao/ops-board-maintenance/plane-kickoff-20261011T040900Z`.
Its `result.json` completed at `2026-10-11T04:13:57Z`; `pg19/cold/result.json`
records the candidate's own PostgreSQL-only recovery proof.

## Remaining Gates

Next is the complete restored Plane family against the patched database, including
normal existing-account access, queries, workspace/work-item behavior and upload
flows, then full-family recovery. This turn did not retest browser login or run
Plane on the patched database. Cache, application, storage and broker stages remain
separate. No live Plane cutover occurred.

The existing empty-browser-MIME text-file upload limitation remains documented,
unfixed and unwaived; `application_rehearsal_passed` remains false. A successful
PNG or database test does not replace that acceptance decision.
