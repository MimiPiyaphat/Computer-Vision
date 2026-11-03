import math
import unittest
from types import SimpleNamespace

from src.face_identity import LandmarkFaceIdentity, create_face_identity, cosine_similarity


def landmarks(transform=lambda x, y: (x, y)):
    points = []
    for index in range(478):
        angle = 2 * math.pi * index / 478
        x, y = transform(0.5 + 0.15 * math.cos(angle), 0.5 + 0.20 * math.sin(angle))
        points.append(SimpleNamespace(x=x, y=y))
    # Stable, distinct iris centres required for the coordinate frame.
    points[468] = SimpleNamespace(x=transform(0.45, 0.45)[0], y=transform(0.45, 0.45)[1])
    points[473] = SimpleNamespace(x=transform(0.55, 0.45)[0], y=transform(0.55, 0.45)[1])
    return points


class LandmarkIdentityTests(unittest.TestCase):
    def test_descriptor_is_normalised_and_transform_stable(self):
        model = LandmarkFaceIdentity()
        original = model.embed(None, landmarks())
        moved = model.embed(None, landmarks(lambda x, y: (0.1 + 1.4 * x, -0.2 + 1.4 * y)))
        self.assertEqual(len(original), 512)
        self.assertAlmostEqual(math.hypot(*original), 1.0)
        self.assertGreater(cosine_similarity(original, moved), 0.999999)

    def test_factory_uses_lightweight_backend_without_facenet(self):
        self.assertIsInstance(create_face_identity("landmark"), LandmarkFaceIdentity)

    def test_factory_rejects_unknown_backend(self):
        with self.assertRaisesRegex(ValueError, "facenet.*landmark"):
            create_face_identity("unknown")


if __name__ == "__main__":
    unittest.main()
