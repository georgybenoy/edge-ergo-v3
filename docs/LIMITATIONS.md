# EdgeErgo V3 — Scientific & Technical Limitations

This document explicitly defines the scientific, mathematical, and platform boundaries of EdgeErgo V3 per PRD §7.8, §9, §10, and §12. These boundaries are non-negotiable and must be faithfully reflected in all user interfaces, pilot agreements, administrator documentation, and telemetry exports.

---

## 1. Ergonomic Screening Indicator vs. Medical Diagnosis

- **Not a Medical Device or Clinical Diagnostic:** EdgeErgo V3 provides automated ergonomic *screening indicators* based on monocular computer vision. It is **not** a certified medical diagnostic device, physical therapy assessment, or clinical evaluation.
- **No Injury Prediction Claims:** The software does not claim to predict musculoskeletal disorders (MSDs), repetitive strain injuries (RSIs), spinal pathology, or injury likelihood.
- **Explicit Non-Ranking Guarantee (FR-071, DESIGN §16):** Posture indicators and risk scores must never be utilized for employee performance evaluations, productivity ratings, employee ranking, attendance monitoring, or disciplinary measures. The web dashboard intentionally omits individual employee names, rankings, and leaderboards.

---

## 2. Partial RULA Methodology Scope

- **Upper-Body Screening Focus:** Standard workstation environments naturally occlude wrists, hands, and lower limbs behind desk surfaces and keyboards.
- **Excluded RULA Table B Factors:** The screening algorithm (`rula_v1_screening`) evaluates upper-body posture (neck flexion/extension, trunk flexion/extension, and upper-arm elevation). It intentionally excludes wrist twist, wrist flexion, muscle use score, and external load/force scoring because monocular webcams cannot accurately measure tendon strain or external mechanical loads.
- **Fail-Closed Observation Policy (FR-008):** Missing, occluded, or low-confidence keypoints (e.g. nose, shoulders, hips, elbows) **never** result in fabricated or guessed numeric scores. If key anatomical landmarks are missing or confidence is below 0.5, the observation is marked `validity: "insufficient_data"` with `score: null`.

---

## 3. Monocular 2D Webcam Constraints

- **Monocular Depth Ambiguity:** Standard workstation webcams capture monocular 2D RGB frames. While MediaPipe Pose generates approximate 3D joint landmark coordinates, the depth axis (`Z`) is inferred relative to hip midpoints and is subject to spatial ambiguity.
- **Focal Length & Perspective Distortion:** Wide-angle webcams (especially laptop integrated cameras with wide fields of view) can introduce barrel distortion or foreshortening when users sit very close to the lens.
- **Multi-Person Scenes:** If multiple individuals are visible within the camera frame, the landmark detector locks onto the primary detected human. In busy open-plan offices, background foot traffic can momentarily cause jitter or quality invalidation.

---

## 4. Workstation Camera Placement Guidelines

To achieve reliable posture estimation without occlusions:
- **Optimal Placement:** Position the webcam at a **30° to 45° diagonal angle** relative to the user's sagittal plane (side-profile view showing the ear, shoulder, elbow, and hip).
- **Height:** The webcam lens should be approximately at user eye-to-shoulder level (avoid extreme low-angle laptop lid cameras pointing upward toward the ceiling).
- **Distance:** 1.0 to 1.5 meters from the user, ensuring the upper torso, head, and hip line remain completely inside the field of view.
- **Direct Front-Facing Cameras:** Integrated laptop lid cameras directly in front of the user can measure lateral shoulder tilt and neck rotation, but underestimate sagittal neck and trunk flexion due to foreshortening.

---

## 5. Lighting & Environmental Constraints

- **Illumination Range:** Recommended workplace ambient lighting is **300 to 500 lux**.
- **Backlighting Avoidance:** Do not position the workstation directly in front of bright windows or high-contrast backlighting, which causes silhouette effects and keypoint loss.
- **Clothing Considerations:** Bulky, loose jackets, thick scarves, or oversized blankets obscure joint centers (shoulders and neck) and may cause quality validation gates to reject observations.

---

## 6. Edge Platform Support

- **Supported Edge OS:** Windows 10 and Windows 11 (64-bit AMD64) with native Win32/PySide6 desktop integration. Linux and macOS edge agents are not supported in the V3 pilot release.
- **Hardware Minimums:** Multi-core x86_64 CPU (Intel Core i5 8th Gen or AMD Ryzen 5 equivalent), 8 GB RAM, and a functional DirectShow / Media Foundation webcam (minimum 720p @ 15 FPS).
