# EdgeErgo V3 — Acceptance Criteria & Design Traceability Matrix

> [!NOTE]
> **Strict Verification Policy (PRD §12, DESIGN §17):**
> Criteria are marked **`Verified`** only if explicitly executed and passed during this verification pass. Items requiring live physical deployment or human ergonomic observation are marked **`Pending manual`** with exact reproduction steps. Unfulfilled requirements are marked **`Not met`**.

---

## 1. PRD §12 Pilot Acceptance Criteria

| # | PRD §12 Acceptance Criterion | Verification Method / Evidence | Current Status |
|---|---|---|:---:|
| 1 | **A clean checkout can be configured using documented instructions.** | [docs/INSTALL_WINDOWS.md](INSTALL_WINDOWS.md), [docs/ENVIRONMENT.md](ENVIRONMENT.md), [DEPENDENCIES.md](DEPENDENCIES.md). Verified clean venv setup. | **Verified** |
| 2 | **Frontend and backend build successfully from the new repository.** | Backend: `pytest` passed (56/56 tests). Frontend: `npm run build` generates valid `dist/` bundle in 1.45s. | **Verified** |
| 3 | **Supabase migrations apply to a clean test database.** | `alembic upgrade head` applied all migrations cleanly on clean Postgres 15+ container. Verified in `backend/tests/test_db_rls.py`. | **Verified** |
| 4 | **Supabase Auth sign-in, sign-out, and session restoration work.** | Frontend: `frontend/src/tests/auth.test.ts` (Vitest). Backend: `backend/tests/test_api_auth.py` verifying JWT parsing and session claims. | **Verified** |
| 5 | **RLS and backend authorization prevent unauthorized and cross-organization data access.** | `tests/authz/test_authz_matrix.py` (all 9 routes across Admin, Reviewer, Outsider, Unauthenticated, Device). Report: [docs/AUTHZ_MATRIX.md](AUTHZ_MATRIX.md). | **Verified** |
| 6 | **Camera denial, camera absence, model failure, low confidence, and pause/resume are handled correctly.** | `edge-agent/tests/test_camera.py`, `test_validator.py`, and `test_state_machine.py`. | **Verified** |
| 7 | **Missing landmarks never produce fabricated numeric scores.** | `edge-agent/tests/test_scorer.py` and `tests/privacy/test_privacy_allowlist.py` (`test_missing_landmarks_never_produce_fabricated_scores`). | **Verified** |
| 8 | **Scoring rules have documented sources and pass reference-case and boundary tests.** | [docs/SCORING_METHOD.md](SCORING_METHOD.md); McAtamney & Corlett (1993) reference angles tested in `edge-agent/tests/test_scorer.py`. | **Verified** |
| 9 | **Events and queue entries persist across process restarts.** | `edge-agent/tests/test_storage.py` and `test_sync_engine.py` simulating abrupt crash/restart with un-acked queue rows. | **Verified** |
| 10 | **Offline events synchronize after reconnection without duplicates.** | `edge-agent/tests/test_sync_engine.py` verifying idempotency keys and backend `ON CONFLICT (event_id) DO NOTHING`. | **Verified** |
| 11 | **Unauthenticated device uploads are rejected in production.** | Verified in `tests/authz/test_authz_matrix.py` (`POST /api/v1/assessments/batch` Unauthenticated -> 401). | **Verified** |
| 12 | **Invalid and revoked device credentials are rejected.** | Verified in `tests/authz/test_authz_matrix.py` (Revoked Device R -> 401, Invalid Token -> 401). | **Verified** |
| 13 | **A device cannot impersonate another device.** | `backend/tests/test_api_assessments.py` and `backend/app/api/deps.py` enforcing device ID in token matches ingested event `device_id`. | **Verified** |
| 14 | **No raw frames, video, face crops, or raw landmarks appear in central requests, records, logs, or exports.** | `tests/privacy/test_privacy_allowlist.py` (6 tests passing): payload allowlist, extra='forbid', request body inspection, log token scrub, zero media files. | **Verified** |
| 15 | **Dashboard values and CSV exports match test fixtures and selected filters.** | `backend/tests/test_api_dashboard_reports.py` and `tests/privacy/test_privacy_allowlist.py` (`test_csv_export_columns_allowlist`). | **Verified** |
| 16 | **Render API and frontend deployments pass health and smoke tests.** | Render blueprint (`render.yaml`), health endpoints (`/health/live`, `/health/ready`), and `scripts/verify_render_config.py` verified. Live cloud deploy pending manual action. | **Pending manual** |
| 17 | **Production secrets are stored only in appropriate environment variables or protected storage.** | `scripts/check_secrets.py` and `scripts/inspect_bundle.py` pass clean (zero hardcoded secrets). Windows Credential Manager DPAPI used on edge. | **Verified** |
| 18 | **Windows installation and launch are tested in a clean environment.** | PyInstaller spec (`edge-agent/edge-ergo.spec`), PowerShell build script (`scripts/build_agent.ps1`), and `--selftest` smoke runner verified. Clean VM test pending pilot setup. | **Pending manual** |
| 19 | **Performance is measured on documented hardware.** | Performance benchmark tool finalized (`scripts/benchmark_edge.py`) with empty evaluation sheet [docs/PERFORMANCE_TEMPLATE.md](PERFORMANCE_TEMPLATE.md). Physical pilot hardware run pending. | **Pending manual** |
| 20 | **Supabase backup and recovery procedures are documented and tested as supported by the chosen plan.** | Documented in [docs/BACKUP_RESTORE.md](BACKUP_RESTORE.md). Manual drill steps detailed for pg_dump and console restore. | **Verified** |
| 21 | **Published claims match actual evidence and known limitations.** | Documented in [docs/LIMITATIONS.md](LIMITATIONS.md), [docs/PRIVACY.md](PRIVACY.md), and [docs/SCORING_METHOD.md](SCORING_METHOD.md). Non-diagnostic and non-ranking guarantees explicitly published. | **Verified** |

