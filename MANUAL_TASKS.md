# EdgeErgo V3 — Manual Pilot Tasks & Runbook

> [!IMPORTANT]
> The authoritative, step-by-step, de-duplicated manual runbook is located at:
> **[docs/MANUAL_RUNBOOK.md](docs/MANUAL_RUNBOOK.md)**.
>
> All manual procedures are chronologically ordered and grouped into Sections A through H. Each procedure defines prerequisites, exact commands/clicks, expected results, and the exact acceptance checkbox closed in [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md).

Below is the consolidated tracking checklist corresponding directly to the procedures in [docs/MANUAL_RUNBOOK.md](docs/MANUAL_RUNBOOK.md):

---

## Group A: Accounts & Secrets Provisioning
- [ ] **A.1 GitHub Repository Setup & Push Protection** — Enable secret scanning and push protection; push code. *(Closes: PRD §12 #1, #17)*
- [ ] **A.2 External Cloud Account Setup (Supabase & Render)** — Provision 2FA-secured cloud accounts. *(Closes: PRD §12 #1)*

---

## Group B: Supabase Database, Auth & Retention Setup
- [ ] **B.1 Project Creation & CLI Linking** — Create staging and production Supabase projects; link CLI. *(Closes: PRD §12 #3)*
- [ ] **B.2 Push Database Migrations & Verify RLS** — Apply `supabase/migrations/` and verify table RLS. *(Closes: PRD §12 #3, #5)*
- [ ] **B.3 Configure Application Postgres Role & Pooled Connection String** — Set `edgeergo_api` role password and construct transaction pooler URI. *(Closes: PRD §12 #3, #17)*
- [ ] **B.4 Configure Supabase Auth & First Admin User** — Disable open registration, configure redirect URLs, seed initial admin user. *(Closes: PRD §12 #4, #5)*
- [ ] **B.5 Configure Automated pg_cron Retention Purge** — Schedule nightly automated purge via `pg_cron`. *(Closes: PRD §12 #20)*

---

## Group C: Local End-to-End Run
- [ ] **C.1 Environment Configuration** — Copy and populate `.env` files for backend and frontend. *(Closes: PRD §12 #1)*
- [ ] **C.2 Start Local Backend & Frontend Services** — Run FastAPI on `:8000` and Vite dev server on `:5173`. *(Closes: PRD §12 #1, #2)*
- [ ] **C.3 Authenticate & Generate Device Enrollment Token** — Sign in as admin, create 15-minute enrollment token. *(Closes: PRD §12 #4, DESIGN §17 #10)*
- [ ] **C.4 Enroll Edge Agent & Seed Telemetry** — Enroll agent, run posture pipeline, inspect live charts and sanitized CSV export. *(Closes: PRD §12 #2, #10, #15, DESIGN §17 #3, #4, #5)*

---

## Group D: Render Cloud Deployment
- [ ] **D.1 Deploy Infrastructure Blueprint via Render Dashboard** — Link `render.yaml` Blueprint to GitHub repository. *(Closes: PRD §12 #16)*
- [ ] **D.2 Two-Stage Deployment Sequencing & Origin Lock** — Deploy backend, update frontend API URL, lock backend CORS `FRONTEND_ORIGIN`. *(Closes: PRD §12 #16)*
- [ ] **D.3 Execute Automated Deployment Smoke Tests** — Run `scripts/smoke_test.py` against live URLs; verify 100% pass. *(Closes: PRD §12 #16)*

---

## Group E: Windows Agent Packaging & Clean-Machine Test
- [ ] **E.1 Build Standalone Executable** — Run `scripts/build_agent.ps1` to produce `edge-ergo-v3.0.0-win64.zip`. *(Closes: PRD §12 #18)*
- [ ] **E.2 Clean Windows Machine Deployment Drill** — Extract to vanilla Windows PC without dev dependencies; verify `--version` and `--selftest`. *(Closes: PRD §12 #18, DESIGN §17 #13)*
- [ ] **E.3 Camera Disconnect, Privacy Toggle & Focus Non-Interference** — Test camera permission toggle, unplugging, fast typing focus non-interference, and multi-monitor DPI scaling. *(Closes: PRD §12 #6, DESIGN §17 #12, #13)*

---

## Group F: Privacy & Security Evidence Verification
- [ ] **F.1 Network Traffic Proxy Interception Drill** — Intercept outbound batches via mitmproxy/Wireshark; confirm 0 raw pixels and 0 landmarks on wire. *(Closes: PRD §12 #14, DESIGN §17 #9)*
- [ ] **F.2 Windows Credential Manager DPAPI Vault Inspection** — Confirm device secret is stored in Windows Credential Manager and absent from SQLite and logs. *(Closes: PRD §12 #17)*
- [ ] **F.3 Administrative Device Revocation Drill** — Revoke device in web dashboard; verify immediate HTTP 401 fail-closed halt on agent. *(Closes: PRD §12 #12, #13)*

---

## Group G: Performance & Hardware Measurements
- [ ] **G.1 Pilot Workstation Profiling Drill** — Execute `scripts/benchmark_edge.py` on real hardware; populate [docs/PERFORMANCE_TEMPLATE.md](docs/PERFORMANCE_TEMPLATE.md). *(Closes: PRD §12 #19)*

---

## Group H: Clinical & Legal Reviews
- [ ] **H.1 Independent Ergonomics Methodology Review** — Submit [docs/SCORING_METHOD.md](docs/SCORING_METHOD.md) and [docs/LIMITATIONS.md](docs/LIMITATIONS.md) to certified ergonomist (CPE) for sign-off. *(Closes: PRD §12 #8, #21)*
- [ ] **H.2 Workplace Privacy Notice & Employee Consent** — Provide pilot privacy disclosure to legal/HR and obtain signed participant agreements. *(Closes: PRD §12 #21, DESIGN §17 #14)*
