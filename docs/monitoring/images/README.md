# Monitoring Images

These screenshots support `docs/monitoring/ops-board-user-manual.md`.

Capture them from the repo root after the board is running:

```powershell
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:3000 docs/monitoring/images/homepage-overview.png
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:3001/status/ops-board docs/monitoring/images/uptime-kuma-first-run.png
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:8080 docs/monitoring/images/signoz-first-run.png
npx playwright screenshot --viewport-size "1365,900" --wait-for-timeout 3000 http://localhost:8082 docs/monitoring/images/plane-first-run.png
```

SigNoz and Plane screenshots may show setup, login, or dashboard states depending on whether the local runtime has been initialized. Do not commit screenshots that expose credentials, tokens, or private project data.
