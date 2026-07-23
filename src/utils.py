"""
utils.py
========
ฟังก์ชันช่วยเหลือทั่วไปที่ใช้ร่วมกันระหว่างโมดูล face_analytics และ arm_pose
"""

import math
import time


def euclidean_distance(point_a, point_b):
    """คำนวณระยะห่างแบบ Euclidean ระหว่างจุด 2 จุด (x, y)."""
    return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])


def calculate_ear(eye_landmarks):
    """
    คำนวณ Eye Aspect Ratio (EAR) จากจุด landmark ของดวงตา 6 จุด
    eye_landmarks: list ของ (x, y) จำนวน 6 จุด เรียงตามรูปแบบมาตรฐาน
        p1, p2, p3, p4, p5, p6 (p1, p4 คือหัว-หางตา, ที่เหลือคือขอบบน-ล่าง)
    """
    if len(eye_landmarks) != 6:
        raise ValueError("eye_landmarks ต้องมี 6 จุดเท่านั้น")

    vertical_1 = euclidean_distance(eye_landmarks[1], eye_landmarks[5])
    vertical_2 = euclidean_distance(eye_landmarks[2], eye_landmarks[4])
    horizontal = euclidean_distance(eye_landmarks[0], eye_landmarks[3])

    if horizontal == 0:
        return 0.0

    ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
    return ear


class FPSCounter:
    """ตัวช่วยวัด FPS แบบ real-time สำหรับ debug/แสดงผลบนหน้าจอ"""

    def __init__(self, smoothing=0.9):
        self._prev_time = None
        self._fps = 0.0
        self._smoothing = smoothing

    def update(self):
        now = time.time()
        if self._prev_time is not None:
            instant_fps = 1.0 / max(now - self._prev_time, 1e-6)
            self._fps = (self._smoothing * self._fps) + (1.0 - self._smoothing) * instant_fps
        self._prev_time = now
        return self._fps

    @property
    def fps(self):
        return round(self._fps, 1)
