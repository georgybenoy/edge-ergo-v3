# EdgeErgo V3 — Architectural and Technical Decisions

This document records the foundational architectural, security, and operational decisions for EdgeErgo V3.
Any adjustments to these decisions must follow the schema:
`Decision / Options considered / Why / How to change it later`.

---

## 1. Tenancy Model

- **Decision:** The database schema is multi-organization-capable from the start (`organizations`, `organization_members`). For the initial release, the system seeds ONE default organization (`default-org`), and all API queries and RLS policies are strictly organization-scoped (`WHERE organization_id = :org_id`).
- **Options considered:**
  1. *Single-tenant schema (no organization table, flat device/user ownership):* Simpler initial migration, but requires major schema rewrites, data migrations, and API contract changes when multi-tenant support is introduced.
  2. *Full dynamic self-service multi-tenancy in Release 1:* Higher implementation complexity, registration flows, and tenant switching overhead for the pilot.
  3. *Multi-organization-capable schema seeded with one default organization (Selected):* Preserves strict tenant isolation boundaries in SQL, models, and API parameters without adding administrative UI complexity for pilot single-org deployment.
- **Why:** Meets the PRD requirements for clean tenant scoping and future enterprise scalability while keeping the first release operationally simple.
- **How to change it later:** Create tenant-provisioning endpoints, invite flows, and an organization switcher in the frontend. The database schema and authorization checks already expect `organization_id` on all tenant resources.

---

## 2. User Roles and Workstation Separation

- **Decision:** Dashboard users have two distinct roles: `admin` and `reviewer`. Workstation users (employees seated at desks) do not sign in to the web dashboard.
- **Options considered:**
  1. *Three-tier role model including `workstation_user` on the dashboard:* Gives desk users web portal accounts, but increases attack surface and requires complex user management and privacy controls to prevent self-monitoring or cross-user comparison.
  2. *Single generic user role:* Fails principle of least privilege; reviewers could revoke devices or generate tokens.
  3. *`admin` and `reviewer` roles for dashboard, workstation users separated (Selected):* Workstation users interact purely through the local desktop overlay and do not have dashboard credentials. `admin` can enroll/revoke devices, manage roles, and change org settings; `reviewer` has read-only access to authorized aggregated trends and filtered assessment records.
- **Why:** Minimizes credential exposure, simplifies privacy compliance, and strictly enforces the boundary between workstation telemetry collection and administrative/ergonomic review.
- **How to change it later:** Add custom roles or permissions in `organization_members` (e.g. `auditor`, `operator`), update authorization decorators in FastAPI, and map roles in Supabase user metadata or custom claims.

---

## 3. Device Credential Format and Storage

- **Decision:** Device credentials use an opaque high-entropy random secret format: `eed_<public_id>.<secret>`, where `<public_id>` is a URL-safe random string (or UUIDv4) and `<secret>` is a 256-bit cryptographically secure random token (base64url-encoded). The server stores only `<public_id>` and `sha256(secret)`. Verification uses constant-time comparison (`hmac.compare_digest`). The agent stores the credential in Windows Credential Manager via the `keyring` library (falling back to DPAPI-encrypted file storage if keyring service is unavailable).
- **Options considered:**
  1. *Plain API Key or JWT signed for devices:* Device JWTs require expiration/renewal logic and risk token leaks; plaintext API keys risk server database breach.
  2. *Mutual TLS (mTLS):* Strong security, but heavy operational burden on deployment and certificate management for desktop clients.
  3. *Hashed Bearer token with public ID prefix `eed_<public_id>.<secret>` (Selected):* Public ID allows fast database lookup without scanning or decrypting keys; SHA-256 hash ensures a compromised database does not reveal client secrets; constant-time comparison prevents timing attacks; Windows Credential Manager secures the secret at rest on the endpoint.
- **Why:** Satisfies FR-035, FR-037, FR-038, and FR-039 without requiring privileged keys or plain-text file storage.
- **How to change it later:** Add a `credential_version` or `algorithm` field in the `devices` table to support Ed25519 request signing or mTLS if required by enterprise security policies.