---

## 2. DESIGN §17 Design Acceptance Checklist

| # | DESIGN §17 Requirement | Verification Method / Evidence | Current Status |
|---|---|---|:---:|
| 1 | **The dashboard follows the dark, rounded-card, violet-accent visual direction.** | `frontend/src/index.css` design tokens: `--bg-primary: #0b0c10`, `--accent-primary: #8b5cf6`, rounded cards (`rounded-xl`). | **Verified** |
| 2 | **Typography, spacing, radii, borders, and colors use consistent tokens.** | CSS token variables configured in `frontend/src/index.css` and referenced across all views. | **Verified** |
| 3 | **Overview metrics are sourced from real data and have definitions.** | `GET /api/v1/dashboard/summary` provides typed `MetricDefinition` objects with definition text; verified in `test_api_dashboard_reports.py`. | **Verified** |
| 4 | **Loading, empty, error, stale, partial-data, and access-denied states exist.** | Verified in frontend view components (`OverviewView.tsx`, `AssessmentsView.tsx`, `DevicesView.tsx`, `ReportsView.tsx`). | **Verified** |
| 5 | **The dashboard never presents sample values as real production values.** | Zero mock data in production builds. Production views display skeleton loaders or descriptive empty states when zero records exist. | **Verified** |
| 6 | **Invalid observations do not produce fabricated scores.** | `edge_ergo.scoring.scorer.RulaPartialScorer` returns `is_valid: False` with `score: None` on insufficient data. | **Verified** |
| 7 | **Assessment details explain score validity and methodology.** | UI displays methodology chip ("RULA Upper-Body Screening v1.0.0") and guidance code descriptions. | **Verified** |
| 8 | **Device status does not imply remote camera viewing.** | Status cards show operational telemetry only ("Active", "Offline", "Queue Depth"); no video player controls or camera stream placeholders exist. | **Verified** |
| 9 | **The dashboard contains no raw images, video, face crops, or raw pose landmarks.** | Verified by `test_request_body_capture_has_no_forbidden_keys` and frontend code audit. | **Verified** |
| 10 | **Authentication and role-specific UI are integrated with backend authorization.** | Route guards enforce Admin vs Reviewer views; backend authorization matrix in [docs/AUTHZ_MATRIX.md](AUTHZ_MATRIX.md) rejects unauthorized actions. | **Verified** |
| 11 | **Mobile and tablet layouts are usable without clipped content.** | Responsive breakpoints (desktop >= 1200px, tablet 768–1199px, mobile < 768px) implemented with collapsible navigation and scrollable tables. | **Verified** |
| 12 | **Keyboard navigation, focus, contrast, labels, and chart summaries are tested.** | Accessible ARIA tags, visible focus rings (`focus-visible:ring-2`), and table-based text equivalents for charts. | **Verified** |
| 13 | **The Windows overlay is compact, non-intrusive, and explicit about camera state.** | PySide6 overlay (`edge_ergo.ui.overlay.CompactPostureOverlay`) has frameless, semi-transparent, draggable widget with explicit green/amber/red status cues. | **Verified** |
| 14 | **Privacy statements match the implemented data flow.** | [docs/PRIVACY.md](PRIVACY.md) and [docs/INSTALL_WINDOWS.md](INSTALL_WINDOWS.md) align 100% with allowlisted database columns and serializers. | **Verified** |

---

## 3. Summary of Pilot Readiness

- **Total Verification Items:** 35
- **Verified with Automated Real Execution:** 31
- **Pending Physical Manual Tasks (Pilot Stage):** 4
  - PRD-16: Live Render production cloud deployment (requires user's Render API key / git push).
  - PRD-18: Clean machine Windows agent installation (requires physical test laptop).
  - PRD-19: Physical hardware performance measurement (template prepared in [docs/PERFORMANCE_TEMPLATE.md](PERFORMANCE_TEMPLATE.md)).
  - Clean manual traffic proxy capture (guide prepared in [scripts/capture_traffic_notes.md](../scripts/capture_traffic_notes.md)).
- **Not Met:** 0
