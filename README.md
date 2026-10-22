# EdgeErgo V3

> **Privacy-Preserving Workplace Ergonomic Assessment Platform**
>
> An enterprise-grade, edge-first ergonomics platform that estimates workstation posture locally via computer vision, computes validated upper-body screening indicators, and provides real-time, non-punitive desktop feedback without transmitting biometric data.

---

## 1. Privacy Boundary Statement (Non-Negotiable)

- **Local Inference Only:** Camera frames, video buffers, face crops, and raw coordinate landmarks are processed exclusively in volatile workstation RAM. They are **never** stored on disk, never uploaded to central services, and never logged.
- **Strictly Minimized Telemetry:** The edge agent sends only allowlisted, aggregated assessment records (UUID, timestamp, validity state, versioned scoring indicators, and guidance codes) over HTTPS with `extra="forbid"` schema validation.
- **No Diagnostic or Ranking Claims:** EdgeErgo is an ergonomic screening indicator and proactive posture habit guide. It is **not** a clinical diagnostic medical device and **must never** be used for employee performance evaluation or ranking.

---

## 2. Architecture Overview

```text
+------------------------------------+        +-----------------------------+        +-----------------------------+
|         Windows Edge Agent         |        |       Hosted REST API       |        |      Supabase Postgres      |
|        (Python 3.10 / PyQt)        |  HTTPS |          (FastAPI)          |  Pool  |            + RLS            |
|  - MediaPipe Pose (Volatile RAM)   |=======>|  - Asymmetric JWKS Auth     |=======>|  - Multi-Tenant RLS         |
|  - RULA Upper-Body Scorer          | Batch  |  - Device Auth & Idempotency|  6543  |  - Assessment Events        |
|  - SQLite FIFO Sync Spool          | Ingest |  - Fail-Closed Security     |        |  - Revocable Devices        |
|  - Compact Floating Overlay        |        |  - Rate Limiting & Logs     |        |  - pg_cron Retention Purge  |
+------------------------------------+        +-----------------------------+        +-----------------------------+
                                                             ^
                                                             | HTTPS / JWT
                                              +-----------------------------+
                                              |     React Web Dashboard     |
                                              |      (React 18 / Vite)      |
                                              |  - Supabase Auth            |
                                              |  - Non-Interpolated Trends  |
                                              |  - Device Enrollment/Revoke |
                                              |  - Sanitized CSV Export     |
                                              +-----------------------------+
```

---

## 3. System Requirements & Prerequisites

