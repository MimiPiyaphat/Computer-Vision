"""Shoulder-relative arm motion, expressed in shoulder-span units."""

import math
from config import (ARM_INITIAL_CHECK_SEC, ARM_INITIAL_LIFT_MIN_PX,
                    ARM_RAISED_WRIST_MAX_SHOULDER_SPANS,
                    ARM_REQUIRED_RAISED_HOLD_SEC, SETUP_TOLERANCES)


ARM_FUNCTION_STATUSES = frozenset(("normal", "unable_to_raise", "unable_to_hold"))


def validate_arm_function(value):
    required = {"status", "left_raised", "right_raised", "hold_sec", "required_hold_sec"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("Invalid arm function result.")
    if value["status"] not in ARM_FUNCTION_STATUSES:
        raise ValueError("Invalid arm function status.")
    if type(value["left_raised"]) is not bool or type(value["right_raised"]) is not bool:
        raise ValueError("Arm raised flags must be boolean.")
    for key in ("hold_sec", "required_hold_sec"):
        if type(value[key]) not in (int, float) or not math.isfinite(value[key]) or value[key] < 0:
            raise ValueError("Arm hold times must be finite non-negative numbers.")
    return dict(value)


class ArmFeatures:
    def __init__(self):
        self.setup = None
        self.base = {}
        self.highest = {}
        self.drift = {"left": 0.0, "right": 0.0}
        self.lift = None
        self.raised_ever = {"left": False, "right": False}
        self._raised_started_at = None
        self.max_hold_sec = 0.0

    def observe(self, wrists, shoulders, width, height, elapsed):
        if any(point is None for point in (*wrists.values(), *shoulders.values())):
            return False
        left, right = shoulders["left"], shoulders["right"]
        span = math.dist(left, right)
        if span < 20:
            return False
        setup = {"body_roll": math.degrees(math.atan2(right[1] - left[1], abs(right[0] - left[0]))),
                 "body_scale": span / width, "body_x": (left[0] + right[0]) / (2 * width),
                 "body_y": (left[1] + right[1]) / (2 * height)}
        position = {side: (wrists[side][1] - shoulders[side][1]) / span for side in wrists}
        if self.setup is None:
            self.setup = setup
        if any(abs(setup[k] - self.setup[k]) > SETUP_TOLERANCES[k] for k in setup):
            return False

        raised = {side: position[side] <= ARM_RAISED_WRIST_MAX_SHOULDER_SPANS for side in position}
        for side in raised:
            self.raised_ever[side] = self.raised_ever[side] or raised[side]
        if all(raised.values()):
            if self._raised_started_at is None:
                self._raised_started_at = elapsed
            self.max_hold_sec = max(self.max_hold_sec, elapsed - self._raised_started_at)
        else:
            self._raised_started_at = None

        # A lowered reference is still preferred for the continuous drift
        # features, but the functional raise/hold result above remains usable
        # when a person enters the frame with their arms already raised.
        if not self.base:
            if min(position.values()) >= .2:
                self.base = dict(position)
                self.highest = dict(position)
            return True
        if elapsed <= ARM_INITIAL_CHECK_SEC:
            for side in position:
                self.highest[side] = min(self.highest[side], position[side])
        else:
            if self.lift is None:
                self.lift = {side: max(0.0, self.base[side] - self.highest[side]) for side in position}
                if max(self.lift.values()) * span < ARM_INITIAL_LIFT_MIN_PX:
                    self.lift = None
            for side in position:
                self.drift[side] = max(self.drift[side], position[side] - self.highest[side])
        return True

    def vector(self):
        if self.lift is None:
            return None
        return {"left_arm_drift": self.drift["left"], "right_arm_drift": self.drift["right"],
                "arm_lift_skew": self.lift["left"] - self.lift["right"]}

    def complete_vector(self):
        """Complete the legacy numeric contract after the timed test.

        The explicit arm_function result carries raise/hold failure semantics;
        zeros here mean that no reliable drift vector was available, not that
        the functional test passed.
        """
        return self.vector() or {"left_arm_drift": 0.0, "right_arm_drift": 0.0,
                                 "arm_lift_skew": 0.0}

    def function_result(self):
        if self.max_hold_sec >= ARM_REQUIRED_RAISED_HOLD_SEC:
            status = "normal"
        elif all(self.raised_ever.values()):
            status = "unable_to_hold"
        else:
            status = "unable_to_raise"
        return {
            "status": status,
            "left_raised": self.raised_ever["left"],
            "right_raised": self.raised_ever["right"],
            "hold_sec": round(self.max_hold_sec, 2),
            "required_hold_sec": float(ARM_REQUIRED_RAISED_HOLD_SEC),
        }
