# EdgeErgo V3 — Pinned Dependencies & License Review

**Date:** 2026-10-20  
**Environment:** Windows 10/11 x64, Python 3.10.11, Node.js v22.23.2

All dependencies across backend, edge-agent, and frontend are explicitly verified for compatibility, pinned, and reviewed for license compliance with commercial and privacy-preserving deployment.

---

## 1. Backend Service (`backend/`)

Python version: `>=3.10,<3.11` (Runtime verified: Python 3.10.11 AMD64)

| Package | Pinned Version | License | Responsibility & Justification |
|---|---|---|---|
| `fastapi` | `0.111.1` | MIT | High-performance asynchronous web framework for REST API |
| `uvicorn[standard]` | `0.30.6` | BSD-3-Clause | Production ASGI server |
| `pydantic` | `2.13.5` | MIT | Request/response data validation and serialization |
| `pydantic-settings` | `2.3.4` | MIT | Strongly typed environment variable management |
| `sqlalchemy` | `2.0.52` | MIT | SQL ORM, pooled database connections, query building |
| `alembic` | `1.20.0` | MIT | Version-controlled database schema migrations |
| `asyncpg` | `0.32.0` | Apache-2.0 | High-speed asynchronous PostgreSQL client driver |
| `psycopg[binary]` | `3.3.6` | BSD-3-Clause | Synchronous/asynchronous PostgreSQL driver |
| `pyjwt[crypto]` | `2.10.1` | MIT | JWT token decoding, asymmetric JWKS verification |
| `cryptography` | `45.0.5` | Apache-2.0 / BSD-3-Clause | Cryptographic operations and token hashing |
| `httpx` | `0.27.2` | BSD-3-Clause | Asynchronous HTTP client for JWKS fetching and tests |
| `pytest` | `9.0.2` | MIT | Test framework (dev/test) |
| `pytest-asyncio` | `0.23.8` | Apache-2.0 | Async test runner for FastAPI test client (dev/test) |

---

## 2. Windows Edge Agent (`edge-agent/`)

Python version: `>=3.10,<3.11` (Runtime verified: Python 3.10.11 AMD64)

| Package | Pinned Version | License | Responsibility & Justification |
|---|---|---|---|
| `opencv-python` | `4.11.0.86` | Apache-2.0 | Local webcam capture, frame processing, BGR/RGB conversion |
| `mediapipe` | `0.10.35` | Apache-2.0 | On-device Pose landmark estimation via Tasks API (`PoseLandmarker`) using local pre-packaged `pose_landmarker_lite.task` model asset (Apache-2.0) |
| `numpy` | `1.26.4` | BSD-3-Clause | Vector geometry, angle calculations, spatial normalization |
| `PySide6` | `6.8.3` | LGPL-3.0 | Modern Windows desktop UI overlay, system tray, notifications. Note: LGPL compliant via dynamic linking |
| `keyring` | `25.7.0` | MIT | Windows Credential Manager integration for device secrets |
| `httpx` | `0.27.2` | BSD-3-Clause | HTTPS client for enrollment, heartbeat, and batch sync |
| `pyinstaller` | `6.22.3` | GPL-2.0 with Exception | Windows binary packaging; special exception allows commercial proprietary app distribution |
| `pytest` | `9.0.2` | MIT | Automated test framework for geometry, scoring, and storage (dev/test) |

---

## 3. Web Dashboard (`frontend/`)

Runtime: Node.js v22.23.2, npm 10.9.8

| Package | Pinned Version | License | Responsibility & Justification |
|---|---|---|---|
| `react` | `18.3.1` | MIT | Declarative UI component library |
| `react-dom` | `18.3.1` | MIT | React DOM renderer |
| `vite` | `6.0.3` | MIT | Fast frontend build tool and local dev server |
| `typescript` | `5.6.3` | Apache-2.0 | Static typing and strict compiler checks |
| `tailwindcss` | `3.4.16` | MIT | Utility-first CSS styling conforming to `DESIGN.md` |
| `lucide-react` | `0.468.0` | ISC | Accessible, clean UI iconography |
| `@supabase/supabase-js` | `2.47.10` | MIT | Supabase Auth client for session and token management |
| `vitest` | `2.1.8` | MIT | Fast unit test runner matching Vite configuration |
| `@testing-library/react` | `16.1.0` | MIT | Component test utilities |
| `@testing-library/jest-dom` | `6.6.3` | MIT | Custom DOM element matchers |
| `eslint` | `9.17.0` | MIT | Code quality and linting |
| `prettier` | `3.4.2` | MIT | Code formatting |


---

## 4. License Compliance Summary

- All core backend, frontend, and edge agent libraries use permissive open-source licenses (MIT, Apache-2.0, BSD-3-Clause, ISC).
- `PySide6` is licensed under LGPLv3: the edge agent dynamically links to Qt runtime binaries and does not modify the Qt source code, complying with LGPLv3 redistribution requirements.
- `pyinstaller` is licensed under GPLv2 with a special runtime exception that explicitly grants permission to distribute proprietary and closed-source executables bundled by PyInstaller.
- No restrictive copyleft (AGPL) dependencies are used in any service or bundle.
