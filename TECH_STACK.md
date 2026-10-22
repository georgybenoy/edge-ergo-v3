# EdgeErgo V3 — Technology Stack

**Version:** 1.0  
**Purpose:** Defines the implementation technologies and deployment responsibilities for EdgeErgo V3.  
**Coding agent:** Google Antigravity  
**Source of truth:** `PRD.md`

---

## 1. Architecture Summary

EdgeErgo V3 is a monorepo with three runtime components:

1. A Windows desktop edge agent that performs computer vision locally.
2. A FastAPI backend hosted on Render.
3. A React dashboard hosted on Render.

Supabase provides dashboard authentication and hosted PostgreSQL persistence. The browser must not connect directly to privileged database operations. The API verifies Supabase access tokens, enforces authorization, validates payloads, and handles device synchronization.

```text
Windows Edge Agent
  ├── OpenCV + MediaPipe + NumPy
  ├── PySide6 desktop overlay
  └── SQLite + durable sync queue
            │ HTTPS + device credential
            ▼
Render: FastAPI API
  ├── Pydantic validation
  ├── Supabase JWT verification
  ├── Role and device authorization
  └── SQLAlchemy / PostgreSQL access
            │
            ▼
Supabase PostgreSQL + RLS
  ├── Profiles and roles
  ├── Devices and enrollment
  ├── Assessment events
  └── Audit metadata

Browser
  └── React + TypeScript + Vite
        ├── Supabase Auth client
        └── HTTPS requests to FastAPI
                  │
                  ▼
             Render API
```

## 2. Selected Technologies

| Layer | Technology | Responsibility |
|---|---|---|
| Language — edge/backend | Python | Vision, desktop agent, API |
| Camera and image processing | OpenCV | Local webcam capture and frame handling |
| Pose estimation | MediaPipe Pose or reviewed compatible alternative | Local body landmark estimation |
| Numerical calculations | NumPy | Feature and angle calculations |
| Desktop interface | PySide6 | Overlay, controls, status and feedback |
| Edge persistence | SQLite | Local history, settings, sync queue and acknowledgements |
| Local schema changes | Versioned SQLite migrations | Safe upgrades of local data |
| API framework | FastAPI | Versioned REST API |
| API schemas | Pydantic | Request/response validation |
| API/database integration | SQLAlchemy | Database models and transactions |
| Hosted schema migrations | Alembic and/or versioned Supabase SQL migrations | Reproducible database evolution |
| Hosted database | Supabase PostgreSQL | Central assessment, user-linked, and device data |
| Dashboard identity | Supabase Auth | Sign-in, sign-out, access-token issuance and session management |
| Database access control | PostgreSQL RLS | Restrict browser-accessible rows |
| Frontend | React + TypeScript | Dashboard UI |
| Frontend build tool | Vite | Development server and production build |
| Styling | Tailwind CSS | Consistent responsive styling |
| Charts | Recharts or an equivalent accessible chart library | Dashboard visualizations |
| Frontend API client | Native `fetch` or Axios | Requests to FastAPI |
| Desktop packaging | PyInstaller | Windows executable packaging after testing |
| Version control | Git + GitHub | Source history and collaboration |
| Coding agent | Google Antigravity | Assisted implementation, edits, and test execution |
| Backend hosting | Render Web Service | Production FastAPI process |
| Frontend hosting | Render Static Site | Production React build |
| Deployment configuration | `render.yaml` where supported | Version-controlled service/build configuration |
| CI | GitHub Actions | Automated lint, type, test, migration and build checks |
| Tests — Python | pytest | API, vision logic, scoring, sync and storage tests |
| Tests — frontend | Vitest + React Testing Library | UI and frontend logic tests |
| Browser end-to-end tests | Playwright, if needed for critical flows | Authenticated dashboard smoke tests |

Use pinned and compatible dependency versions. Confirm current MediaPipe, Python, PySide6, and packaging compatibility before locking the environment.

## 3. Repository Layout