---

## 4. Device Enrollment Token Lifecycle

- **Decision:** Device enrollment tokens are high-entropy cryptographically random strings with a 15-minute time-to-live (TTL). Only a SHA-256 hash of the token is stored in `device_enrollment_tokens`. Tokens are strictly single-use and consumed atomically in a transaction during device enrollment.
- **Options considered:**
  1. *Long-lived multi-use enrollment keys:* High risk of leakage, shared tokens, and inability to audit specific workstation provisioning.
  2. *Admin-driven push provisioning:* Requires remote access or MDM agent integration into workstation OS, out of scope for V3.
  3. *Short-lived, single-use, hashed enrollment token (Selected):* Admin creates token in dashboard; agent submits token within 15 minutes; backend consumes token atomically and returns the device credential.
- **Why:** Satisfies FR-036; eliminates replay attacks and prevents brute force token guessing.
- **How to change it later:** Adjust `ENROLLMENT_TOKEN_TTL_MINUTES` in backend environment configuration, or support automated bulk provisioning via signed enterprise MDM tokens.

---

## 5. Dashboard JWT Verification

- **Decision:** FastAPI verifies Supabase Auth access tokens asymmetrically using the Supabase project's JWKS endpoint (`SUPABASE_JWKS_URL`), with strict verification of signature, `iss` (issuer), `aud` (audience), and `exp` (expiry). Legacy HS256 shared-secret verification is supported strictly as an opt-in fallback only if `SUPABASE_JWT_SECRET` is explicitly configured.
- **Options considered:**
  1. *Verify via Supabase Auth API (`/auth/v1/user`) on every request:* Introduces network latency and Supabase rate-limit bottlenecks on every API call.
  2. *Shared symmetric secret (HS256) only:* Requires distributing the project JWT secret to backend config, which is less secure than public-key cryptography.
  3. *Asymmetric JWKS verification with cached public keys (Selected):* Fast, secure, standard OAuth2/OIDC practice, does not require sharing the Supabase master secret, automatically handles key rotation.
- **Why:** Satisfies FR-052 and PRD Section 15. Ensures robust token validation without network round-trips for each request.
- **How to change it later:** Modify `app/core/auth.py` and backend configuration to add alternative identity providers or custom OIDC issuers.

---

## 6. API Database Access and Least Privilege

- **Decision:** FastAPI accesses Supabase PostgreSQL via SQLAlchemy over the Supabase pooled connection string (port 6543 / 5432) using a dedicated application Postgres role (`edgeergo_api_user`) with explicit grants (CRUD on application tables, usage on sequences), rather than the PostgreSQL `postgres` superuser or bypassing policies with `service_role`.
- **Options considered:**
  1. *Direct Supabase postgREST client via `service_role`:* Couples backend to PostgREST HTTP layer and requires distributing the all-powerful `service_role` key to application logic.
  2. *Postgres superuser connection:* Violates least-privilege principles (FR-060).
  3. *SQLAlchemy connection pool with dedicated least-privilege role (Selected):* Clean transactional control, type-safe queries, migration support with Alembic, and defense-in-depth isolation.
- **Why:** Complies with FR-060, FR-047, and PRD Section 8. Allows strict database permission sandboxing.
- **How to change it later:** Connection parameters are controlled by `DATABASE_URL` in the environment; role permissions are managed via version-controlled SQL migrations in `supabase/migrations/`.

---

## 7. Ergonomic Scoring Methodology

- **Decision:** As specified in FR-010, FR-013, FR-014, FR-016, and Phase 6, EdgeErgo implements a documented partial RULA-based screening calculation (versioned as `rula_v1_screening`). Scores are calculated strictly from valid upper-body landmarks (neck flexion/extension, trunk flexion, shoulder elevation/abduction, upper arm angle). It never calculates or fabricates scores for missing or occluded body segments (e.g. wrist twist, legs if outside frame). Missing landmarks result in `validity: "insufficient_data"` and `score: null`. Scores are presented as screening indicators, never as medical diagnoses or employee rankings.
- **Options considered:**
  1. *Fabricate/estimate default neutral values for hidden joints:* Grossly scientifically dishonest, creates false confidence, violates PRD FR-008.
  2. *Full RULA including wrist/leg estimation using AI guesswork:* Unreliable from standard single webcam workstation angles.
  3. *Documented partial RULA screening indicator with explicit missing-landmark gates (Selected):* Transparent, repeatable, scientifically sound, flags when camera angle prevents measurement.
