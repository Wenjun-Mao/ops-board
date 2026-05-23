Onboarding to shared SigNoz

Purpose
- Run one SigNoz stack as shared observability infrastructure.
- Accept telemetry from multiple projects — same host, LAN peers, or remote VPS.
- Keep each project responsible for its own shipper agent and log parsing rules.

Access model
- Same-host Docker containers: `http://host.docker.internal:4318/v1/logs`
- Same-host non-Docker processes: `http://localhost:4318/v1/logs`
- LAN peers: `http://<signoz-host-ip>:4318/v1/logs`
- Remote / VPS (via nginx + SSL): `https://<domain>/v1/logs`

Published endpoints
- UI: `0.0.0.0:8080`
- OTLP gRPC: `0.0.0.0:4317`
- OTLP HTTP: `0.0.0.0:4318`
- Collector health check: `0.0.0.0:13133` (useful as nginx upstream probe)

Start SigNoz
1) From this repo root:
   - `docker compose -p signoz -f docker/compose.yaml up -d --remove-orphans`
2) Open UI:
   - `http://localhost:8080`
3) Verify collector port is exposed:
   - `docker ps --format "table {{.Names}}\t{{.Ports}}" | Select-String "signoz-otel-collector|4318"`

Project-side requirements (per project)
- Run a shipper that speaks OTLP (Vector, OTel Collector, or SDK direct).
- Point the exporter to one of the access endpoints above.
- If using Vector, set these env vars in your project compose:
  - `VECTOR_SIGNOZ_OTLP_HTTP_URI=http://<signoz-host>:4318/v1/logs`
  - `VECTOR_PROJECT_NAME=<your-project-name>`
  - `VECTOR_DEPLOYMENT_ENV=<local|dev|staging|prod>`
- Ensure OTLP payload includes at least:
  - resource attributes: `service.name`, `deployment.environment`
  - log attributes: `project.name` (plus any domain-specific keys)

Recommended project naming
- Use stable lowercase IDs for `project.name` (example: `talking-head-orchestrator-api`).
- Keep `deployment.environment` to a small enum (`local`, `dev`, `staging`, `prod`).

Vector agent compose snippet (copy/paste template)
```yaml
  vector-agent:
    image: timberio/vector:0.44.0-debian
    command: ["--config", "/etc/vector/vector.yaml"]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./vector.yaml:/etc/vector/vector.yaml:ro
      - vector-data:/vector-data-dir
    environment:
      - VECTOR_SIGNOZ_OTLP_HTTP_URI=http://<signoz-host>:4318/v1/logs
      - VECTOR_PROJECT_NAME=<your-project-name>
      - VECTOR_DEPLOYMENT_ENV=local
    restart: always

volumes:
  vector-data:
```

Verification queries
- Recent project/service activity:
  - `docker exec signoz-clickhouse clickhouse-client -q "SELECT attributes_string['project.name'] AS project, resources_string['service.name'] AS service, count() AS c FROM signoz_logs.distributed_logs_v2 WHERE timestamp > now() - INTERVAL 10 MINUTE GROUP BY project, service ORDER BY project, service"`
- Verify environment tags:
  - `docker exec signoz-clickhouse clickhouse-client -q "SELECT attributes_string['project.name'] AS project, resources_string['deployment.environment'] AS env, count() AS c FROM signoz_logs.distributed_logs_v2 WHERE timestamp > now() - INTERVAL 10 MINUTE GROUP BY project, env ORDER BY project, env"`

Troubleshooting
- No logs arriving:
  - check project `vector-agent` container logs for transport errors.
  - confirm SigNoz collector container is running and `4318` is published.
- Wrong/missing project grouping:
  - verify `VECTOR_PROJECT_NAME` is set in that project's compose.
  - verify `project.name` is mapped into OTLP log attributes by Vector.
- Time skew in logs:
  - prefer source event timestamp (`.timestamp`) in Vector and only fallback to `now()`.

Operational boundaries
- SigNoz stack lifecycle is independent from any single project stack.
- Restarting one project should not restart shared SigNoz.
- Upgrades to SigNoz should be planned and communicated because all projects share it.
