"""Stable acquisition reason codes, shared by capture and presentation."""

MESSAGES = {
    "person_missing": "Step into view so the camera can see you",
    "multiple_people": "Keep only one person in the camera view",
    "wrists_missing": "Both wrists are not visible",
    "wrist_missing": "One wrist is not visible",
    "shoulders_missing": "Keep both shoulders visible",
    "body_small": "Move closer while keeping both wrists visible",
    "start_arms_down": "Start with both arms down",
    "body_moved": "Return to the starting body position and keep still",
    "raise_arms": "Raise both arms together from a lowered position",
    "spread_arms": "Spread both arms out to the sides so the camera can measure them",
    "hold_arms": "Keep both arms raised",
    "face_unavailable": "A complete forward-facing face could not be measured",
    "lighting": "Improve uneven lighting before continuing.",
    "identity_unavailable": "Identity could not be confirmed within the capture time limit",
    "insufficient_samples": "Not enough valid samples were collected",
    "features_incomplete": "Incomplete required face or arm measurements",
    "angles_missing": "Both projected arm angles are required",
    "baseline_angles_missing": "The baseline has no complete arm angles; contact staff to collect a new baseline",
}


class AcquisitionError(ValueError):
    def __init__(self, reason_code):
        self.reason_code = reason_code
        super().__init__(MESSAGES[reason_code])


class SaveFailure(OSError):
    """Persistence failed after measurement; retain any already computed alert."""

    def __init__(self, error, comparison=None):
        self.comparison = comparison
        super().__init__(str(error))


def require_complete(features, setup, angles=None):
    from src.features import numeric_map, FEATURE_KEYS, SETUP_KEYS
    from src.research import ANGLE_KEYS, validate_angles
    try:
        numeric_map(features, FEATURE_KEYS)
        numeric_map(setup, SETUP_KEYS)
    except ValueError as exc:
        raise AcquisitionError("features_incomplete") from exc
    if angles is not None:
        try:
            numeric_map(angles, ANGLE_KEYS)
            validate_angles(angles)
        except ValueError as exc:
            raise AcquisitionError("angles_missing") from exc
