"""Labels and stage metadata: edit copy here without touching CV code."""

from config import ARM_HOLD_DURATION_SEC, EYE_TEST_DURATION_SEC, EYE_CLOSURE_HOLD_SEC, EXPRESSION_HOLD_SEC, NEUTRAL_CAPTURE_SEC

STEPS = [
    ("quality_gate", "ตรวจสอบกล้อง", "มองตรงไปที่กล้อง ให้แสงบนใบหน้าสม่ำเสมอ", 0),
    ("neutral_capture", "ใบหน้าผ่อนคลาย", "ผ่อนคลายใบหน้าและมองตรงไปข้างหน้า", NEUTRAL_CAPTURE_SEC),
    ("mouth_test", "ยิ้ม", "ยิ้มให้กว้างเท่าที่ทำได้แล้วค้างไว้", EXPRESSION_HOLD_SEC),
    ("eye_closure", "หลับตา", "หลับตาทั้งสองข้างเบา ๆ แล้วค้างไว้", EYE_CLOSURE_HOLD_SEC),
    ("eye_test", "กะพริบตา", "กะพริบตาทั้งสองข้างตามธรรมชาติหลายครั้ง", EYE_TEST_DURATION_SEC),
    ("arm_test", "ยกแขน", "ยกแขนทั้งสองข้างขึ้นแล้วค้างไว้ต่อเนื่อง 3 วินาที ภายในเวลาที่กำหนด", ARM_HOLD_DURATION_SEC),
    ("summary", "สรุปผล", "ดูผลสรุปเบื้องต้นจากการเก็บข้อมูล", 0),
]
