"""Writable local runtime paths for optional inference libraries."""

import os
from pathlib import Path


def configure_yolo_runtime():
    """Keep settings/cache in gitignored data; respect explicit user overrides."""
    path = Path(os.environ.get("YOLO_CONFIG_DIR") or
                Path(__file__).resolve().parents[1] / "data" / "ultralytics")
    path.mkdir(parents=True, exist_ok=True)
    if not os.environ.get("YOLO_CONFIG_DIR"):
        os.environ["YOLO_CONFIG_DIR"] = str(path)
    return path
