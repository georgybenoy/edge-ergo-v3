# EdgeErgo V3 — Authorization Matrix & Tenant Isolation Report

**Generated:** 2026-10-20 18:15:32 UTC
**Verification Engine:** `pytest tests/authz/test_authz_matrix.py`
**Multi-Tenancy Model:** Strict Organization Isolation with Row-Level Enforcement (PRD FR-052, FR-060, FR-061)

---

## 1. End-to-End Route Access Matrix

| Protected Endpoint | Admin (Org 1) | Reviewer (Org 1) | Outsider (Org 2) | Unauthenticated | Device A (Org 1) | Device R (Revoked) | Device B (Org 2) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `GET /api/v1/me` | `200` | `200` | `200` | `401` | `401` | `401` | `401` |
| `GET /api/v1/dashboard/summary` | `200` | `200` | `200` | `401` | `401` | `401` | `401` |
| `GET /api/v1/assessments` | `200` | `200` | `200` | `401` | `401` | `401` | `401` |
| `GET /api/v1/devices` | `200` | `200` | `200` | `401` | `401` | `401` | `401` |
| `POST /api/v1/devices/enrollment-tokens` | `200` | `403` | `200` | `401` | `401` | `401` | `401` |
| `POST /api/v1/devices/d0000004-0000-0000-0000-000000000004/revoke` | `200` | `403` | `404` | `401` | `401` | `401` | `401` |
| `GET /api/v1/reports/assessments.csv` | `200` | `200` | `200` | `401` | `401` | `401` | `401` |
| `POST /api/v1/devices/heartbeat` | `401` | `401` | `401` | `401` | `200` | `401` | `200` |
| `POST /api/v1/assessments/batch` | `401` | `401` | `401` | `401` | `200` | `401` | `200` |

---

## 2. Security Boundaries & Authorization Invariants

### A. Multi-Tenant Isolation (Org 1 vs Org 2)
- Users authenticated in **Org 2 (Beta Ltd)** can never see, mutate, or export records belonging to **Org 1 (Alpha Corp)**.
- In attempting to mutate an Org 1 device (`/api/v1/devices/{device_id}/revoke`), an Org 2 administrator receives **HTTP 404** (Not Found), confirming zero existence leakage across tenant boundaries.
- Summary metrics (`/api/v1/dashboard/summary`) and CSV exports (`/api/v1/reports/assessments.csv`) are strictly bounded by `organization_id` in SQL queries and Row Level Security (RLS) policies.

### B. Role-Based Access Control (RBAC: Admin vs Reviewer)
- **Reviewers** possess read-only privileges across Overview, Assessments, Devices, and Reports.
- When a Reviewer attempts to generate an enrollment token (`POST /api/v1/devices/enrollment-tokens`), the server returns **HTTP 403 Forbidden** with `ADMIN_REQUIRED` error code.
- When a Reviewer attempts to revoke a workstation (`POST /api/v1/devices/{id}/revoke`), the server returns **HTTP 403 Forbidden**.

### C. Device Credential Boundaries
- Workstation devices authenticate exclusively using scoped Bearer credentials: `eed_<public_id>.<secret>`.
- Workstation credentials cannot access any user endpoints (`/me`, `/dashboard/summary`, `/reports`); the backend derives user identity strictly from verified Supabase JWTs and returns **HTTP 401** if a device attempts user actions.
- User access tokens cannot submit device heartbeats or assessment batches; ingestion endpoints enforce device credential authentication and return **HTTP 401** on user tokens.

### D. Instant Server-Side Device Revocation
- When an administrator revokes a workstation, its database state immediately transitions to `status = 'revoked'`.
- All subsequent heartbeat and batch ingestion attempts using that device's credential immediately fail with **HTTP 401 Invalid device credentials**.
- Revocation error responses are timing-attack mitigated and indistinguishable from invalid or unknown secrets.

---

## 3. Row Level Security (RLS) Policy Status

| Table | RLS Status | Tenant Policy Enforced |
|---|:---:|---|
| `organizations` | ENABLED | Users can only select their active organization |
| `profiles` | ENABLED | Users can only view profiles in shared organizations |
| `organization_members` | ENABLED | Scoped to user's permitted organizations |
| `devices` | ENABLED | Workstations scoped strictly to owning organization |
| `devices_public` | VIEW | Sanitized public view excluding credential hashes |
| `device_enrollment_tokens` | ENABLED | Admins can view/create; members cannot read hashes |
| `assessment_events` | ENABLED | Telemetry scoped strictly to owning organization |
| `device_heartbeats` | ENABLED | Operational metadata scoped to owning organization |
| `audit_events` | ENABLED | Audit trail restricted to organization admins |

**Verification Statement:** The entire matrix above has been executed against live PostgreSQL database instances. All authorization checks passed 100%.
