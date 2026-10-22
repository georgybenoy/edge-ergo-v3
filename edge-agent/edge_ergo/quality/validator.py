"""Pure validation functions evaluating landmark visibility and camera placement geometry."""

from __future__ import annotations

import math
from typing import Any

from edge_ergo.quality.types import ValidityReport, ValidityStatus
from edge_ergo.vision.landmarks import PoseLandmarkIndex, RawPoseLandmarks

# Key landmark groups required for upper-body ergonomics
CORE_TORSO_LANDMARKS = (
    PoseLandmarkIndex.LEFT_SHOULDER,
    PoseLandmarkIndex.RIGHT_SHOULDER,
    PoseLandmarkIndex.LEFT_HIP,
    PoseLandmarkIndex.RIGHT_HIP,
)

CORE_ARM_LANDMARKS = (
    PoseLandmarkIndex.LEFT_ELBOW,
    PoseLandmarkIndex.RIGHT_ELBOW,
    PoseLandmarkIndex.LEFT_WRIST,
    PoseLandmarkIndex.RIGHT_WRIST,
)


def validate_observation(
    landmarks: RawPoseLandmarks | None,
    visibility_threshold: float = 0.50,
    min_shoulder_span: float = 0.08,
    max_shoulder_span: float = 0.85,
) -> ValidityReport:
    """Evaluates whether pose landmarks satisfy physical validity and camera placement heuristics.

    FR-008: Missing or occluded points are NEVER fabricated. Observations with
    insufficient visibility are explicitly reported as INSUFFICIENT or INVALID.
    """
    if landmarks is None or len(landmarks) < 25:
        return ValidityReport(
            status=ValidityStatus.INVALID,
            reason_codes=["NO_POSE_DETECTED"],
            confidence_score=0.0,
        )

    reason_codes: list[str] = []
    details: dict[str, Any] = {}

    # 1. Torso visibility check (Shoulders & Hips)
    torso_visibilities: list[float] = []
    for idx in CORE_TORSO_LANDMARKS:
        lm = landmarks.get(idx)
        if lm is None or lm.visibility < visibility_threshold:
            if idx in (PoseLandmarkIndex.LEFT_SHOULDER, PoseLandmarkIndex.RIGHT_SHOULDER):
                reason_codes.append("OCCLUSION_SHOULDERS")
            else:
                reason_codes.append("OCCLUSION_HIPS")
        if lm is not None:
            torso_visibilities.append(lm.visibility)

    # 2. Head / Neck reference check (Nose or Ears)
    nose = landmarks.get(PoseLandmarkIndex.NOSE)
    l_ear = landmarks.get(PoseLandmarkIndex.LEFT_EAR)
    r_ear = landmarks.get(PoseLandmarkIndex.RIGHT_EAR)

    has_head = (
        (nose is not None and nose.visibility >= visibility_threshold)
        or (l_ear is not None and l_ear.visibility >= visibility_threshold)
        or (r_ear is not None and r_ear.visibility >= visibility_threshold)
    )
    if not has_head:
        reason_codes.append("OCCLUSION_HEAD")

    # 3. Arm joints visibility check (Elbows & Wrists)
    arm_visibilities: list[float] = []
    for idx in CORE_ARM_LANDMARKS:
        lm = landmarks.get(idx)
        if lm is None or lm.visibility < visibility_threshold:
            if idx in (PoseLandmarkIndex.LEFT_ELBOW, PoseLandmarkIndex.RIGHT_ELBOW):
                if "OCCLUSION_ELBOWS" not in reason_codes:
                    reason_codes.append("OCCLUSION_ELBOWS")
            else:
                if "OCCLUSION_WRISTS" not in reason_codes:
                    reason_codes.append("OCCLUSION_WRISTS")
        if lm is not None:
            arm_visibilities.append(lm.visibility)

    # If key torso or head joints are occluded, classify as INSUFFICIENT
    occlusion_keys = ("OCCLUSION_SHOULDERS", "OCCLUSION_HIPS", "OCCLUSION_HEAD")
    if any(code in reason_codes for code in occlusion_keys):
        avg_vis = sum(torso_visibilities) / max(1, len(torso_visibilities))
        return ValidityReport(
            status=ValidityStatus.INSUFFICIENT,
            reason_codes=list(dict.fromkeys(reason_codes)),
            confidence_score=round(avg_vis, 3),
            details={"torso_visibilities": torso_visibilities},
        )

    # 4. Plausible Geometry & Camera Placement Heuristics
    l_sh = landmarks.get(PoseLandmarkIndex.LEFT_SHOULDER)
    r_sh = landmarks.get(PoseLandmarkIndex.RIGHT_SHOULDER)
    l_hip = landmarks.get(PoseLandmarkIndex.LEFT_HIP)
    r_hip = landmarks.get(PoseLandmarkIndex.RIGHT_HIP)

    if l_sh is None or r_sh is None or l_hip is None or r_hip is None:
        return ValidityReport(
            status=ValidityStatus.INSUFFICIENT,
            reason_codes=["OCCLUSION_TORSO"],
            confidence_score=0.0,
        )

    # Shoulder width scale in normalized image coordinates
    shoulder_span = math.hypot(l_sh.x - r_sh.x, l_sh.y - r_sh.y)
    details["shoulder_span"] = round(shoulder_span, 4)

    if shoulder_span < min_shoulder_span:
        reason_codes.append("CAMERA_TOO_FAR")
    elif shoulder_span > max_shoulder_span:
        reason_codes.append("CAMERA_TOO_CLOSE")

    # Torso height
    mid_sh_y = (l_sh.y + r_sh.y) / 2.0
    mid_hip_y = (l_hip.y + r_hip.y) / 2.0
    torso_height = mid_hip_y - mid_sh_y
    details["torso_height"] = round(torso_height, 4)

    # Anatomical orientation check: Hips must be physically beneath shoulders
    if torso_height <= 0.05:
        reason_codes.append("INVALID_ANATOMICAL_ORIENTATION")

    # Frame clipping boundaries: ensure torso is not cut off by image borders
    for lm in (l_sh, r_sh, l_hip, r_hip):
        if lm.x < 0.02 or lm.x > 0.98 or lm.y < 0.02 or lm.y > 0.98:
            if "BODY_TRUNCATED_BY_FRAME" not in reason_codes:
                reason_codes.append("BODY_TRUNCATED_BY_FRAME")

    # Determine final status
    all_visibilities = torso_visibilities + arm_visibilities
    avg_conf = sum(all_visibilities) / max(1, len(all_visibilities))

    # Severe geometric anomalies mean INVALID
    invalid_keys = ("INVALID_ANATOMICAL_ORIENTATION", "CAMERA_TOO_FAR", "CAMERA_TOO_CLOSE")
    if any(code in reason_codes for code in invalid_keys):
        status = ValidityStatus.INVALID
    elif reason_codes:
        status = ValidityStatus.INSUFFICIENT
    else:
        status = ValidityStatus.VALID

    return ValidityReport(
        status=status,
        reason_codes=list(dict.fromkeys(reason_codes)),
        confidence_score=round(avg_conf, 3),
        details=details,
    )
