"""
config.py
=========
ค่าคงที่และการตั้งค่าที่ใช้ร่วมกันทั้งโปรเจกต์ StrokeVision AI
ปรับค่า threshold ต่าง ๆ ที่นี่ที่เดียว ไม่ต้องไปแก้กระจายในแต่ละโมดูล
"""

# ---------------------------------------------------------
# Camera settings
# ---------------------------------------------------------
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
TARGET_FPS = 30

# ---------------------------------------------------------
# Face Analytics (F - Face)
# ---------------------------------------------------------
# Eye Aspect Ratio (EAR) threshold สำหรับตรวจ ptosis / eyelid drooping
EAR_THRESHOLD = 0.21
EAR_ASYMMETRY_THRESHOLD = 0.05  # ความต่างของ EAR ซ้าย-ขวาที่ถือว่าผิดปกติ

# Facial symmetry: ความต่างของมุมปาก/ปีกจมูก (normalized distance)
MOUTH_ASYMMETRY_THRESHOLD = 0.03

# ---------------------------------------------------------
# Arm Pose Estimation (A - Arm) — YOLOv8-Pose
# ---------------------------------------------------------
YOLO_POSE_MODEL = "yolov8n-pose.pt"  # nano รุ่นเบาสุด เหมาะ CPU realtime; โหลดอัตโนมัติครั้งแรกที่รัน
YOLO_CONF_THRESHOLD = 0.5
ARM_HOLD_DURATION_SEC = 10          # เวลาที่ให้ผู้ใช้ยกแขนค้าง
ARM_DRIFT_THRESHOLD_PX = 40         # ระยะที่ข้อมือขยับลงถือว่า "แขนตก"
ARM_DRIFT_CHECK_INTERVAL_SEC = 1.0  # ความถี่ในการเช็คตำแหน่งแขน

# ---------------------------------------------------------
# Screening flow (S & T)
# ---------------------------------------------------------
STEP_ORDER = ["smile", "blink", "raise_arm"]
COUNTDOWN_SEC = 3

# ---------------------------------------------------------
# Logging / Output
# ---------------------------------------------------------
LOG_DIR = "logs"
SAVE_SCREENING_RESULT = True