```text
edge-ergo-v3/
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── lib/
│   │   └── pages/
│   ├── public/
│   ├── .env.example
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── tests/
│   ├── .env.example
│   ├── pyproject.toml
│   └── alembic.ini
├── edge-agent/
│   ├── edge_ergo/
│   │   ├── camera/
│   │   ├── vision/
│   │   ├── features/
│   │   ├── scoring/
│   │   ├── overlay/
│   │   ├── storage/
│   │   ├── sync/
│   │   └── main.py
│   ├── tests/
│   └── pyproject.toml
├── supabase/
│   ├── config.toml
│   └── migrations/
├── tests/
├── .github/
│   └── workflows/
├── .gitignore
├── .env.example
├── render.yaml
├── PRD.md
├── TECH_STACK.md
└── README.md
```

Antigravity may refine the exact internal module names as implementation proceeds, but must preserve the separation between frontend, hosted API, and local edge agent.

## 4. Supabase Responsibilities

### Supabase Auth

Use Supabase Auth for dashboard users. The frontend uses the Supabase project URL and publishable/anon key to sign in and obtain a session. It sends the access token to the FastAPI backend as a bearer token.

The backend must verify the token using a supported, secure Supabase JWT verification approach and derive the authenticated user identity from the verified claims. Never trust a user ID supplied only in the request body.

### Supabase PostgreSQL

Store hosted application records in Supabase PostgreSQL. Suggested initial tables:

- `profiles`
- `organizations` and `organization_members` if multi-organization support is in the first release
- `devices`
- `assessment_events`
- `device_enrollment_tokens`
- `audit_events`

Use migrations, foreign keys, indexes, uniqueness constraints, check constraints, and transactions. Keep migrations in version control.

### Row Level Security

Enable RLS on tables accessible through Supabase's client APIs. Policies must restrict users to their permitted records. Users must not be able to grant themselves elevated roles. Sensitive role changes, enrollment, revocation, and device ingestion must pass through trusted backend code.

RLS does not replace API authorization. Both layers must be tested.

### Server-side secrets

Keep any Supabase service-role key or privileged database credential exclusively in backend environment variables configured in Render. Never place it in:

- `frontend/.env` variables exposed to the browser
- React source or compiled frontend assets
- GitHub commits
- the Windows edge-agent executable
- logs, screenshots, test fixtures, or documentation examples

Use the least-privilege access method practical for the selected schema and policies.

## 5. Render Deployment Responsibilities

### Backend — Render Web Service

- Root directory: `backend/`, or repository root if the build configuration explicitly supports the monorepo.
- Build command: install pinned Python dependencies.
- Start command: run the FastAPI ASGI application with a production ASGI server such as Uvicorn, binding to `0.0.0.0` and Render's provided port.
- Health endpoints: separate `/health/live` and `/health/ready` endpoints.
- Environment variables: Supabase URL, required verification configuration, database connection configuration if used, allowed frontend origin, and other server-only secrets.
- Configure HTTPS through Render's managed service URL.
- Do not store durable application data on the Render filesystem.

Exact commands must match the committed project files and be verified against Render's current runtime requirements.

### Frontend — Render Static Site

- Root directory: `frontend/`.
- Build command: install dependencies and run the production build.
- Publish directory: `dist`.
- Set the API base URL to the deployed FastAPI URL.
- Set only public Supabase project configuration in browser-exposed variables.
- Configure SPA route fallback to `index.html` if needed by the chosen routing library.
- Restrict backend CORS to the actual production frontend origin.

### Render configuration

Use `render.yaml` to keep service definitions reproducible where practical. The file may define service names, build commands, start commands, health-check paths, and environment-variable references. It must not contain secret values. Confirm that the configuration is compatible with the actual Render service setup before deploying.

Render hosts the web application and API; Supabase remains responsible for authentication and the hosted PostgreSQL database.

## 6. Environment Variables

Exact names should be standardized in the first implementation phase and used consistently across code, `.env.example`, CI, and Render.

### Frontend

Example public variables:

```dotenv
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLIC_PUBLISHABLE_OR_ANON_KEY
VITE_API_BASE_URL=http://127.0.0.1:8000
```

