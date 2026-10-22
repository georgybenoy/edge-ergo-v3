# EdgeErgo V3 — Ergonomic Scoring Methodology Specification

## Document Information
- **Method Identifier:** `rula_partial`
- **Current Version:** `1.0.0`
- **Method Title:** Rapid Upper Limb Assessment (RULA) Screening Indicator for Single 2D Workstation Webcam
- **Status:** Baseline Specification (Requires Independent Human Ergonomics Validation prior to commercial claims)

---

## 1. Scientific Foundations & Authoritative Literature

The EdgeErgo V3 edge scoring methodology is derived from established, peer-reviewed ergonomic assessment literature:

1. **RULA (Rapid Upper Limb Assessment):**
   - *Citation:* McAtamney, L., & Corlett, E. N. (1993). RULA: a survey method for the investigation of work-related upper limb disorders. *Applied Ergonomics*, 24(2), 91–99. doi:10.1016/0003-6870(93)90080-S.
   - *Scope:* Evaluates biomechanical and postural load on the neck, trunk, and upper limbs in seated workstation environments.

2. **REBA (Rapid Entire Body Assessment):**
   - *Citation:* Hignett, S., & McAtamney, L. (2000). Rapid Entire Body Assessment (REBA). *Applied Ergonomics*, 31(2), 201–216. doi:10.1016/S0003-6870(99)00039-3.
   - *Scope:* Evaluates entire body postural load, referenced for comparative joint angle threshold verification.

---

## 2. Capabilities & Boundaries of Monocular 2D Workstation Webcams

Standard office workstations operate with a single integrated or monitor-mounted 2D webcam. Single-viewpoint computer vision imposes immutable physical constraints:

### What a Single 2D Webcam CAN Assess:
- **Neck Flexion / Forward Head Posture Proxy:** Angle of the head/ear-to-cervical-spine vector relative to vertical in sagittal/oblique views.
- **Trunk Inclination:** Angular deviation of the shoulder-to-hip spinal axis from the gravitational vertical.
- **Shoulder Elevation & Asymmetry:** Relative vertical displacement of the acromion processes indicating shoulder shrugging or lateral tilt.
- **Upper Arm (Humerus) Elevation:** Angle of the shoulder-to-elbow vector relative to the torso axis in flexion or abduction.
- **Lower Arm (Forearm) Flexion:** Included interior angle between the humerus (upper arm) and radius/ulna (forearm).

### What a Single 2D Webcam CANNOT Assess:
- **Wrist Twist (Pronation/Supination):** Sub-millimeter rotational tracking of the radius/ulna is physically unresolvable from standard 720p/1080p webcam distances.
- **Fine Wrist Deviation (Radial/Ulnar):** Keystroke occlusions and hands resting on laptop decks obstruct wrist deviation angles.
- **Force / Load Scores:** Video capture cannot measure external physical resistance, keyboard spring force, or carried weights.
- **Muscle Use Score (Static vs. Repetitive):** Requires fine-grained electromyography (EMG) or multi-hour continuous micro-movement tracking.
- **Lower Limbs / Feet Support:** Seated office desks create total visual occlusion of knees, ankles, and floor foot placement.

---

## 3. The `rula_partial` (1.0.0) Method Definition

To maintain absolute scientific integrity and avoid fabricating unobservable variables:

1. **Explicit "Not Assessed" Classification:**
   All parameters that cannot be measured via single-camera computer vision are explicitly classified as `"not assessed"`, and their baseline neutral values are held constant with documented defaults:
   - `wrist_score`: Defaulted to 1 (neutral baseline).
   - `wrist_twist`: Defaulted to 1 (mid-range baseline).
   - `muscle_use`: Set to 0 (unassessed).
   - `force_load`: Set to 0 (unassessed).
   - `legs_score`: Defaulted to 1 (supported seated posture baseline).

2. **Assessed Components:**
   Every generated assessment event records the exact assessed sub-components:
   `assessed_components = ["neck", "trunk", "upper_arm", "lower_arm"]`

3. **Strict All-or-Nothing Completeness Requirement:**
   A numeric grand score (1.0 to 7.0) is computed **ONLY** when all four required components (`neck`, `trunk`, `upper_arm`, `lower_arm`) are simultaneously valid and above confidence thresholds in the observation window. If ANY required component is occluded, missing, or below confidence threshold:
   - `score = null`
   - `validity = "insufficient"` or `"invalid"`
   - `reason_codes = ["OCCLUSION_UPPER_ARM", ...]`
   - No score or action level is ever imputed or fabricated.

---

## 4. Angular Feature Mapping & Lookup Tables

### 4.1 Upper Arm (Humerus) Scoring (Table A Component)
Measured as the elevation angle of the shoulder-to-elbow vector relative to the trunk axis:
- **Score 1:** 20° extension to 20° flexion (-20° to +20°).
- **Score 2:** > 20° extension OR 20° to 45° flexion.
- **Score 3:** 45° to 90° flexion.
- **Score 4:** > 90° flexion.
- **Adjustment (+1):** Shoulder elevated (detected when shoulder height difference or shoulder shrug angle > 10°).

