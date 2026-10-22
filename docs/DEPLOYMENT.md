# EdgeErgo V3 — Production Deployment Guide (Render & Supabase)

**Platform:** Render (Hosted API Web Service & Web Dashboard Static Site)  
**Database & Auth:** Supabase PostgreSQL (via Connection Pooler) + Supabase Auth  
**Blueprint:** `render.yaml` in repository root  
**Target Architecture:** Multi-tenant production deployment with fail-closed configuration

---

## 1. Architecture & Hosting Strategy

EdgeErgo V3 decouples the cloud footprint into:
1. **Hosted API (`edge-ergo-api`):** Python FastAPI ASGI service running on Render Web Service. It performs device credential authentication, ingest validation, telemetry aggregation, and dashboard reporting.
2. **Web Dashboard (`edge-ergo-dashboard`):** React 18 + Vite SPA deployed as a Render Static Site with global CDN distribution and SPA rewrite fallback.
3. **Database & Auth:** Supabase-managed PostgreSQL connection pooler (port 6543) accessed via a dedicated least-privilege `edgeergo_api` role, combined with Supabase Auth for asymmetric JWT verification.

```
+-------------------------------------------------------------------------+
|                               RENDER CLOUD                              |
|                                                                         |
|  +------------------------------+     +------------------------------+  |
|  |     edge-ergo-dashboard      |     |        edge-ergo-api         |  |
|  |     (Render Static Site)     |     |     (Render Web Service)     |  |
|  |   SPA: /* -> /index.html     |     |  Uvicorn 0.0.0.0:$PORT       |  |
|  |   Global CDN Edge Delivery   |     |  /health/ready (DB probe)    |  |
|  +--------------+---------------+     +--------------+---------------+  |
+-----------------|------------------------------------|------------------+
                  | HTTPS                              | TLS (Pooled 6543)
                  v                                    v
+-------------------------------------------------------------------------+
|                             SUPABASE CLOUD                              |
|                                                                         |
|  +------------------------------+     +------------------------------+  |
|  |        Supabase Auth         |     |     Supabase PostgreSQL      |  |
|  |  JWKS: auth/v1/.well-known   |     |  Schema: public & auth stub  |  |
|  |  Site URL & Redirect Whitelist|    |  RLS + Dedicated API Role    |  |
|  +------------------------------+     +------------------------------+  |
+-------------------------------------------------------------------------+
```

---

## 2. Prerequisites & Credentials Checklist

Before beginning deployment, gather the following values from your Supabase project dashboard:

| Value Name | Where to Find in Supabase Dashboard | Destination in Render |
|---|---|---|
| **Project URL** | `Project Settings > API > Project URL` (e.g., `https://xyzcompany.supabase.co`) | Backend `SUPABASE_URL`<br>Frontend `VITE_SUPABASE_URL` |
| **Publishable / Anon Key** | `Project Settings > API > Project API keys > anon public` | Frontend `VITE_SUPABASE_PUBLISHABLE_KEY` |
| **Database Pooler URL** | `Project Settings > Database > Connection string > Transaction Pooler (port 6543)` | Backend `DATABASE_URL` |
| **JWT Issuer URL** | Append `/auth/v1` to Project URL (e.g., `https://xyzcompany.supabase.co/auth/v1`) | Backend `SUPABASE_JWT_ISSUER` |
| **Public JWKS URL** | Append `/auth/v1/.well-known/jwks.json` to Project URL | Backend `SUPABASE_JWKS_URL` |

> [!CAUTION]
> **Never configure `SUPABASE_SERVICE_ROLE_KEY` in frontend environment variables.** The EdgeErgo backend uses direct PostgreSQL role authentication and does not require the service-role key for normal operations.

---

## 3. Step-by-Step Deployment (Render Blueprint)

