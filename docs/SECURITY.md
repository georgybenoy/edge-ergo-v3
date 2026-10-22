# EdgeErgo V3 — Security Architecture & Threat Model

## 1. Security Overview

EdgeErgo V3 processes ergonomic telemetry derived from on-device posture tracking across enterprise workstations.
The system is built upon a defense-in-depth model that guarantees:
1. Zero video frames or raw landmarks ever leave the edge workstation.
2. Complete organizational isolation across multi-tenant database layers.
3. Cryptographic authentication with constant-time secret verification.
4. Fail-closed production settings and automated secret scrubbing across logs and audit trails.

---

## 2. Threat Model & Mitigations

### 2.1 Token Theft & Impersonation
- **Threat:** An adversary intercepts or exfiltrates user session tokens or workstation credentials.
- **Mitigation:**
  - **Short-Lived Web JWTs:** Dashboard users authenticate via Supabase Auth RS256/ES256 access tokens. Tokens carry a short expiration (`exp`) and are validated against remote JWKS keys with automatic kid rotation.
  - **Asymmetric Key Rotation:** The backend fetches public signing keys from Supabase JWKS with a 1-hour cache TTL and forces a single refresh if an unfamiliar `kid` is encountered, enabling smooth zero-downtime key rotation.
  - **Single-Use Enrollment Tokens:** Enrollment tokens (`eet_<random>`) expire after 15 minutes and are consumed atomically in a database transaction (`consumed_at IS NULL`). Only the SHA-256 hash of the token is stored in PostgreSQL.
  - **Device Credential Hashing:** Workstation credentials (`eed_<public_id>.<secret>`) are hashed using SHA-256. Database records store only `credential_hash`. Plaintext secrets exist only on the workstation in Windows Credential Manager and are never returned after enrollment.

### 2.2 Device Spoofing & Timing Attacks
- **Threat:** An attacker attempts to forge credentials or uses response timing differences to enumerate registered devices.
- **Mitigation:**
  - **Constant-Time Verification:** Secrets are hashed and compared using `hmac.compare_digest`.
  - **Timing Equivalence:** If a device public ID is unknown, revoked, or pending, a dummy constant-time hash comparison is executed against a static dummy hash (`DUMMY_HASH`). All failure paths return an identical `401 Unauthorized` with error code `INVALID_CREDENTIALS` and the same error message.
  - **Client Cannot Choose Identity:** Workstations cannot specify `device_id` or `organization_id` in ingest payloads. Ingestion dependencies automatically resolve `(device_id, organization_id)` from the verified Bearer credential. Any attempt by device A to ingest telemetry for device B is structurally impossible.

### 2.3 Cross-Tenant Isolation
- **Threat:** An authenticated user from Organization A attempts to view, modify, or export devices, assessments, or audit logs belonging to Organization B.
- **Mitigation:**
  - **Verified DB Membership:** User roles and organization memberships are never taken from unverified client headers or JWT body payloads. They are resolved via parameterized SQL queries against `organization_members`.
  - **Row-Level Organization Scoping:** Every SQL query executed by the backend joins or filters by `WHERE organization_id = current_user.organization_id`.
  - **Existence Concealment:** If a user requests a resource (e.g. `GET /api/v1/devices/{device_id}`) that belongs to another organization, the query returns 0 rows and the API raises `404 Not Found` rather than `403 Forbidden`, concealing the existence of other tenants' resources.

### 2.4 Replay Attacks & Idempotent Ingestion
- **Threat:** Network retries, proxy retransmissions, or malicious replay duplicate assessment telemetry records.
- **Mitigation:**
  - **Compound Primary Key Uniqueness:** In PostgreSQL, `assessment_events` has a composite primary key `(device_id, event_id)`.
  - **PostgreSQL `ON CONFLICT DO NOTHING`:** The ingestion engine executes:
    ```sql
    INSERT INTO assessment_events (...) VALUES (...)
    ON CONFLICT (device_id, event_id) DO NOTHING
    RETURNING event_id;
    ```
  - **Idempotent Response:** Any event whose `event_id` already exists in the database is recorded as `status: "duplicate"` with reason code `ALREADY_INGESTED` without raising an error. Whole-batch persistence is atomic per accepted event set.

