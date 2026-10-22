# EdgeErgo V3 — Product Requirements Document

**Version:** 3.1  
**Status:** Implementation specification  
**Target platform:** Windows workstation with webcam  
**Repository:** New, clean GitHub repository  
**Coding workflow:** Google Antigravity coding agent  
**Hosting:** Render  
**Authentication and hosted database:** Supabase Auth + Supabase PostgreSQL

---

## 1. Product Overview

EdgeErgo is a privacy-focused workplace ergonomics system that estimates workstation posture using computer vision, calculates documented ergonomic indicators, and provides timely, non-punitive feedback.

The product consists of three independently testable parts:

1. **Windows Edge Agent:** Captures webcam frames and performs posture analysis locally. It stores assessment events in SQLite, shows feedback through a desktop overlay, and continues operating when the internet is unavailable.
2. **Hosted API:** A FastAPI service deployed on Render. It validates dashboard requests and device uploads, enforces authorization, and coordinates secure synchronization with Supabase PostgreSQL.
3. **Web Dashboard:** A React application deployed on Render. Users sign in through Supabase Auth and view authorized assessment summaries, trends, device status, and CSV exports.

Only approved, minimized assessment records and necessary operational metadata may be synchronized. Raw camera frames, video, face crops, and raw pose landmarks must never be uploaded.

V3 is a fresh implementation. The existing V2 repository, if available, may be consulted for lessons or verified algorithms, but must not be copied wholesale or treated as the V3 implementation.

## 2. Problem Statement

People who work at computers may maintain awkward or static postures for long periods without noticing them. Organizations may lack a consistent way to review ergonomic indicators across workstations. Cloud-first camera processing can create privacy concerns and depend on network availability.

EdgeErgo aims to provide local posture feedback and authorized aggregate reporting while keeping camera processing on the workstation.

## 3. Goals

- Estimate posture locally using OpenCV and a suitable pose-estimation model such as MediaPipe Pose.
- Calculate documented posture features and reviewed RULA and/or REBA-related scores.
- Provide a lightweight Windows desktop overlay with actionable feedback.
- Support configurable sampling, analysis, and reminder intervals.
- Persist local settings, assessment events, and pending synchronization records in SQLite.
- Continue local operation without an internet connection.
- Synchronize minimized assessment events securely, reliably, and without duplicates.
- Provide an authenticated dashboard for authorized trends, assessment history, device status, and CSV exports.
- Use Supabase Auth for dashboard identity and Supabase PostgreSQL for hosted persistence.
- Use Render to host the API and web dashboard.
- Make privacy, security, scientific limitations, tests, and deployment reproducible.

## 4. Non-Goals and Safety Boundaries

- EdgeErgo is not a medical diagnostic tool or a replacement for a qualified ergonomic assessment.
- It must not claim to predict injuries with certainty.
- It must not rank employees or support disciplinary or performance decisions.
- It must not perform facial recognition or infer emotion, mental health, attention, productivity, stress, or intent.
- Facial-expression analysis is outside the initial V3 scope.
- Raw frames, video, face crops, and raw pose landmarks must not be uploaded centrally.
- The hosted dashboard must not be presented as live camera monitoring.
- A successful UI build or a demo score alone does not mean the product is complete.

## 5. Users and Roles

- **Workstation user:** Starts or pauses local assessment, sees feedback, and understands camera and synchronization status.
- **Reviewer:** Views authorized assessment summaries, trends, and exports.
- **Administrator:** Manages users and roles, enrolls and revokes devices, and configures organization settings.
- **Developer/evaluator:** Runs the system, verifies requirements, and reviews tests and deployment evidence.

All permissions must be enforced by the backend and database policies, not only by hiding UI elements.

## 6. Main User Journey

1. An administrator signs in to the dashboard.
2. An administrator creates a short-lived, single-use device-enrollment token.
3. A workstation user installs and launches the Windows edge agent and completes enrollment.
4. The user grants camera access and sees a clear privacy notice.
5. The edge agent estimates posture locally and shows feedback only when observations are valid.
6. Assessment events are persisted locally.
7. During an internet outage, local operation continues and eligible events remain queued.
8. On reconnection, the agent synchronizes events over HTTPS using a device-specific credential.
9. The hosted API validates and persists approved events, returning per-event accepted, duplicate, or rejected results.
10. An authorized reviewer filters dashboard summaries and exports permitted data.
11. An administrator revokes a device and verifies it can no longer upload records.

