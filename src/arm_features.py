"""Shoulder-relative arm motion, expressed in shoulder-span units."""

import math
from config import ARM_INITIAL_CHECK_SEC, ARM_INITIAL_LIFT_MIN_PX, SETUP_TOLERANCES


class ArmFeatures:
    def __init__(self):
        self.setup = None
        self.base = {}
        self.highest = {}
        self.drift = {"left": 0.0, "right": 0.0}
        self.lift = None
        self.reason_code = None

    def observe(self, wrists, shoulders, width, height, elapsed):
        self.reason_code = None
        if any(point is None for point in (*wrists.values(), *shoulders.values())):
            self.reason_code = "wrists_missing"
            return False
        left, right = shoulders["left"], shoulders["right"]
        span = math.dist(left, right)
        if span < 20:
            self.reason_code = "body_small"
            return False
        setup = {"body_roll": math.degrees(math.atan2(right[1] - left[1], abs(right[0] - left[0]))),
                 "body_scale": span / width, "body_x": (left[0] + right[0]) / (2 * width),
                 "body_y": (left[1] + right[1]) / (2 * height)}
        position = {side: (wrists[side][1] - shoulders[side][1]) / span for side in wrists}
        if self.setup is None:
            if min(position.values()) < .2:
                self.reason_code = "start_arms_down"
                return False  # Initial acquisition requires lowered arms.
            self.setup = setup
            self.base = dict(position)
            self.highest = dict(position)
        if any(abs(setup[k] - self.setup[k]) > SETUP_TOLERANCES[k] for k in setup):
            self.reason_code = "body_moved"
            return False
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