- **Why:** Directly complies with FR-008, FR-010, FR-013, FR-014, FR-017, and safety boundaries.
- **How to change it later:** Future scoring models (e.g. REBA, OSHA workstation checklist) will be added as new scoring modules, each with an incremented/distinct `scoring_method` identifier (e.g., `reba_v1_screening`), maintaining backward compatibility in historical events.

---

## 8. Data Retention Defaults

- **Decision:** Default data retention windows are established as follows:
  - Local edge events in SQLite: 90 days.
  - Central hosted assessment events in PostgreSQL: 365 days.
  - Device heartbeats: 30 days.
  - Audit log events: 365 days.
  - Application and server logs: 30 days.
- **Options considered:**
  1. *Indefinite retention:* Increases database storage bloat, compliance risk, and potential privacy liabilities.
  2. *Extremely short retention (e.g. 14 days):* Prevents meaningful quarterly or annual ergonomic trend analysis.
  3. *Tiered retention schedule with local 90-day and central 365-day defaults (Selected):* Balances long-term organizational health ergonomics trend analysis with privacy data minimization principles.
- **Why:** Satisfies FR-024, FR-034, and PRD Section 15.
- **How to change it later:** Retention windows are configured in backend environment variables (`RETENTION_DAYS_EVENTS=365`, `RETENTION_DAYS_HEARTBEATS=30`, `RETENTION_DAYS_AUDIT=365`) and local agent config (`local_retention_days = 90`). Automated cleanup jobs enforce these periods.

---

## 9. Migration Tooling and Schema Source of Truth

- **Decision:** Supabase versioned SQL migrations located in `supabase/migrations/` are the definitive source of truth for database schema, tables, foreign keys, constraints, triggers, and Row Level Security (RLS) policies. Alembic is retained as an optional developer/CI utility (`alembic.ini` and `backend/alembic/`) for local offline PostgreSQL schema generation and SQLAlchemy model comparison, but is never executed as an override against production Supabase instances.
- **Options considered:**
  1. *Alembic as sole migration runner:* Cannot natively represent Supabase Auth triggers (`auth.users` references) or test Supabase client RLS semantics accurately.
  2. *Supabase SQL migrations solely:* Canonical for Supabase, but Python developers without Supabase CLI in local environments benefit from Alembic for standalone SQLite/Postgres model generation in tests.
  3. *Supabase SQL migrations as source of truth + Alembic developer stub (Selected):* Guarantees RLS and database constraints are version-controlled in standard SQL while allowing backend testing tools to introspect schemas.
- **Why:** Preserves the integrity of Supabase RLS and Auth integration while keeping Python backend tooling clean and standard.
- **How to change it later:** If moving away from Supabase or standardizing on Python-driven schema migrations, translate `supabase/migrations/*.sql` into Alembic revisions in `backend/alembic/versions/`.

---

## 10. SPA Routing Fallback and Deep Linking on Render Static Site

- **Decision:** The web dashboard deployed as a Render static site (`edge-ergo-dashboard`) utilizes an explicit URL rewrite rule (`routes: - type: rewrite, source: /*, destination: /index.html` declared in `render.yaml`) to enable HTML5 History pushState client routing (`react-router-dom`). All nested route requests (such as `/assessments`, `/devices`, `/settings`, `/login`) are served `index.html` by the static host, allowing React Router to resolve routes, execute authentication checks, and restore state client-side without HTTP 404 errors.
- **Options considered:**
  1. *Hash router (`#/login`, `#/settings`):* Avoids server rewrites but produces non-standard URLs, harms accessibility, and complicates Supabase OAuth/magic link callback fragment parsing.
  2. *Custom Express or Node server for static serving:* Introduces extra infrastructure, memory overhead, and maintenance burden for what is essentially a static frontend.
  3. *Static site with root wildcard rewrite to `/index.html` (Selected):* Follows official Render best practices for Vite React SPAs, preserves clean URLs, and ensures direct navigation and page reloads resolve reliably.
