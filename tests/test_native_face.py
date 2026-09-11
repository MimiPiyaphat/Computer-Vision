"""Optional native smoke tests; synthetic inputs do not validate recognition."""

import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HAS_CV = all(importlib.util.find_spec(name) is not None for name in ('cv2', 'numpy'))


@unittest.skipUnless(HAS_CV, 'Native CV dependencies are not installed in this interpreter')
class HeadPoseTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('ultralytics') is not None, 'YOLO missing')
    def test_arm_adapter_retains_normalized_drift_and_pauses_on_missing_pose(self):
        import numpy as np
        from src.arm_pose import ArmPoseAnalyzer
        model = Mock()
        with patch('src.arm_pose.YOLO', return_value=model):
            arm = ArmPoseAnalyzer()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        arm.start_test()
        with patch('src.arm_pose.time.monotonic', return_value=0) as clock:
            for now, left_y, right_y in ((0, 200, 200), (1, 70, 70), (3, 90, 70)):
                clock.return_value = now
                xy = np.zeros((1, 17, 2))
                xy[0, [5, 6, 9, 10]] = ((100, 100), (200, 100), (100, left_y), (200, right_y))
                model.predict.return_value = [SimpleNamespace(keypoints=SimpleNamespace(xy=xy, conf=np.ones((1, 17))))]
                result = arm.analyze(frame)
            self.assertAlmostEqual(result['normalized_features']['left_arm_drift'], .2)
            self.assertEqual(result['elapsed_sec'], 3)
            self.assertNotIn('left_wrist_drift_px', result)
            clock.return_value = 100
            model.predict.return_value = []
            missing = arm.analyze(frame)
            self.assertEqual(missing['elapsed_sec'], 3)
            self.assertFalse(missing['test_complete'])
            self.assertIsNone(arm._last_detected_at)
        arm.close()

    def test_projected_known_rotations_and_distances(self):
        import cv2
        import numpy as np
        from src.head_pose import MODEL_POINTS, INDICES, estimate_head_pose
        camera = np.array(((640., 0, 320), (0, 640., 240), (0, 0, 1)))
        for axis, key in ((0, 'face_pitch'), (1, 'face_yaw')):
            for degrees in (-25, -18, 0, 18, 25):
                for depth in (500., 900.):
                    rotation = np.zeros(3)
                    rotation[axis] = math.radians(degrees)
                    projected, _ = cv2.projectPoints(np.array(MODEL_POINTS, dtype=float), rotation,
                                                      np.array((30., -20., depth)), camera, np.zeros(4))
                    mesh = [SimpleNamespace(x=.5, y=.5) for _ in range(478)]
                    for index, (x, y) in zip(INDICES, projected.reshape(-1, 2)):
                        mesh[index] = SimpleNamespace(x=float(x) / 640, y=float(y) / 480)
                    self.assertAlmostEqual(estimate_head_pose(mesh, 640, 480)[key], degrees, places=4)

    @unittest.skipUnless(importlib.util.find_spec('mediapipe') is not None, 'MediaPipe missing')
    def test_refined_mesh_starts_and_blank_frame_is_rejected(self):
        import numpy as np
        from src.face_analytics import FaceAnalyzer
        face = FaceAnalyzer()
        try:
            self.assertIsNone(face._observe(np.zeros((480, 640, 3), dtype=np.uint8)))
        finally:
            face.close()

    @unittest.skipUnless(importlib.util.find_spec('facenet_pytorch') is not None,
                         'Optional FaceNet package is missing')
    def test_real_weights_and_crop_produce_repeatable_finite_embedding(self):
        import numpy as np
        from config import IDENTITY_MODEL_PATH
        from src.face_identity import FaceIdentity, cosine_similarity
        import test_paired_screening as fixtures
        if not Path(IDENTITY_MODEL_PATH).is_file():
            self.skipTest('Run prepare_identity_model.py first')
        model = FaceIdentity()
        try:
            frame = np.random.default_rng(17).integers(0, 256, (480, 640, 3), dtype=np.uint8)
            mesh = fixtures.GeometryTests().mesh()
            before, after = model.embed(frame, mesh), model.embed(frame, mesh)
            self.assertEqual(len(before), 512)
            self.assertTrue(all(math.isfinite(v) for v in before))
            self.assertAlmostEqual(math.hypot(*before), 1)
            self.assertAlmostEqual(cosine_similarity(before, after), 1)
            with self.assertRaises(ValueError):
                model.embed(frame, None)
            for p in mesh:
                p.x -= .4
            with self.assertRaisesRegex(ValueError, 'entire face'):
                model.embed(frame, mesh)
        finally:
            model.close()


if __name__ == '__main__':
    unittest.main()
