# EdgeErgo V3 — Architecture Overview

EdgeErgo V3 is structured as an architectural monorepo containing three distinct, decoupled execution tiers:

```text
+-------------------------------------------------------------------+
|                     Workstation (Local Windows)                  |
|                                                                   |
|   +-----------------------------------------------------------+   |
|   |                    Edge Agent (Python)                    |   |
|   |  - Camera capture (OpenCV)                                |   |
|   |  - Pose estimation (MediaPipe Pose)                       |   |
|   |  - Geometric Feature Extraction (NumPy)                   |   |
|   |  - Scoring Engine (Versioned Partial RULA Screening)     |   |
|   |  - Desktop Overlay (PySide6)                              |   |
|   |  - Local Durable Storage (SQLite)                         |   |
|   |  - Credential Storage (Windows Credential Manager)        |   |
|   +-----------------------------+-----------------------------+   |
+---------------------------------|---------------------------------+
                                  |
                                  | HTTPS (Device Bearer Credential)
                                  | Minimized telemetry summaries only
                                  | (NO raw frames, video, or landmarks)
                                  v
+-------------------------------------------------------------------+
|                        Render (Cloud Hosted)                      |
|                                                                   |
|   +-----------------------------------------------------------+   |
|   |                      Hosted REST API                      |   |
|   |  - FastAPI ASGI Service                                   |   |
|   |  - Request/Response Validation (Pydantic)                 |   |
|   |  - Asymmetric JWT Verification (Supabase JWKS)            |   |
|   |  - Device Credential Constant-Time Verification           |   |
|   |  - Batch Ingestion & Idempotency Enforcement              |   |
|   |  - Least-Privilege DB Pooler Integration (SQLAlchemy)    |   |
|   +-----------------------------+-----------------------------+   |
+---------------------------------|---------------------------------+
                                  |
                                  | Direct PostgreSQL Connection
                                  v
+-------------------------------------------------------------------+
|                      Supabase PostgreSQL + RLS                    |
|                                                                   |
|   - Organizations & Organization Members (Tenant Boundaries)      |
|   - Devices & Hashed Device Credentials                           |
|   - Assessment Events (Immutable Telemetry History)               |
|   - Hashed Single-Use Enrollment Tokens                           |
|   - Audit Logs & Metadata                                         |
|   - Row Level Security (RLS) policies                             |
+-------------------------------------------------------------------+
                                  ^
                                  |
            +---------------------+---------------------+
            |                                           |
            | Supabase Auth Session                     | REST Queries & Exports
            | (Bearer Access Token)                     | (Authorized via API)
            |                                           |
+-----------+-------------------------------------------+-----------+
|                          Web Browser                              |
|                                                                   |
|   +-----------------------------------------------------------+   |
|   |                    React Web Dashboard                    |   |
|   |  - React 18 + TypeScript + Vite + Tailwind CSS            |   |
|   |  - Supabase Auth Client                                   |   |
|   |  - Overview KPIs & Aggregated Assessment Trends           |   |
|   |  - Device Status & Enrollment Management                  |   |
|   |  - Filtered CSV Exports                                   |   |
|   +-----------------------------------------------------------+   |
+-------------------------------------------------------------------+
```

---

## Component Separation & Privacy Rules

1. **Strict Privacy Boundary:** Camera frames, video files, face crops, and raw coordinate landmarks are processed entirely in workstation RAM and never leave the local machine.
2. **Minimized Telemetry:** The edge agent transmits only structured, validated ergonomic summaries (event ID, timestamp, validity status, scoring method version, and computed angles/scores).
3. **Identity Separation:** Dashboard users (administrators and ergonomic reviewers) authenticate via Supabase Auth. Workstations authenticate using scoped, hashed device credentials (`eed_<public_id>.<secret>`). Workstation users do not have web dashboard access.
4. **Tenant Isolation:** All database tables and API queries enforce organization-level boundaries (`organization_id`).
