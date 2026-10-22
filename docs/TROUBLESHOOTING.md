# EdgeErgo V3 — Troubleshooting & Diagnostics Guide

This guide provides targeted remediation procedures for common edge agent and administrative issues encountered in pilot deployments.

---

## 1. Camera & Video Pipeline Issues

### Symptom: Status Indicator shows "Camera Unavailable" / Red
**Causes:**
1. Another desktop application (e.g. Microsoft Teams, Zoom, Slack) has an exclusive lock on the camera handle.
2. Windows Camera Privacy settings are blocking desktop application access.
3. Hardware privacy shutter is closed or physical USB cable is loose.

**Remediation Steps:**
1. Check whether other video applications are active. Close them or select an alternate camera.
2. Verify Windows Settings: `Settings` > `Privacy & Security` > `Camera` > Ensure `Let desktop apps access your camera` is **ON**.
3. If multiple cameras are attached (e.g., laptop camera vs external monitor webcam), restart the agent with an explicit device index:
   ```powershell
   edge-ergo.exe --device-index 1
   ```
4. Run the offline self-test to verify camera pipeline logic independent of hardware:
   ```powershell
   edge-ergo.exe --selftest
   ```

### Symptom: Posture Status shows "Insufficient Data" / Yellow
**Causes:**
1. The user's upper torso or shoulders are occluded (e.g. sitting too close, or camera angled too low).
2. Extreme backlighting (e.g. window behind user) causing silhouette keypoint degradation.
3. Heavy, bulky clothing obscuring shoulder and neck landmarks.

**Remediation Steps:**
1. Consult [LIMITATIONS.md](LIMITATIONS.md) for camera placement recommendations.
2. Position the webcam at a 30°–45° diagonal angle, approximately 1.2 meters away at eye/shoulder level.
3. Improve ambient room lighting (recommended 300–500 lux).

---

## 2. Authentication & Authorization Errors

### Symptom: Agent logs report `INVALID_CREDENTIALS` (HTTP 401)
**Causes:**
1. The device secret stored in Windows Credential Manager was cleared or corrupted.
2. An administrator revoked the workstation in the web dashboard.
3. The device clock has drifted significantly (greater than 5 minutes) from server UTC.

**Remediation Steps:**
1. Check device status in the Web Dashboard under **Devices**. If status is `revoked`, re-enrollment with a new token is required.
2. Verify Windows system clock synchronization:
   ```powershell
   w32tm /resync
   ```
3. If credentials were lost, run re-enrollment with a fresh single-use token:
   ```powershell
   edge-ergo.exe --enroll "eet_newtoken..." --api-url "https://api.edge-ergo.example.com"
   ```

### Symptom: Dashboard displays "ADMIN_REQUIRED" (HTTP 403)
**Causes:**
The authenticated user holds the `reviewer` role rather than `admin`.
**Remediation:**
Device enrollment and revocation require administrative privileges. Request an administrator to elevate the user's role or perform the device action.

---

## 3. Network Outage & Offline Synchronization

### Symptom: Agent indicates "Offline Buffer Active"
**Expected Behavior:**
This is normal operation during network disconnection, VPN drops, or flights. The agent continues capturing, evaluating, and buffering posture assessments locally in `%LOCALAPPDATA%\EdgeErgo\edge_agent.db`.
- Up to 90 days of offline records are safely buffered.
- The agent retries upload with exponential backoff and jitter (initial 5s, capped at 300s).

**Remediation if stuck after reconnecting:**
1. Verify outbound HTTPS connectivity to the API base URL:
   ```powershell
   curl.exe -i https://api.edge-ergo.example.com/health/ready
   ```
2. If the health check passes but sync is halted, check if corporate proxy SSL inspection is blocking custom certificates. Follow [capture_traffic_notes.md](../scripts/capture_traffic_notes.md) to diagnose proxy behavior.

---

## 4. Stuck Sync Queue Remediation

### Symptom: Sync Queue Depth does not decrease
**Causes:**
1. A corrupted batch payload was rejected with HTTP 422.
2. Queue entries are stuck in `in_flight` due to an unexpected process termination during network upload.

**Remediation Steps:**
1. Terminate the edge agent:
   ```powershell
   Stop-Process -Name "edge-ergo" -Force
   ```
2. Re-launch the agent. On startup, the sync queue automatically releases orphaned `in_flight` leases older than 5 minutes back to `pending` status.
3. Review agent diagnostic log in `%LOCALAPPDATA%\EdgeErgo\logs\agent.log` for rejected batch errors.
4. To safely inspect the local queue count without modifying data:
   ```powershell
   python scripts/inspect_bundle.py --db "$env:LOCALAPPDATA\EdgeErgo\edge_agent.db"
   ```
