"""
face_analytics.py
==================
โมดูลตรวจจับความผิดปกติของใบหน้า (F - Face) ตามหลัก FAST
- Facial Symmetry: เทียบมุมปาก / ปีกจมูก ซ้าย-ขวา
- Ptosis & Blinking (EAR): ตรวจหนังตาตกและการกะพริบตาไม่เท่ากัน

สถานะ: SKELETON — ยังไม่ implement logic จริง รอ step ถัดไป
ใช้ MediaPipe Face Mesh เป็น backend หลัก
"""

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

    def analyze(self, frame_bgr):
        """
        รับภาพ (BGR, จาก OpenCV) 1 เฟรม
        คืนค่า dict ผลลัพธ์ เช่น:
        {
            "face_found": bool,
            "left_ear": float,
            "right_ear": float,
            "ear_asymmetry": float,
            "mouth_asymmetry": float,
            "is_droop_suspected": bool,
        }

        TODO (step ถัดไป):
        1. แปลง frame_bgr -> RGB แล้วส่งเข้า self._face_mesh.process()
        2. ดึงพิกัด landmark ตาม LEFT_EYE_IDX / RIGHT_EYE_IDX มาคำนวณ EAR แต่ละข้าง
        3. คำนวณ mouth asymmetry จากระยะ MOUTH_LEFT_CORNER / MOUTH_RIGHT_CORNER เทียบ NOSE_TIP
        4. เทียบค่ากับ threshold ใน config.py เพื่อสรุปผล is_droop_suspected
        """
        raise NotImplementedError("จะ implement ใน step ถัดไป")

    def close(self):
        self._face_mesh.close()
