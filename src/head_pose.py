"""Approximate head rotation gate, added 2026-09-11 with ratio normalization.

Generic face geometry and estimated camera intrinsics mean these degrees are
engineering estimates, not calibrated clinical angles. Translation and scale
are not baseline compatibility gates. See validation/RATIO_IDENTITY.md.
"""

INDICES = (1, 152, 33, 263, 61, 291)
MODEL_POINTS = ((0, 0, 0), (0, 63.6, 12.5), (-43.3, -32.7, 26),
                (43.3, -32.7, 26), (-28.9, 28.9, 24.1), (28.9, 28.9, 24.1))


def estimate_head_pose(landmarks, width, height):
    import cv2
    import numpy as np
    points = np.array([(landmarks[i].x * width, landmarks[i].y * height) for i in INDICES], dtype=np.float64)
    model = np.array(MODEL_POINTS, dtype=np.float64)
    camera = np.array(((width, 0, width / 2), (0, width, height / 2), (0, 0, 1)), dtype=np.float64)
    distortion = np.zeros((4, 1))
    try:
        ok, rotation, translation = cv2.solvePnP(model, points, camera, distortion, flags=cv2.SOLVEPNP_EPNP)
        if not ok:
            raise ValueError("Head pose unavailable.")
        ok, rotation, translation = cv2.solvePnP(model, points, camera, distortion, rotation, translation,
                                               useExtrinsicGuess=True, flags=cv2.SOLVEPNP_ITERATIVE)
        angles = cv2.RQDecomp3x3(cv2.Rodrigues(rotation)[0])[0]
    except cv2.error as exc:
        raise ValueError("Head pose unavailable.") from exc
    if not ok or translation[2, 0] <= 0 or not np.isfinite(angles).all():
        raise ValueError("Head pose unavailable.")
    return {"face_pitch": float(angles[0]), "face_yaw": float(angles[1])}