## 7. Functional Requirements

### 7.1 Edge Camera and Vision

- **FR-001:** Capture webcam frames locally only after camera access is granted.
- **FR-002:** Use OpenCV and a suitable pose-estimation model for local inference.
- **FR-003:** Separate capture, vision, feature extraction, scoring, UI, storage, and synchronization into testable modules.
- **FR-004:** Handle camera denial or unavailability, model failure, and processing errors safely.
- **FR-005:** Support pause/resume and configurable sampling intervals.
- **FR-006:** Show clear active, paused, unavailable, low-confidence, offline, syncing, and authentication-failure states.
- **FR-007:** Do not save frames or video by default.
- **FR-008:** Never replace missing or occluded landmarks with fabricated values.

### 7.2 Features and Ergonomic Scoring

- **FR-009:** Calculate relevant joint and body-segment features from valid pose landmarks.
- **FR-010:** Implement RULA and/or REBA only from a documented, reviewed methodology and applicable scoring rules.
- **FR-011:** Keep feature extraction separate from scoring logic.
- **FR-012:** Version the scoring method and store its version with each event.
- **FR-013:** Mark observations unavailable or invalid when visibility, confidence, or camera placement is insufficient.
- **FR-014:** Show a score only when required inputs are valid.
- **FR-015:** Link recommendations to specific observations or scoring rules.
- **FR-016:** Test score logic against reference cases and boundary conditions before claiming correctness.
- **FR-017:** Present scores as screening indicators, not diagnoses or definitive injury predictions.

### 7.3 Desktop Overlay

- **FR-018:** Provide a compact desktop overlay using PySide6 or a justified equivalent.
- **FR-019:** Show assessment state, a valid score/category if available, concise guidance, and last-update time.
- **FR-020:** Avoid stealing focus or blocking normal work.
- **FR-021:** Support quiet mode and configurable reminder cooldowns.
- **FR-022:** Provide pause/resume and settings/status controls.
- **FR-023:** Use neutral, actionable language and never show another workstation's records.
- **FR-024:** Explain what is processed locally and what data may synchronize.

### 7.4 Local Storage and Offline Operation

- **FR-025:** Use SQLite for local settings, assessment history, synchronization queue, and acknowledgements.
- **FR-026:** Use migrations and transactions for local schema changes.
- **FR-027:** Persist assessment and queue entries safely across application restarts.
- **FR-028:** Generate a stable unique event ID for every syncable event.
- **FR-029:** Retry transient synchronization failures with bounded exponential backoff and jitter.
- **FR-030:** Distinguish transient failures from permanent validation/authentication errors.
- **FR-031:** Acknowledge or remove queue entries only after explicit server confirmation.
- **FR-032:** Recover stale in-flight queue entries after a crash or restart.
- **FR-033:** Display queue depth, last successful synchronization, and a safe error status.
- **FR-034:** Define retention rules for local records.
- **FR-035:** Store device credentials in OS-protected storage where feasible, not plain configuration files.

### 7.5 Device Enrollment, Authentication, and Synchronization

- **FR-036:** Support administrator-controlled enrollment using a short-lived, single-use token.
- **FR-037:** Issue a device-specific, revocable credential after enrollment.
- **FR-038:** Require authentication for every production device upload.
- **FR-039:** Ensure a device can submit events only for its authenticated device identity.
- **FR-040:** Support device credential revocation and rotation.
- **FR-041:** Use HTTPS for all hosted communication.
- **FR-042:** Send only an allowlisted, minimized payload.
- **FR-043:** Support bounded batch uploads with explicit per-event accepted, duplicate, or rejected results.
- **FR-044:** Make retries idempotent so a timeout cannot create duplicate records.
- **FR-045:** Never bypass authentication when a credential is invalid, expired, or revoked.

Dashboard user authentication and device authentication are separate concerns. Supabase Auth handles dashboard users. The edge agent must use its own scoped device credential; it must not embed an administrator key, Supabase service-role key, or other privileged secret.

### 7.6 Hosted API and Supabase Database

