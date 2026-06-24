# Onboarding Maintainer Admin Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the onboarding docs visually distinguish colleague/project-owner steps from Ops Board maintainer/admin steps.

**Architecture:** Keep the human guide as the single colleague-facing golden path, but use GitHub-style callouts for handoff points where Ops Board maintainers/admins own the action. Mirror the same ownership model in the Codex guide and onboarding contract, then add a maintainer checklist to the monitoring manual where the admin work naturally lives.

**Tech Stack:** Markdown docs, GitHub callout syntax, `rg` verification, `git diff --check`.

---

## File Structure

- Modify `docs/onboarding/human-guide.md`: add visually distinct maintainer/admin callouts at handoff points and split first-success wording by role.
- Modify `docs/onboarding/codex-guide.md`: tell future Codex sessions to separate project changes from Ops Board maintainer/admin follow-up.
- Modify `docs/onboarding/onboarding-contract.md`: record the role contract so acceptance/evidence language does not imply the colleague configures Ops Board tools.
- Modify `docs/monitoring/ops-board-user-manual.md`: add the maintainer/admin checklist for turning a colleague-provided health URL into Ops Board monitor/dashboard state.

No code or runtime config changes are planned.

---

## Task 1: Mark Maintainer/Admin Handoffs In The Human Guide

**Files:**
- Modify: `docs/onboarding/human-guide.md`

- [ ] **Step 1: Update the onboarding summary to avoid assigning monitor creation to the colleague**

Replace this bullet:

```markdown
- Uptime Kuma can monitor that health endpoint.
```

with:

```markdown
- Long-running services provide a health endpoint that the Ops Board maintainer/admin can monitor.
```

Expected effect: the "What Onboarding Means" section still names the monitoring outcome, but no longer implies the colleague personally configures Uptime Kuma.

- [ ] **Step 2: Replace the direct Uptime Kuma instruction with a visible maintainer/admin callout**

Replace this paragraph in `## Python Web/API Service`:

```markdown
Then open Uptime Kuma at `http://hp-15:3001` and create an HTTP monitor for the health URL. See `docs/monitoring/ops-board-user-manual.md` for the monitor workflow and context.
```

with:

```markdown
Confirm the health endpoint returns a successful response from a tailnet machine, then share the health URL with the Ops Board maintainer/admin.

> [!NOTE]
> **Ops Board maintainer/admin step**
> The colleague onboarding the project only needs to provide the health URL and confirm it returns a successful response. The Ops Board maintainer/admin creates or confirms the Uptime Kuma HTTP monitor from `http://hp-15:3001`; the maintainer workflow lives in `docs/monitoring/ops-board-user-manual.md`.
```

Expected effect: the colleague knows what to do next, and the admin work is visually separated.

- [ ] **Step 3: Clarify removal ownership**

Replace item 4 under `## Removing Ops Board Later`:

```markdown
4. Remove or update any Uptime Kuma monitor, Homepage link, or project docs link that was added for Ops Board.
```

with:

```markdown
4. Tell the Ops Board maintainer/admin whether the Uptime Kuma monitor, Homepage link, or Ops Board-side references should be removed or updated.
```

Expected effect: a colleague removing the package is not told to edit Ops Board itself unless they are also acting as maintainer/admin.

- [ ] **Step 4: Add a maintainer/admin note to remote health-check wording**

After this paragraph:

```markdown
Health checks can point either from Uptime Kuma to the remote service's tailnet URL, or from the service host back to Ops Board if the service cannot accept inbound checks.
```

add:

```markdown
> [!NOTE]
> **Ops Board maintainer/admin step**
> The maintainer/admin chooses the monitor direction and Uptime Kuma settings. The colleague provides the reachable health URL, or explains why inbound tailnet checks are not possible.
```

Expected effect: network topology decisions stay with the Ops Board maintainer/admin.

- [ ] **Step 5: Split first-success checks by role**

Replace the `## First Success Test` block:

```markdown
After onboarding, prove these checks:

```text
Uptime Kuma can see the health endpoint.
SigNoz can see at least one trace from the project.
The docs say who owns the project.
The docs say where the project runs.
```
```

with:

````markdown
After onboarding, prove the project-owner checks:

```text
The health endpoint returns a successful response.
SigNoz can see at least one trace from the project.
The project docs say who owns the project.
The project docs say where the project runs.
```

