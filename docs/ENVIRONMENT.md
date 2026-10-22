# EdgeErgo V3 — Standardized Environment Variables

This document defines all environment variables across EdgeErgo V3.
All variables must use placeholders in `.env.example` files. No real secrets may be committed to source control.

---

## 1. Web Frontend (`frontend/.env.example`)

These variables are consumed at build time by Vite and bundled into browser-accessible assets.
**Never place server-side secrets or service-role keys here.**

| Variable Name | Type | Description | Example Placeholder |
|---|---|---|---|
| `VITE_SUPABASE_URL` | URL | Public URL of the Supabase project | `https://your-project.supabase.co` |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | String | Public publishable / anon client key for browser authentication | `your-supabase-publishable-key` |
| `VITE_API_BASE_URL` | URL | Base URL of the deployed FastAPI backend service | `http://127.0.0.1:8000` |

---

## 2. Hosted API Backend (`backend/.env.example`)

These variables are consumed by the FastAPI service in `app/core/config.py`.

| Variable Name | Type | Default | Description |
|---|---|---|---|
| `APP_ENV` | String | `development` | Application runtime environment (`development`, `test`, `production`) |
| `API_V1_PREFIX` | String | `/api/v1` | URL prefix for version 1 API endpoints |
| `FRONTEND_ORIGIN` | String | `http://localhost:5173` | Allowed CORS origin (deployed frontend URL in production) |
| `SUPABASE_URL` | URL | - | Supabase project URL (e.g. `https://your-project.supabase.co`) |
| `SUPABASE_JWT_ISSUER` | URL | - | Supabase JWT issuer URL (e.g. `https://your-project.supabase.co/auth/v1`) |
| `SUPABASE_JWKS_URL` | URL | - | Supabase public JWKS endpoint (e.g. `https://your-project.supabase.co/auth/v1/.well-known/jwks.json`) |
| `SUPABASE_JWT_AUDIENCE` | String | `authenticated` | Expected JWT audience claim |
| `DATABASE_URL` | Connection String | - | PostgreSQL connection URL via connection pooler (dedicated least-privilege role) |
| `TEST_DATABASE_URL` | Connection String | `postgresql+asyncpg://postgres:password@localhost:5432/edgeergo_test` | Dedicated connection URL for automated tests |
| `LOG_LEVEL` | String | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ENROLLMENT_TOKEN_TTL_MINUTES` | Integer | `15` | Single-use device enrollment token expiry window in minutes |
| `MAX_BATCH_SIZE` | Integer | `100` | Maximum number of assessment events allowed per batch upload |
| `MAX_EXPORT_ROWS` | Integer | `10000` | Maximum number of records returned in a single CSV export |
| `MAX_REQUEST_BODY_SIZE_BYTES` | Integer | `2097152` | Maximum request payload body size in bytes (default 2 MB) |
| `DEVICE_ONLINE_WINDOW_SECONDS` | Integer | `180` | Window in seconds within which a device is considered online (3x interval) |
| `ENROLLMENT_RATE_LIMIT_PER_MINUTE` | Integer | `10` | Max device enrollment attempts per minute per IP |
| `FAILED_AUTH_RATE_LIMIT_PER_MINUTE` | Integer | `20` | Max failed authentication attempts per minute per IP |
| `ENABLE_API_DOCS` | Boolean | `true` | Whether Swagger UI (`/docs`) and ReDoc (`/redoc`) are enabled (strictly `false` in production) |
| `SUPABASE_SERVICE_ROLE_KEY` | String (Optional) | `null` | **OPTIONAL SERVER-ONLY VARIABLE**. Documented as NOT required for normal operation since database access uses direct least-privilege PostgreSQL role. Must never be exposed to frontend or edge agent. |
| `SUPABASE_JWT_SECRET` | String (Optional) | `null` | Optional legacy HS256 secret for local development/testing only. |

---

## 3. Windows Edge Agent (`edge-agent/.env.example` / config)

These variables configure local workstation behavior. No secrets or administrative tokens are ever configured here; device authentication secrets are provisioned via enrollment and stored in Windows Credential Manager.

| Variable Name | Type | Default | Description |
|---|---|---|---|
| `EDGE_ERGO_API_BASE_URL` | URL | `http://127.0.0.1:8000` | Hosted API base URL for enrollment, heartbeats, and event synchronization |
| `EDGE_ERGO_DATA_DIR` | Path | `~/.edge_ergo` | Local directory for SQLite database, settings, and logs |
| `EDGE_ERGO_LOG_LEVEL` | String | `INFO` | Local agent logging level |

---

## 4. Environment Matrix (Dev / Test / Prod Separation — FR-061)

To prevent test-data contamination and credential leakage, EdgeErgo enforces strict isolation across runtime tiers:

| Parameter | Development (`APP_ENV=development`) | Automated Tests (`APP_ENV=test`) | Production (`APP_ENV=production`) |
|---|---|---|---|
| **Database Connection** | Local PostgreSQL (`postgres:password@localhost:5432/postgres`) | Isolated Test DB (`postgres:password@localhost:5432/edgeergo_test`) | Supabase Transaction Pooler (`edgeergo_api:SECRET@aws-0.pooler.supabase.com:6543/postgres`) |
| **Fail-Closed Validation** | Permissive (placeholders allowed for rapid bootstrapping) | Strict (rejects live production DB credentials) | **Strict Fail-Closed** (blocks start if `DATABASE_URL` has localhost/password, if origin is `*`, or if placeholders exist) |
| **CORS `FRONTEND_ORIGIN`** | `http://localhost:5173` | Not enforced in pure unit tests | Exact Render Static Site domain (`https://edge-ergo-dashboard.onrender.com`) |
| **API Documentation (`/docs`)** | Enabled (`ENABLE_API_DOCS=true`) | Enabled (`ENABLE_API_DOCS=true`) | **Disabled** (`ENABLE_API_DOCS=false`, returns 404) |
| **JWT Verification** | Local JWKS or HS256 secret stub | In-memory ephemeral RSA-256 test keypair (`TestJWTSigner`) | Real Supabase Asymmetric JWKS (`auth/v1/.well-known/jwks.json`) |
| **Device Credential Store** | Windows Credential Manager or local dev | In-memory store (`MemoryCredentialStore`) | Windows Credential Manager (OS Vault) |
| **Logging Format** | Human-readable colored console | Minimal test runner output | Structured JSON with automated redaction filters |
| **Camera Processing** | Live webcam or `--fake-camera` synthetic frames | Synthetic mathematical pose landmarks | Live webcam (ephemeral RAM buffers only) |