- **FR-046:** Provide a versioned FastAPI service with validated request and response schemas.
- **FR-047:** Use Supabase PostgreSQL as the hosted database.
- **FR-048:** Manage schema changes through version-controlled SQL migrations in `supabase/migrations/`.
- **FR-049:** Validate IDs, timestamps, numeric ranges, enums, payload sizes, and batch sizes.
- **FR-050:** Persist accepted events transactionally before acknowledging success.
- **FR-051:** Support enrollment, device heartbeat/status, revocation, ingestion, dashboard queries, and exports.
- **FR-052:** Require Supabase-authenticated users and server-side role authorization for protected dashboard endpoints.
- **FR-053:** Configure explicit production CORS origins and safe error responses.
- **FR-054:** Provide bounded date filters and pagination.
- **FR-055:** Never log credentials, raw camera data, or sensitive request bodies.
- **FR-056:** Fail closed if required production security configuration is missing.
- **FR-057:** Do not use Render's ephemeral application filesystem as the production database.
- **FR-058:** Use Supabase Row Level Security (RLS) for browser-accessible data and enforce authorization in the API as well.
- **FR-059:** Keep the Supabase service-role key exclusively in trusted server-side environment variables, never in frontend code or the edge-agent package.
- **FR-060:** Use a least-privilege database access strategy and parameterized queries.
- **FR-061:** Keep development, test, and production credentials separate.
- **FR-062:** Provide separate liveness and readiness endpoints; readiness must verify required dependencies without exposing secrets.

### 7.7 Dashboard and Reporting

- **FR-063:** Use React, TypeScript, Vite, and Tailwind CSS or a justified equivalent styling system.
- **FR-064:** Provide overview summaries, assessment views, device status, and report/export views.
- **FR-065:** Show the relevant date range, sample count, units, and unavailable data.
- **FR-066:** Ensure CSV exports respect permissions and active filters.
- **FR-067:** Include loading, empty, error, and success states.
- **FR-068:** Do not display fabricated metrics as real production data. Clearly label any development-only fixtures.
- **FR-069:** Make charts accessible through labels and textual summaries.
- **FR-070:** Configure the API base URL through environment variables; do not hardcode production URLs.
- **FR-071:** Provide sign-in, sign-out, session restoration, and protected-route behavior using Supabase Auth.
- **FR-072:** Show role-appropriate screens while relying on server-side authorization for actual protection.
- **FR-073:** Include a clear session-expired and access-denied experience.

### 7.8 Deployment, Packaging, and Operations

- **FR-074:** Provide reproducible local setup instructions.
- **FR-075:** Deploy the FastAPI backend as a Render web service.
- **FR-076:** Deploy the React frontend as a Render static site unless a documented deployment constraint justifies another Render service type.
- **FR-077:** Use Render environment variables for backend secrets and environment-specific settings.
- **FR-078:** Use `render.yaml` where practical to describe the Render services and build/start commands. Do not commit secrets to it.
- **FR-079:** Configure frontend build-time variables safely. Only public Supabase project URL and publishable/anon key may be included in browser code; never expose the service-role key.
- **FR-080:** Configure production CORS to allow only the deployed frontend origin and any explicitly approved origins.
- **FR-081:** Package the Windows edge agent using PyInstaller or a justified equivalent after core functionality is tested.
- **FR-082:** Never embed production credentials in executables or frontend bundles.
- **FR-083:** Run CI checks for linting, type checks, tests, database migrations, and dashboard builds.
- **FR-084:** Document installation, upgrade, rollback, backup, restore, revocation, and troubleshooting.
- **FR-085:** Measure resource usage and responsiveness on documented hardware before publishing performance claims.
- **FR-086:** Document Render deployment, health checks, environment variables, logs, and restart behavior.
- **FR-087:** Verify Supabase backup and restore options appropriate to the selected plan and test recovery procedures.

## 8. Supabase Data and Access Design

The exact schema must be implemented as version-controlled migrations and reviewed before production use. The initial design should include:

- **profiles:** Supabase Auth user ID, display name, and application role or role reference.
- **organizations:** organization metadata if multi-organization support is enabled for the first release.
- **organization_members:** links users to organizations and their roles, if organization scoping is enabled.
- **devices:** pseudonymous device ID, organization/owner scope, status, enrollment and last-seen metadata, credential metadata but never plaintext device secrets.
- **assessment_events:** stable event ID, device ID, timestamp, scoring method/version, approved score/features, validity indicators, and necessary software metadata.
- **device_enrollment_tokens:** hashed token, expiry, single-use status, creator, and consumption metadata.
- **audit_events:** security-relevant administrative actions without secrets or raw camera-derived data.

