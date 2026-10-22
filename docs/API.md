# EdgeErgo V3 — Hosted API Specification

## 1. Overview & Architectural Principles

The EdgeErgo V3 Hosted API is a secure, versioned FastAPI service (`/api/v1`) providing authentication, device lifecycle management, idempotent telemetry ingestion, and ergonomic analytics for the EdgeErgo web dashboard and Windows edge agents.

### Core Architectural Guarantees
- **Asymmetric Zero-Trust Authentication:** Web dashboard users authenticate via Supabase Auth RS256/ES256 JWTs verified against Supabase JWKS endpoints. User identity is derived strictly from verified token claims; organization membership and roles are resolved directly from PostgreSQL (`organization_members`).
- **High-Entropy Device Credentials:** Workstations authenticate using dedicated credentials in the format `eed_<public_id>.<secret>`. Secrets are hashed with SHA-256 before database comparison using constant-time algorithms. Plaintext secrets are never stored.
- **Fail-Closed Privacy Boundary:** No raw video frames, images, or 33 raw MediaPipe landmark coordinate arrays are ever accepted or stored. All ingestion and enrollment schemas enforce Pydantic v2 `extra="forbid"`, rejecting unknown or malformed fields immediately.
- **Idempotent Telemetry Ingestion:** Telemetry upload uses database-enforced compound primary keys `(device_id, event_id)` with `INSERT ... ON CONFLICT DO NOTHING` semantics. Re-sending identical batches succeeds without duplicating observations.
- **Tenant Isolation:** All database queries are explicitly scoped to the caller's resolved `organization_id`. Cross-organization requests yield `404 Not Found` or `403 Forbidden` without leaking resource existence.

---

## 2. Authentication Schemes

### 2.1 Web Dashboard (User Authentication)
Web dashboard clients authenticate by transmitting a Supabase JWT in the `Authorization` header:
```http
Authorization: Bearer <supabase_jwt_access_token>
```
Optional organization context header (for users belonging to multiple organizations):
```http
X-Organization-ID: <uuid>
```
The API validates:
- Signature via cached JWKS keys (automatic rotation/refresh on unknown `kid`).
- `alg` header must be in allowlist (`RS256`, `ES256`). `alg=none` is rejected with `401 Unauthorized`.
- Standard claims: `iss` equals `SUPABASE_JWT_ISSUER`, `aud` equals `SUPABASE_JWT_AUDIENCE`, token is within valid window (`nbf` <= now <= `exp` with 10s leeway).

### 2.2 Edge Workstation (Device Authentication)
Enrolled Windows edge agents authenticate using a Bearer token containing their public device ID and high-entropy secret:
```http
Authorization: Bearer eed_<public_id>.<secret>
```
The API:
- Extracts `public_id` and looks up the device in PostgreSQL.
- Verifies `hmac.compare_digest(sha256(secret), credential_hash)` in constant time.
- Verifies device status is `active`. Revoked devices or incorrect secrets return identical `401 Unauthorized` responses to eliminate timing and enumeration side-channels.
- Automatically updates `last_seen_at` upon successful authentication.

---

## 3. Standardized Error Format