### 2.5 CSV Formula Injection
- **Threat:** An attacker crafts a device label, software version, or guidance code starting with formula operators (`=`, `+`, `-`, `@`, `\t`, `\r`) that executes malicious code in Microsoft Excel or Google Sheets upon export.
- **Mitigation:**
  - **Cell Escaping:** The CSV streaming exporter (`reports.py`) runs every exported text cell through `escape_csv_cell()`:
    ```python
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{text}"
    ```
  - **Header Standardization:** All headers explicitly document numeric units (`score_rula_1_to_7`, `neck_angle_deg`, etc.).

### 2.6 Denial of Service (DoS) Limits
- **Threat:** Excessive payload sizes or high-frequency requests exhaust server memory and CPU.
- **Mitigation:**
  - **Payload Size Enforcement:** `RequestBodyLimitMiddleware` inspects `Content-Length` and rejects any payload exceeding `MAX_REQUEST_BODY_SIZE_BYTES` (default 1 MB) with `413 Request Entity Too Large`.
  - **Bounded Ingestion Batches:** Ingest endpoints enforce `MAX_BATCH_SIZE` (default 100 events). Oversized requests are rejected with `400 Bad Request` (`BATCH_OVERSIZED`).
  - **Date Window Bounding:** Assessment listing and CSV export queries enforce a maximum query range of 366 days, preventing unbounded database scans.
  - **In-Memory Rate Limiting:**
    - Device enrollment: maximum 10 requests per 60 seconds per IP.
    - Failed authentication: maximum 5 failures per 60 seconds per IP, locking out subsequent attempts.
    - *Note:* In-memory rate limiting is per-instance. In multi-instance deployments, this can be backed by a centralized Redis cluster if distributed enforcement is required.

### 2.7 Secret Handling & Information Leakage
- **Threat:** Passwords, tokens, or private customer data leak via application logs, error traces, or API documentation.
- **Mitigation:**
  - **Fail-Closed Production Settings:** In `APP_ENV=production`, `Settings` strictly validates that no placeholder values, default credentials, wildcard CORS (`*`), or local addresses are configured, and that API documentation (`/docs`, `/redoc`) is disabled unless `ENABLE_API_DOCS=true` is explicitly set.
  - **Structured Log Sanitization:** `RedactingJsonFormatter` scrubs all log records using regular expressions to replace Bearer JWTs, device credentials (`eed_`), enrollment tokens (`eet_`), and database passwords with `[REDACTED]`.
  - **No Request Body Logging:** Request bodies and raw client payloads are strictly prohibited from being logged.
  - **Audit Event Sanitizer:** Before writing to `audit_events`, all metadata fields are sanitized to strip any keys matching `token`, `secret`, `credential`, or `password`.
  - **Standardized Safe Errors:** Global exception handlers catch all unhandled exceptions and return generic error responses (`INTERNAL_SERVER_ERROR`) with a traceable `request_id`, suppressing raw internal exception messages and stack traces.

---

## 3. Security Headers Enforced

All HTTP responses emitted by the FastAPI backend include the following security headers via `SecurityHeadersMiddleware`:

| Header | Value | Purpose |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Prevents clickjacking in iframes |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer leakage |
| `Content-Security-Policy` | `default-src 'self'` | Restricts content sources |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | Enforced when HTTPS or in production |

---

## 4. Edge Device Credential Security & Revocation Model

### 4.1 On-Device Credential Storage via Windows Credential Manager
Workstation credentials (`eed_<public_id>.<secret>`) are stored using the OS-level credential store (`keyring.backends.Windows.WinVaultKeyring`).
- **Encrypted at Rest:** Secrets are encrypted by the Windows Data Protection API (DPAPI) and tied to the user's Windows login session.
- **Zero Local Database Storage:** The local SQLite database (`edge_ergo.db`) stores only `public_id`, `device_id`, and `api_base_url`. The secret is **never** written to SQLite, `.ini`, `.json`, or configuration files.
- **Sanitized Memory Lifecycle:** The secret is loaded from `keyring` in memory exclusively when constructing the `Authorization: Bearer` header for outgoing requests, and is never logged or included in debug traces.