Use UUIDs where appropriate, foreign keys, indexes for common filters, check constraints for valid values, and unique constraints for idempotent event ingestion.

RLS must be enabled on tables exposed to the Supabase client. Users must not be able to assign themselves administrator roles. Role changes and sensitive administrative operations must be performed through trusted server-side code. The backend must derive user identity from a verified Supabase access token and enforce organization and role permissions on every protected operation.

Do not assume that hiding a page, using a frontend role check, or possessing a device ID grants authorization.

## 9. Privacy Requirements

1. Raw frames and video remain on the edge workstation.
2. Raw face crops and raw pose landmarks are not sent to the central service.
3. Central data is minimized to approved assessment summaries and necessary operational metadata.
4. A device ID is pseudonymous, not automatically anonymous.
5. Permitted payload fields may include event ID, pseudonymous device ID, timestamp, scoring method/version, approved scores/features, validity indicators, and necessary software metadata.
6. The API rejects unsupported fields and enforces an allowlisted schema.
7. Users can see when analysis is active and understand what synchronizes.
8. Retention, access, deletion, and pilot-notice policies must be defined before real workplace deployment.
9. Privacy claims must be verified through payload inspection, tests, logs, and exports.
10. Raw media capture for debugging is not permitted by default.
11. No secrets, access tokens, or service-role credentials may appear in logs, source control, frontend bundles, or packaged agent files.
12. Dashboard access and device ingestion must be tested against unauthorized, cross-device, and cross-organization access attempts.

## 10. Non-Functional Requirements

- **Performance:** Aim for responsive local feedback on a supported Windows laptop. Measure startup time, processing latency, CPU, memory, throughput, and dropped frames before setting release thresholds.
- **Reliability:** Local assessment continues during network outages; queued records survive normal restarts.
- **Security:** Hosted traffic uses HTTPS; dashboard access is authenticated; device credentials are scoped and revocable; production endpoints fail closed.
- **Maintainability:** Clear module boundaries, typed API contracts, migrations, deterministic tests, and documented setup.
- **Accessibility:** Keyboard-operable dashboard, visible focus, readable text, semantic labels, accessible chart summaries, and status cues that do not rely on color alone.
- **Portability:** Windows is the initial supported edge platform. Other operating systems are not promised until tested.
- **Observability:** Structured, sanitized logs without secrets or raw camera-derived data.
- **Deployment:** Clean-checkout builds and documented Render deployment must be repeatable.

## 11. Target Technology Stack

The companion `TECH_STACK.md` defines the selected implementation technologies. Exact versions must be pinned during implementation and verified for compatibility.

## 12. Acceptance Criteria

V3 is eligible for a controlled pilot only when applicable criteria are verified:

- [ ] A clean checkout can be configured using documented instructions.
- [ ] Frontend and backend build successfully from the new repository.
- [ ] Supabase migrations apply to a clean test database.
- [ ] Supabase Auth sign-in, sign-out, and session restoration work.
- [ ] RLS and backend authorization prevent unauthorized and cross-organization data access.
- [ ] Camera denial, camera absence, model failure, low confidence, and pause/resume are handled correctly.
- [ ] Missing landmarks never produce fabricated numeric scores.
- [ ] Scoring rules have documented sources and pass reference-case and boundary tests.
- [ ] Events and queue entries persist across process restarts.
- [ ] Offline events synchronize after reconnection without duplicates.
- [ ] Unauthenticated device uploads are rejected in production.
- [ ] Invalid and revoked device credentials are rejected.
- [ ] A device cannot impersonate another device.
- [ ] No raw frames, video, face crops, or raw landmarks appear in central requests, records, logs, or exports.
- [ ] Dashboard values and CSV exports match test fixtures and selected filters.
- [ ] Render API and frontend deployments pass health and smoke tests.
- [ ] Production secrets are stored only in appropriate environment variables or protected storage.
- [ ] Windows installation and launch are tested in a clean environment.
- [ ] Performance is measured on documented hardware.
- [ ] Supabase backup and recovery procedures are documented and tested as supported by the chosen plan.
- [ ] Published claims match actual evidence and known limitations.

## 13. Implementation Phases