> [!NOTE]
> **Ops Board maintainer/admin step**
> The Ops Board maintainer/admin confirms Uptime Kuma can monitor the health endpoint and that Ops Board-side links or references are in the right place.
````

Expected effect: first success has an obvious handoff rather than a hidden admin requirement.

- [ ] **Step 6: Verify the human guide role split**

Run:

```bash
rg -n "open Uptime Kuma|create an HTTP monitor|Uptime Kuma can see|maintainer/admin step|share the health URL|Remove or update any Uptime Kuma" docs/onboarding/human-guide.md
```

Expected:

- No hits for `open Uptime Kuma`.
- No hits for `create an HTTP monitor` outside the maintainer/admin callout.
- No hits for `Uptime Kuma can see`.
- At least three hits for `maintainer/admin step`.
- A hit for `share the health URL`.
- No hit for `Remove or update any Uptime Kuma`.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add docs/onboarding/human-guide.md
git commit -m "docs: mark human onboarding admin handoffs"
```

---

## Task 2: Align The Codex Guide With The Same Ownership Boundary

**Files:**
- Modify: `docs/onboarding/codex-guide.md`

- [ ] **Step 1: Add a role boundary near the top of the Codex guide**

After the paragraph that defines the normal OTLP endpoint:

```markdown
For colleague projects running somewhere other than `hp-15`, use `http://hp-15:4318` as the normal OTLP endpoint. Use `localhost` only for code running directly on `hp-15` itself or for playground-local checks.
```

add:

```markdown
Keep project-owner work separate from Ops Board maintainer/admin work. In the target project, add package config, health endpoints, tests, and telemetry. Do not create or edit Uptime Kuma monitors, Homepage entries, Plane workspaces, or Ops Board-side credentials unless the user explicitly says this Codex session is acting as the Ops Board maintainer/admin.
```

Expected effect: future Codex sessions do not silently cross the role boundary.

- [ ] **Step 2: Add a maintainer/admin handoff after health verification**

After the `Verify health endpoint` command block:

```markdown
curl -fsS --max-time 20 <health-url>
```

add:

```markdown
Record or report the health URL for the Ops Board maintainer/admin.

> [!NOTE]
> **Ops Board maintainer/admin step**
> The maintainer/admin creates or confirms the Uptime Kuma HTTP monitor and any Homepage link. The target project only needs a reachable health URL and working telemetry.
```

Expected effect: the guide names what Codex should report rather than doing admin setup by default.

- [ ] **Step 3: Rewrite acceptance criteria by role**

Replace:

```markdown
- Uptime Kuma has or can create a monitor for the health endpoint.
```

with:

```markdown
- The health URL is recorded for the Ops Board maintainer/admin.
- The Ops Board maintainer/admin has enough information to create or confirm the Uptime Kuma monitor.
```

Expected effect: acceptance criteria no longer imply that target-project onboarding includes direct Uptime Kuma configuration.

- [ ] **Step 4: Verify the Codex guide role split**

Run:

```bash
rg -n "acting as the Ops Board maintainer/admin|Record or report the health URL|Uptime Kuma has or can create|maintainer/admin step|Homepage link" docs/onboarding/codex-guide.md
```

Expected:

- A hit for `acting as the Ops Board maintainer/admin`.
- A hit for `Record or report the health URL`.
- No hit for `Uptime Kuma has or can create`.
- A hit for `maintainer/admin step`.
- A hit for `Homepage link` in the maintainer/admin context.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add docs/onboarding/codex-guide.md
git commit -m "docs: separate codex onboarding admin work"
```

---

## Task 3: Make The Onboarding Contract Explicit About Role Ownership

**Files:**
- Modify: `docs/onboarding/onboarding-contract.md`

- [ ] **Step 1: Add a Role Ownership section after Required Signals**

After the Required Signals table, add:

```markdown
## Role Ownership

| Role | Owns | Does not need to own |
|------|------|----------------------|
| Project owner or colleague | Project package install, `ops-board.yaml` or `OPS_BOARD_*` values, health endpoint, app/job telemetry, project docs for owner and runtime host | Uptime Kuma monitor creation, Homepage entries, Plane workspace/admin setup, Ops Board credentials |
| Ops Board maintainer/admin | Uptime Kuma monitors, Homepage entries, Ops Board-side links, SigNoz and Plane admin/workspace setup, monitor naming and status-page placement | Target project code unless explicitly helping with onboarding |

When a person is wearing both hats, they may do both sets of work. The docs should still label Ops Board maintainer/admin steps so the handoff is visible.
```

