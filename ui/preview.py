"""Deterministic UI fixture: never accesses a camera, models, or result logs."""

import time
from ui.content import STEPS


class PreviewSession:
    debug = False

    def open(self):
        self.stop()

    def start(self, request=None):
        self.visit_mode = (request or {}).get("mode", "baseline")
        self.index = 0
        self.started = time.monotonic()

    def stop(self):
        self.visit_mode = None
        self.index = -1
        self.started = time.monotonic()

    def read(self):
        elapsed = time.monotonic() - self.started
        if 0 <= self.index < len(STEPS) - 1 and elapsed >= 3:
            self.index += 1
            self.started = time.monotonic()
            elapsed = 0
        state, _, instruction, duration = STEPS[self.index] if self.index >= 0 else (
            "idle", "", "Explore the interface with simulated data.", 0)
        return {
            "state": state, "instruction": instruction,
            "visit_mode": self.visit_mode,
            "elapsed": min(duration, elapsed * duration / 3),
            "extra": {"detected": True, "left": 2, "right": 2},
            "frame": None,
            "assessment": {"level": "Preview only", "reasons": ["Simulated summary for interface development."],
                           "disclaimer": "No screening was performed."} if state == "summary" else None,
            "save_status": "Preview data is never saved.",
        }

    def close(self):
        pass