1. **Foundation:** Initialize the new repository, frontend, backend, edge-agent skeleton, environment examples, formatting/linting, and CI.
2. **Supabase foundation:** Configure the existing Supabase project, create migrations, enable RLS, establish roles and access policies, and test schema setup.
3. **Hosted API:** Implement FastAPI configuration, Supabase token verification, role authorization, health endpoints, and validated response/error schemas.
4. **Dashboard authentication:** Implement Supabase Auth flows, protected routes, session handling, and basic responsive layout.
5. **Dashboard data:** Add real assessment summaries, filters, device status, and CSV exports against the real API; do not use fabricated production metrics.
6. **Edge core:** Implement camera lifecycle, pose adapter, quality checks, feature calculation, versioned scoring, and desktop overlay.
7. **Offline synchronization:** Add SQLite migrations, durable queue, enrollment, scoped device credentials, retries, acknowledgements, and restart recovery.
8. **Render deployment:** Deploy API and frontend, configure environment variables, CORS, health checks, logs, and smoke tests.
9. **Packaging and pilot validation:** Build the Windows agent, test on a clean machine, validate privacy boundaries, test multi-device authorization, and measure performance.

## 14. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Camera placement or occlusion makes estimates unreliable | Setup guidance, quality gates, and an unavailable state |
| Scoring implementation is inaccurate | Authoritative methodology, independent review, and reference tests |
| Device credential is exposed | OS-protected storage, revocation, rotation, and sanitized logs |
| Network failure loses or duplicates events | Durable queue, stable IDs, acknowledgements, and idempotency tests |
| Supabase policy is misconfigured | RLS tests, backend authorization tests, and least privilege |
| Privileged key leaks into browser or executable | Environment separation, secret scanning, and bundle inspection |
| Hosted data is lost | Supabase backup/recovery plan and restore drills |
| Render filesystem is treated as durable storage | Keep persistent application data in Supabase and local agent data in SQLite |
| Edge processing is too heavy | Profile early, adjust sampling, and optimize from measurements |
| Users interpret scores as medical judgments | Clear limitations, neutral feedback, and no diagnostic claims |
| Dashboard exposes excess data | Data minimization, role checks, scoped queries, and export tests |
| Dependency/model licensing issue | License review and version pinning before release |

## 15. Decisions and Configuration to Confirm During Implementation

- Exact Supabase project URL and publishable/anon key, stored in local environment configuration.
- Backend-only Supabase secret/service-role key or preferred least-privilege database connection approach, stored only in Render secret environment variables.
- Whether the first release is single-organization or multi-organization.
- Exact RULA/REBA methodology, authoritative references, and implementation constraints.
- Retention/deletion periods for local records, central records, heartbeats, logs, and backups.
- Minimum supported Windows version and hardware baseline.
- Device credential format, storage, rotation, and expiry.
- Render service names, regions, health-check paths, and deployment settings.
- Supabase backup capabilities available under the existing project plan.

Do not commit `.env` files or secrets. Commit only safe `.env.example` files with placeholder values.

## 16. Antigravity Implementation Rules

Use this PRD and `TECH_STACK.md` as the source of truth while coding.

- Inspect the current repository before editing; it is expected to be a clean V3 repository.
- Implement in small, verifiable phases instead of generating the whole application in one pass.
- Before each phase, list the files to create/change and the acceptance checks for that phase.
- Do not silently change the product scope, stack, privacy boundaries, or deployment targets.
- Do not fabricate completed features, tests, deployment URLs, or metrics.
- Do not use mock data as if it were production data.
- Never commit secrets or put privileged keys in frontend or edge-agent code.
- Add tests alongside features and run the relevant checks before marking work complete.
- Use database migrations for schema changes; do not rely on manual dashboard edits as the only record of schema.
- Keep API contracts and environment variable names documented and consistent.
- If a requirement is ambiguous or a security decision is consequential, explain the options and ask before making an irreversible assumption.
- At the end of each phase, report changed files, commands run, test results, known limitations, and the next phase.
- Do not claim deployment succeeded unless the live service has actually been checked.

## Product Definition of Done

EdgeErgo V3 is not complete merely because the UI runs or a demo produces a score. It must satisfy applicable acceptance criteria, pass automated and manual tests, demonstrate its privacy and authorization boundaries with evidence, document scientific limitations, and provide reproducible setup, deployment, and recovery procedures.