All error responses across HTTP 4xx and 5xx return a consistent JSON schema with zero stack traces:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description of error.",
    "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
  }
}
```

### Standard Error Codes
| Code | HTTP Status | Description |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing, expired, malformed, or invalid Bearer token. |
| `INVALID_CREDENTIALS` | 401 | Device secret mismatch or device not found/revoked. |
| `INVALID_KEY_ID` | 401 | JWT `kid` not present in Supabase JWKS. |
| `FORBIDDEN` | 403 | Authenticated user lacks permission for the requested action. |
| `ADMIN_REQUIRED` | 403 | Action requires `admin` role in the organization. |
| `NO_ORGANIZATION_MEMBERSHIP` | 403 | User is not a member of the requested organization. |
| `NOT_FOUND` | 404 | Resource does not exist or belongs to another organization. |
| `RATE_LIMITED` | 429 | Rate limit exceeded (e.g. repeated enrollment or failed auth). |
| `REQUEST_TOO_LARGE` | 413 | Request payload exceeds `MAX_REQUEST_BODY_SIZE_BYTES`. |
| `VALIDATION_ERROR` | 422 | Schema validation failed (e.g. extra fields or boundary breach). |
| `BATCH_OVERSIZED` | 400 | Ingestion batch exceeds `MAX_BATCH_SIZE`. |
| `DATABASE_UNAVAILABLE` | 503 | Readiness check failed to establish database connectivity. |
| `INTERNAL_SERVER_ERROR` | 500 | Unhandled internal error (safe generic message). |

---

## 4. API Endpoints

### 4.1 System & Health Checks

#### `GET /health/live`
- **Auth:** None
- **Response:** `200 OK`
  ```json
  {"status": "alive"}
  ```

#### `GET /health/ready`
- **Auth:** None
- **Response:** `200 OK` when DB is connected and configuration is valid; `503 Service Unavailable` if database check fails (no internal credentials leaked).
  ```json
  {"status": "ready"}
  ```

---

### 4.2 User & Profile Endpoints

#### `GET /api/v1/me`
- **Auth:** Web User (`Bearer <jwt>`)
- **Response:** `200 OK`
  ```json
  {
    "user_id": "11111111-1111-1111-1111-111111111111",
    "email": "user@company.com",
    "organization_id": "22222222-2222-2222-2222-222222222222",
    "organization_slug": "acme-corp",
    "role": "admin"
  }
  ```

---

### 4.3 Device Lifecycle & Enrollment

#### `POST /api/v1/devices/enrollment-tokens`
- **Auth:** Admin (`Bearer <jwt>`, role `admin`)
- **Request Body:**
  ```json
  {
    "label": "Engineering Workstation 04"
  }
  ```
- **Response:** `201 Created`
  ```json
  {
    "token": "eet_7f3b8c9a1e2d4f5a6b7c8d9e0f1a2b3c",
    "label": "Engineering Workstation 04",
    "expires_at": "2026-10-20T12:15:00Z"
  }
  ```
  *Note:* Plaintext token is returned exactly once. Only its SHA-256 hash is stored in PostgreSQL.

#### `POST /api/v1/devices/enroll`
- **Auth:** None (Guarded by enrollment token & client IP sliding rate limiting)
- **Request Body:**
  ```json
  {
    "token": "eet_7f3b8c9a1e2d4f5a6b7c8d9e0f1a2b3c",
    "agent_version": "3.0.0"
  }
  ```
- **Response:** `201 Created`
  ```json
  {
    "device_id": "33333333-3333-3333-3333-333333333333",
    "public_id": "edp_a1b2c3d4e5f67890",
    "credential": "eed_edp_a1b2c3d4e5f67890.example_device_secret_token_12345",
    "label": "Engineering Workstation 04",
    "organization_id": "22222222-2222-2222-2222-222222222222"
  }
  ```
  *Note:* Device credential is returned exactly once and must be persisted by the agent in Windows Credential Manager.

#### `POST /api/v1/devices/heartbeat`
- **Auth:** Device (`Bearer eed_<public_id>.<secret>`)
- **Request Body:**
  ```json
  {
    "agent_version": "3.0.0",
    "queue_depth": 0,
    "state": "active_tracking"
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "status": "ok",
    "received_at": "2026-10-20T12:00:00Z"
  }
  ```

#### `GET /api/v1/devices`
- **Auth:** User (`Bearer <jwt>`, role `admin` or `reviewer`)
- **Query Parameters:** `limit` (default 50), `offset` (default 0)
- **Response:** `200 OK`
  ```json
  [
    {
      "id": "33333333-3333-3333-3333-333333333333",
      "label": "Engineering Workstation 04",
      "public_id": "edp_a1b2c3d4e5f67890",
      "status": "active",
      "computed_status": "online",
      "enrolled_at": "2026-10-20T12:00:00Z",
      "last_seen_at": "2026-10-20T12:05:00Z",
      "last_sync_at": "2026-10-20T12:05:00Z",
      "agent_version": "3.0.0"
    }
  ]
  ```
  *Computed Status Values:* `online` (heartbeat within 3× heartbeat interval / 450s), `offline`, `sync_pending`, `revoked`.

#### `POST /api/v1/devices/{device_id}/revoke`
- **Auth:** Admin (`Bearer <jwt>`, role `admin`)
- **Response:** `200 OK`
  ```json
  {
    "device_id": "33333333-3333-3333-3333-333333333333",
    "status": "revoked",
    "revoked_at": "2026-10-20T12:10:00Z"
  }
  ```

#### `POST /api/v1/devices/{device_id}/rotate-credential`
- **Auth:** Admin (`Bearer <jwt>`, role `admin`)
- **Response:** `200 OK`
  ```json
  {
    "device_id": "33333333-3333-3333-3333-333333333333",
    "public_id": "edp_a1b2c3d4e5f67890",
    "credential": "eed_edp_a1b2c3d4e5f67890.example_rotated_secret_token_99999",
    "credential_version": 2
  }
  ```

---

### 4.4 Telemetry Ingestion & Assessment Query

#### `POST /api/v1/assessments/batch`
- **Auth:** Device (`Bearer eed_<public_id>.<secret>`)
- **Constraints:** Maximum 100 events per request (`MAX_BATCH_SIZE`). Reject unknown fields (`extra="forbid"`).
- **Request Body:**
  ```json
  {
    "events": [
      {
        "event_id": "55555555-5555-5555-5555-555555555555",
        "captured_at": "2026-10-20T12:00:00Z",
        "scoring_method": "rula_v1_screening",
        "scoring_version": "1.0",
        "validity": "valid",
        "score": 3.0,
        "neck_score": 2,
        "trunk_score": 1,
        "upper_arm_score": 2,
        "guidance_codes": ["NECK_FLEXED_FORWARD"],
        "software_version": "3.0.0"
      }
    ]
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "results": [
      {
        "event_id": "55555555-5555-5555-5555-555555555555",
        "status": "accepted",
        "reason_code": null
      }
    ],
    "total_accepted": 1,
    "total_duplicates": 0,
    "total_rejected": 0
  }
  ```
  *Fault Tolerance:* If an individual event in a batch is malformed, it is marked `rejected` with an explanatory `reason_code` without poisoning the valid events in the batch.

#### `GET /api/v1/assessments`
- **Auth:** User (`Bearer <jwt>`, role `admin` or `reviewer`)
- **Query Parameters:**
  - `start_date` / `end_date` (ISO-8601; bounded to a max window of 366 days)
  - `device_id` (UUID filter)
  - `validity` (`valid`, `insufficient`, `invalid`)
  - `scoring_version` (e.g. `1.0`)
  - `limit` (1-100, default 50)
  - `offset` (>= 0, default 0)
- **Response:** `200 OK`
  ```json
  {
    "items": [
      {
        "event_id": "55555555-5555-5555-5555-555555555555",
        "device_id": "33333333-3333-3333-3333-333333333333",
        "captured_at": "2026-10-20T12:00:00Z",
        "scoring_method": "rula_v1_screening",
        "scoring_version": "1.0",
        "validity": "valid",
        "score": 3.0,
        "neck_score": 2,
        "trunk_score": 1,
        "upper_arm_score": 2,
        "guidance_codes": ["NECK_FLEXED_FORWARD"],
        "software_version": "3.0.0"
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  }
  ```

---

### 4.5 Dashboard Summary & Reports

#### `GET /api/v1/dashboard/summary`
- **Auth:** User (`Bearer <jwt>`, role `admin` or `reviewer`)
- **Response:** `200 OK`
  ```json
  {
    "total_assessments": 1500,
    "valid_count": 1420,
    "insufficient_count": 60,
    "invalid_count": 20,
    "average_rula_score": {
      "name": "average_rula_score",
      "value": 3.25,
      "sample_count": 1420,
      "definition": "Mean partial RULA screening risk score across valid upper-body observations",
      "reason": null
    },
    "active_devices": 10,
    "online_devices": 8
  }
  ```
  *Note:* When zero valid observations exist, `value` is returned as `null` with explicit `reason: "Insufficient valid observations in organization"` rather than `0.0`.

#### `GET /api/v1/reports/assessments.csv`
- **Auth:** User (`Bearer <jwt>`, role `admin` or `reviewer`)
- **Query Parameters:** Identical filters to `/api/v1/assessments` (date range <= 366 days).
- **Behavior:**
  - Streams CSV rows using `StreamingResponse`.
  - Escapes formula injection triggers (`=`, `+`, `-`, `@`, `\t`, `\r`) by prefixing cells with `'`.
  - Column headers specify exact units (`score_rula_1_to_7`, `neck_angle_deg`, etc.).
  - Maximum 10,000 rows exported per request (`MAX_EXPORT_ROWS`).

#### `GET /api/v1/audit-events`
- **Auth:** Admin (`Bearer <jwt>`, role `admin`)
- **Response:** `200 OK`
  ```json
  {
    "items": [
      {
        "id": "77777777-7777-7777-7777-777777777777",
        "action": "device.enrolled",
        "target_type": "device",
        "target_id": "33333333-3333-3333-3333-333333333333",
        "metadata": {
          "label": "Engineering Workstation 04",
          "public_id": "edp_a1b2c3d4e5f67890",
          "agent_version": "3.0.0"
        },
        "created_at": "2026-10-20T12:00:00Z"
      }
    ],
    "total": 1
  }
  ```
  *Security Note:* Audit event metadata is automatically filtered before persistence to ensure tokens, credentials, and passwords are never recorded.
