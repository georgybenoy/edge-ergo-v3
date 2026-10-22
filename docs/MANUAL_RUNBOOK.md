# EdgeErgo V3 — Consolidated Manual Runbook

This runbook is the single, de-duplicated, chronologically ordered guide for all manual steps required to deploy, verify, and validate EdgeErgo V3 for enterprise pilots.

Every item provides:
1. **Prerequisites & Target**
2. **Exact Commands or Clicks**
3. **Expected Result**
4. **Acceptance Criteria Closed** (referenced to [docs/ACCEPTANCE.md](ACCEPTANCE.md))

---

## Group A: Accounts & Secrets Provisioning

### A.1 GitHub Repository Setup & Push Protection
- **Target:** GitHub Repository
- **Actions:**
  1. Create a private GitHub repository named `edge-ergo-v3`.
  2. Add the remote and push the codebase:
     ```bash
     git remote add origin https://github.com/<org>/edge-ergo-v3.git
     git branch -M main
     git push -u origin main
     ```
  3. In GitHub web UI: Navigate to **Settings** > **Code security and analysis**.
  4. Enable **Secret scanning** and **Push protection**.
  5. In **Settings** > **Actions** > **General**, ensure Actions permissions are set to *Allow all actions and reusable workflows*.
- **Expected Result:** Main branch is pushed with 0 secrets. GitHub push protection actively blocks any accidental commit containing API keys or certificates.
- **Acceptance Checkbox Closed:** PRD §12 #1, PRD §12 #17.

