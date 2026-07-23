"""
arm_pose.py
===========
โมดูลตรวจจับแขนอ่อนแรง (A - Arm) ตามหลัก FAST
ให้ผู้ใช้ยกแขนค้างไว้ตามเวลาที่กำหนด (config.ARM_HOLD_DURATION_SEC)
แล้วติดตามตำแหน่งข้อมือ (wrist) ว่ามีอาการ "แขนตก" (Arm Drift) หรือไม่

สถานะ: SKELETON — ยังไม่ implement logic จริง รอ step ถัดไป
ใช้ MediaPipe Pose เป็น backend หลัก
"""

import time

import mediapipe as mp

from config import ARM_DRIFT_THRESHOLD_PX, ARM_HOLD_DURATION_SEC, ARM_DRIFT_CHECK_INTERVAL_SEC

mp_pose = mp.solutions.pose

# Landmark index ของ MediaPipe Pose ที่เกี่ยวข้อง
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16


class ArmPoseAnalyzer:
    """
    ติดตามตำแหน่งแขนเพื่อตรวจ Arm Drift
    ใช้งาน: start_test() -> analyze(frame) วนหลายเฟรม -> get_result()
    """

    def __init__(self, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        self._pose = mp_pose.Pose(
            static_image_mode=False,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._test_start_time = None
        self._baseline_wrist_y = {}  # เก็บตำแหน่ง y เริ่มต้นของข้อมือแต่ละข้าง

    def start_test(self):
        """เริ่มจับเวลาการทดสอบยกแขนค้าง"""
        self._test_start_time = time.time()
        self._baseline_wrist_y = {}

    def analyze(self, frame_bgr):
        """
        รับภาพ (BGR) 1 เฟรมระหว่างช่วงทดสอบยกแขน
        คืนค่า dict เช่น:
        {
            "pose_found": bool,
            "elapsed_sec": float,
            "left_wrist_drift_px": float,
            "right_wrist_drift_px": float,
            "is_drift_suspected": bool,
            "test_complete": bool,
        }

        TODO (step ถัดไป):
        1. แปลง frame_bgr -> RGB แล้วส่งเข้า self._pose.process()
        2. ดึงพิกัด LEFT_WRIST / RIGHT_WRIST มาบันทึกเป็น baseline ในเฟรมแรก
        3. คำนวณ drift = ตำแหน่ง y ปัจจุบัน - baseline_y (ทุก ARM_DRIFT_CHECK_INTERVAL_SEC)
        4. เทียบกับ ARM_DRIFT_THRESHOLD_PX และเช็คว่าเวลาผ่าน ARM_HOLD_DURATION_SEC หรือยัง
        """
        raise NotImplementedError("จะ implement ใน step ถัดไป")

    def close(self):
        self._pose.close()