### 4.2 Atomic Credential Rotation
When an administrator rotates a device's credential via `POST /api/v1/devices/{device_id}/rotate-credential`, or when the agent re-enrolls:
1. The new secret is committed to Windows Credential Manager under `(service="edge_ergo_device", username=public_id)` overwriting the old value.
2. The SQLite `device_identity` table metadata is updated in a transaction.
3. The sync worker reloads the credential from `keyring` on its next cycle.

### 4.3 Revocation Latency & Fail-Safe Halting
- **Revocation Latency:** In the Supabase database, revocation sets `status = 'revoked'` immediately. Because the backend checks `devices.status == 'active'` on **every** request, revocation takes effect with **zero server-side latency**.
- **Client-Side Halting Behavior:** When the edge agent receives a `401 Unauthorized` with error code `INVALID_CREDENTIALS` (caused by revocation or invalid secret):
  1. The sync worker enters a hard halt and terminates all outgoing upload requests immediately.
  2. Queued assessment events remain securely saved in local SQLite; they are **never deleted or discarded** upon revocation.
  3. The desktop overlay transitions to `AUTH_ERROR` status, notifying the user: *"Workstation authorization failed or device was revoked. Telemetry uploads paused."*
  4. Local posture monitoring continues uninterrupted.

---

## 5. Dependency Audit & Vulnerability Triage (Phase 8 Security Pass)

Comprehensive security auditing was conducted using `pip-audit` for Python services and `npm audit` for Node.js frontend packages.

### 5.1 Python Backend Dependencies (`pip-audit`)

| Package | Version | Audit Findings | Triage Assessment & Operational Mitigation |
|---|---|---|---|
| **`pyjwt`** | 2.10.1 | Advisory on algorithm confusion / verification edge cases | **Triaged & Mitigated:** In EdgeErgo V3, `app/core/auth.py` strictly restricts verification algorithms to `algorithms=["RS256", "ES256"]` against remote Supabase JWKS endpoints. Symmetric HMAC fallback is strictly disabled in production. Major upgrades require API verification and will be scheduled in subsequent maintenance windows. |
| **`cryptography`** | 45.0.5 | Upstream OpenSSL/hazmat notices | **Triaged & Mitigated:** Used solely as the cryptographic backend engine for asymmetric signature validation in PyJWT. Zero user-controllable encryption primitives or private keys are accepted. |
| **`starlette`** | 0.37.2 | Starlette multipart / form-parsing notices | **Triaged & Mitigated:** Transitive dependency pinned by `fastapi==0.111.1`. EdgeErgo Hosted API strictly parses `application/json` payloads (enforced by `RequestBodyLimitMiddleware`) and accepts zero multipart form uploads. Major upgrades to Starlette 1.x require FastAPI 0.115+ and will not be auto-upgraded without regression testing. |

### 5.2 Frontend Web Dependencies (`npm audit`)

| Package | Severity | Category | Triage Assessment & Production Impact |
|---|---|---|---|
| **`vitest` / `tinypool`** | Critical / Moderate | `devDependencies` | **Zero Production Impact:** Test runner executed strictly in CI and local development. Never included in the compiled production bundle (`dist/`). |
| **`tailwindcss` / `braces`** | High | `devDependencies` | **Zero Production Impact:** CSS build-time post-processor. Generated production CSS contains pure static style classes without runtime JavaScript. Major upgrade to Tailwind v4 requires migration of all CSS directives and is deferred. |
| **`esbuild` / `vite`** | Moderate | `devDependencies` | **Zero Production Impact:** Build bundler and dev server. Output bundle (`dist/assets/*.js`) contains static browser JavaScript served over global CDN. |


