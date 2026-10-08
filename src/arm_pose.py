"""YOLO pose acquisition with shoulder-normalized drift and research angles.

2026-09-11: removed duplicate pixel drift tracking and legacy risk flags.
Only visible, stable shoulder/wrist samples advance the hold timer.
"""

import time
import math

from src.runtime import configure_yolo_runtime

configure_yolo_runtime()  # Must precede Ultralytics' import-time settings access.
from ultralytics import YOLO
from src.arm_features import ArmFeatures
from src.projected_arm_angle import ProjectedArmAngle
from src.acquisition import MESSAGES

from config import (
    ARM_HOLD_DURATION_SEC,
    ARM_INITIAL_CHECK_SEC,
    ARM_INITIAL_LIFT_MIN_PX,
    ARM_KEYPOINT_CONF_THRESHOLD,
    YOLO_POSE_MODEL,
    YOLO_CONF_THRESHOLD,
    YOLO_DEVICE,
    YOLO_IMAGE_SIZE,
)

# COCO keypoint indices used by YOLOv8-Pose (17 standard points)
# Reference: https://docs.ultralytics.com/tasks/pose/
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_WRIST = 9
RIGHT_WRIST = 10


class ArmPoseAnalyzer:
    """
    Tracks arm position with YOLOv8-Pose to detect Arm Weakness.
    Usage: start_test() -> analyze(frame) repeatedly across frames during the test.
    """

    def __init__(self, model_path=YOLO_POSE_MODEL, conf_threshold=YOLO_CONF_THRESHOLD,
                 keypoint_conf_threshold=ARM_KEYPOINT_CONF_THRESHOLD, require_angles=False):
        self._model = YOLO(model_path)
        self._conf_threshold = conf_threshold                    # used for person detection
        self._keypoint_conf_threshold = keypoint_conf_threshold  # used for individual keypoints (wrists)
        self._started = False
        self.require_angles = require_angles
        self._detected_elapsed_sec = 0.0
        self._last_detected_at = None
        self._last_yolo_results = None
        self.normalized = ArmFeatures()
        self.projected_angle = ProjectedArmAngle()

    def start_test(self):
        """Starts a new arm-hold test and clears all state from the previous round."""
        self._started = True
        self._detected_elapsed_sec = 0.0
        self._last_detected_at = None
        self.normalized = ArmFeatures()
        self.projected_angle = ProjectedArmAngle()

    @staticmethod
    def _empty_result(elapsed_sec=0.0, person_found=False, reason_code="person_missing"):
        return {
            "pose_found": False,
            "person_found": person_found,   # True if a person was detected but wrists weren't visible/confident enough
            "elapsed_sec": round(elapsed_sec, 1),
            "test_complete": False,
            "reason_code": reason_code,
            "instruction": MESSAGES[reason_code],
            "capture_paused": True,
        }

    def analyze(self, frame_bgr):
        """Return normalized measurements and visibility/timing metadata."""
        if not self._started:
            raise RuntimeError("start_test() must be called before analyze()")

        results = self._model.predict(
            frame_bgr, conf=self._conf_threshold, verbose=False, device=YOLO_DEVICE, imgsz=YOLO_IMAGE_SIZE
        )
        self._last_yolo_results = results

        pose = results[0].keypoints if results else None
        shape = pose.xy.shape if pose is not None else ()
        # Some Ultralytics versions represent no detection as (1, 0, 2).
        person_found = len(shape) == 3 and shape[0] == 1 and shape[1] >= 17 and shape[2] == 2

        if not person_found:
            self._last_detected_at = None
            detected_elapsed = self._detected_elapsed_sec
            reason = "multiple_people" if len(shape) == 3 and shape[0] > 1 else "person_missing"
            return self._empty_result(elapsed_sec=detected_elapsed, reason_code=reason)

        keypoints = results[0].keypoints.xy[0]  # tensor shape (17, 2)
        conf_scores = results[0].keypoints.conf
        confs = conf_scores[0] if conf_scores is not None else None

        def _get_point(idx):
            # Individual keypoints use a more lenient threshold than the person box itself -
            # a raised wrist near the edge of frame often scores lower than the person as a whole.
            if confs is not None:
                confidence = float(confs[idx])
                if not math.isfinite(confidence) or confidence < self._keypoint_conf_threshold:
                    return None
            x, y = keypoints[idx]
            x, y = float(x), float(y)
            if not math.isfinite(x) or not math.isfinite(y) or not (0 < x < frame_bgr.shape[1] and 0 < y < frame_bgr.shape[0]):
                return None
            return (x, y)

        left_wrist = _get_point(LEFT_WRIST)
        right_wrist = _get_point(RIGHT_WRIST)
        shoulders = {"left": _get_point(LEFT_SHOULDER), "right": _get_point(RIGHT_SHOULDER)}

        # The README's arm test requires both arms to be visible. Pausing the
        # timer on a missing wrist avoids accepting a partial pose as a full
        # ten-second hold.
        if left_wrist is None or right_wrist is None or any(p is None for p in shoulders.values()):
            self._last_detected_at = None
            detected_elapsed = self._detected_elapsed_sec
            reason = ("wrists_missing" if left_wrist is None and right_wrist is None else
                      "wrist_missing" if left_wrist is None or right_wrist is None else "shoulders_missing")
            # The person is visible, but the required shoulder/wrist set is incomplete.
            return self._empty_result(elapsed_sec=detected_elapsed, person_found=True, reason_code=reason)

        # Both wrists are visible: accumulate continuous detected hold time.
        now = time.monotonic()
        proposed_elapsed = self._detected_elapsed_sec + (now - self._last_detected_at if self._last_detected_at is not None else 0)
        span = math.dist(shoulders["left"], shoulders["right"])
        attempted = self.normalized.base and max(
            self.normalized.base[s] - self.normalized.highest[s] for s in ("left", "right")) * span >= ARM_INITIAL_LIFT_MIN_PX
        if not self.normalized.observe({"left": left_wrist, "right": right_wrist}, shoulders,
                                       frame_bgr.shape[1], frame_bgr.shape[0], proposed_elapsed):
            self._last_detected_at = None
            return self._empty_result(elapsed_sec=self._detected_elapsed_sec, person_found=True,
                                      reason_code=self.normalized.reason_code)
        projected_now = self.projected_angle.angles({"left": left_wrist, "right": right_wrist}, shoulders)
        self._detected_elapsed_sec = proposed_elapsed
        self._last_detected_at = now
        detected_elapsed = self._detected_elapsed_sec
        self.projected_angle.observe({"left": left_wrist, "right": right_wrist}, shoulders, detected_elapsed)
        arm_function = self.normalized.function_result()
        test_complete = (detected_elapsed >= ARM_HOLD_DURATION_SEC or
                         arm_function["status"] == "normal")
        vector, angles = self.normalized.vector(), self.projected_angle.vector()
        reason = ("hold_arms" if arm_function["status"] in ("normal", "unable_to_hold") else
                  "spread_arms" if projected_now is None and attempted else "raise_arms")

        return {
            "pose_found": True,
            "person_found": True,
            "elapsed_sec": round(detected_elapsed, 1),
            "test_complete": test_complete,
            "normalized_features": (self.normalized.complete_vector() if test_complete
                                    else vector),
            "capture_setup": self.normalized.setup,
            "research_angles": angles,
            "arm_function": arm_function,
            "reason_code": reason,
            "instruction": MESSAGES[reason],
            "capture_paused": False,
        }

    def draw_debug(self, frame_bgr):
        """Draws the skeleton last detected by YOLOv8-Pose (uses ultralytics' built-in .plot())."""
        if not self._last_yolo_results:
            return frame_bgr
        return self._last_yolo_results[0].plot(img=frame_bgr)

    def close(self):
        self._last_yolo_results = None
        self._model = None
