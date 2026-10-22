# EdgeErgo V3 — Comprehensive Privacy Architecture & Data Governance

This document defines the strict privacy boundaries, data minimization principles, and governance controls implemented in EdgeErgo V3 per PRD §7.8, §9, §12, and DESIGN §10.

---

## 1. Complete Data Flow & Minimization Matrix

| Data Item | Stays Local to Workstation | Synchronizes to Central Cloud | Local Retention | Cloud Retention | Access Permissions |
|---|:---:|:---:|:---:|:---:|---|
| **Raw Webcam Video & RGB Frames** | **YES (In-Memory Only)** | **NEVER** | 0s (Discarded immediately after frame inference) | N/A | None (Never written to disk or network) |
| **Raw Facial Crops / Head Photos** | **YES (Never Captured)** | **NEVER** | 0s | N/A | None |
| **Raw 33 Joint Pose Landmarks (X, Y, Z coordinates)** | **YES (In-Memory Only)** | **NEVER** | Discarded after computing joint angles & RULA features | N/A | Local vision pipeline only |
| **Calculated Postural Features (Neck, Trunk, Arm Angles)** | **YES** | **NEVER (Only risk score + guidance codes sync)** | 90 days in local SQLite | N/A | Local user overlay |
| **Screening Scores (RULA Partial Score, e.g. 3.0)** | **YES** | **YES (Allowlisted JSON payload)** | 90 days in local SQLite | Organization-defined (e.g. 1 year) | Admin & Reviewer roles in owning organization |
| **Postural Guidance Codes (e.g. `NECK_FLEXION_MILD`)** | **YES** | **YES (Allowlisted JSON payload)** | 90 days in local SQLite | Organization-defined (e.g. 1 year) | Admin & Reviewer roles in owning organization |
| **Workstation Device Secret (`eed_*.secret`)** | **YES (Windows Credential Manager)** | **NEVER (Only SHA-256 hash stored in DB)** | Until de-enrollment | N/A | Windows OS DPAPI / Local agent process |
| **Single-Use Enrollment Token (`eet_*`)** | Discarded after enrollment | Stored as SHA-256 hash in DB | Discarded | Expired / Deleted after 15 minutes | Admin only during generation |
| **Workstation Heartbeat Metadata (version, queue depth)** | **YES** | **YES** | Cached in local DB | 30 days rolling | Admin & Reviewer roles in owning organization |
| **System Tray Error / Crash Diagnostics Logs** | **YES (`%LOCALAPPDATA%\EdgeErgo\logs`)** | **NEVER** | 14 days local rolling | N/A | Local user only (secrets sanitized) |

---

## 2. Technical Safeguards & Privacy Enforcement

1. **Strict Backend Schema Allowlisting (FR-011, FR-084):**
   - The ingestion endpoint (`POST /api/v1/assessments/batch`) uses Pydantic schemas configured with `extra = "forbid"`.
   - If an edge agent or attacker attempts to send unexpected keys (e.g., `landmarks`, `image`, `frame`, `face`), the request is immediately rejected with **HTTP 422 Unprocessable Entity**.
2. **Payload Allowlist Automated Verification (`tests/privacy/`):**
   - Automated tests compare the edge serializer fields, Pydantic schemas, and database columns to ensure zero landmark or image attributes exist anywhere in the pipeline.
3. **Log Sanitization Filter (FR-017):**
   - Structured logging pipelines sanitize request bodies, query strings, and exception traces. Device secrets, JWTs, and landmark arrays are strictly redacted before output.
4. **Zero-Disk Media Invariant:**
   - The edge agent camera loop creates zero `.jpg`, `.png`, `.mp4`, or temporary video files. Verified continuously via `test_no_media_files_created_during_assessment`.

---

## 3. Pilot Privacy Notice & Employee Consent Agreement Template

Enterprise human resources and safety committees must provide this disclosure to workstation users:

```text
================================================================================
           EDGEERGO WORKPLACE ERGONOMIC PILOT — PRIVACY DISCLOSURE
================================================================================

1. PURPOSE OF THE PILOT:
   The EdgeErgo system is deployed to help identify ergonomic risk factors
   (such as sustained neck flexion or improper monitor heights) to support
   workplace wellness and self-directed posture correction.

2. CAMERA PRIVACY GUARANTEE:
   - Your webcam is used exclusively for real-time mathematical joint angle
     estimation.
   - All video processing occurs directly in memory on your laptop/workstation.
   - NO IMAGES, NO VIDEO RECORDINGS, and NO FACIAL RECOGNITION data are ever
     saved to your hard drive or transmitted across the company network.

3. CENTRAL DATA COLLECTION:
   - The only information sent to the ergonomic dashboard is anonymous, aggregated
     posture screening scores (e.g. "Neck Score: 2") and general software status.
   - Individual employee names are not attached to workstation risk records.

4. NON-PUNITIVE USE COVENANT:
   - Management and HR explicitly agree that EdgeErgo data SHALL NEVER be used
     for employee performance evaluations, productivity measurement, working
     hours monitoring, or disciplinary action.
   - There are no leaderboards, individual rankings, or performance scores.

5. PARTICIPANT CONTROL:
   - You may pause posture analysis at any time using the desktop menu.
   - A clear indicator shows when the camera is in use.
   - You may opt out of the pilot at any time without penalty.

I have read and understand this Privacy Disclosure:

Employee Name (Print): ________________________________________________________

Signature: _____________________________________   Date: ______________________
================================================================================
```