### Step 3.1: Create Render Blueprint Instance
1. Log in to the [Render Dashboard](https://dashboard.render.com).
2. Click **New +** > **Blueprint**.
3. Connect your GitHub repository (`Edge-Ergo`).
4. Render will parse `render.yaml` and discover two services:
   - `edge-ergo-api` (Web Service)
   - `edge-ergo-dashboard` (Static Site)
5. Under **Environment Variables**, populate the un-synced (`sync: false`) parameters:
   - `SUPABASE_URL`: e.g. `https://xyzcompany.supabase.co`
   - `SUPABASE_JWT_ISSUER`: e.g. `https://xyzcompany.supabase.co/auth/v1`
   - `SUPABASE_JWKS_URL`: e.g. `https://xyzcompany.supabase.co/auth/v1/.well-known/jwks.json`
   - `DATABASE_URL`: Transaction pooler string (e.g. `postgresql+asyncpg://edgeergo_api:password@aws-0-us-west-1.pooler.supabase.com:6543/postgres`)
   - `FRONTEND_ORIGIN`: Set temporarily to placeholder `https://edge-ergo-dashboard.onrender.com` (see Section 4 for sequencing)
   - `VITE_API_BASE_URL`: Set to planned API URL `https://edge-ergo-api.onrender.com`
   - `VITE_SUPABASE_URL`: e.g. `https://xyzcompany.supabase.co`
   - `VITE_SUPABASE_PUBLISHABLE_KEY`: Public anon key
6. Click **Apply**.

---

## 4. Strict Deployment Sequencing & CORS Resolution Order

FastAPI enforces strict CORS validation (`FRONTEND_ORIGIN` cannot be `*` or `localhost` in production). To prevent chicken-and-egg deployment failures, execute the deployment in this exact order:

```mermaid
sequenceDiagram
    autonumber
    participant Dev as DevOps Engineer
    participant API as Render API Web Service
    participant FE as Render Dashboard Static Site
    participant SB as Supabase Auth Console

    Dev->>API: 1. Deploy API Web Service (initial build)
    API-->>Dev: API deployed at https://edge-ergo-api.onrender.com
    Dev->>FE: 2. Deploy Frontend Static Site with VITE_API_BASE_URL
    FE-->>Dev: Frontend deployed at https://edge-ergo-dashboard.onrender.com
    Dev->>API: 3. Set FRONTEND_ORIGIN = https://edge-ergo-dashboard.onrender.com
    Dev->>API: 4. Trigger API Manual Redeploy (clears restart grace)
    Dev->>SB: 5. Configure Supabase Auth Site URL & Redirect Whitelist
```

### Details for Step 5 (Supabase Auth Configuration):
1. Navigate to **Supabase Dashboard > Authentication > URL Configuration**.
2. Set **Site URL** to:
   ```text
   https://edge-ergo-dashboard.onrender.com
   ```
3. Under **Redirect URLs**, add:
   ```text
   https://edge-ergo-dashboard.onrender.com/*
   https://edge-ergo-dashboard.onrender.com/assessments
   https://edge-ergo-dashboard.onrender.com/devices
   https://edge-ergo-dashboard.onrender.com/reports
   ```
4. Click **Save**.

---

## 5. Free-Tier vs Starter Plan & Cold-Start Tolerances

Render offers both Free and Starter plans:

| Feature | Render Free Tier | Starter Plan ($7/mo — Recommended) |
|---|---|---|
| **Always-On** | No (Spins down after 15 min idle) | **Yes (0% spin-down, 24/7)** |
| **Cold Start Latency** | ~50 seconds on initial wake-up | **Zero cold start latency** |
| **Zero-Downtime Deployments** | No | **Yes (health-checked rolling deploys)** |
| **Memory Limit** | 512 MB | **512 MB dedicated** |

### How EdgeErgo Tolerates Free-Tier Cold Starts:
If deployed on the Free tier, incoming API requests after 15 minutes of inactivity will wait ~50 seconds while the container initializes.
- **Web Dashboard:** Shows standard loading skeletons; frontend API queries use a 30-second abort controller.
- **Edge Agent (`SyncWorker`):** Uses truncated exponential backoff (2.0s to 300.0s) with non-negative random jitter (0.0s to 3.0s). If an upload attempt times out or receives HTTP 502/504 while Render is warming up, the observations remain queued in SQLite and retry seamlessly once the container is ready. **Zero telemetry data is ever dropped.**

### Optional Uptime Ping (Free Tier Only):
To prevent free-tier containers from sleeping during workday hours, configure a free monitoring check (e.g., [UptimeRobot](https://uptimerobot.com) or [BetterStack](https://betterstack.com)):
- **Monitor Type:** HTTP(s)
- **URL:** `https://edge-ergo-api.onrender.com/health/live`
- **Interval:** Every 10 minutes

---

## 6. Health Checks & Zero-Downtime Verification

In `render.yaml`, the backend specifies:
```yaml
healthCheckPath: /health/ready
```

### Why `/health/ready` over `/health/live`?
- `/health/live` returns HTTP 200 simply if Uvicorn is executing.
- `/health/ready` actively executes `SELECT 1;` against PostgreSQL.
- Using `/health/ready` guarantees Render will **not** route live user traffic to newly built instances until the database connection pooler is active and verified.

---

## 7. Production Logging & Security Redaction

FastAPI logs in production are formatted as single-line structured JSON records sent to `stdout`. Render captures `stdout` natively and displays it in the Render service log viewer.

### Redaction Invariants:
1. `Authorization` headers (Bearer tokens and Device credentials) are redacted (`Bearer [REDACTED]`).
2. Request payload bodies are never logged.
3. Database passwords and connection URIs are scrubbed.
4. Error responses return standard `{error: {code, message, request_id}}` schemas without stack traces.

---

## 8. Rollback Procedures

If an issue is identified in production:
1. In the Render Dashboard, navigate to **Services > edge-ergo-api** (or `edge-ergo-dashboard`).
2. Go to the **Deploys** tab.
3. Identify the previous successful commit / build.
4. Click the three dots `...` next to the deploy and select **Rollback to this deploy**.
5. Render immediately spins up the prior container image without re-building.

---

## 9. Post-Deployment Verification via Smoke Test Suite

After deploying both services, run the automated smoke test suite:

```bash
# Run against live production deployment
python scripts/smoke_test.py \
  --api-url https://edge-ergo-api.onrender.com \
  --frontend-url https://edge-ergo-dashboard.onrender.com
```

### Optional Authenticated Verification:
```bash
python scripts/smoke_test.py \
  --api-url https://edge-ergo-api.onrender.com \
  --frontend-url https://edge-ergo-dashboard.onrender.com \
  --token "<SUPABASE_USER_JWT>" \
  --device-cred "eed_<public_id>.<secret>"
```

Alternatively, trigger the GitHub Actions workflow manually via:
**GitHub Repository > Actions > Deployment Smoke Tests > Run workflow**.

---

## 10. Operational Troubleshooting Guide

| Symptom | Probable Cause | Corrective Action |
|---|---|---|
| **503 on `/health/ready`** | Database pooler unreachable or invalid credentials | Verify `DATABASE_URL` uses transaction pooler port `6543` (not direct `5432`). Verify password has no unencoded special characters. |
| **CORS Blocked in Browser** | `FRONTEND_ORIGIN` mismatch | Check browser DevTools console. Ensure `FRONTEND_ORIGIN` matches exact protocol, domain, and port without a trailing slash (e.g. `https://edge-ergo-dashboard.onrender.com`). |
| **401 Unauthorized on Login** | Misconfigured JWT issuer or JWKS endpoint | Ensure `SUPABASE_JWT_ISSUER` has `/auth/v1` and `SUPABASE_JWKS_URL` points to `auth/v1/.well-known/jwks.json`. |
| **404 on Page Refresh** | Static site SPA rewrite missing | Confirm `render.yaml` includes `routes: [{type: rewrite, source: /*, destination: /index.html}]`. |
| **500 on Device Upload** | Schema mismatch or invalid tenant ID | Inspect Render backend logs with Request ID to view sanitized error code. |
