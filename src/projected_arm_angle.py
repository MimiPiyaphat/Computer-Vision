"""2D camera-plane descent proxy. Does NOT estimate forearm pronation."""

import math
from config import ARM_INITIAL_CHECK_SEC


class ProjectedArmAngle:
    def __init__(self):
        self.reference = {}
        self.maximum = {}
        self.current_valid = False

    @staticmethod
    def angles(wrists, shoulders):
        a, b = shoulders["left"], shoulders["right"]
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx < 0:
            dx, dy = -dx, -dy
        span = math.hypot(dx, dy)
        if span < 20:
            return None
        values = {}
        for side in ("left", "right"):
            x, y = wrists[side][0] - shoulders[side][0], wrists[side][1] - shoulders[side][1]
            outward = abs((x * dx + y * dy) / span)
            down = (-x * dy + y * dx) / span
            # Forward-pointing/foreshortened arms cannot supply reliable 2D
            # angles. Missing angles stay missing, never a fabricated zero.
            if outward < .25 * span:
                return None
            values[side] = math.degrees(math.atan2(down, outward))
        return values

    def observe(self, wrists, shoulders, elapsed):
        values = self.angles(wrists, shoulders)
        self.current_valid = values is not None
        if values is None:
            return
        if elapsed <= ARM_INITIAL_CHECK_SEC:
            for side, value in values.items():
                self.reference[side] = min(self.reference.get(side, value), value)
        elif len(self.reference) == 2:
            for side, value in values.items():
                self.maximum[side] = max(self.maximum.get(side, 0.0), value - self.reference[side])

    def vector(self):
        if not self.current_valid or len(self.maximum) != 2:
            return {}
        return {side + "_projected_drift_deg": value for side, value in self.maximum.items()}
