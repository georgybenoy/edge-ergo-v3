# EdgeErgo V3 — Network Traffic Capture & Privacy Audit Guide

This guide describes how an auditor or security engineer can intercept, decrypt, and inspect live network traffic transmitted between the EdgeErgo Windows desktop agent and the hosted FastAPI backend to verify PRD **FR-042** and **§9 (Privacy Requirements)**.

---

## 1. Privacy Guarantee Under Verification

EdgeErgo enforces absolute data minimization across all network boundaries:
1. **Zero Raw Video / Frames:** Webcam images, frames, and video streams never leave local device memory.
2. **Zero Facial Biometrics:** No face meshes, iris coordinates, or facial crops are ever transmitted.
3. **Zero Raw Pose Landmarks:** 3D Cartesian coordinates (`x, y, z, visibility`) computed by MediaPipe are processed strictly in local RAM and discarded; they are never serialized or sent over the wire.
4. **Allowlisted Scalar Telemetry Only:** Central ingestion accepts only bounded numerical posture scores, validity state enums, guidance rule codes, and software version strings.

---

## 2. Recommended Interception Tools

| Tool | Platform | Best For |
|---|---|---|
| **mitmproxy** | Windows / macOS / Linux | Headless or CLI HTTPS interception and scriptable payload analysis |
| **Fiddler Everywhere** | Windows | Visual GUI inspection of request headers, JSON formatting, and TLS handshake |
| **Wireshark** | Windows | Packet-level TLS handshake and payload capture (requires TLS master secret logging) |

---

## 3. Step-by-Step Setup: mitmproxy / Fiddler Everywhere

### Step 3.1: Install and Launch Interception Proxy

#### Using mitmproxy:
```powershell
pip install mitmproxy
mitmweb --listen-host 127.0.0.1 --listen-port 8080
```
*mitmweb will open an interactive web interface at `http://127.0.0.1:8081`.*

#### Using Fiddler Everywhere:
1. Download and launch Fiddler Everywhere.
2. Under **Settings > HTTPS**, enable **Capture HTTPS traffic** and click **Trust Root Certificate**.
3. Note listening port (default: `8888`).

### Step 3.2: Trust the Local Proxy Certificate on Windows

1. Navigate to `http://mitm.it` in a browser routed through the proxy.
2. Download the Windows `.p12` / `.crt` certificate.
3. Open `certmgr.msc` -> **Trusted Root Certification Authorities > Certificates**.
4. Right-click -> **All Tasks > Import** -> Select downloaded certificate -> Confirm import.

### Step 3.3: Route Edge Agent Traffic Through Proxy

Configure proxy environment variables before launching the agent:
```powershell
$env:HTTP_PROXY = "http://127.0.0.1:8080"
$env:HTTPS_PROXY = "http://127.0.0.1:8080"
$env:SSL_CERT_FILE = "$HOME\.mitmproxy\mitmproxy-ca-cert.pem"
```

---

## 4. Capturing Live Ingestion Traffic

### Step 4.1: Enroll the Test Workstation
```powershell
python -m edge_ergo.main enroll --api https://api.edgeergo.com --token eet_sample_token_12345
```

### Step 4.2: Execute Real or Synthetic Assessment Cycles
```powershell
# For synthetic validation:
python -m edge_ergo.main --fake-camera --sampling-interval 2.0 --duration 10

# For real webcam hardware validation:
python -m edge_ergo.main --device-index 0 --sampling-interval 5.0 --duration 30
```

---

## 5. Traffic Inspection & Audit Checklist

Inspect the captured HTTP flows in the proxy interface.

### Flow 1: Device Heartbeat
- **Method & Path:** `POST /api/v1/devices/heartbeat`
- **Headers:**
  - `Host: <backend-domain>`
  - `Authorization: Device eed_<public_id>.<secret>`
  - `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "agent_version": "3.0.0",
    "queue_depth": 0,
    "state": "active"
  }
  ```

### Flow 2: Batch Telemetry Ingestion
- **Method & Path:** `POST /api/v1/assessments/batch`
- **Headers:**
  - `Host: <backend-domain>`
  - `Authorization: Device eed_<public_id>.<secret>`
  - `Content-Type: application/json`
- **Request Body (Must match exactly):**
  ```json
  {
    "events": [
      {
        "event_id": "c7a8b412-28e4-4a21-9fd1-6b2f483c19e5",
        "captured_at": "2026-10-20T17:00:00.000000Z",
        "scoring_method": "RULA_PARTIAL",
        "scoring_version": "1.0.0",
        "validity": "valid",
        "score": 3.0,
        "neck_score": 2,
        "trunk_score": 2,
        "upper_arm_score": 2,
        "guidance_codes": [
          "NECK_FLEXION_MODERATE"
        ],
        "software_version": "3.0.0"
      }
    ]
  }
  ```

---

## 6. Prohibited Elements (Immediate Audit Failure)

If ANY of the following patterns appear in captured request headers, bodies, or query strings, the test has **FAILED**:

| Prohibited Pattern | Reason |
|---|---|
| `landmarks`, `landmark_list`, `keypoints` | Raw coordinate arrays violate PRD §9.2 |
| `[[-0.12, 0.45, -0.22, 0.98], ...]` | Unprocessed spatial points violate data minimization |
| `data:image/jpeg;base64,...` | Image transmission strictly prohibited by PRD §9.1 |
| `frame`, `video`, `camera_raw`, `pixels` | Raw sensor buffers strictly prohibited |
| `face`, `eyes`, `iris`, `mouth`, `emotion` | Facial biometric harvesting strictly prohibited |
| `Windows User: <username>` | Unapproved device identity leakage |

---

## 7. Automated Reproduction

To automatically run this privacy verification programmatically without a manual proxy, run the automated privacy test suite:
```powershell
python -m pytest tests/privacy/ -v
```
This suite executes recording transport interception and asserts the exact same constraints.
