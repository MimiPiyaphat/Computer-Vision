"""
main.py
=======
Entry point หลักของ StrokeVision AI
โครง flow การคัดกรองตามหลัก FAST: Face -> Arm -> (Speech, ไม่รวมใน scope นี้) -> Time

สถานะ: Face module (MediaPipe Face Mesh) และ Arm module (YOLOv8-Pose) implement แล้ว
คำสั่งขณะรัน:
  - 'r' เริ่ม/เริ่มใหม่ การทดสอบยกแขนค้าง (Arm Drift Test)
  - 'q' ออกจากโปรแกรม
"""

import sys

import cv2

from config import CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT, ARM_HOLD_DURATION_SEC
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

    arm_test_active = False
    arm_last_result = None

    print("[INFO] StrokeVision AI เริ่มทำงาน — กด 'r' เพื่อเริ่มทดสอบยกแขน, 'q' เพื่อออก")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARN] อ่านเฟรมจากกล้องไม่สำเร็จ")
                break

            frame = cv2.flip(frame, 1)  # mirror สำหรับ UX ที่เป็นธรรมชาติ
            fps = fps_counter.update()

            face_result = face_analyzer.analyze(frame)
            frame = face_analyzer.draw_debug(frame, face_result)

            cv2.putText(
                frame,
                f"FPS: {fps}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )

            if face_result["face_found"]:
                info_text = (
                    f"EAR L:{face_result['left_ear']} R:{face_result['right_ear']} "
                    f"| EarDiff:{face_result['ear_asymmetry']} "
                    f"| MouthDiff:{face_result['mouth_asymmetry']}"
                )
                cv2.putText(
                    frame, info_text, (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1,
                )

                if face_result["is_droop_suspected"]:
                    cv2.putText(
                        frame, "!! FACE DROOP SUSPECTED !!", (10, 95),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,
                    )
            else:
                cv2.putText(
                    frame, "No face detected", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 1,
                )

            # --- Arm Drift Test (YOLOv8-Pose) ---
            if arm_test_active:
                arm_last_result = arm_analyzer.analyze(frame)
                frame = arm_analyzer.draw_debug(frame)

                arm_text = (
                    f"Arm test: {arm_last_result['elapsed_sec']}s / {ARM_HOLD_DURATION_SEC}s "
                    f"| DriftL:{arm_last_result['left_wrist_drift_px']}px "
                    f"DriftR:{arm_last_result['right_wrist_drift_px']}px"
                )
                cv2.putText(
                    frame, arm_text, (10, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 1,
                )

                if arm_last_result["is_drift_suspected"]:
                    cv2.putText(
                        frame, "!! ARM DRIFT SUSPECTED !!", (10, 165),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,
                    )

                if arm_last_result["test_complete"]:
                    arm_test_active = False
                    print(f"[INFO] Arm test เสร็จสิ้น: {arm_last_result}")
            else:
                hint = "Arm test" + (" (last: drift detected)" if arm_last_result and arm_last_result["is_drift_suspected"] else "")
                cv2.putText(
                    frame, f"กด 'r' เพื่อเริ่มทดสอบยกแขนค้าง {ARM_HOLD_DURATION_SEC} วินาที", (10, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1,
                )

            cv2.putText(
                frame,
                "StrokeVision AI - Face (MediaPipe) + Arm (YOLOv8-Pose)",
                (10, FRAME_HEIGHT - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 200, 255),
                1,
            )

            cv2.imshow("StrokeVision AI", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("r"):
                arm_test_active = True
                arm_analyzer.start_test()
                print("[INFO] เริ่มทดสอบยกแขนค้าง...")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        face_analyzer.close()
        arm_analyzer.close()


if __name__ == "__main__":
    main()
