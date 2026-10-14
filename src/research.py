"""Explicit opt-in demonstration rules; never presented as validated policies."""

import hashlib
import json
import math
from pathlib import Path

from src.features import FACE_KEYS, FEATURE_KEYS, delta_features, numeric_map
from src.arm_features import validate_arm_function
from src.protocol import CARE_MESSAGE
from config import ARM_HOLD_CHANGE_ALERT_SEC, ARM_RAISE_CHANGE_ALERT_PERCENT

PARAMETER_PATH = Path(__file__).resolve().parents[1] / "research_parameters.json"
ANGLE_KEYS = ("left_projected_drift_deg", "right_projected_drift_deg")


def _arm_function_worsened(before, after):
    """Compare function to this person's baseline, not to an ideal body."""
    if before is None:
        return after["status"] != "normal", None, None
    severity = {"normal": 0, "unable_to_hold": 1, "unable_to_raise": 2}
    raise_change = (after.get("raise_percent") - before.get("raise_percent")
                    if "raise_percent" in before and "raise_percent" in after else None)
    hold_change = (after["hold_sec"] - before["hold_sec"])
    worsened = severity[after["status"]] > severity[before["status"]]
    # When the coarse status is unchanged, flag only a material deterioration.
    if severity[after["status"]] == severity[before["status"]] and after["status"] != "normal":
        worsened = ((raise_change is not None and raise_change < -ARM_RAISE_CHANGE_ALERT_PERCENT) or
                    hold_change < -ARM_HOLD_CHANGE_ALERT_SEC)
    return worsened, raise_change, hold_change


def load_parameters(path=PARAMETER_PATH):
    values = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(values, dict) or values.get("research_only") is not True or values.get("deployment_approved") is not False:
        raise ValueError("Research parameters must explicitly remain unapproved and research-only.")
    for key, maximum in (("face_delta_threshold", 10), ("arm_angle_delta_threshold_deg", 180), ("arm_angle_alternative_deg", 180)):
        value = values.get(key)
        if type(value) not in (float, int) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError(f"Invalid research parameter: {key}")
    targets = values.get("targets", {})
    for key in ("face_sensitivity", "face_specificity", "overall_sensitivity_minimum", "overall_sensitivity_stretch"):
        value = targets.get(key)
        if type(value) not in (float, int) or not math.isfinite(value) or not 0 < value <= 1:
            raise ValueError(f"Invalid performance target: {key}")
    if targets["overall_sensitivity_minimum"] > targets["overall_sensitivity_stretch"]:
        raise ValueError("The sensitivity floor must not exceed the stretch target.")
    return values


def validate_angles(angles):
    numeric_map(angles, ANGLE_KEYS, complete=False)
    if any(not 0 <= value <= 180 for value in angles.values()):
        raise ValueError("Projected drift angles must be between 0 and 180 degrees.")
    return angles


def compare_research(before, after, before_angles, after_angles, parameters, partial=False,
                     before_arm_function=None, after_arm_function=None):
    measurement = delta_features(before, after, partial=partial)
    validate_angles(before_angles)
    validate_angles(after_angles)
    angle_deltas = {k: after_angles[k] - before_angles[k] for k in ANGLE_KEYS if k in before_angles and k in after_angles}
    arm_delta = max([0.0] + list(angle_deltas.values())) if angle_deltas else None
    baseline_arm_function = (validate_arm_function(before_arm_function)
                             if before_arm_function is not None else None)
    arm_function = validate_arm_function(after_arm_function) if after_arm_function is not None else None
    face_available = any(key in after for key in FACE_KEYS)
    # Keep absolute differences for auditing, but a decrease in measured
    # asymmetry must not be labelled an increase requiring attention.
    face_increase = max([0.0] + [measurement["deltas"][key] for key in FACE_KEYS if key in after])
    face_alert = face_available and face_increase > parameters["face_delta_threshold"]
    arm_function_alert = False
    arm_raise_change = arm_hold_change = None
    if arm_function is not None:
        arm_function_alert, arm_raise_change, arm_hold_change = _arm_function_worsened(
            baseline_arm_function, arm_function)
        # An in-progress hold is not a failed hold. Only the finished arm step
        # may create or latch a functional alert.
        arm_function_alert = arm_function_alert and not partial
    arm_alert = arm_function_alert or (arm_delta is not None and arm_delta > parameters["arm_angle_delta_threshold_deg"])
    # A directly observed raise-and-hold outcome can complete the arm portion
    # even when a camera-plane angle could not be calculated.
    complete = set(after) == set(FEATURE_KEYS) and (len(angle_deltas) == 2 or arm_function is not None)
    alert = face_alert or arm_alert
    status = "research_alert" if alert else ("research_below_placeholder" if complete else "research_incomplete")
    return {
        "status": status, "alert": alert, "research_only": True,
        "measurement": measurement, "threshold": None,
        "policy_id": "research-" + hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()[:24],
        "care_message": CARE_MESSAGE,
        "reason": "Unvalidated university demo: " + ("a provisional rule was exceeded." if alert else
                  "rules were not exceeded; this cannot exclude disease." if complete else
                  "one or more measurements are unavailable; this is inconclusive."),
        "research_measurement": {"face_asymmetry_increase": face_increase,
                                 "face_trigger_features": [key for key in FACE_KEYS if key in after and
                                                           measurement["deltas"][key] > parameters["face_delta_threshold"]],
                                 "arm_angle_delta_deg": arm_delta, "angle_deltas": angle_deltas,
                                 "face_delta_threshold": parameters["face_delta_threshold"],
                                 "arm_angle_delta_threshold_deg": parameters["arm_angle_delta_threshold_deg"],
                                 "face_alert": bool(face_alert), "arm_alert": bool(arm_alert),
                                 "baseline_arm_function_status": baseline_arm_function["status"] if baseline_arm_function else None,
                                 "arm_function_status": arm_function["status"] if arm_function else None,
                                 "arm_function_alert": bool(arm_function_alert),
                                 "arm_raise_change_percent": arm_raise_change,
                                 "arm_hold_change_sec": arm_hold_change,
                                 "arm_raise_percent": arm_function.get("raise_percent") if arm_function else None,
                                 "arm_raise_threshold_percent": arm_function.get("required_raise_percent") if arm_function else None,
                                 "arm_hold_sec": arm_function["hold_sec"] if arm_function else None,
                                 "arm_hold_required_sec": arm_function["required_hold_sec"] if arm_function else None},
        "arm_function": arm_function,
    }


def assess_targets(metrics, targets, task):
    names = {"face": {"sensitivity": targets["face_sensitivity"], "specificity": targets["face_specificity"]},
             "overall": {"sensitivity": targets["overall_sensitivity_minimum"]}}
    requirements = names[task]
    checks = {name: None if metrics.get(name) is None else metrics[name] >= target for name, target in requirements.items()}
    return {"targets": requirements, "checks": checks,
            "status": "not_evaluable" if any(value is None for value in checks.values()) else
                      "met_on_this_sample" if all(checks.values()) else "not_met",
            "overall_stretch_met": (metrics.get("sensitivity") >= targets["overall_sensitivity_stretch"])
            if task == "overall" and metrics.get("sensitivity") is not None else None,
            "clinical_performance_established": False}