### A.2 External Cloud Account Setup (Supabase & Render)
- **Target:** Supabase and Render Web Portals
- **Actions:**
  1. Create or log into an administrative account on [Supabase](https://supabase.com).
  2. Create an account on [Render](https://render.com).
  3. Ensure both accounts use hardware-backed 2FA (TOTP/FIDO2).
- **Expected Result:** Active cloud administrative accounts ready for project provisioning.
- **Acceptance Checkbox Closed:** PRD §12 #1.

---

## Group B: Supabase Database, Auth & Retention Setup

### B.1 Project Creation & CLI Linking
- **Target:** Supabase Cloud & Local Terminal
- **Actions:**
  1. Create two Supabase projects:
     - Production: `edgeergo-prod`
     - Staging/Testing: `edgeergo-staging`
  2. Log in with the Supabase CLI in your local terminal:
     ```bash
     npx supabase login
     ```
  3. Link your staging project for migration testing:
     ```bash
     npx supabase link --project-ref <STAGING_PROJECT_REF>
     ```
- **Expected Result:** `supabase/config.toml` links cleanly; `npx supabase status` displays remote project health.
- **Acceptance Checkbox Closed:** PRD §12 #3.

### B.2 Push Database Migrations & Verify RLS
- **Target:** Supabase PostgreSQL Database
- **Actions:**
  1. Push canonical migrations from the repository root:
     ```bash
     npx supabase db push
     ```
  2. Open Supabase Dashboard > **Database** > **Tables**.
  3. Verify the existence of the 8 core tables:
     - `organizations`
     - `profiles`
     - `organization_members`
     - `devices`
     - `device_enrollment_tokens`
     - `assessment_events`
     - `device_heartbeats`
     - `audit_events`
  4. Verify the `devices_public` view exists and excludes `credential_hash`.
  5. In **Authentication** > **Policies**, confirm Row Level Security (RLS) is toggled **ON** for all tables.
- **Expected Result:** Schema deploys cleanly. All application tables have RLS enabled with organization-scoping policies.
- **Acceptance Checkbox Closed:** PRD §12 #3, PRD §12 #5.

### B.3 Configure Application Postgres Role & Pooled Connection String
- **Target:** Supabase SQL Editor
- **Actions:**
  1. Open Supabase Dashboard > **SQL Editor**.
  2. Execute the following SQL to assign a secure random password to the least-privilege `edgeergo_api` application role:
     ```sql
     ALTER ROLE edgeergo_api WITH LOGIN PASSWORD '<STRONG_GENERATED_PASSWORD>';
     ```
  3. In **Project Settings** > **Database** > **Connection string**, select **Transaction Pooler** (port 6543).
  4. Construct the pooled database URL:
     ```text
     DATABASE_URL=postgresql://edgeergo_api:<STRONG_GENERATED_PASSWORD>@<PROJECT_REF>.pooler.supabase.com:6543/postgres?sslmode=require
     ```
- **Expected Result:** `edgeergo_api` has login rights and least-privilege access restricted strictly to application tables.
- **Acceptance Checkbox Closed:** PRD §12 #3, PRD §12 #17.

### B.4 Configure Supabase Auth & First Admin User
- **Target:** Supabase Authentication Dashboard
- **Actions:**
  1. Navigate to **Authentication** > **Providers** > **Email**:
     - Enable Email provider.
     - Toggle **OFF** "Allow new users to sign up" (ensures invite/admin-only access).
  2. In **Authentication** > **URL Configuration**:
     - Set **Site URL** to `http://localhost:5173` (for local run) or production frontend URL.
     - Add redirect patterns: `http://localhost:5173/**`, `https://*.onrender.com/**`.
  3. In **Authentication** > **Users**, click **Invite user** or **Add user** to create the initial admin account (e.g. `admin@company.com`).
  4. Open **SQL Editor** and bind the user to the default organization with the `admin` role:
     ```sql
     INSERT INTO public.organization_members (organization_id, user_id, role)
     SELECT o.id, u.id, 'admin'
     FROM public.organizations o
     CROSS JOIN auth.users u
     WHERE o.slug = 'default-org' AND u.email = 'admin@company.com'
     ON CONFLICT (organization_id, user_id) DO NOTHING;
     ```
  5. Check **Project Settings** > **API**: Note the JWKS URL:
     `https://<PROJECT_REF>.supabase.co/auth/v1/.well-known/jwks.json` and Issuer URL: `https://<PROJECT_REF>.supabase.co/auth/v1`.
- **Expected Result:** Public self-registration is blocked. The admin user exists in `organization_members` with `role = 'admin'`.
- **Acceptance Checkbox Closed:** PRD §12 #4, PRD §12 #5.

### B.5 Configure Automated pg_cron Retention Purge
- **Target:** Supabase Database Extensions & SQL Editor
- **Actions:**
  1. Navigate to **Database** > **Extensions** and ensure `pg_cron` is enabled.
  2. In **SQL Editor**, schedule the automated nightly purge:
     ```sql
     SELECT cron.schedule(
       'nightly-purge-expired-records',
       '0 3 * * *',
       'SELECT public.purge_expired_records(365, 30, 365);'
     );
     ```
  3. Verify registration:
     ```sql
     SELECT * FROM cron.job WHERE jobname = 'nightly-purge-expired-records';
     ```
- **Expected Result:** Nightly cron runs at 03:00 UTC purging telemetry older than 365 days, heartbeats older than 30 days, and audit events older than 365 days.
- **Acceptance Checkbox Closed:** PRD §12 #20.

---

## Group C: Local End-to-End Run

### C.1 Environment Configuration
- **Target:** Local Workspace
- **Actions:**
  1. Configure `backend/.env`:
     ```bash
     cp backend/.env.example backend/.env
     ```
     Edit `backend/.env` with:
     ```ini
     APP_ENV=development
     DATABASE_URL=postgresql://edgeergo_api:<PASSWORD>@<PROJECT_REF>.pooler.supabase.com:6543/postgres?sslmode=require
     SUPABASE_URL=https://<PROJECT_REF>.supabase.co
     SUPABASE_JWT_ISSUER=https://<PROJECT_REF>.supabase.co/auth/v1
     SUPABASE_JWKS_URL=https://<PROJECT_REF>.supabase.co/auth/v1/.well-known/jwks.json
     FRONTEND_ORIGIN=http://localhost:5173
     LOG_LEVEL=INFO
     ```
  2. Configure `frontend/.env`:
     ```bash
     cp frontend/.env.example frontend/.env
     ```
     Edit `frontend/.env` with:
     ```ini
     VITE_SUPABASE_URL=https://<PROJECT_REF>.supabase.co
     VITE_SUPABASE_PUBLISHABLE_KEY=<SUPABASE_ANON_KEY>
     VITE_API_BASE_URL=http://localhost:8000
     ```
- **Expected Result:** Both configuration files are populated without placeholder errors.
- **Acceptance Checkbox Closed:** PRD §12 #1.

### C.2 Start Local Backend & Frontend Services
- **Target:** Two Terminal Sessions
- **Actions:**
  1. **Terminal 1 (Backend):**
     ```bash
     cd backend
     python -m uvicorn app.main:app --port 8000 --reload
     ```
     Verify health check:
     ```bash
     curl http://localhost:8000/health/ready
     # Returns: {"status":"ready","database":"connected","timestamp":...}
     ```
  2. **Terminal 2 (Frontend):**
     ```bash
     cd frontend
     npm run dev -- --port 5173
     ```
     Open `http://localhost:5173` in a web browser.
- **Expected Result:** Backend is healthy; frontend renders the login page without any `<ConfigMissingScreen />` error.
- **Acceptance Checkbox Closed:** PRD §12 #1, PRD §12 #2.

### C.3 Authenticate & Generate Device Enrollment Token
- **Target:** Browser at `http://localhost:5173`
- **Actions:**
  1. Sign in with the admin credentials created in **B.4**.
  2. Confirm navigation tabs: **Overview**, **Assessments**, **Devices**, **Reports**, **Settings**.
  3. Navigate to **Devices** (`/devices`).
  4. Click **Enroll New Device**:
     - Label: `Pilot Station 01`
     - Expiry: `15 minutes`
  5. Copy the generated single-use token (e.g. `eet_...`).
- **Expected Result:** Plaintext token is shown once. Dismissing the modal clears it from memory. The device list displays the pending token with an expiration countdown.
- **Acceptance Checkbox Closed:** PRD §12 #4, DESIGN §17 #10.

### C.4 Enroll Edge Agent & Seed Telemetry
- **Target:** Terminal 3
- **Actions:**
  1. Enroll the workstation:
     ```bash
     cd edge-agent
     python -m edge_ergo.main enroll --api http://127.0.0.1:8000 --token <ENROLLMENT_TOKEN>
     ```
  2. Run the agent in fake-camera mode or launch the GUI:
     ```bash
     python -m edge_ergo.main --fake-camera --dry-run
     ```
  3. Seed test telemetry batches:
     ```bash
     python scripts/dev_send_test_event.py --api-url http://localhost:8000 --count 10 --validity valid
     ```
  4. In the browser, navigate to:
     - **Overview** (`/`): Verify KPI cards show sample counts, Recharts trend renders discrete points, and Posture Breakdown displays percentages.
     - **Assessments** (`/assessments`): Filter by date and device; click a row to view joint angles in the detail drawer.
     - **Reports** (`/reports`): Click **Export CSV** and verify the downloaded file has escaped formula cells (`'` prefix on `=,+,-,@`) and strict allowlisted headers.
- **Expected Result:** End-to-end enrollment, batch ingestion, dashboard data visualization, and sanitized CSV export succeed.
- **Acceptance Checkbox Closed:** PRD §12 #2, PRD §12 #10, PRD §12 #15, DESIGN §17 #3, #4, #5.

---

## Group D: Render Cloud Deployment

### D.1 Deploy Infrastructure Blueprint via Render Dashboard
- **Target:** Render Web Console (https://dashboard.render.com)
- **Actions:**
  1. Click **New +** > **Blueprint**.
  2. Connect your GitHub repository (`edge-ergo-v3`).
  3. Render detects `render.yaml` declaring:
     - `edge-ergo-backend` (Python Web Service, rootDir: `backend`)
     - `edge-ergo-frontend` (Static Site, rootDir: `frontend`)
  4. Under `edge-ergo-backend` Environment tab, configure secrets:
     - `DATABASE_URL`: Your Supabase pooler URL (port 6543)
     - `SUPABASE_URL`: `https://<PROJECT_REF>.supabase.co`
     - `SUPABASE_JWT_ISSUER`: `https://<PROJECT_REF>.supabase.co/auth/v1`
     - `SUPABASE_JWKS_URL`: `https://<PROJECT_REF>.supabase.co/auth/v1/.well-known/jwks.json`
     - `FRONTEND_ORIGIN`: Temporary placeholder `https://localhost` (updated in D.2)
  5. Under `edge-ergo-frontend` Environment tab, configure:
     - `VITE_SUPABASE_URL`: `https://<PROJECT_REF>.supabase.co`
     - `VITE_SUPABASE_PUBLISHABLE_KEY`: `<SUPABASE_ANON_KEY>`
     - `VITE_API_BASE_URL`: Temporary placeholder (updated in D.2)
  6. Click **Apply**.
- **Expected Result:** Render creates both services.
- **Acceptance Checkbox Closed:** PRD §12 #16.

### D.2 Two-Stage Deployment Sequencing & Origin Lock
- **Target:** Render Web Console
- **Actions:**
  1. Wait for `edge-ergo-backend` build to complete. Copy its assigned URL:
     `https://edge-ergo-backend-<hash>.onrender.com`
  2. Update `edge-ergo-frontend` environment variable:
     `VITE_API_BASE_URL=https://edge-ergo-backend-<hash>.onrender.com`
  3. Trigger frontend deploy. Once complete, copy the frontend URL:
     `https://edge-ergo-frontend-<hash>.onrender.com`
  4. Update `edge-ergo-backend` environment variable:
     `FRONTEND_ORIGIN=https://edge-ergo-frontend-<hash>.onrender.com`
  5. Trigger backend redeploy to enforce CORS whitelisting.
  6. In Supabase Dashboard > **Authentication** > **URL Configuration**:
     - Set **Site URL** to `https://edge-ergo-frontend-<hash>.onrender.com`
     - Add `https://edge-ergo-frontend-<hash>.onrender.com/**` to **Redirect URLs**.
- **Expected Result:** Backend strictly whitelists the frontend domain in CORS headers. Supabase Auth redirects correctly to the production domain.
- **Acceptance Checkbox Closed:** PRD §12 #16.

### D.3 Execute Automated Deployment Smoke Tests
- **Target:** Local Terminal
- **Actions:**
  1. Run the black-box smoke suite against the live Render URLs:
     ```bash
     python scripts/smoke_test.py \
       --api-url https://edge-ergo-backend-<hash>.onrender.com \
       --frontend-url https://edge-ergo-frontend-<hash>.onrender.com
     ```
  2. Confirm output reports 10/10 tests passed (or 12/12 with test tokens):
     - Liveness & Readiness: HTTP 200
     - Security Headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
     - CORS Origin: Rogue origin blocked with 400/403
     - Unauthenticated `/me`: HTTP 401
     - Docs disabled: `/docs` returns HTTP 404
     - Static SPA rewrite: `/assessments` returns HTTP 200 with index HTML
     - Bundle secret scan: 0 leaked keys in JavaScript assets
  3. If using Render free tier, register an external ping monitor (e.g. UptimeRobot) targeting `https://<backend-url>/health/live` every 10 minutes to prevent spin-down delays.
- **Expected Result:** All production security and routing checks pass.
- **Acceptance Checkbox Closed:** PRD §12 #16.

---

## Group E: Windows Agent Packaging & Clean-Machine Test

### E.1 Build Standalone Executable
- **Target:** Windows Build Machine (PowerShell)
- **Actions:**
  1. Run the build pipeline:
     ```powershell
     powershell -ExecutionPolicy Bypass -File scripts/build_agent.ps1
     ```
  2. The script:
     - Cleans old artifacts.
     - Runs PyInstaller on `edge-agent/edge-ergo.spec`.
     - Invokes `scripts/inspect_bundle.py` verifying zero `.env`, zero `*.sqlite`, zero media files, and zero secrets.
     - Runs smoke tests: `edge-ergo.exe --version` and `edge-ergo.exe --selftest`.
  3. Compress the output folder into a portable archive:
     ```powershell
     Compress-Archive -Path edge-agent/dist/edge-ergo -DestinationPath edge-ergo-v3.0.0-win64.zip -Force
     ```
- **Expected Result:** `edge-ergo-v3.0.0-win64.zip` is created (~120 MB zipped, ~350 MB uncompressed).
- **Acceptance Checkbox Closed:** PRD §12 #18.

### E.2 Clean Windows Machine Deployment Drill
- **Target:** Clean Windows 10/11 Workstation (No Python, No Git, No VS Code installed)
- **Actions:**
  1. Copy `edge-ergo-v3.0.0-win64.zip` to the test PC via USB drive or network share.
  2. Extract archive to `C:\Program Files\EdgeErgo` or `%LOCALAPPDATA%\Programs\EdgeErgo`.
  3. Open Command Prompt in the extracted folder:
     ```cmd
     edge-ergo.exe --version
     edge-ergo.exe --selftest
     ```
  4. Launch the application:
     ```cmd
     edge-ergo.exe
     ```
  5. Verify:
     - No "Missing VCRUNTIME140.dll" or other dynamic linking errors occur.
     - The dark charcoal floating overlay appears in the top-right corner.
     - The system tray icon appears with context menu options: *Settings*, *Pause Tracking*, *Quit*.
- **Expected Result:** Edge agent launches cleanly out-of-the-box on vanilla Windows.
- **Acceptance Checkbox Closed:** PRD §12 #18, DESIGN §17 #13.

### E.3 Camera Disconnect, Privacy Toggle & Focus Non-Interference
- **Target:** Clean Workstation with Webcam
- **Actions:**
  1. While the agent is running, open **Windows Settings** > **Privacy & Security** > **Camera**.
  2. Toggle **Camera access** to **OFF**.
     - Verify overlay status immediately shifts to `Camera unavailable`.
     - Confirm the application does not crash.
  3. Toggle **Camera access** back to **ON**.
     - Verify overlay automatically reconnects and returns to `Active`.
  4. Open **Notepad** and position the EdgeErgo overlay over the Notepad text area.
  5. Type continuously at high speed while the overlay updates every sampling cycle.
     - Verify no keystrokes are intercepted or lost (`Qt.WindowType.WindowDoesNotAcceptFocus`).
  6. Drag the overlay across two monitors with different DPI settings (e.g. 100% vs 150%).
     - Verify vector text, status pills, and buttons scale smoothly without blurring or clipping.
- **Expected Result:** Camera permission drops and hardware disconnects auto-recover safely. Typing is completely uninterrupted. DPI scaling is artifact-free.
- **Acceptance Checkbox Closed:** PRD §12 #6, DESIGN §17 #12, #13.

---

## Group F: Privacy & Security Evidence Verification

### F.1 Network Traffic Proxy Interception Drill
- **Target:** Workstation with Local HTTP Proxy (mitmproxy or Fiddler Classic)
- **Actions:**
  1. Configure proxy per [scripts/capture_traffic_notes.md](scripts/capture_traffic_notes.md).
  2. Launch edge agent configured to use the proxy and allow self-signed proxy cert:
     ```powershell
     $env:HTTPS_PROXY="http://127.0.0.1:8080"
     $env:REQUESTS_CA_BUNDLE="C:\Users\username\.mitmproxy\mitmproxy-ca-cert.cer"
     .\edge-ergo.exe
     ```
  3. Let the agent perform 5 minutes of tracking and batch uploads.
  4. Intercept outbound HTTP `POST /api/v1/assessments/batch` request bodies.
  5. Verify:
     - Payload contains strictly allowlisted keys: `event_id`, `captured_at`, `scoring_method`, `scoring_version`, `validity`, `score`, `neck_score`, `trunk_score`, `upper_arm_score`, `guidance_codes`, `software_version`.
     - Zero raw pixels, base64 images, face crops, or 33-point (x, y, z) pose coordinate arrays exist in request bodies.
- **Expected Result:** Total confirmation that raw biometric data never leaves workstation memory.
- **Acceptance Checkbox Closed:** PRD §12 #14, DESIGN §17 #9.

### F.2 Windows Credential Manager DPAPI Vault Inspection
- **Target:** Windows Control Panel
- **Actions:**
  1. Open **Control Panel** > **User Accounts** > **Credential Manager** > **Windows Credentials**.
  2. Scroll to **Generic Credentials**.
  3. Confirm the presence of an entry:
     - **Internet or network address:** `edge_ergo_device`
     - **User name:** `edp_<public_id>`
     - **Password:** `eed_<public_id>.<secret>`
  4. Inspect the agent's local SQLite database using SQLite CLI or DB Browser:
     ```cmd
     sqlite3 "%LOCALAPPDATA%\EdgeErgo\edge_ergo.db" "SELECT * FROM device_identity;"
     ```
  5. Confirm `device_identity` stores only `device_id`, `public_id`, and `api_base_url`—**never** the secret.
  6. Scan agent logs in `%LOCALAPPDATA%\EdgeErgo\logs\` for the secret string.
- **Expected Result:** The device secret is stored exclusively in Windows DPAPI storage. Zero plaintext secrets exist in database files or log outputs.
- **Acceptance Checkbox Closed:** PRD §12 #17.

### F.3 Administrative Device Revocation Drill
- **Target:** Web Dashboard & Workstation
- **Actions:**
  1. In the web dashboard, navigate to **Devices** (`/devices`).
  2. Locate the enrolled pilot workstation.
  3. Click **Revoke Device** and confirm the warning dialog.
  4. The device status immediately transitions to `Revoked`.
  5. Observe the workstation overlay on the next upload cycle (within 60 seconds):
     - The server rejects uploads with HTTP 401 (`INVALID_CREDENTIALS`).
     - The agent immediately halts further sync attempts.
     - The overlay status displays `Authorization error`.
     - Inspection of local SQLite shows unsynced observations remain queued safely without being deleted or corrupted.
- **Expected Result:** Server-side revocation takes effect instantly without token cache lag, and the agent fails closed.
- **Acceptance Checkbox Closed:** PRD §12 #12, PRD §12 #13.

---

## Group G: Performance & Hardware Measurements

### G.1 Pilot Workstation Profiling Drill
- **Target:** Pilot Laptops (Intel Core i5/i7 and AMD Ryzen 5/7)
- **Actions:**
  1. On the physical pilot laptop running on battery power (balanced mode), execute:
     ```powershell
     python scripts/benchmark_edge.py --real-camera --duration 120 --output station_benchmark.json
     ```
  2. Open the generated `station_benchmark.json`.
  3. Open [docs/PERFORMANCE_TEMPLATE.md](PERFORMANCE_TEMPLATE.md) and record the measured values:
     - Hardware specification (CPU model, core count, RAM)
     - Cold startup time (seconds)
     - Average inference latency (ms)
     - Latency percentiles (p50, p95)
     - Average CPU utilization (%)
     - Peak memory RSS footprint (MB)
     - Dropped frame count
  4. Verify measured values meet PRD §10 thresholds:
     - CPU < 20% on quad-core
     - RAM < 400 MB
     - p95 latency < 150 ms
- **Expected Result:** Performance template is filled with real measured hardware evidence.
- **Acceptance Checkbox Closed:** PRD §12 #19.

---

## Group H: Clinical & Legal Reviews

### H.1 Independent Ergonomics Methodology Review
- **Target:** External Certified Professional Ergonomist (CPE / Eur.Erg)
- **Actions:**
  1. Provide [docs/SCORING_METHOD.md](SCORING_METHOD.md) and [docs/LIMITATIONS.md](LIMITATIONS.md) to the consulting ergonomist.
  2. Review the upper-body screening scope:
     - Neck flexion/extension angles
     - Trunk flexion/inclination angles
     - Upper arm elevation & shoulder abduction
  3. Review the explicit exclusions:
     - Wrist twist / deviation (not observable via 2D webcam)
     - Load / force exertion (not measurable via camera)
     - Lower limb posture (occluded behind desk)
  4. Obtain written sign-off confirming the calculation is valid as a non-diagnostic postural screening tool.
- **Expected Result:** Clinical validation confirming scientific integrity and appropriate non-diagnostic classification.
- **Acceptance Checkbox Closed:** PRD §12 #8, PRD §12 #21.

### H.2 Workplace Privacy Notice & Employee Consent
- **Target:** Pilot Organization Legal & HR Counsel
- **Actions:**
  1. Provide the Employee Pilot Consent Notice template in [docs/PRIVACY.md](PRIVACY.md).
  2. Review the data flow disclosure:
     - Ephemeral frame processing in RAM
     - Zero image or video recording
     - Strict non-punitive, non-ranking covenant
     - 365-day central / 90-day local retention schedule
  3. Distribute the notice to pilot participants and collect signed acknowledgments before activating agent tracking.
- **Expected Result:** Pilot launch complies with labor and privacy standards (GDPR, CCPA, works council agreements).
- **Acceptance Checkbox Closed:** PRD §12 #21, DESIGN §17 #14.
