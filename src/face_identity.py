"""2026-09-11: CPU FaceNet one-to-one matching, separate from clinical features.

This is identity consistency checking, NOT photo/replay/liveness detection.
No face crops are written. Missing/invalid embeddings always fail closed.
"""

import hashlib
import math
from pathlib import Path
from config import IDENTITY_MODEL_PATH, IDENTITY_CPU_THREADS

EMBEDDING_SIZE = 512
MISMATCH_MESSAGE = "Identity mismatch: does not match registered user"
MODEL_URL = "https://github.com/timesler/facenet-pytorch/releases/download/v2.2.9/20180402-114759-vggface2.pt"


class IdentityMismatch(ValueError):
    pass


def normalized_embedding(vector):
    if not isinstance(vector, (list, tuple)) or len(vector) != EMBEDDING_SIZE:
        raise ValueError("Identity embedding must contain 512 finite numbers.")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in vector):
        raise ValueError("Invalid identity embedding.")
    norm = math.hypot(*vector)
    if not math.isfinite(norm) or norm <= 1e-12:
        raise ValueError("Identity embedding has no usable magnitude.")
    return [v / norm for v in vector]


def identity_payload(embedding, model):
    if not isinstance(model, str) or not model.strip() or len(model) > 256:
        raise ValueError("Missing identity model signature.")
    return {"embedding": normalized_embedding(embedding), "model": model}


def cosine_similarity(before, after):
    left, right = normalized_embedding(before), normalized_embedding(after)
    return max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(left, right))))


class FaceIdentity:
    """Pinned VGGFace2 InceptionResnetV1; MediaPipe crop, RGB 160, CPU eval.

    Model files must be prepared explicitly with prepare_identity_model.py.
    The signature binds weights, package and crop/preprocessing implementation.
    """
    def __init__(self, model_path=IDENTITY_MODEL_PATH):
        import importlib.metadata
        import torch
        from facenet_pytorch import InceptionResnetV1
        torch.set_num_threads(IDENTITY_CPU_THREADS)
        path = Path(model_path)
        if not path.is_file():
            raise ValueError("Face identity weights missing. Run python prepare_identity_model.py before camera capture.")
        # weights_only avoids executing arbitrary pickle globals. Runtime does not download.
        state = torch.load(path, map_location="cpu", weights_only=True)
        self.model = InceptionResnetV1(classify=True, num_classes=8631, device="cpu")
        self.model.load_state_dict(state, strict=True)
        self.model.classify = False
        self.model.eval()
        digest = hashlib.sha256(path.read_bytes() + Path(__file__).read_bytes()).hexdigest()
        self.signature = "facenet-vggface2-" + importlib.metadata.version("facenet-pytorch") + "-" + digest

    def embed(self, frame_bgr, landmarks):
        """Align by iris axis, crop visible facial mesh with 10% margin, infer.

        Uses the same mesh already required by the app; no second face detector.
        A custom crop needs local threshold tuning; 0.6 is experimental.
        """
        import cv2
        import numpy as np
        import torch
        if landmarks is None or len(landmarks) != 478:
            raise ValueError("Keep exactly one complete face visible for identity verification.")
        height, width = frame_bgr.shape[:2]
        points = np.array([(p.x * width, p.y * height) for p in landmarks], dtype=np.float32)
        if not np.isfinite(points).all():
            raise ValueError("Invalid face crop for identity verification.")
        left, right = points[468], points[473]
        angle = math.degrees(math.atan2(float(right[1] - left[1]), float(right[0] - left[0])))
        transform = cv2.getRotationMatrix2D(tuple(float(v) for v in (left + right) / 2), angle, 1)
        aligned_points = cv2.transform(points[:468].reshape(1, -1, 2), transform)[0]
        low, high = aligned_points.min(axis=0), aligned_points.max(axis=0)
        size = float(max(high - low)) * 1.1
        if size < 40:
            raise ValueError("Move closer for identity verification.")
        origin = (low + high - size) / 2
        transform[:, 2] -= origin
        transform *= 160 / size
        # Reject padding: every output corner must originate inside the camera frame.
        inverse = cv2.invertAffineTransform(transform)
        corners = cv2.transform(np.array([[[0, 0], [159, 0], [159, 159], [0, 159]]], dtype=np.float32), inverse)[0]
        if (corners < 0).any() or (corners[:, 0] >= width).any() or (corners[:, 1] >= height).any():
            raise ValueError("Keep the entire face and a small margin inside the camera view.")
        crop = cv2.warpAffine(frame_bgr, transform, (160, 160))
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        tensor = (torch.from_numpy(rgb.copy()).permute(2, 0, 1).float() - 127.5) / 128.0
        with torch.inference_mode():
            vector = self.model(tensor.unsqueeze(0)).squeeze(0).tolist()
        return normalized_embedding(vector)

    def close(self):
        self.model = None
