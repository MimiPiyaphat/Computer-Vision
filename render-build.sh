#!/usr/bin/env bash
set -euo pipefail

python -m pip install -r requirements.txt

# MediaPipe declares the GUI-enabled contrib wheel. The hosted service has no
# display server, so replace all OpenCV variants with one compatible headless
# wheel after dependency resolution.
python -m pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless || true
python -m pip install --no-deps --force-reinstall opencv-contrib-python-headless==4.10.0.84

python prepare_web_models.py