| Component | Requirements |
|---|---|
| **Python** | Python `3.10.x` (64-bit AMD64). Verified on Python 3.10.11. |
| **Node.js** | Node.js `>= 18.x` and npm `>= 9.x`. Verified on Node.js v22.23.2, npm 10.9.8. |
| **OS Support** | **Windows 10/11 (64-bit)** for the Edge Agent (PySide6, Windows Credential Manager, webcam).<br>**Linux, macOS, or Windows** for the Hosted API and React Web Dashboard. |
| **Git** | Standard Git client. |
| **Cloud Services** | (Optional for production) [Supabase](https://supabase.com) (Postgres 15+ & Auth) and [Render](https://render.com). |

---

## 4. Repository Layout

```text
.
├── backend/                # FastAPI backend service (Render Web Service)
│   ├── app/                # Application modules (api, core, db, models, schemas, services)
│   ├── tests/              # Pytest test suite (auth, devices, telemetry, RLS, security)
│   ├── pyproject.toml      # Pinned backend dependencies & tools
│   ├── requirements.txt    # Production dependencies for container/Render builds
│   └── alembic.ini         # Developer schema migration utility
├── edge-agent/             # Windows desktop edge agent
│   ├── edge_ergo/          # Agent core (camera, vision, quality, features, scoring, overlay, storage, sync)
│   ├── tests/              # Unit and integration test suite (camera, pose, RULA, SQLite, sync)
│   ├── edge-ergo.spec      # PyInstaller standalone packaging specification
│   └── pyproject.toml      # Pinned edge agent dependencies & tools
├── frontend/               # Analytics web dashboard (Render Static Site)
│   ├── src/                # React source (app, components, features, lib, pages)
│   ├── package.json        # Pinned frontend dependencies
│   ├── vite.config.ts      # Vite & Vitest configuration
│   └── tailwind.config.ts  # Tailored design system tokens
├── supabase/               # Database migrations & local configuration
│   ├── config.toml         # Supabase CLI project configuration
│   ├── migrations/         # Canonical SQL migrations (schema, RLS policies, functions, pg_cron)
│   └── seed.sql            # Base organization seed
├── docs/                   # Authoritative architectural documentation & runbooks
│   ├── MANUAL_RUNBOOK.md   # Chronologically ordered, de-duplicated manual runbook (Groups A–H)
│   ├── ACCEPTANCE.md       # Full acceptance criteria & design traceability matrix
│   ├── ENVIRONMENT.md      # Standardized environment variables specification
│   ├── SCORING_METHOD.md   # Validated RULA upper-body screening methodology
│   ├── LIMITATIONS.md      # Physical camera and algorithmic boundaries
│   ├── PRIVACY.md          # Workplace privacy notice and data flow disclosure
│   ├── DEPLOYMENT.md       # Render cloud deployment guide
│   ├── DATABASE.md         # Database schema, RLS policies, and retention schedules
│   ├── SYNC_PROTOCOL.md    # Offline spooling and synchronization protocol
│   └── DECISIONS.md        # Architectural decision records (ADRs)
├── scripts/                # Automated verification, benchmarking, and build tooling
│   ├── build_agent.ps1     # Windows PyInstaller build and smoke automation script
│   ├── inspect_bundle.py   # Security scanner for packaged desktop bundle
│   ├── check_secrets.py    # Zero-tolerance secret pattern scanner
│   ├── smoke_test.py       # Production acceptance black-box smoke suite
│   ├── benchmark_edge.py   # Edge CPU, RAM, and inference latency profiler
│   ├── dev.ps1             # PowerShell developer runner (test, lint, typecheck, build)
│   └── dev.sh              # Unix/Bash developer runner
├── render.yaml             # Render Infrastructure-as-Code Blueprint
├── MANUAL_TASKS.md         # High-level checklist referencing docs/MANUAL_RUNBOOK.md
└── PRD.md                  # Authoritative Product Requirements Document
```

---

## 5. Quick Start: Clean Checkout to Running All Three Components

Follow these exact steps from a freshly cloned repository.

### Step 5.1: Clone and Prepare Environment

```powershell
# Clone the repository
git clone https://github.com/<org>/edge-ergo-v3.git
cd edge-ergo-v3

# Verify prerequisites
python --version   # Must be Python 3.10.x
node --version     # Must be >= 18.x
```

---

### Step 5.2: Run Component 1 — Hosted REST API (FastAPI)

1. Open a terminal session in the `backend/` directory:
   ```bash
   cd backend
   ```

2. Copy the environment template:
   ```bash
   # Windows PowerShell
   Copy-Item .env.example .env
   # Or Bash
   cp .env.example .env
   ```
   *(In development mode with `APP_ENV=development`, default values allow running the API server locally without external cloud dependencies.)*

3. Install backend dependencies in your active Python 3.10 environment:
   ```bash
   pip install -e ".[dev]"
   ```

4. Launch the FastAPI server:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Verify it is running:**
   Open a separate terminal and query the readiness probe:
   ```bash
   curl http://localhost:8000/health/ready
   # Expected output: {"status":"ready","database":"...","timestamp":...}
   ```
   The interactive API docs are available in development at [http://localhost:8000/docs](http://localhost:8000/docs).

---

### Step 5.3: Run Component 2 — Web Dashboard (React + Vite)

1. Open a new terminal session in the `frontend/` directory:
   ```bash
   cd frontend
   ```

2. Copy the frontend environment template:
   ```bash
   # Windows PowerShell
   Copy-Item .env.example .env
   # Or Bash
   cp .env.example .env
   ```
   *(By default, `VITE_API_BASE_URL` points to `http://localhost:8000`.)*

3. Install dependencies:
   ```bash
   npm install
   ```

4. Start the Vite development server:
   ```bash
   npm run dev -- --port 5173
   ```

5. **Access the Dashboard:**
   Open your browser to [http://localhost:5173](http://localhost:5173).
   - In development mode, a persistent **"DEVELOPMENT FIXTURE DATA"** banner is available. This enables full exploration of the **Overview** (KPIs, non-interpolated trend charts, posture breakdown), **Assessments** (filter controls, joint angle drawer), **Devices** (workstation statuses, single-use token enrollment), and **Reports** (scope preview, sanitized CSV export) without requiring live Supabase cloud credentials.

---

### Step 5.4: Run Component 3 — Windows Desktop Edge Agent

1. Open a new terminal session in the `edge-agent/` directory:
   ```bash
   cd edge-agent
   ```

2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. **Run the Offline Self-Test:**
   Verifies OpenCV, MediaPipe, NumPy, PySide6, SQLite schema migrations in a temporary directory, and the feature extraction pipeline:
   ```bash
   python -m edge_ergo.main --selftest
   # Expected output: [PASS] Selftest completed successfully! Edge agent core is functional.
   ```

4. **Run in Simulation Mode (No Webcam Required):**
   Executes the desktop agent with synthetic in-memory posture frames and launches the compact floating overlay:
   ```bash
   python -m edge_ergo.main --fake-camera --dry-run
   ```
   - A dark charcoal floating overlay appears on your desktop.
   - You can drag the overlay anywhere.
   - It updates smoothly without stealing focus from active applications (`Qt.WindowType.WindowDoesNotAcceptFocus`).

5. **Run with Live Webcam Posture Tracking:**
   ```bash
   python -m edge_ergo.main
   ```
   - Connects to your default webcam (hardware index 0) via OpenCV DirectShow.
   - Evaluates posture every 5 seconds.
   - When poor posture (e.g. forward head tilt > 20° or trunk slouching > 20°) is sustained for 3 consecutive intervals, gentle non-intrusive visual guidance is displayed.

6. **Enroll the Agent with the Local Hosted API:**
   - On the web dashboard at [http://localhost:5173/devices](http://localhost:5173/devices), click **Enroll New Device** and copy the generated token (e.g. `eet_...`).
   - Run the enrollment command:
     ```bash
     python -m edge_ergo.main enroll --api http://127.0.0.1:8000 --token <ENROLLMENT_TOKEN>
     ```
   - The device secret is stored securely in **Windows Credential Manager** (DPAPI). The agent can now sync posture telemetry batches to the local API.

---

### Step 5.5: Build the Standalone Windows Executable (Optional)

To package the agent into a self-contained Windows executable that requires no Python runtime:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_agent.ps1
```

The script:
1. Cleans previous builds.
2. Runs PyInstaller against `edge-agent/edge-ergo.spec`.
3. Runs `scripts/inspect_bundle.py` to ensure zero `.env` files, zero SQLite databases, and zero hardcoded secrets exist in the distribution.
4. Executes smoke verification: `edge-ergo.exe --version` and `edge-ergo.exe --selftest`.
5. Outputs the standalone distribution to `edge-agent/dist/edge-ergo/edge-ergo.exe`.

---

## 6. Automated Verification Runner

Execute the complete quality gate across all three components with a single command:

### Windows PowerShell:
```powershell
# Run all checks (secret scan, lint, typecheck, tests, production build)
.\scripts\dev.ps1 all

# Or run individual checks:
.\scripts\dev.ps1 check-secrets  # Zero-tolerance secret pattern scan
.\scripts\dev.ps1 lint           # Ruff (Python) and ESLint (TypeScript)
.\scripts\dev.ps1 typecheck      # Mypy and tsc -b
.\scripts\dev.ps1 test           # Pytest (backend + agent) and Vitest (frontend)
.\scripts\dev.ps1 build          # Frontend production bundle build
```

### Linux / macOS (Bash):
```bash
chmod +x ./scripts/dev.sh
./scripts/dev.sh all
```

---

## 7. Known Limitations and Unverified Claims

In accordance with PRD §12 and DESIGN §17, EdgeErgo strictly avoids claiming achievements that have not been physically verified. The following 4 items from [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) are categorized as **Pending manual** and await physical deployment or human clinical sign-off:

| Item | Requirement | Verification Status & Required Manual Action | Reference |
|---|---|---|---|
| **PRD §12 #16** | **Live Render Production Deployment** | **Pending manual cloud operator action.**<br>The Infrastructure Blueprint (`render.yaml`), health endpoints (`/health/live`, `/health/ready`), and local production verification harness (`scripts/verify_production_local.py`) pass 12/12 checks. However, live cloud instances on Render have not been provisioned. This requires a human operator to link the GitHub repository in the Render Dashboard and configure secrets. | [docs/MANUAL_RUNBOOK.md Group D](docs/MANUAL_RUNBOOK.md#group-d-render-cloud-deployment) |
| **PRD §12 #18** | **Clean-Machine Windows VM Test** | **Pending manual pilot workstation testing.**<br>The standalone Windows executable builds cleanly via PyInstaller and passes `--selftest` in the developer environment. Testing the executable on a fresh, non-developer Windows 10/11 laptop (clean OS without Python, Git, or C++ build tools installed) is scheduled for the pilot cohort roll-out. | [docs/MANUAL_RUNBOOK.md Group E](docs/MANUAL_RUNBOOK.md#group-e-windows-agent-packaging--clean-machine-test) |
| **PRD §12 #19** | **Real Hardware Performance Benchmarks** | **Pending physical pilot workstation measurement.**<br>The benchmarking profiler (`scripts/benchmark_edge.py`) is verified. In accordance with anti-fabrication policies, hardware latency (p50/p95), CPU %, and memory RSS fields in [docs/PERFORMANCE_TEMPLATE.md](docs/PERFORMANCE_TEMPLATE.md) are left unpopulated (`[   ]`) until measured on physical pilot participant laptops. | [docs/MANUAL_RUNBOOK.md Group G](docs/MANUAL_RUNBOOK.md#group-g-performance--hardware-measurements) |
| **PRD §12 #8, #21** | **Clinical Ergonomist Sign-Off & Consent** | **Pending pilot roll-out reviews.**<br>The RULA upper-body screening algorithm is scientifically documented in [docs/SCORING_METHOD.md](docs/SCORING_METHOD.md). Formal written sign-off from an independent Certified Professional Ergonomist (CPE) and physical proxy packet capture (mitmproxy/Wireshark) are to be completed prior to live employee tracking. | [docs/MANUAL_RUNBOOK.md Group H](docs/MANUAL_RUNBOOK.md#group-h-clinical--legal-reviews) |

---

## 8. Authoritative Documentation Index

For in-depth operational procedures, consult the linked documents:

- **[docs/MANUAL_RUNBOOK.md](docs/MANUAL_RUNBOOK.md)** — Consolidated, chronologically ordered manual runbook (Sections A–H).
- **[docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)** — Pilot acceptance criteria and design traceability matrix.
- **[docs/PROGRESS.md](docs/PROGRESS.md)** — Comprehensive implementation log and verification evidence.
- **[docs/SCORING_METHOD.md](docs/SCORING_METHOD.md)** — Validated RULA upper-body scoring methodology and lookups.
- **[docs/LIMITATIONS.md](docs/LIMITATIONS.md)** — Scientific limitations of 2D webcam posture screening.
- **[docs/PRIVACY.md](docs/PRIVACY.md)** — Technical privacy guarantees and employee pilot notice.
- **[docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)** — Canonical environment variable dictionary.
- **[docs/DATABASE.md](docs/DATABASE.md)** — Database schema, RLS policy matrix, and retention schedules.
- **[docs/SYNC_PROTOCOL.md](docs/SYNC_PROTOCOL.md)** — Offline spooling and synchronization protocol specification.
- **[docs/AUTHZ_MATRIX.md](docs/AUTHZ_MATRIX.md)** — Multi-role API and database authorization matrix.
- **[docs/DECISIONS.md](docs/DECISIONS.md)** — Architectural decision records (ADRs).
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** — Render cloud deployment procedures and origin locking.
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** — Diagnostic workflows for camera, auth, and sync issues.