Expected effect: the contract gives future docs a shared vocabulary for ownership.

- [ ] **Step 2: Clarify the health signal row**

Replace the Health endpoint row:

```markdown
| Health endpoint | Uptime Kuma | Yes for services, recommended for long-running workers | Answers whether it is alive right now. |
```

with:

```markdown
| Health endpoint | Project plus Uptime Kuma | Yes for services, recommended for long-running workers | Project exposes it; Ops Board maintainer/admin monitors it. |
```

Expected effect: the signal table reflects split ownership.

- [ ] **Step 3: Clarify acceptance checklist ownership**

Replace these two bullets:

```markdown
- A long-running service exposes a health endpoint.
- Uptime Kuma can monitor that health endpoint.
```

with:

```markdown
- A long-running service exposes a health endpoint and the health URL is recorded.
- The Ops Board maintainer/admin can create or confirm the Uptime Kuma monitor for that health endpoint.
```

Replace:

```markdown
- A teammate can find the project from docs or Homepage.
```

with:

```markdown
- A teammate can find the project from project docs, and the Ops Board maintainer/admin has enough information to add or update Homepage when needed.
```

Expected effect: acceptance is still meaningful before the maintainer/admin has finished optional board-side polish.

- [ ] **Step 4: Clarify evidence checklist ownership**

Replace:

```markdown
- Health monitor evidence: when a health endpoint exists, Uptime Kuma or the chosen monitor can reach it successfully.
```

with:

```markdown
- Health monitor evidence: when a health endpoint exists, the Ops Board maintainer/admin confirms Uptime Kuma or the chosen monitor can reach it successfully.
```

Expected effect: monitor evidence is explicitly an admin confirmation.

- [ ] **Step 5: Verify the contract role ownership**

Run:

```bash
rg -n "Role Ownership|Project owner or colleague|Ops Board maintainer/admin|Project exposes it|Uptime Kuma can monitor|A teammate can find the project from docs or Homepage|Health monitor evidence" docs/onboarding/onboarding-contract.md
```

Expected:

- Hits for `Role Ownership`, `Project owner or colleague`, and `Ops Board maintainer/admin`.
- A hit for `Project exposes it`.
- No hit for the old sentence `Uptime Kuma can monitor that health endpoint`.
- No hit for the old sentence `A teammate can find the project from docs or Homepage`.
- A `Health monitor evidence` hit that includes `Ops Board maintainer/admin confirms`.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add docs/onboarding/onboarding-contract.md
git commit -m "docs: define onboarding role ownership"
```

---

## Task 4: Add The Maintainer/Admin Handoff Workflow To The Monitoring Manual

**Files:**
- Modify: `docs/monitoring/ops-board-user-manual.md`

- [ ] **Step 1: Add a maintainer/admin workflow after Which Tool To Use**

After the `## Which Tool To Use` table, add:

```markdown
## Maintainer/Admin Workflow: Onboard A Colleague Project

When a colleague provides a service name, runtime host, and health URL:

1. Open Uptime Kuma at `http://hp-15:3001`.
2. Create or confirm an HTTP monitor for the health URL.
3. Use the project service name in the monitor name.
4. Confirm the monitor can reach the health endpoint from Ops Board.
5. Add or update Homepage links only when the project should appear on the launch board.
6. Ask the colleague to run one request or job so SigNoz receives a trace for the service name.

The colleague owns the target project code and health endpoint. The Ops Board maintainer/admin owns monitor naming, monitor placement, status-page placement, and Ops Board-side links.
```

Expected effect: the admin action moved out of the colleague instructions has a clear home.

- [ ] **Step 2: Update v1 limits to mention monitor ownership if useful**

In `## Limits Of V1`, keep the current bullets and add this bullet after `Add real project entries to Homepage manually.`:

```markdown
- Create or confirm real project Uptime Kuma monitors manually after the colleague provides the health URL.
```

Expected effect: v1 manual work includes real project monitors, not just Homepage entries.

- [ ] **Step 3: Verify the monitoring manual handoff**

Run:

```bash
rg -n "Maintainer/Admin Workflow|colleague provides|Create or confirm an HTTP monitor|monitor naming|real project Uptime Kuma monitors" docs/monitoring/ops-board-user-manual.md
```

