"""Run the rehabilitation exercise classifier on one local video."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from train_classifier import VideoNet, sample_video


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    args = parser.parse_args()

    checkpoint = torch.load(args.model, map_location="cpu", weights_only=True)
    model = VideoNet()
    model.load_state_dict(checkpoint["model"])
    model.eval()
    video = sample_video(args.video, checkpoint["frames"], checkpoint["size"])
    video = video.float().div_(255.0).unsqueeze(0)
    with torch.no_grad():
        exercise_logits, status_logits = model(video)
        exercise_prob = exercise_logits.softmax(1)[0]
        status_prob = status_logits.softmax(1)[0]
    result = {
        "video": str(args.video),
        "exercise": checkpoint["classes"][exercise_prob.argmax().item()],
        "exercise_confidence": round(exercise_prob.max().item(), 6),
        "status": checkpoint["statuses"][status_prob.argmax().item()],
        "status_confidence": round(status_prob.max().item(), 6),
        "warning": "Volunteer rehabilitation classifier; not a stroke diagnosis.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
