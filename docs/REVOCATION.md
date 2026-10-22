# EdgeErgo V3 — Workstation Revocation & De-enrollment Guide

This document details the revocation lifecycle of EdgeErgo workstation devices, server-side enforcement, edge agent behavior, and cryptographic audit guarantees per PRD §7.4, FR-032, and FR-060.

---

## 1. When to Revoke a Workstation

Administrators should revoke a workstation when:
- A laptop or desktop is lost, stolen, or reassigned to a different employee.
- A workstation is decommissioned or reformatted.
- An anomalous telemetry pattern or compromised network token is suspected.
- A pilot user withdraws from the program.

---

## 2. Revocation Procedure via Web Dashboard

1. Log into the EdgeErgo Web Dashboard with an **Admin** role account.
2. Navigate to **Devices**.
3. Locate the target workstation in the inventory table.
4. Click the device row or action menu and select **Revoke Device**.
5. Confirm the action in the security prompt:
   - The dashboard issues a `POST /api/v1/devices/{device_id}/revoke` request.
   - The backend transitions `devices.status` to `'revoked'` and sets `devices.revoked_at = NOW()`.
   - An immutable record is created in `audit_events` logging the user ID, device ID, timestamp, and action.

---

## 3. Server-Side Enforcement (Fail-Closed)

Once revoked in PostgreSQL:
- **Instant Heartbeat Invalidation:** The next heartbeat sent by the agent (`POST /api/v1/devices/heartbeat`) immediately returns **HTTP 401 Unauthorized** with `error: "INVALID_CREDENTIALS"`.
- **Instant Ingestion Invalidation:** Batch assessment ingestion (`POST /api/v1/assessments/batch`) immediately rejects all records with **HTTP 401 Unauthorized**.
- **Timing-Attack Neutral:** In accordance with PRD §7.4, the backend dependency (`app.api.deps.get_current_device`) returns identical HTTP 401 error payloads and timing for invalid secrets, unknown public IDs, and revoked devices, preventing status enumeration attacks.
- **Tenant Scope Isolation:** Administrators from other organizations cannot see or revoke the device; attempting to access a device from another organization returns **HTTP 404 Not Found**.

---

## 4. Edge Agent Behavior upon Revocation

When the EdgeErgo agent receives an HTTP 401 response indicating revocation:
1. **Sync Engine State Transition:** The background sync worker halts outbound batch uploads and transitions the local state to `REVOKED`.
2. **Notification to User:** The desktop system tray icon displays an alert:
   > *"Workstation registration has been revoked by your administrator. Telemetry synchronization is permanently disabled."*
3. **Queue Freezing:** Outbound items remain in the local SQLite queue but will not attempt further network transmission.
4. **Credential Removal:** The user or IT administrator can execute de-enrollment to purge stored credentials from Windows Credential Manager:
   ```powershell
   edge-ergo.exe --de-enroll
   ```
   This deletes the credential from Windows Credential Manager and resets the local `device_identity` table.
