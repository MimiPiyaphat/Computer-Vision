"""
arm_pose.py
===========
โมดูลตรวจจับแขนอ่อนแรง (A - Arm) ตามหลัก FAST
ให้ผู้ใช้ยกแขนค้างไว้ตามเวลาที่กำหนด (config.ARM_HOLD_DURATION_SEC)
แล้วติดตามตำแหน่งข้อมือ (wrist) ว่ามีอาการ "แขนตก" (Arm Drift) หรือไม่

สถานะ: IMPLEMENTED — ใช้ YOLOv8-Pose (ultralytics) เป็น backend
โมเดล yolov8n-pose.pt จะถูกดาวน์โหลดอัตโนมัติจาก ultralytics ในการรันครั้งแรก
(ต้องมีอินเทอร์เน็ตตอนรันครั้งแรกเท่านั้น หลังจากนั้นแคชไว้ในเครื่อง)
"""

import time

from ultralytics import YOLO

from config import (
    ARM_DRIFT_THRESHOLD_PX,
    ARM_HOLD_DURATION_SEC,
    YOLO_POSE_MODEL,
    YOLO_CONF_THRESHOLD,
)

# COCO keypoint index ที่ YOLOv8-Pose ใช้ (17 จุดมาตรฐาน)
# อ้างอิง: https://docs.ultralytics.com/tasks/pose/
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_ELBOW = 7
RIGHT_ELBOW = 8
LEFT_WRIST = 9
RIGHT_WRIST = 10


class ArmPoseAnalyzer:
    """
    ติดตามตำแหน่งแขนด้วย YOLOv8-Pose เพื่อตรวจ Arm Drift
    ใช้งาน: start_test() -> analyze(frame) วนหลายเฟรมระหว่างทดสอบ
    """

    def __init__(self, model_path=YOLO_POSE_MODEL, conf_threshold=YOLO_CONF_THRESHOLD):
        self._model = YOLO(model_path)
        self._conf_threshold = conf_threshold
        self._test_start_time = None
        self._baseline_wrist_y = {}  # {"left": y_px, "right": y_px}
        self._last_yolo_results = None

    def start_test(self):
        """เริ่มจับเวลาการทดสอบยกแขนค้าง และล้าง baseline เดิม"""
        self._test_start_time = time.time()
        self._baseline_wrist_y = {}

    @staticmethod
    def _empty_result(elapsed_sec=0.0, test_complete=False):
        return {
            "pose_found": False,
            "elapsed_sec": round(elapsed_sec, 1),
            "left_wrist_drift_px": 0.0,
            "right_wrist_drift_px": 0.0,
            "is_drift_suspected": False,
            "test_complete": test_complete,
        }

    def analyze(self, frame_bgr):
        """
        รับภาพ (BGR) 1 เฟรมระหว่างช่วงทดสอบยกแขน (ต้องเรียก start_test() ก่อน)
        คืนค่า dict:
        {
            "pose_found": bool,
            "elapsed_sec": float,
            "left_wrist_drift_px": float,   # ระยะที่ข้อมือซ้ายขยับลงจาก baseline (พิกเซล)
            "right_wrist_drift_px": float,
            "is_drift_suspected": bool,     # true ถ้าข้างใดข้างหนึ่งขยับลงเกิน threshold
            "test_complete": bool,          # true เมื่อครบเวลา ARM_HOLD_DURATION_SEC
        }
        """
        if self._test_start_time is None:
            raise RuntimeError("ต้องเรียก start_test() ก่อนเริ่ม analyze()")

        elapsed = time.time() - self._test_start_time
        test_complete = elapsed >= ARM_HOLD_DURATION_SEC

        results = self._model.predict(
            frame_bgr, conf=self._conf_threshold, verbose=False
        )
        self._last_yolo_results = results

        if not results or results[0].keypoints is None or len(results[0].keypoints) == 0:
            return self._empty_result(elapsed_sec=elapsed, test_complete=test_complete)

        # ใช้คนแรกที่ตรวจพบ (สมมติมีผู้ทดสอบคนเดียวหน้ากล้อง)
        keypoints = results[0].keypoints.xy[0]  # tensor shape (17, 2)
        conf_scores = results[0].keypoints.conf
        confs = conf_scores[0] if conf_scores is not None else None

        def _get_point(idx):
            if confs is not None and confs[idx] < self._conf_threshold:
                return None
            x, y = keypoints[idx]
            x, y = float(x), float(y)
            if x == 0.0 and y == 0.0:
                return None
            return (x, y)

        left_wrist = _get_point(LEFT_WRIST)
        right_wrist = _get_point(RIGHT_WRIST)

        if left_wrist is None and right_wrist is None:
            return self._empty_result(elapsed_sec=elapsed, test_complete=test_complete)

        # บันทึก baseline ในเฟรมแรกที่เจอข้อมือแต่ละข้าง
        if left_wrist is not None and "left" not in self._baseline_wrist_y:
            self._baseline_wrist_y["left"] = left_wrist[1]
        if right_wrist is not None and "right" not in self._baseline_wrist_y:
            self._baseline_wrist_y["right"] = right_wrist[1]

        left_drift = 0.0
        right_drift = 0.0
        if left_wrist is not None and "left" in self._baseline_wrist_y:
            # y เพิ่มขึ้น = แขนตกลง (แกน y ของภาพนับจากบนลงล่าง)
            left_drift = max(0.0, left_wrist[1] - self._baseline_wrist_y["left"])
        if right_wrist is not None and "right" in self._baseline_wrist_y:
            right_drift = max(0.0, right_wrist[1] - self._baseline_wrist_y["right"])

        is_drift_suspected = (
            left_drift > ARM_DRIFT_THRESHOLD_PX or right_drift > ARM_DRIFT_THRESHOLD_PX
        )

        return {
            "pose_found": True,
            "elapsed_sec": round(elapsed, 1),
            "left_wrist_drift_px": round(left_drift, 1),
            "right_wrist_drift_px": round(right_drift, 1),
            "is_drift_suspected": is_drift_suspected,
            "test_complete": test_complete,
        }

    def draw_debug(self, frame_bgr):
        """วาด skeleton ที่ YOLOv8-Pose ตรวจพบล่าสุด (ใช้ ultralytics .plot() ในตัว)"""
        if self._last_yolo_results is None:
            return frame_bgr
        return self._last_yolo_results[0].plot(img=frame_bgr)

    def close(self):
        # YOLO (ultralytics) ไม่มี handle ที่ต้องปิดแบบ MediaPipe
        pass