These values are visible in the browser bundle by design. They are not substitutes for database access policies. Use the publishable key name supported by the current Supabase project; legacy projects may label the public key as an anon key.

### Backend

Illustrative names; finalize them consistently during implementation:

```dotenv
APP_ENV=development
API_V1_PREFIX=/api/v1
FRONTEND_ORIGIN=http://localhost:5173
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_JWT_ISSUER=https://YOUR_PROJECT.supabase.co/auth/v1
SUPABASE_JWKS_URL=https://YOUR_PROJECT.supabase.co/auth/v1/.well-known/jwks.json
DATABASE_URL=YOUR_SERVER_SIDE_DATABASE_CONNECTION
```

Only include a privileged key if the chosen backend access method requires it. If required, use a clearly named server-only variable such as `SUPABASE_SERVICE_ROLE_KEY`, configure it only in trusted server environments, and never expose it to the frontend or edge agent.

Do not assume every Supabase project uses the same JWT signing-key configuration. Implement and test verification against the actual project configuration. If SQLAlchemy connects directly to PostgreSQL, select the correct Supabase connection string and TLS/pooling option for the Render runtime.

### Edge agent

The edge agent should read non-secret configuration from a user-controlled settings file or environment as appropriate. Device credentials must be stored in OS-protected storage where feasible. Do not put service-role keys or shared administrator secrets in the agent.

Commit `.env.example` files with placeholders only. Keep actual `.env` files out of Git.

## 7. Authentication and Authorization Flows

### Dashboard user

1. User signs in through Supabase Auth.
2. Frontend obtains a Supabase session/access token.
3. Frontend sends the access token to FastAPI as `Authorization: Bearer <token>`.
4. Backend verifies token signature, issuer, expiry, and relevant claims using the selected supported verification method.
5. Backend resolves user role and organization scope from trusted records.
6. Backend authorizes the requested action and returns only permitted data.
7. RLS provides an additional boundary for browser-accessible data.

### Edge device

1. An authorized administrator requests a short-lived, single-use enrollment token.
2. The agent submits the token through a protected enrollment flow.
3. Backend validates and consumes the token atomically.
4. Backend issues a device-specific credential or securely provisions a suitable revocable credential.
5. Agent sends batches over HTTPS with its device credential.
6. Backend maps the credential to one device; the client cannot select a different trusted device identity.
7. Backend validates each event and stores it transactionally with a unique event ID.
8. Backend returns explicit per-event outcomes.
9. Revocation immediately prevents further uploads after the server's defined revocation check.

Do not treat a device ID as a credential. Do not reuse a dashboard user's access token as a long-lived device secret.

## 8. API Design Principles

Use a versioned REST API, initially under `/api/v1`.

Potential endpoint groups:

- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/me`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/assessments`
- `GET /api/v1/devices`
- `POST /api/v1/devices/enrollment-tokens`
- `POST /api/v1/devices/enroll`
- `POST /api/v1/devices/heartbeat`
- `POST /api/v1/assessments/batch`
- `POST /api/v1/devices/{device_id}/revoke`
- `GET /api/v1/reports/assessments.csv`

These are proposed routes, not claims that endpoints already exist. Antigravity should finalize route contracts with Pydantic request/response schemas and tests.

Requirements:

- Validate all inputs and bound page sizes, date ranges, payload sizes, and batch sizes.
- Return consistent safe error responses.
- Do not expose stack traces, secrets, or sensitive request bodies.
- Make event ingestion idempotent with database-enforced uniqueness.
- Distinguish accepted, duplicate, and rejected batch events.
- Apply server-side authorization to every protected route.
- Keep API docs useful during development and restrict or configure them appropriately for production.

## 9. Local Edge-Agent Stack

- **OpenCV:** webcam capture and frame handling.
- **MediaPipe Pose or reviewed alternative:** local landmark estimation.
- **NumPy:** angles and geometric feature calculations.
- **Scoring module:** documented and versioned RULA/REBA implementation only after the methodology has been reviewed and reference-tested.
- **PySide6:** desktop overlay and controls.
- **SQLite:** local settings, event history, sync queue, and acknowledgements.
- **HTTP client:** a maintained Python HTTP client such as `httpx` for HTTPS API requests.
- **OS-protected secret storage:** use an appropriate Windows credential-storage library or Windows API where feasible.
- **PyInstaller:** package a tested application for Windows.