Expected:

- A hit for the new workflow heading.
- A hit for `colleague provides`.
- A hit for `Create or confirm an HTTP monitor`.
- A hit for `monitor naming`.
- A hit for `real project Uptime Kuma monitors`.

- [ ] **Step 4: Commit Task 4**

Run:

```bash
git add docs/monitoring/ops-board-user-manual.md
git commit -m "docs: add maintainer onboarding workflow"
```

---

## Task 5: Final Verification And Review

**Files:**
- Review: `docs/onboarding/human-guide.md`
- Review: `docs/onboarding/codex-guide.md`
- Review: `docs/onboarding/onboarding-contract.md`
- Review: `docs/monitoring/ops-board-user-manual.md`

- [ ] **Step 1: Run stale ownership wording scan**

Run:

```bash
rg -n "Then open Uptime Kuma|create an HTTP monitor for the health URL|Uptime Kuma can see the health endpoint|Uptime Kuma has or can create|Remove or update any Uptime Kuma monitor|A teammate can find the project from docs or Homepage" docs/onboarding docs/monitoring -g "*.md"
```

Expected: no hits.

- [ ] **Step 2: Run maintainer/admin wording scan**

Run:

```bash
rg -n "Ops Board maintainer/admin step|Ops Board maintainer/admin|Maintainer/Admin Workflow|share the health URL|health URL is recorded|Homepage link" docs/onboarding docs/monitoring -g "*.md"
```

Expected:

- Human guide has visible `Ops Board maintainer/admin step` callouts.
- Codex guide has the explicit role-boundary paragraph and handoff note.
- Onboarding contract has `Role Ownership`.
- Monitoring manual has `Maintainer/Admin Workflow`.

- [ ] **Step 3: Run formatting check**

Run:

```bash
git diff --check
```

Expected: exit code `0`.

- [ ] **Step 4: Read the changed docs in order**

Read:

```bash
Get-Content -Raw docs/onboarding/human-guide.md
Get-Content -Raw docs/onboarding/codex-guide.md
Get-Content -Raw docs/onboarding/onboarding-contract.md
Get-Content -Raw docs/monitoring/ops-board-user-manual.md
```

Expected:

- The colleague can follow the human guide without being told to administer Ops Board.
- The maintainer/admin handoffs are visually obvious.
- The Codex guide does not authorize Ops Board admin changes unless the user explicitly says so.
- The contract and manual agree on who owns monitors and Homepage links.

- [ ] **Step 5: Optional docs-only test sanity**

Run this if any commands or package examples were changed while implementing the docs:

```bash
uv run --project packages/ops-board-observe pytest packages/ops-board-observe/tests -q
uv run --project examples/onboarding pytest examples/onboarding/tests examples/onboarding/dummy-job/tests examples/onboarding/dummy-api/tests -q
```

Expected:

- `37 passed` for `packages/ops-board-observe`.
- `9 passed` for `examples/onboarding`.

If implementation only changes prose ownership labels and no commands, record that package/example tests were not necessary for the docs-only change.

- [ ] **Step 6: Final review**

Request a review focused on:

```text
Do these docs keep colleague/project-owner onboarding separate from Ops Board maintainer/admin work?
Are the callouts visually obvious without being noisy?
Do any acceptance or evidence checklists still imply the colleague configures Ops Board tools?
```

Expected: no Critical or Important findings before merge/push.

- [ ] **Step 7: Commit any final fixes**

If final review requires fixes, commit them with:

```bash
git add docs/onboarding docs/monitoring
git commit -m "docs: clarify onboarding admin ownership"
```

If no fixes are required, do not create an empty commit.

---

## Self-Review

- Spec coverage: The plan covers the human guide line that started the concern, plus Codex guide, onboarding contract, and monitoring manual places where role ownership affects acceptance or admin workflow.
- Placeholder scan: No `TBD`, `TODO`, `implement later`, or vague "add appropriate wording" steps remain. Each doc edit has concrete replacement text or insertion text.
- Type/name consistency: The chosen label is consistently `Ops Board maintainer/admin step` for callouts and `Ops Board maintainer/admin` in prose. The monitoring manual section uses `Maintainer/Admin Workflow` because it is already an admin-facing document.
- Scope check: This is docs-only. No package, Compose, monitor bootstrap, or screenshot changes are included.
