# EdgeErgo V3 — Windows Edge Agent Installation & Enrollment Guide

This document provides complete instructions for workstation end users and enterprise IT administrators deploying the EdgeErgo V3 Windows Edge Agent.

---

## 1. System Requirements

> [!NOTE]
> These minimum requirements represent the baseline software stack. Hardware requirements are formatted as placeholders to be filled from measured physical hardware during the pilot benchmark (PRD §10, §12).

| Component | Minimum Specification | Recommended Specification |
|---|---|---|
| **Operating System** | Windows 10 (64-bit Build 19041+) or Windows 11 | Windows 11 Enterprise 64-bit |
| **Processor (CPU)** | `[To be confirmed via docs/PERFORMANCE_TEMPLATE.md]` (e.g. 4 cores @ 2.0 GHz) | `[To be confirmed via docs/PERFORMANCE_TEMPLATE.md]` (e.g. 8 cores @ 2.8 GHz) |
| **System Memory (RAM)**| `[To be confirmed via docs/PERFORMANCE_TEMPLATE.md]` (min 8 GB) | 16 GB DDR4/DDR5 |
| **Storage Space** | 500 MB free disk space for bundle and SQLite WAL storage | 2 GB NVMe SSD storage |
| **Webcam Hardware** | DirectShow-compatible USB or integrated camera (720p @ 15 FPS) | 1080p @ 30 FPS with dedicated diagonal desk mount |
| **Network** | HTTPS (Port 443 outbound) to central hosted API for periodic sync | Stable Wi-Fi or Ethernet (offline queue buffers up to 90 days) |
| **Permissions** | Standard user execution (Administrator rights **NOT** required for runtime) | Standard user with Windows Credential Manager access |

---

## 2. Windows Camera Permission Configuration

Modern Windows 10 and Windows 11 systems require explicit desktop application camera access permissions.

1. Open **Windows Settings** (`Win + I`).
2. Navigate to **Privacy & Security** > **Camera**.
3. Ensure **Camera access** is toggled to **ON**.
4. Scroll down to **Let desktop apps access your camera** and toggle it to **ON**.
5. Verify that `edge-ergo.exe` (or your Python executable in dev mode) appears in the list of permitted desktop applications.

> [!WARNING]
> If a physical hardware privacy shutter is closed, or a third-party antivirus suite blocks webcam handles, the edge agent will detect the absence of frames and transition to `CAMERA_UNAVAILABLE` state without crashing.

---

## 3. Workstation Enrollment Walkthrough

Each workstation edge agent operates under a pseudonymous device identifier (`eed_<public_id>`) tied to an organization.

### Step 1: Obtain Single-Use Enrollment Token
1. The company ergonomics administrator navigates to the EdgeErgo Web Dashboard: `https://dashboard.edge-ergo.example.com`.
2. Go to **Devices** > **Enroll New Device**.
3. Specify a descriptive workstation label (e.g., `Engineering-Station-04`).
4. Click **Generate Token**. The dashboard displays a single-use token formatted as:
   ```text
   eet_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
   *(Note: Enrollment tokens expire after 15 minutes by default.)*

### Step 2: Launch and Enroll the Agent
1. Download and extract the EdgeErgo Windows bundle:
   ```powershell
   Expand-Archive -Path edge-ergo-v3.0.0-win64.zip -DestinationPath C:\Users\%USERNAME%\AppData\Local\EdgeErgo
   ```
2. Run the executable in enrollment mode or pass the token:
   ```powershell
   cd C:\Users\$env:USERNAME\AppData\Local\EdgeErgo
   .\edge-ergo.exe --enroll "eet_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" --api-url "https://api.edge-ergo.example.com"
   ```
3. The agent validates the token against the backend API, exchanges it for a permanent scoped device secret (`eed_<public_id>.<secret>`), securely stores the secret in **Windows Credential Manager** (via OS DPAPI), initializes the local SQLite database at `%LOCALAPPDATA%\EdgeErgo\edge_agent.db`, and launches the system tray overlay.

---

## 4. Workstation Privacy Notice (Pilot Agreement Text)

Administrators must present this disclosure to all pilot participants prior to enabling camera analysis:

```text
================================================================================
                    EDGEERGO WORKSTATION PRIVACY NOTICE
================================================================================

Welcome to the EdgeErgo Ergonomic Screening Pilot. Your privacy and dignity are
our highest engineering priorities. Please review how your data is handled:

1. LOCAL PROCESSING ONLY:
   Your webcam frames are processed strictly in memory on this workstation.
   Raw images, live video streams, and facial photographs are NEVER saved to disk,
   NEVER uploaded to cloud servers, and NEVER viewable by IT administrators,
   management, or ergonomists.

2. LOCAL POSE ESTIMATION:
   An on-device computer vision model measures upper-body joint angles (neck, trunk,
   and upper arms) in real-time. Joint landmark coordinates are discarded immediately
   after calculating ergonomic risk scores.

3. MINIMAL DATA SYNCHRONIZATION:
   Only aggregated, anonymous risk scores (e.g., "RULA Score: 3, Neck Flexion") and
   operational device health metrics synchronize to the central dashboard.

4. NON-PUNITIVE GUARANTEE:
   EdgeErgo indicators are designed solely for self-correction and workplace
   ergonomic design improvements. This software does not measure employee
   productivity, does not track active working hours, and is NEVER used for
   performance reviews or employee ranking.

5. CONTROL & VISIBILITY:
   You can pause or close EdgeErgo at any time using the desktop system tray icon.
   When the camera is active, a clear green indicator is displayed on your screen.

By enrolling this workstation, you acknowledge and agree to participate in the
EdgeErgo pilot under these privacy safeguards.
================================================================================
```
