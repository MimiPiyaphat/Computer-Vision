"""
main.py
=======
Entry point หลักของ StrokeVision AI
โครง flow การคัดกรองตามหลัก FAST: Face -> Arm -> (Speech, ไม่รวมใน scope นี้) -> Time

สถานะ: SKELETON — เดินลูปกล้องได้ และเรียกใช้โมดูลต่าง ๆ ได้
        แต่ logic การวิเคราะห์จริงยัง raise NotImplementedError
        (จะ implement ทีละโมดูลใน step ถัดไป)
"""

import sys

import cv2

from config import CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT
from src.face_analytics import FaceAnalyzer
from src.arm_pose import ArmPoseAnalyzer
from src.utils import FPSCounter


def main():
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    if not cap.isOpened():
        print("[ERROR] ไม่สามารถเปิดกล้องได้ ตรวจสอบ CAMERA_INDEX ใน config.py")
        sys.exit(1)

    face_analyzer = FaceAnalyzer()
    arm_analyzer = ArmPoseAnalyzer()
    fps_counter = FPSCounter()

    print("[INFO] StrokeVision AI เริ่มทำงาน — กด 'q' เพื่อออก")
    print("[INFO] โมดูลวิเคราะห์ยังเป็น skeleton — เฟรมจะแสดงผลได้ปกติ")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARN] อ่านเฟรมจากกล้องไม่สำเร็จ")
                break

            frame = cv2.flip(frame, 1)  # mirror สำหรับ UX ที่เป็นธรรมชาติ
            fps = fps_counter.update()

            cv2.putText(
                frame,
                f"FPS: {fps}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )
            cv2.putText(
                frame,
                "StrokeVision AI - setup OK (analysis modules pending)",
                (10, FRAME_HEIGHT - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 200, 255),
                1,
            )

            cv2.imshow("StrokeVision AI", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        face_analyzer.close()
        arm_analyzer.close()


if __name__ == "__main__":
    main()
