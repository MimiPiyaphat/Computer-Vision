"""MediaPipe: 468 facial points + 10 iris points; YOLO never analyzes faces."""

import cv2
import mediapipe as mp
import numpy as np

from config import EYE_CLOSED_RATIO, MIN_FACE_DETECTION_CONFIDENCE, QUALITY_MAX_BRIGHTNESS_DIFF
from src.features import face_geometry
from src.head_pose import estimate_head_pose
from src.protocol import check_head_pose


class FaceAnalyzer:
    def __init__(self):
        # Two faces let us reject ambiguous multi-person acquisition.
        self._mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False, max_num_faces=2, refine_landmarks=True,
            min_detection_confidence=MIN_FACE_DETECTION_CONFIDENCE,
            min_tracking_confidence=MIN_FACE_DETECTION_CONFIDENCE)
        self._last_landmarks = None
        self.latest_features = None
        self._neutral_ear = None

    def _observe(self, frame_bgr):
        self.latest_features = None
        self._last_landmarks = None
        result = self._mesh.process(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        faces = result.multi_face_landmarks or []
        if len(faces) != 1:
            return None
        landmarks = faces[0].landmark
        if any(not 0 <= p.x <= 1 or not 0 <= p.y <= 1 for p in landmarks):
            return None
        try:
            height, width = frame_bgr.shape[:2]
            pose = estimate_head_pose(landmarks, width, height)
            values = face_geometry(landmarks, width, height, pose)
            check_head_pose(values)
        except ValueError:
            return None
        self._last_landmarks = landmarks
        self.latest_features = values
        return values

    def check_quality(self, frame_bgr):
        if self._observe(frame_bgr) is None:
            return {"ok": False, "reason": "Keep exactly one complete face visible, close enough to the camera."}
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        midpoint = gray.shape[1] // 2
        difference = abs(float(np.mean(gray[:, :midpoint])) - float(np.mean(gray[:, midpoint:])))
        if difference > QUALITY_MAX_BRIGHTNESS_DIFF:
            return {"ok": False, "reason": "Improve uneven lighting before continuing."}
        return {"ok": True, "reason": ""}

    def capture_neutral(self, frame_bgr):
        observation = self._observe(frame_bgr)
        return (observation["left_ear"], observation["right_ear"]) if observation else None

    def set_neutral_baseline(self, samples):
        self._neutral_ear = tuple(float(v) for v in np.median(samples, axis=0)) if samples else None

    def measure_eyes(self, frame_bgr):
        observation = self._observe(frame_bgr)
        if observation is None:
            return None
        left, right = observation["left_ear"], observation["right_ear"]
        baseline = self._neutral_ear or (left, right)
        return {"left_ear": left, "right_ear": right,
                "left_closed": left < baseline[0] * EYE_CLOSED_RATIO,
                "right_closed": right < baseline[1] * EYE_CLOSED_RATIO}

    def draw_debug(self, frame_bgr):
        if self._last_landmarks:
            height, width = frame_bgr.shape[:2]
            for point in self._last_landmarks:
                cv2.circle(frame_bgr, (int(point.x * width), int(point.y * height)), 1, (255, 200, 0), -1)
        return frame_bgr

    def close(self):
        self._mesh.close()