### 4.2 Lower Arm (Forearm) Scoring (Table A Component)
Measured as the interior elbow angle:
- **Score 1:** 60° to 100° flexion (optimal ergonomic typing angle).
- **Score 2:** < 60° flexion OR > 100° extension.

### 4.3 Table A Lookup (Upper Limb Posture)
With `wrist = 1` and `wrist_twist = 1`:

| Upper Arm Score | Lower Arm = 1 | Lower Arm = 2 |
| :---: | :---: | :---: |
| **1** | 1 | 2 |
| **2** | 2 | 2 |
| **3** | 3 | 3 |
| **4** | 4 | 4 |
| **5** | 5 | 5 |
| **6** | 6 | 6 |

`Score A = Table_A[upper_arm, lower_arm] + muscle_use (0) + force_load (0)`

---

### 4.4 Neck Posture Scoring (Table B Component)
Measured as sagittal neck flexion from vertical:
- **Score 1:** 0° to 10° flexion (neutral).
- **Score 2:** 10° to 20° flexion.
- **Score 3:** > 20° flexion.
- **Score 4:** Any observable extension (< 0°).
- **Adjustment (+1):** Lateral side-bending or neck twist detected > 10°.

### 4.5 Trunk Posture Scoring (Table B Component)
Measured as trunk inclination from vertical in seated posture:
- **Score 1:** 0° to 5° (upright seated with backrest support).
- **Score 2:** 5° to 20° flexion.
- **Score 3:** 20° to 60° flexion.
- **Score 4:** > 60° flexion.
- **Adjustment (+1):** Lateral trunk tilt or twisting detected > 10°.

### 4.6 Table B Lookup (Neck & Trunk Posture)
With `legs = 1` (seated supported):

| Neck Score | Trunk = 1 | Trunk = 2 | Trunk = 3 | Trunk = 4 | Trunk = 5 |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | 1 | 2 | 3 | 5 | 6 |
| **2** | 2 | 3 | 4 | 6 | 7 |
| **3** | 3 | 4 | 5 | 6 | 7 |
| **4** | 5 | 5 | 6 | 7 | 8 |
| **5** | 6 | 6 | 7 | 8 | 8 |
| **6** | 7 | 7 | 8 | 8 | 8 |

`Score B = Table_B[neck, trunk] + muscle_use (0) + force_load (0)`

---

### 4.7 Table C (Grand Score & Action Levels)
The final RULA Screening Indicator combines `Score A` and `Score B`:

| Score A \ Score B | **1** | **2** | **3** | **4** | **5** | **6** | **7+** |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | 1 | 2 | 3 | 3 | 4 | 5 | 5 |
| **2** | 2 | 2 | 3 | 4 | 4 | 5 | 5 |
| **3** | 3 | 3 | 3 | 4 | 4 | 5 | 6 |
| **4** | 3 | 3 | 4 | 5 | 5 | 6 | 6 |
| **5** | 4 | 4 | 4 | 5 | 6 | 7 | 7 |
| **6** | 4 | 4 | 5 | 6 | 6 | 7 | 7 |
| **7+**| 5 | 5 | 6 | 6 | 7 | 7 | 7 |

### 4.8 Action Level Interpretations

| RULA Grand Score | Risk Level | Action Level | Ergonomic Guidance Category |
| :---: | :---: | :---: | :--- |
| **1 – 2** | Negligible | **Level 1** | Posture is currently acceptable; maintain neutral positioning. |
| **3 – 4** | Low | **Level 2** | Further investigation may be beneficial; minor adjustments recommended. |
| **5 – 6** | Medium | **Level 3** | Investigation and workstation changes recommended soon. |
| **7** | High | **Level 4** | Immediate workstation ergonomic intervention and adjustment required. |

---

## 5. Guidance Code Mappings

To comply with privacy data minimization principles, only standardized `guidance_codes` are generated and synchronized with central servers:

- `GUID_NECK_FLEX_01`: Neck flexion exceeds 20°. *"Your screen may be too low; consider raising your monitor so the top third is at eye level."*
- `GUID_TRUNK_INCL_01`: Trunk flexion exceeds 20°. *"Consider adjusting your backrest to support an upright or slightly reclined posture (100°–110°)."*
- `GUID_SHOULDER_ELEV_01`: Shoulder elevation detected. *"Shoulder shrugging observed. Try lowering desk height or armrests to relax upper trapezius muscles."*
- `GUID_ARM_ELEV_01`: Upper arm flexion exceeds 45°. *"Your keyboard or mouse may be too far forward; try bringing them closer to reduce forward reach."*
- `GUID_ELBOW_ANGLE_01`: Elbow angle < 60° or > 100°. *"Consider adjusting chair height so forearms rest parallel to the desk surface."*
- `GENERAL_GOOD_POSTURE`: All assessed indicators within neutral bounds. *"Posture indicators are within recommended neutral ranges."*

---

## 6. Regulatory & Clinical Disclaimer

> [!IMPORTANT]
> The `rula_partial` scoring algorithm is an automated **screening indicator and educational prompt** only. It is **not** a clinical diagnostic system, medical device, or formal occupational hazard assessment. Variations in camera angle, lens distortion, user clothing, and individual anatomical morphology can influence computer vision joint approximations. Posture scores must never be utilized for employment performance evaluations or disciplinary actions.
