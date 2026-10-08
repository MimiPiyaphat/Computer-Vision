"""State machine for the README's FAST screening sequence.

Sequence: quality check -> neutral calibration -> smile -> eye closure -> blink -> arms ->
summary. Timers advance only while the required landmarks are visible.
"""

import time

from config import (
    ARM_INITIAL_CHECK_SEC,
    BLINK_TARGET_COUNT,
    EYE_TEST_DURATION_SEC,
    EYE_CLOSURE_HOLD_SEC,
    EXPRESSION_HOLD_SEC,
    NEUTRAL_CAPTURE_SEC,
)
from src.features import aggregate, FACE_SETUP_KEYS
from src.protocol import check_head_pose

STATE_IDLE = "idle"
STATE_QUALITY_GATE = "quality_gate"
STATE_NEUTRAL_CAPTURE = "neutral_capture"
STATE_MOUTH_TEST = "mouth_test"
STATE_EYE_TEST = "eye_test"
STATE_EYE_CLOSURE = "eye_closure"
STATE_ARM_TEST = "arm_test"
STATE_SUMMARY = "summary"


class ScreeningFlow:
    """Coordinate the individual face and arm analyzers without CV details."""

    def __init__(self, face_analyzer, arm_analyzer):
        self.face_analyzer = face_analyzer
        self.arm_analyzer = arm_analyzer
        self.state = STATE_IDLE
        self._active_elapsed = 0.0
        self._last_detected_at = None
        self.results = {}
        self._neutral_samples = []
        self._blink_counts = {"left": 0, "right": 0}
        self._eye_was_closed = {"left": False, "right": False}
        self.features = {}
        self.setup = {}
        self.research_angles = {}
        self.arm_function = {}
        self._geometry = {"neutral": [], "smile": [], "closure": []}

    def start(self):
        """Start a fresh screening round."""
        self.results = {}
        self._neutral_samples = []
        self._blink_counts = {"left": 0, "right": 0}
        self._eye_was_closed = {"left": False, "right": False}
        self.features = {}
        self.setup = {}
        self.research_angles = {}
        self.arm_function = {}
        self._geometry = {"neutral": [], "smile": [], "closure": []}
        self._go_to(STATE_QUALITY_GATE)

    def _capture_features(self, stage):
        values = self.face_analyzer.latest_features
        if values is None:
            return False
        # 2026-09-11: ratios tolerate translation/distance; retain rotation gates.
        try:
            check_head_pose(values)
        except ValueError:
            return False
        self._geometry[stage].append(dict(values))
        return True

    def is_active(self):
        return self.state not in (STATE_IDLE, STATE_SUMMARY)

    def _go_to(self, state):
        self.state = state
        self._active_elapsed = 0.0
        self._last_detected_at = None

    def _record_detected_time(self, detected):
        """Accumulate only time during which the required landmark is visible."""
        now = time.monotonic()
        if detected:
            if self._last_detected_at is not None:
                self._active_elapsed += now - self._last_detected_at
            self._last_detected_at = now
        else:
            self._last_detected_at = None
        return self._active_elapsed

    def _eye_result(self):
        left = self._blink_counts["left"]
        right = self._blink_counts["right"]
        return {
            "left_blinks": left,
            "right_blinks": right,
            "target_blinks": BLINK_TARGET_COUNT,
        }

    def _update_blink_counts(self, eye_reading):
        for side in ("left", "right"):
            closed = eye_reading[f"{side}_closed"]
            if self._eye_was_closed[side] and not closed:
                self._blink_counts[side] += 1
            self._eye_was_closed[side] = closed

    def update(self, frame_bgr):
        """Advance the flow by one video frame and return UI-ready state."""
        if self.state == STATE_IDLE:
            return {"state": self.state, "instruction": "Start a visit step to begin", "elapsed": 0.0, "extra": {}}

        if self.state == STATE_QUALITY_GATE:
            quality = self.face_analyzer.check_quality(frame_bgr)
            if quality["ok"]:
                self._go_to(STATE_NEUTRAL_CAPTURE)
                return {"state": self.state, "instruction": "Relax your face and look at the camera", "elapsed": 0.0, "extra": {}}
            return {"state": self.state, "instruction": quality["reason"], "elapsed": 0.0, "extra": quality}

        if self.state == STATE_NEUTRAL_CAPTURE:
            sample = self.face_analyzer.capture_neutral(frame_bgr)
            if sample is not None and not self._capture_features("neutral"):
                sample = None
            elapsed = self._record_detected_time(sample is not None)
            if sample is not None:
                self._neutral_samples.append(sample)
            if elapsed >= NEUTRAL_CAPTURE_SEC and len(self._geometry["neutral"]) >= 3:
                self.face_analyzer.set_neutral_baseline(self._neutral_samples)
                values = aggregate(self._geometry["neutral"], ("mouth_ratio", "brow_ratio", "eyelid_ratio") + FACE_SETUP_KEYS)
                self.setup.update({key: values[key] for key in FACE_SETUP_KEYS})
                self.features.update({"neutral_" + key: values[key] for key in ("mouth_ratio", "brow_ratio", "eyelid_ratio")})
                self._go_to(STATE_MOUTH_TEST)
                return {"state": self.state, "instruction": "Smile as wide as you can and hold", "elapsed": 0.0, "extra": {}}
            return {
                "state": self.state,
                "instruction": "Relax your face and look at the camera" if sample else "Face the camera to calibrate",
                "elapsed": elapsed,
                "extra": {"detected": sample is not None},
            }

        if self.state == STATE_MOUTH_TEST:
            observation = self.face_analyzer._observe(frame_bgr)
            detected = observation is not None and self._capture_features("smile")
            elapsed = self._record_detected_time(detected)
            if elapsed >= EXPRESSION_HOLD_SEC and len(self._geometry["smile"]) >= 5:
                samples = self._geometry["smile"]
                self.features["smile_mouth_ratio"] = aggregate(samples[len(samples) // 3:], ("mouth_ratio",))["mouth_ratio"]
                self.results["mouth"] = {"asymmetry": self.features["smile_mouth_ratio"]}
                self._go_to(STATE_EYE_CLOSURE)
                return {"state": self.state, "instruction": "Gently close both eyes and hold", "elapsed": 0.0, "extra": {}}

            return {
                "state": self.state,
                "instruction": "Smile as wide as you can and hold" if detected else "Keep your face visible and face the camera without turning or tilting",
                "elapsed": elapsed,
                "extra": {"detected": detected},
            }

        if self.state == STATE_EYE_CLOSURE:
            eyes = self.face_analyzer.measure_eyes(frame_bgr)
            detected = eyes is not None and self._capture_features("closure")
            elapsed = self._record_detected_time(detected)
            # Detection, not successful closure, advances time: inability to
            # close an eye must remain measurable rather than stall the test.
            if elapsed >= EYE_CLOSURE_HOLD_SEC and len(self._geometry["closure"]) >= 5:
                samples = self._geometry["closure"]
                values = aggregate(samples[len(samples) // 3:], ("eyelid_ratio",))
                self.features.update({"closed_" + key: value for key, value in values.items()})
                self._go_to(STATE_EYE_TEST)
                return {"state": self.state, "instruction": "Blink both eyes naturally several times", "elapsed": 0.0, "extra": {}}
            return {
                "state": self.state,
                "instruction": "Gently close both eyes and hold" if detected else "Keep your face visible and face the camera without turning or tilting",
                "elapsed": elapsed,
                "extra": {"detected": detected, **(eyes or {})},
            }

        if self.state == STATE_EYE_TEST:
            eyes = self.face_analyzer.measure_eyes(frame_bgr)
            detected = eyes is not None
            elapsed = self._record_detected_time(detected)
            if eyes:
                self._update_blink_counts(eyes)
            else:
                self._eye_was_closed = {"left": False, "right": False}
            if elapsed >= EYE_TEST_DURATION_SEC:
                self.results["eye"] = self._eye_result()
                self.arm_analyzer.start_test()
                self._go_to(STATE_ARM_TEST)
                return {"state": self.state, "instruction": "Start with arms down, then raise both arms together", "elapsed": 0.0, "extra": {}}
            extra = {"detected": detected, **(eyes or {}), **self._blink_counts, "target_blinks": BLINK_TARGET_COUNT}
            return {
                "state": self.state,
                "instruction": "Blink both eyes naturally several times" if detected else "Face the camera to continue the blink test",
                "elapsed": elapsed,
                "extra": extra,
            }

        if self.state == STATE_ARM_TEST:
            arm = self.arm_analyzer.analyze(frame_bgr)
            self.research_angles = arm.get("research_angles", {})
            self.arm_function = arm.get("arm_function", {})
            if arm.get("normalized_features"):
                # Max drift is monotonic: expose an early lower-bound score
                # during the hold rather than waiting for the full timer.
                self.features.update(arm["normalized_features"])
                self.setup.update(arm["capture_setup"])
            if arm["test_complete"]:
                self.results["arm"] = arm
                self._go_to(STATE_SUMMARY)
                return {"state": self.state, "instruction": "Screening complete", "elapsed": 0.0, "extra": self.results}
            if arm["pose_found"]:
                instruction = (
                    "Raise both arms together from a lowered position"
                    if arm["elapsed_sec"] < ARM_INITIAL_CHECK_SEC
                    else "Keep both arms raised for 3 seconds"
                )
            elif arm["person_found"]:
                instruction = "Keep shoulders and wrists visible; start with arms down and keep your body still"
            else:
                instruction = "Step into view so the camera can see you"
            return {"state": self.state, "instruction": instruction, "elapsed": arm["elapsed_sec"], "extra": arm}

        if self.state == STATE_SUMMARY:
            return {"state": self.state, "instruction": "Start a new visit step when ready", "elapsed": 0.0, "extra": self.results}

        return {"state": self.state, "instruction": "", "elapsed": 0.0, "extra": {}}
