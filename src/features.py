"""Versioned, dimensionless feature contract. No images or identity embeddings."""

import math
from statistics import median
from src.utils import calculate_ear

SCHEMA = "mesh478-ipd-ratios-pose17-v2"
SCORE = "max-absolute-face-ratio-change+max-arm-change-v2"
FACE_KEYS = ("neutral_mouth_ratio", "neutral_brow_ratio", "neutral_eyelid_ratio",
             "smile_mouth_ratio", "closed_eyelid_ratio")
ARM_KEYS = ("left_arm_drift", "right_arm_drift", "arm_lift_skew")
FEATURE_KEYS = FACE_KEYS + ARM_KEYS
FACE_SETUP_KEYS = ("face_roll", "face_yaw", "face_pitch", "face_scale", "face_x", "face_y")
ARM_SETUP_KEYS = ("body_roll", "body_scale", "body_x", "body_y")
SETUP_KEYS = FACE_SETUP_KEYS + ARM_SETUP_KEYS
LEFT_EYE = (33, 160, 158, 133, 153, 144)
RIGHT_EYE = (362, 385, 387, 263, 373, 380)


def numeric_map(values, allowed, complete=True):
    if not isinstance(values, dict) or set(values) - set(allowed):
        raise ValueError("Unexpected fields; only numeric feature vectors are accepted.")
    if complete and set(values) != set(allowed):
        raise ValueError("Incomplete feature vector; repeat acquisition without delaying care.")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values.values()):
        raise ValueError("Feature values must be finite numbers, not missing data.")
    return {k: float(v) for k, v in values.items()}


def asymmetry_ratio(left, right, ipd):
    """2026-09-11: IPD-normalized S = 1 - min(L/R, R/L).

    Common scale cancels algebraically, but normalize explicitly for a documented
    dimensionless contract. Equal zero distances are symmetric; one zero is S=1.
    """
    if not all(math.isfinite(v) for v in (left, right, ipd)) or min(left, right) < 0 or ipd <= 0:
        raise ValueError("Invalid regional distance or IPD.")
    left, right = left / ipd, right / ipd
    largest = max(left, right)
    return 0.0 if largest <= 1e-8 else 1.0 - min(left, right) / largest


def face_geometry(landmarks, width, height, pose=None):
    """2026-09-11: replace signed skew with IPD-normalized regional ratios.

    Iris centers (468, 473) supply image-space IPD, not calibrated millimeters.
    The sagittal midline passes through the iris midpoint, perpendicular to the
    iris axis. Use bilateral perpendicular distances to that line. Complement
    lateral ratios with mouth/brow distances to the iris axis and lid apertures:
    lateral distances alone cannot measure vertical droop or incomplete closure.
    Each regional score is their maximum; temporal medians and maximum absolute
    delta aggregation are preserved. Ratios lose side information; out-of-plane
    rotations still affect them.
    Pose angles are supplied by the analyzer's independent PnP quality check.
    """
    if len(landmarks) != 478:
        raise ValueError("468 mesh + 10 iris landmarks (478 total) are required for IPD.")
    points = [(float(p.x) * width, float(p.y) * height) for p in landmarks]
    if not all(math.isfinite(v) for point in points for v in point):
        raise ValueError("Non-finite landmarks.")
    a, b = points[468], points[473]
    dx, dy = b[0] - a[0], b[1] - a[1]
    scale = math.hypot(dx, dy)
    if scale < 10 or width <= 0 or height <= 0:
        raise ValueError("Face is too small to measure.")
    center = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)

    def local(index):
        x, y = points[index][0] - center[0], points[index][1] - center[1]
        return ((x * dx + y * dy) / scale, (-x * dy + y * dx) / scale)

    def regional(left_indices, right_indices):
        left = [sum(local(i)[axis] for i in left_indices) / len(left_indices) for axis in (0, 1)]
        right = [sum(local(i)[axis] for i in right_indices) / len(right_indices) for axis in (0, 1)]
        return (asymmetry_ratio(abs(left[0]), abs(right[0]), scale),
                asymmetry_ratio(abs(left[1]), abs(right[1]), scale))

    if any(math.dist(points[indices[0]], points[indices[3]]) <= 1 for indices in (LEFT_EYE, RIGHT_EYE)):
        raise ValueError("Eye landmarks are degenerate or too small to measure.")
    left_ear = calculate_ear([points[i] for i in LEFT_EYE])
    right_ear = calculate_ear([points[i] for i in RIGHT_EYE])
    mouth_lateral, mouth_height = regional((61,), (291,))
    brow_lateral, brow_height = regional((70, 63, 105), (300, 293, 334))
    eye_lateral, _ = regional(LEFT_EYE, RIGHT_EYE)
    apertures = [sum(math.dist(points[i], points[j]) for i, j in
                    ((indices[1], indices[5]), (indices[2], indices[4]))) / 2
                 for indices in (LEFT_EYE, RIGHT_EYE)]
    return {
        "left_ear": left_ear, "right_ear": right_ear,
        "mouth_ratio": max(mouth_lateral, mouth_height),
        "brow_ratio": max(brow_lateral, brow_height),
        "eyelid_ratio": max(eye_lateral, asymmetry_ratio(*apertures, scale)),
        "mouth_lateral_ratio": mouth_lateral, "mouth_height_ratio": mouth_height,
        "brow_lateral_ratio": brow_lateral, "brow_height_ratio": brow_height,
        "face_roll": math.degrees(math.atan2(dy, dx)),
        **(pose or {}),
        "face_scale": scale / width, "face_x": center[0] / width, "face_y": center[1] / height,
    }


def aggregate(samples, keys):
    if len(samples) < 3:
        raise ValueError("Insufficient valid samples.")
    return {key: median(sample[key] for sample in samples) for key in keys}


def closure_asymmetry(samples, neutral_samples):
    """Measure left/right closure against the captured resting eye opening.

    Dividing by the tiny opening of a closed eye amplifies landmark noise.
    EAR uses eye-corner width, and the neutral reference stays fixed during
    closure. An eye that stays open remains measurable; closure is not a gate.
    """
    neutral = aggregate(neutral_samples, ("left_ear", "right_ear"))
    reference = max(neutral.values())
    if not math.isfinite(reference) or reference <= 1e-6:
        raise ValueError("Resting eye opening is too small to measure closure.")
    values = []
    for sample in samples:
        left, right = sample["left_ear"], sample["right_ear"]
        if not all(math.isfinite(v) and v >= 0 for v in (left, right)):
            raise ValueError("Invalid eye aperture measurement.")
        values.append({"closure": abs(left - right) / reference})
    return aggregate(values, ("closure",))["closure"]


def delta_features(before, after, partial=False):
    numeric_map(before, FEATURE_KEYS)
    numeric_map(after, FEATURE_KEYS, complete=not partial)
    deltas = {key: after[key] - before[key] for key in after}
    face = max((abs(deltas[k]) for k in FACE_KEYS if k in deltas), default=0.0)
    arm = max([0.0] + [max(0.0, deltas[k]) for k in ARM_KEYS[:2] if k in deltas]
              + ([abs(deltas["arm_lift_skew"])] if "arm_lift_skew" in deltas else []))
    if not all(math.isfinite(v) for v in (*deltas.values(), face, arm, face + arm)):
        raise ValueError("Feature deltas overflow; acquisition is invalid.")
    return {"deltas": deltas, "face_delta": face, "arm_delta": arm, "score": face + arm}
