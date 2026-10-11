# SigNoz Prepared Release Provenance

Reviewed 2026-10-07. These are prepared source contracts, not runtime receipts.
Machine-readable pins, source/template digests and gates live in [release.json](release.json).

## Authority

- [Upgrade path tool](https://signoz.io/upgrade-path/): the manager's reviewed
  v0.125-series to v0.145 sequence requires 0.131, 0.135 and 0.143 before target.
  First stop selects app patch v0.131.1; it is not a claim that chart 0.131.0's
  `appVersion` is v0.131.1 (that field is v0.131.0).
- [0.131 migration](https://signoz.io/docs/operate/migration/upgrade-0-131/):
  ClickHouse 25.12.5 and backup/format concerns; bundled `deploy/` Compose and
  install.sh deprecated since 0.130. [Chart 0.131.0 values](https://github.com/SigNoz/charts/blob/signoz-0.131.0/charts/signoz/values.yaml)
  provide the collector v0.144.5 and ClickHouse 25.12.5 base pair.
- [0.135 migration](https://signoz.io/docs/operate/migration/upgrade-0-135/) and
  [chart values](https://github.com/SigNoz/charts/blob/signoz-0.135.0/charts/signoz/values.yaml):
  Dashboards V2 and paired collector v0.144.6.
- [0.143 migration](https://signoz.io/docs/operate/migration/upgrade-0-143/):
  collector v0.144.11, AI processors/OpAMP and explicit provider+secret to retain
  JWT. [Final chart values](https://github.com/SigNoz/charts/blob/signoz-0.145.0/charts/signoz/values.yaml)
  pin collector v0.144.12 for app v0.145.0.
- [Official legacy-to-Foundry migration](https://github.com/SigNoz/signoz/blob/main/deploy/MIGRATION.md)
  explicitly supplies SQLite/ZooKeeper casting and old volume reuse, including
  root user for legacy ZooKeeper data. This supports preserving these components,
  not silently adopting Foundry's default Postgres/ClickHouse Keeper topology.

## Foundry Comparison

Official [Foundry v0.3.0](https://github.com/SigNoz/foundry/tree/v0.3.0), source
commit `78c6968a8137341a4be15d8931e2dd796c2a879c`:

- [Compose template](https://github.com/SigNoz/foundry/blob/v0.3.0/internal/casting/dockercomposecasting/templates/compose.yaml.gotmpl)
  supplies the exact migration ready/bootstrap/sync/async sequence and collector
  manager-config/copy-path wiring.
- [Older collector template](https://github.com/SigNoz/foundry/blob/v0.3.0/internal/molding/ingestermolding/templates/config.v0129x.yaml.gotmpl)
  applies below v0.144.6; no AI processors.
- [New collector template](https://github.com/SigNoz/foundry/blob/v0.3.0/internal/molding/ingestermolding/templates/config.v01446.yaml.gotmpl)
  applies at/above v0.144.6 with both processors and exact trace ordering.
- [OpAMP template](https://github.com/SigNoz/foundry/blob/v0.3.0/internal/molding/ingestermolding/templates/opamp.v0129x.yaml.gotmpl)
  supplies the WebSocket `/v1/opamp` endpoint.
- [Compatibility rules](https://github.com/SigNoz/foundry/blob/v0.3.0/internal/compat/installation/compat.go)
  require ClickHouse 25.12.5 above collector 0.144.5. Official v0.143 guidance
  requires collector 0.144.11; use that stricter documented pair, not just Foundry's
  processor minimum of 0.144.6.

The manager supplied an already downloaded/checksum-verified Mac arm64 binary at
`/tmp/ops-board-foundry.naODDI/foundry_darwin_arm64/bin/foundryctl`. This source
slice used it only to forge all four `foundry/*.yaml` castings with ledger and
updater disabled, into separate `/tmp/ops-board-signoz-forge-<stop>` directories.
All four renders succeeded. Their Compose/collector configs were compared in
the optional local tests. Output is disposable upstream comparison, not an
installation or data-conversion proof. No cast, installer or image/container run.

Forge also writes `casting.yaml.lock` beside its input. The initial generated
lock was removed from source; optional comparison tests now copy each casting
into a temporary directory and keep both the lock and pours there. Tests assert
that the checked-in input directory remains byte-for-byte unchanged.

`release.json` records the supplied archive SHA256 values for Mac arm64 and
Linux amd64, plus SHA256 values computed from the four exact raw templates.
The Linux archive was not executed here. Reverify any future downloaded binary
against official release checksums before opting into the forge comparison.

## Reviewed Adaptations

Retain `ops-board` root include model, fixed service/container/network names,
three existing named volumes, root-owned ZooKeeper 3.7.1 data, SQLite provider
and `/var/lib/signoz/signoz.db`. Official casting accepts both legacy kinds and
all four pinned pairs forge successfully. This is compatible preparation evidence,
not certification of SQLite migrations or ZooKeeper/ClickHouse recovery.

Retain existing ClickHouse XML, user scripts, cluster `cluster`, shard `01`,
replica `example01-01-1` and coordinator `zookeeper-1:2181`. Do not replace them
with Foundry-generated YAML or new replication paths. Histogram init stays the
existing local-archive/mirror-aware command, paired with the new ClickHouse image.
No hidden macro remapping or data-volume aliases.

Retain all baseline OTLP/resource attributes, 60-second self-Prometheus scrape,
spanmetric dimensions/histograms, batches (10000/11000/10s and 20000/25000/1s),
exporter timeouts/queues, metadata/meter destinations, telemetry logs and all five
pipelines. The resourcedetection definition remains as-is, not newly inserted
into pipelines. No settings are overwritten with Foundry's larger batch defaults
or shorter dimension list. Tests compare normalized entire configs to baseline.

Prepared pairs use vendor `signoz_health_check`, while baseline remains legacy
`health_check`. Direct source review of `components/components.go` at collector
v0.144.5, v0.144.6, v0.144.11 and v0.144.12 confirms both health factories;
the latter three also register both AI processors. This deliberately changes
only the named health extension in the first-stop ingestion config.

OpAMP host is adapted to `ws://signoz:4320/v1/opamp`, internal only; final collector
arguments include vendor manager-config and writable copy-path. The owned launcher
replaces vendor's non-exec PID 1 shell without changing the initialization command.

Jobs are manual, nonretrying and detached from ClickHouse's automatic init
dependency; writers require explicit selection. This intentionally changes vendor
automatic startup semantics to make migration failure fail-closed. See ADR 011
and the operator gates. No permanent no-restart policy is applied to collector/app.