Keep camera capture, inference, feature extraction, scoring, UI, persistence, and synchronization separate. The UI must show an unavailable state when required landmarks are missing or confidence is insufficient. No raw camera media should be written to disk by default.

## 10. Testing Strategy

### Backend

- pytest for schemas, authentication, authorization, endpoint behavior, enrollment, revocation, ingestion, idempotency, and error handling.
- Use an isolated test database/project or disposable test schema. Never run destructive tests against production.
- Verify migrations on an empty database and an upgrade path.
- Test invalid/expired tokens, insufficient roles, cross-device access, and cross-organization access.
- Test that logs and errors do not expose credentials or raw request payloads.

### Frontend

- Vitest and React Testing Library for components, authentication state, route protection, loading/error/empty states, filters, and export behavior.
- Test that the frontend contains no privileged keys.
- Verify production build and direct navigation to nested routes.

### Edge agent

- pytest for geometry, landmark validity, scoring boundaries, SQLite persistence, migration behavior, queue retries, idempotent event IDs, and restart recovery.
- Mock camera and network dependencies for deterministic tests.
- Perform manual webcam and overlay tests on a supported Windows machine.
- Measure CPU, memory, inference latency, and behavior under low confidence and camera failure.

### Integration and deployment

- Test frontend-to-API authentication against a non-production Supabase project.
- Test device enrollment, batch sync, duplicate submissions, offline recovery, and revocation.
- After deployment, test Render health endpoints, login, dashboard loading, a controlled assessment upload, and CSV export.
- Inspect network requests, database records, logs, and exports to verify that raw camera data never leaves the workstation.

## 11. CI and Code Quality

GitHub Actions should run relevant checks on pull requests and main-branch updates:

- Python formatting and linting (for example, Ruff).
- Python tests (pytest).
- TypeScript checks.
- Frontend lint and production build.
- Frontend unit tests.
- Migration/schema checks in an isolated environment where configured.
- Secret scanning where available.

Do not make CI depend on production secrets. Keep test configuration separate and fail clearly when required non-secret configuration is missing.

## 12. Dependency and Version Policy

- Pin dependencies after verifying compatibility.
- Keep Python dependencies in project-specific manifests and use a reproducible lock strategy.
- Commit the JavaScript package lockfile.
- Review dependency and model licenses.
- Avoid unnecessary packages and services.
- Do not upgrade major versions during unrelated feature work.
- Document model versions and the scoring-method version stored with events.

## 13. Implementation Order

1. Initialize repository, `.gitignore`, README, frontend, backend, edge-agent skeleton, and CI.
2. Configure Supabase schema migrations, Auth settings, RLS policies, and isolated tests.
3. Implement backend authentication, authorization, health endpoints, and error handling.
4. Implement dashboard sign-in and a minimal protected dashboard.
5. Deploy the minimal API and frontend to Render and verify the live flow early.
6. Build dashboard data views using real API/database records.
7. Implement edge vision and validated scoring.
8. Add enrollment, device credentials, offline queue, and idempotent synchronization.
9. Package and test the Windows agent.
10. Complete security, privacy, performance, backup/recovery, and pilot acceptance tests.

## 14. Antigravity Working Agreement

- Read `PRD.md` and this file before coding.
- Inspect repository state and installed tools before changing files.
- Work phase by phase and keep changes reviewable.
- Explain intended files and acceptance checks before substantial changes.
- Run relevant tests and report actual results.
- Do not fabricate test output, data, deployment success, or performance claims.
- Never commit secrets or expose privileged credentials.
- Keep migrations and environment variable names consistent.
- Ask before making consequential assumptions about roles, tenant boundaries, scoring methodology, or retention.
- End each phase with a summary of files changed, commands run, tests passed/failed, known limitations, and the next step.
