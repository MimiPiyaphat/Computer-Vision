"""Central configuration for StrokeVision AI.

These values are screening heuristics, not clinically validated diagnostic
thresholds. Keep calibration values in this file so they can be adjusted
without changing the application logic.
"""

# Camera
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Face Mesh: 468 landmarks + 10 iris landmarks for IPD (2026-09-11).
MIN_FACE_DETECTION_CONFIDENCE = 0.5
QUALITY_MAX_BRIGHTNESS_DIFF = 40.0

# Face-expression and blink screening
NEUTRAL_CAPTURE_SEC = 2.0
EXPRESSION_HOLD_SEC = 5.0
EYE_TEST_DURATION_SEC = 6.0
EYE_CLOSURE_HOLD_SEC = 3.0
BLINK_TARGET_COUNT = 2
EYE_CLOSED_RATIO = 0.70

# Arm-pose screening
YOLO_POSE_MODEL = "yolov8n-pose.pt"
YOLO_CONF_THRESHOLD = 0.5
YOLO_DEVICE = "cpu"
YOLO_IMAGE_SIZE = 640
ARM_KEYPOINT_CONF_THRESHOLD = 0.3
ARM_HOLD_DURATION_SEC = 10.0
ARM_INITIAL_CHECK_SEC = 2.0
# Minimum resolvable attempted lift; an acquisition-quality floor, not a drift score.
ARM_INITIAL_LIFT_MIN_PX = 15.0
# Functional arm check used by the customer workflow. The timer advances only
# while both shoulders and wrists are visible and the body remains in position.
# These are project-demo rules, not clinically validated medical thresholds.
ARM_REQUIRED_RAISED_HOLD_SEC = 3.0
ARM_RAISED_WRIST_MAX_SHOULDER_SPANS = 0.35

# No clinical delta cutoff is supplied by default.
FEATURE_STORE_DIR = "data/features"
DELTA_POLICY_PATH = "validation/deployment_threshold.json"
CAPTURE_STATION_ID = "station-01"  # Fixed physical camera/seat/floor markers.
BASELINE_MAX_AGE_HOURS = 12
HEAD_POSE_MAX_DEGREES = 18.0
# Experimental one-to-one identity verification, not liveness detection.
IDENTITY_COSINE_THRESHOLD = 0.6
IDENTITY_MODEL_PATH = "models/20180402-114759-vggface2.pt"
IDENTITY_CPU_THREADS = 2
# Engineering acquisition checks, NOT clinically validated alert thresholds.
SETUP_TOLERANCES = {
    "body_roll": 8.0, "body_scale": 0.05, "body_x": 0.08, "body_y": 0.08,
}