- **Why:** Satisfies FR-063, FR-071, and FR-076.
- **How to change it later:** If migrating from Render static hosting to a CDN (e.g., Cloudflare Pages, AWS CloudFront, or Vercel), configure the provider's standard single-page application fallback rule redirecting unmapped paths (404) to `/index.html` with status 200.

---

## 11. Dashboard Data Binding and Development Fixture Isolation

- **Decision:** Dashboard views (`OverviewPage`, `AssessmentsPage`, `DevicesPage`, `ReportsPage`) bind exclusively to live backend API contracts with typed error, loading, empty, and stale data states. Development fixtures are restricted to test environments and a developer-only toggle (`DevFixturesProvider`) that is guarded by `import.meta.env.DEV && isDevFixtureActive`. In production builds (`vite build`), dead-code elimination guarantees that development fixture data, mock factories, and the persistent `"DEVELOPMENT FIXTURE DATA"` banner are completely compiled out of production assets (`dist/assets/*.js`).
- **Options considered:**
  1. *Fallback to mock data when API returns empty or errors:* Strictly prohibited by PRD FR-064 and DESIGN.md §4. Fabricating ergonomic telemetry gives a false sense of compliance or misdiagnoses organizational risk.
  2. *Runtime toggle included in production bundles:* Allows users or reviewers to switch into synthetic demo modes, introducing bundle bloat and risking accidental confusion between synthetic data and live telemetry in audit contexts.
  3. *Compile-time tree-shaken dev fixture toggle (Selected):* Enables rapid offline UI development and visual QA in development mode while ensuring zero synthetic data exists in production bundles, verified by automated production bundle invariant tests (`production-build.test.ts`).
- **Why:** Satisfies FR-064–069, DESIGN.md §4–7, §12, §15–17, and zero-fabrication guarantees.
- **How to change it later:** If a dedicated multi-tenant product demonstration or training environment is required, it must be provisioned as a dedicated sandbox organization in the hosted database with real synthetic database seeds, rather than frontend-fabricated metrics.

---

## 12. Edge Vision API Selection and Model Packaging

- **Decision:** The Windows Edge Agent adopts Google MediaPipe's modern Tasks API (`mediapipe.tasks.python.vision.PoseLandmarker`) using the `pose_landmarker_lite.task` model asset (Apache-2.0 license) pre-bundled into `edge-agent/edge_ergo/vision/models/`. The model is loaded exclusively from the local filesystem path (or PyInstaller extracted `sys._MEIPASS` bundle) with zero silent runtime downloads over the network.
- **Options considered:**
  1. *Legacy MediaPipe Solutions API (`mediapipe.solutions.pose`):* Deprecated and completely removed from modern MediaPipe wheels (0.10.x+), raising `AttributeError: module 'mediapipe' has no attribute 'solutions'` on Windows Python 3.10 AMD64.
  2. *Runtime download of model artifacts:* Violates strict edge agent offline-first and privacy design principles. If an enterprise workstation is offline or behind an egress-filtering corporate proxy, agent startup fails.
  3. *Tasks API with pre-packaged local Apache-2.0 `.task` model file (Selected):* Fully supported on MediaPipe 0.10.35, executes in-process on CPU via TensorFlow Lite XNNPACK delegate, deterministically available offline, and packageable into standalone Windows executables via PyInstaller's `--add-data` specification.
- **Why:** Satisfies FR-001–004, FR-007–008, TECH_STACK.md §9, and Phase 6 Task 1 requirements.
- **How to change it later:** To switch to `pose_landmarker_full.task` (higher accuracy, slightly higher latency) or a future custom model, place the `.task` file in `edge_ergo/vision/models/` and configure the model filename in `VisionConfig`.




