"""Download and validate the model assets needed by the hosted web service."""

from config import YOLO_POSE_MODEL, IDENTITY_BACKEND
from prepare_identity_model import main as prepare_identity_model


def main():
    if IDENTITY_BACKEND == "facenet":
        prepare_identity_model()
    else:
        print("Skipping FaceNet weights; hosted identity backend:", IDENTITY_BACKEND)

    from ultralytics import YOLO

    model = YOLO(YOLO_POSE_MODEL)
    model.model.cpu()
    print("Pose model ready:", YOLO_POSE_MODEL)


if __name__ == "__main__":
    main()
