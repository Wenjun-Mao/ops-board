# SigNoz Shared Observability Stack

Standalone SigNoz deployment for centralized logging, tracing, and metrics across multiple projects.

## Quick start

```bash
docker compose -p signoz -f docker/compose.yaml up -d --remove-orphans
```

Open UI at **http://localhost:8080**

## Current stack pins

| Component | Image |
|-----------|-------|
| SigNoz | `signoz/signoz:v0.125.1` |
| SigNoz OTel Collector | `signoz/signoz-otel-collector:v0.144.4` |
| ClickHouse | `clickhouse/clickhouse-server:25.5.6` |
| ZooKeeper | `signoz/zookeeper:3.7.1` |

## Restricted Network Setup (No GitHub Access)

If the host cannot reach GitHub (common in restricted networks), pre-seed the ClickHouse init binary tarball locally.

1. Download the correct archive on any machine with internet:
   - `histogram-quantile_linux_amd64.tar.gz` for `x86_64/amd64`
   - `histogram-quantile_linux_arm64.tar.gz` for `aarch64/arm64`
2. Copy and rename it on the SigNoz host to:
   - `common/clickhouse/user_scripts/histogram-quantile.tar.gz`
3. Start stack:
   - `docker compose -p signoz -f docker/compose.yaml up -d --remove-orphans`
4. Verify init succeeded:
   - `docker logs signoz-init-clickhouse --tail 100`
   - `docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"`

Optional: if you have an accessible mirror URL, set `HISTOGRAM_QUANTILE_URL` in `docker/.env` to override the default GitHub download URL.

## Published ports

| Port  | Protocol   | Purpose                          |
|-------|------------|----------------------------------|
| 8080  | HTTP       | SigNoz web dashboard             |
| 4317  | gRPC       | OTLP receiver (traces/metrics/logs) |
| 4318  | HTTP       | OTLP receiver (traces/metrics/logs) |
| 13133 | HTTP       | Collector health check (`/`)     |

All ports bind to `0.0.0.0` — reachable from localhost, LAN, and nginx reverse proxy.

## Access patterns

| Client location                 | OTLP endpoint                              |
|---------------------------------|--------------------------------------------|
| Same-host Docker container      | `http://host.docker.internal:4318/v1/logs` |
| Same-host non-Docker process    | `http://localhost:4318/v1/logs`            |
| LAN peer                        | `http://<signoz-host-ip>:4318/v1/logs`    |
| Remote / VPS (nginx + SSL)      | `https://<domain>/v1/logs`                |

## Nginx reverse proxy (example snippet)

```nginx
# OTLP HTTP ingestion
upstream signoz_otlp {
    server 127.0.0.1:4318;
}

server {
    listen 443 ssl;
    server_name  signoz-otlp.example.com;

    # ... ssl_certificate directives ...

    location /v1/ {
        proxy_pass  http://signoz_otlp;
        proxy_set_header  Host $host;
        proxy_set_header  X-Real-IP $remote_addr;
    }
}

# SigNoz UI
upstream signoz_ui {
    server 127.0.0.1:8080;
}

server {
    listen 443 ssl;
    server_name  signoz.example.com;

    # ... ssl_certificate directives ...

    location / {
        proxy_pass       http://signoz_ui;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Directory layout

```
signoz/
├── README.md              ← you are here
├── docs/
│   └── ONBOARDING.md      ← per-project onboarding guide
├── common/                ← shared config mounted into containers
│   ├── clickhouse/
│   └── signoz/
│       └── otel-collector-opamp-config.yaml
└── docker/
    ├── compose.yaml
    └── otel-collector-config.yaml
```

## Onboarding new projects

See [docs/ONBOARDING.md](docs/ONBOARDING.md) for:
- endpoint selection by client location
- required OTLP resource/log attributes
- copy-paste Vector agent compose snippet
- verification queries

## Lifecycle

This stack is **shared infrastructure** — independent of any single project.
- Start it once; leave it running.
- Project stacks start/stop without affecting SigNoz.
- Plan and communicate SigNoz upgrades since all projects share it.

## Stop / reset

```bash
# Stop (keep data)
docker compose -p signoz -f docker/compose.yaml down

# Full reset (wipe ClickHouse, SQLite, ZooKeeper volumes)
docker compose -p signoz -f docker/compose.yaml down -v
```
