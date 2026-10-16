"""Download and validate the model assets needed by the hosted web service."""

from config import YOLO_POSE_MODEL
from prepare_identity_model import main as prepare_identity_model


def main():
    prepare_identity_model()

    from ultralytics import YOLO

    model = YOLO(YOLO_POSE_MODEL)
    model.model.cpu()
    print("Pose model ready:", YOLO_POSE_MODEL)


if __name__ == "__main__":
    main()
