"""
face_analytics.py
==================
โมดูลตรวจจับความผิดปกติของใบหน้า (F - Face) ตามหลัก FAST
- Facial Symmetry: เทียบมุมปาก / ปีกจมูก ซ้าย-ขวา
- Ptosis & Blinking (EAR): ตรวจหนังตาตกและการกะพริบตาไม่เท่ากัน

สถานะ: IMPLEMENTED — คำนวณ EAR ซ้าย-ขวา และ mouth asymmetry จาก landmark จริงแล้ว
ใช้ MediaPipe Face Mesh เป็น backend หลัก
"""

import cv2
import mediapipe as mp

from config import EAR_THRESHOLD, EAR_ASYMMETRY_THRESHOLD, MOUTH_ASYMMETRY_THRESHOLD
from src.utils import calculate_ear, euclidean_distance

mp_face_mesh = mp.solutions.face_mesh

# Landmark indices ของ MediaPipe Face Mesh (468 จุด) ที่จะใช้งาน
# อ้างอิงตำแหน่งมาตรฐานของ MediaPipe Face Mesh topology
LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]
MOUTH_LEFT_CORNER = 61
MOUTH_RIGHT_CORNER = 291
NOSE_TIP = 1


class FaceAnalyzer:
    """
    วิเคราะห์ frame รายเฟรมเพื่อหาสัญญาณ Face-droop / Ptosis
    ใช้งานโดยสร้าง instance แล้วเรียก analyze(frame) วนในลูปหลัก
    """

    def __init__(self, max_num_faces=1, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        self._face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=max_num_faces,
            refine_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    @staticmethod
    def _empty_result():
        return {
            "face_found": False,
            "left_ear": 0.0,
            "right_ear": 0.0,
            "ear_asymmetry": 0.0,
            "mouth_asymmetry": 0.0,
            "is_droop_suspected": False,
            "landmarks_px": None,
        }

    def analyze(self, frame_bgr):
        """
        รับภาพ (BGR, จาก OpenCV) 1 เฟรม
        คืนค่า dict:
        {
            "face_found": bool,
            "left_ear": float,
            "right_ear": float,
            "ear_asymmetry": float,      # |left_ear - right_ear|
            "mouth_asymmetry": float,    # ความต่างระยะมุมปาก-จมูก ซ้าย/ขวา (normalized)
            "is_droop_suspected": bool,  # true ถ้าเข้าเกณฑ์ threshold ข้อใดข้อหนึ่ง
            "landmarks_px": list | None, # จุด landmark ทั้งหมด (x, y) เป็นพิกเซล ไว้วาด debug
        }
        """
        h, w = frame_bgr.shape[:2]
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self._face_mesh.process(frame_rgb)

        if not results.multi_face_landmarks:
            return self._empty_result()

        face_landmarks = results.multi_face_landmarks[0]
        points_px = [(lm.x * w, lm.y * h) for lm in face_landmarks.landmark]

        left_eye_pts = [points_px[i] for i in LEFT_EYE_IDX]
        right_eye_pts = [points_px[i] for i in RIGHT_EYE_IDX]
        left_ear = calculate_ear(left_eye_pts)
        right_ear = calculate_ear(right_eye_pts)
        ear_asymmetry = abs(left_ear - right_ear)

        nose_tip = points_px[NOSE_TIP]
        mouth_left = points_px[MOUTH_LEFT_CORNER]
        mouth_right = points_px[MOUTH_RIGHT_CORNER]

        inter_ocular_dist = euclidean_distance(points_px[LEFT_EYE_IDX[0]], points_px[RIGHT_EYE_IDX[3]])
        if inter_ocular_dist == 0:
            mouth_asymmetry = 0.0
        else:
            dist_left = euclidean_distance(mouth_left, nose_tip)
            dist_right = euclidean_distance(mouth_right, nose_tip)
            mouth_asymmetry = abs(dist_left - dist_right) / inter_ocular_dist

        is_droop_suspected = (
            ear_asymmetry > EAR_ASYMMETRY_THRESHOLD
            or mouth_asymmetry > MOUTH_ASYMMETRY_THRESHOLD
            or left_ear < EAR_THRESHOLD
            or right_ear < EAR_THRESHOLD
        )

        return {
            "face_found": True,
            "left_ear": round(left_ear, 3),
            "right_ear": round(right_ear, 3),
            "ear_asymmetry": round(ear_asymmetry, 3),
            "mouth_asymmetry": round(mouth_asymmetry, 3),
            "is_droop_suspected": is_droop_suspected,
            "landmarks_px": points_px,
        }

    @staticmethod
    def draw_debug(frame_bgr, result):
        """วาดจุด landmark ที่เกี่ยวข้อง (ตา/ปาก/จมูก) ลงบนเฟรม เพื่อ debug ด้วยตา"""
        if not result["face_found"] or result["landmarks_px"] is None:
            return frame_bgr

        points_px = result["landmarks_px"]
        idx_to_draw = LEFT_EYE_IDX + RIGHT_EYE_IDX + [MOUTH_LEFT_CORNER, MOUTH_RIGHT_CORNER, NOSE_TIP]
        for idx in idx_to_draw:
            x, y = points_px[idx]
            cv2.circle(frame_bgr, (int(x), int(y)), 2, (0, 255, 255), -1)
        return frame_bgr

    def close(self):
        self._face_mesh.close()
