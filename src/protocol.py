"""Capture compatibility and approved threshold artifact validation."""

import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

import config
from src.features import SCHEMA, SCORE, SETUP_KEYS, numeric_map

CARE_MESSAGE = ("Reported symptoms need prompt medical attention. For sudden facial drooping, arm weakness, "
                "speech difficulty or other stroke signs, call local emergency services now. "
                "Do not wait for this camera test or a high AI score.")


def pipeline_signature():
    """Bind actual model assets, package versions, feature code and settings."""
    import mediapipe
    package = Path(mediapipe.__file__).parent
    root = Path(__file__).resolve().parents[1]
    paths = [package / "modules/face_landmark/face_landmark_with_attention.tflite",
             package / "modules/face_landmark/face_landmark_front_cpu.binarypb",
             package / "modules/face_detection/face_detection_short_range.tflite",
             Path(config.YOLO_POSE_MODEL)]
    paths += [root / "src" / name for name in ("features.py", "head_pose.py", "face_analytics.py", "arm_features.py", "projected_arm_angle.py", "arm_pose.py", "screening_flow.py")]
    assets = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    packages = {name: importlib.metadata.version(name) for name in ("mediapipe", "ultralytics", "opencv-python", "numpy", "torch", "torchvision")}
    settings = {key: value for key, value in vars(config).items() if key.isupper()
                and not key.startswith(("FEATURE_STORE", "DELTA_POLICY", "CAPTURE_STATION", "BASELINE_MAX"))}
    return hashlib.sha256(json.dumps({"assets": assets, "packages": packages, "settings": settings}, sort_keys=True).encode()).hexdigest()


def check_setup(before, after, partial=False):
    numeric_map(before, SETUP_KEYS)
    numeric_map(after, SETUP_KEYS, complete=not partial)
    # 2026-09-11: IPD ratios remove face x/y/scale matching; arms still need it.
    check_head_pose(before)
    check_head_pose(after)
    mismatches = [key for key in after if key.startswith("body_") and
                  abs(before[key] - after[key]) > config.SETUP_TOLERANCES[key]]
    if mismatches:
        raise ValueError("Capture position differs from baseline: " + ", ".join(mismatches) + ". Comparison is inconclusive.")


def check_head_pose(values):
    for key in ("face_roll", "face_yaw", "face_pitch"):
        if key in values and (not math.isfinite(values[key]) or abs(values[key]) > config.HEAD_POSE_MAX_DEGREES):
            raise ValueError(f"Head rotation exceeds {config.HEAD_POSE_MAX_DEGREES:g} degrees: {key}. Face the camera.")


def load_policy(path, pipeline):
    path = Path(path)
    if not path.exists():
        return None
    policy = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(policy, dict):
        raise ValueError("Threshold policy must be a JSON object.")
    if policy.get("schema") != SCHEMA or policy.get("score_definition") != SCORE or policy.get("pipeline") != pipeline:
        raise ValueError("Threshold belongs to a different feature/model pipeline.")
    if policy.get("cohort") != "self_reported_symptoms" or policy.get("deployment_approved") is not True:
        raise ValueError("Threshold has not been approved for the symptomatic workflow.")
    threshold = policy.get("threshold")
    if type(threshold) not in (float, int) or not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("Threshold must be a finite positive number.")
    for key in ("policy_id", "clinical_review_reference", "validation_report_sha256"):
        if not isinstance(policy.get(key), str) or not policy[key].strip():
            raise ValueError("Threshold is missing review/validation provenance.")
    if len(policy["policy_id"]) > 128:
        raise ValueError("Policy ID is too long.")
    counts = policy.get("holdout_counts", {})
    if not isinstance(counts, dict):
        raise ValueError("Holdout counts must be a JSON object.")
    if any(type(counts.get(k)) is not int or counts[k] < 1 for k in ("positive", "negative")):
        raise ValueError("Held-out symptomatic positives and negatives are required.")
    return policy
