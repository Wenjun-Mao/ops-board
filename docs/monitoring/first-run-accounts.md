# First-Run Accounts

Ops Board automates Uptime Kuma first-run setup. SigNoz and Plane first admin/workspace setup remain manual for v1 by decision in `docs/adr/003-first-run-account-boundary.md`.

Use this runbook after the stack is running on HP-15:

```bash
./scripts/init-local-config.sh --host hp-15
docker compose --env-file .env -f compose.yaml up -d
./scripts/bootstrap-uptime-kuma.sh
./scripts/smoke-day1.sh --skip-onboarding
```

## Safety Rules

- Store SigNoz and Plane credentials in a password manager or other user-controlled secret store.
- Do not commit SigNoz, Plane, or Uptime Kuma passwords.
- Do not add SigNoz or Plane passwords to `.env`, docs, screenshots, or tracked config.
- Do not seed SigNoz or Plane databases directly.
- If future automation is needed, first add an ADR that names the supported application-level bootstrap contract and secret storage model.

## SigNoz Admin Setup

Open SigNoz from a tailnet device:

```text
http://hp-15:8080
```

On a fresh volume, SigNoz should show its first admin setup. Create the local admin account using credentials stored outside the repo.

After login:

1. Run the full smoke:

   ```bash
   ./scripts/smoke-day1.sh
   ```

2. In SigNoz, look for services named `dummy-api` and `dummy-job`.
3. Confirm traces exist for `dummy-api.work` and `dummy-job.run`.
4. Confirm the UI is reachable from Uptime Kuma through the `SigNoz UI` monitor.

The Day-1 smoke does not require SigNoz UI credentials. It proves ingestion by sending dummy telemetry and querying ClickHouse directly.

## Plane Workspace Setup

Open Plane from a tailnet device:

```text
http://hp-15:8082
```

On a fresh volume, Plane should show account or workspace setup. Create or log into the local account, then create the workspace:

```text
Ops Board
```

Use Plane for operational follow-up after a monitoring finding becomes work. Do not store Plane credentials in repo files.

After setup:

1. Confirm the `Ops Board` workspace home loads.
2. Create a small test issue only if you want to verify the workflow end to end.
3. Remove or close the test issue if it is not useful as a sample.
4. Confirm the UI is reachable from Uptime Kuma through the `Plane` monitor.

## Automation Boundary

Safe to automate now:

- Detect whether SigNoz and Plane URLs are reachable.
- Detect likely first-run/login/workspace states and print the next manual action.
- Verify Uptime Kuma monitors, SigNoz telemetry ingestion, and Plane HTTP reachability.
- Generate or update non-secret Homepage/project YAML entries.

Not safe to automate yet:

- Creating SigNoz or Plane admin users through private or undocumented endpoints.
- Seeding SigNoz or Plane databases directly.
- Writing SigNoz or Plane passwords into tracked files.
- Creating Plane workspaces without a documented application-level contract.
