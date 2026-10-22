# EdgeErgo V3 — On-Device Edge Performance Evaluation Template

> [!IMPORTANT]
> **Pilot Evidence Rule (PRD §10, §12):** All measured telemetry values in this template must remain **EMPTY** until executed and recorded on real, physical pilot test machines using `scripts/benchmark_edge.py`. Under no circumstances should simulated, guessed, or invented performance metrics be populated in this baseline report.

---

## 1. Test Environment Metadata

| Field | Pilot Station Specification |
|---|---|
| **Station Identifier / Tag** | `[Station ID / e.g. Station-01]` |
| **Testing Date & Time (UTC)** | `[YYYY-MM-DD HH:MM UTC]` |
| **Hardware Platform** | `[e.g., Lenovo ThinkPad T14 Gen 3 / Dell Latitude 5430]` |
| **CPU Model & Base Frequency** | `[e.g., Intel Core i5-1245U @ 1.60 GHz (10 cores, 12 threads)]` |
| **Total System RAM** | `[e.g., 16 GB DDR4-3200]` |
| **GPU / Acceleration Device** | `[e.g., Integrated Intel Iris Xe / Discrete NVIDIA T550]` |
| **Webcam Model & Resolution** | `[e.g., Integrated 720p HD Camera (1280x720 @ 30 FPS)]` |
| **Operating System & Build** | `[e.g., Windows 11 Enterprise 23H2 (Build 22631.3007)]` |
| **Power State** | `[e.g., AC Mains Connected / Battery (85% remaining)]` |
| **Windows Power Mode** | `[e.g., Best Performance / Balanced / Power Saver]` |
| **Edge Agent Binary Version** | `[e.g., 3.0.0.0 (dist/edge-ergo/edge-ergo.exe)]` |
| **MediaPipe / OpenCV Version** | `[e.g., MediaPipe 0.10.14 / OpenCV 4.10.0.84]` |

---

## 2. On-Device Benchmark Results

Execution command:
```powershell
python scripts/benchmark_edge.py --real-camera --duration 120 --output station_01_benchmark.json
```
*(Or against packaged executable: `.\dist\edge-ergo\edge-ergo.exe --selftest`)*

| Performance Metric | Requirement Target (PRD §10) | Measured Value | Pilot Compliance Status |
|---|:---:|:---:|:---:|
| **Cold Startup Time (to 1st Inference)** | `< 5000 ms` | `[           ms]` | `[Pending Measurement]` |
| **Total Per-Frame Latency (p50 / Median)** | `< 100 ms` | `[           ms]` | `[Pending Measurement]` |
| **Total Per-Frame Latency (p95)** | `< 250 ms` | `[           ms]` | `[Pending Measurement]` |
| **Total Per-Frame Latency (p99)** | `< 500 ms` | `[           ms]` | `[Pending Measurement]` |
| **Vision Inference Latency (p50)** | Informational | `[           ms]` | `[Pending Measurement]` |
| **Feature Extraction + Scoring Latency** | `< 10 ms` | `[           ms]` | `[Pending Measurement]` |
| **Mean Process CPU Utilization (1 Process)** | `< 15%` of multi-core capacity | `[            %]` | `[Pending Measurement]` |
| **Working Set Memory Footprint (RSS)** | `< 350 MB` | `[           MB]` | `[Pending Measurement]` |
| **Memory Delta (120s Run - RSS Drift)** | `< 10 MB` (no leak) | `[           MB]` | `[Pending Measurement]` |
| **Frame Loss Rate (Dropped / Total)** | `< 1.0%` | `[            %]` | `[Pending Measurement]` |
| **Valid Postural Scores Computed Rate** | Real-world posture dependent | `[            %]` | `[Pending Measurement]` |

---

## 3. Battery & Thermal Impact

Run duration: **60 minutes continuous edge screening**.

| Evaluation Item | Metric Target | Measured Value |
|---|:---:|:---:|
| **Battery Drain Rate (% / hour)** | Baseline + `< 12%/hr` | `[           %/hr]` |
| **Thermal Throttling Observed** | None | `[Yes / No]` |
| **Fan Acoustic Impact** | Inaudible or Moderate office ambient | `[Silent / Moderate / High]` |
| **System Responsiveness (Foreground Task UI)** | Fluid, 60 FPS desktop interaction | `[Normal / Degraded]` |

---

## 4. Benchmark Execution Verification

- **Tester Signature:** `___________________________`
- **Reviewed by Pilot Ergonomist / IT Admin:** `___________________________`
- **Raw Telemetry JSON Log Attached:** `[ ] Yes   Path: ___________________________`
