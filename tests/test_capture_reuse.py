"""Regression checks for shared observations and face-local lighting."""

import importlib.util
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


@unittest.skipUnless(all(importlib.util.find_spec(n) for n in ("cv2", "numpy", "mediapipe")), "Native CV missing")
class CaptureReuseTests(unittest.TestCase):
    def test_session_runs_mesh_once_per_frame_and_does_not_reuse_missing_face(self):
        import numpy as np
        from src.face_analytics import FaceAnalyzer
        from src.screening_flow import ScreeningFlow
        from src.session import ScreeningSession
        from test_paired_screening import GeometryTests

        for stage in ("quality_gate", "neutral_capture", "mouth_test", "eye_closure", "eye_test", "arm_test"):
            with self.subTest(stage=stage):
                face = FaceAnalyzer.__new__(FaceAnalyzer)
                face._mesh = Mock()
                face._mesh.process.side_effect = [
                    SimpleNamespace(multi_face_landmarks=[SimpleNamespace(landmark=GeometryTests().mesh())]),
                    SimpleNamespace(multi_face_landmarks=[]),
                ]
                face._last_landmarks = face.latest_features = face._neutral_ear = None
                session = ScreeningSession()
                session.face = face
                session.arm = Mock()
                session.arm.analyze.return_value = {"pose_found": True, "person_found": True,
                                                   "test_complete": False, "elapsed_sec": 0}
                session.flow = ScreeningFlow(face, session.arm)
                session.flow.state = stage
                session.workflow = Mock(request={"mode": "baseline"}, context={"width": 640, "height": 480})
                session.identity_model = Mock()
                session.cap = Mock()
                session.cap.read.return_value = (True, np.full((480, 640, 3), 128, dtype=np.uint8))
                with patch("src.face_analytics.estimate_head_pose", return_value={"face_yaw": 0, "face_pitch": 0}):
                    first = session.read()
                    self.assertNotEqual(first["state"], "identity_check")
                    self.assertEqual(face._mesh.process.call_count, 1)
                    self.assertEqual(session.read()["state"], "identity_check")
                self.assertEqual(face._mesh.process.call_count, 2)
                session.identity_model.embed.assert_called_once()
                self.assertIsNone(face.latest_features)
                if stage == "arm_test":
                    session.arm.analyze.assert_called_once()
                    session.arm.start_test.assert_called_once()

    def test_lighting_ignores_background_but_rejects_unbalanced_face(self):
        import numpy as np
        from src.face_analytics import FaceAnalyzer
        face = FaceAnalyzer.__new__(FaceAnalyzer)
        face.latest_features = {"face_x": .5}
        face._last_landmarks = [SimpleNamespace(x=x, y=y) for x, y in
                                ((.3, .2), (.7, .2), (.7, .8), (.3, .8))] * 120
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[:, 50:] = 255
        frame[20:81, 30:71] = 128
        self.assertTrue(face.check_quality(frame, observed=True)["ok"])
        frame[20:81, 30:50] = 20
        self.assertFalse(face.check_quality(frame, observed=True)["ok"])
        face.latest_features = None
        self.assertFalse(face.check_quality(frame, observed=True)["ok"])


if __name__ == "__main__":
    unittest.main()
