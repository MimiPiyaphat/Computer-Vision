"""Train a compact video classifier for the downloaded rehabilitation dataset.

This predicts exercise identity and complete/incomplete execution. It is not a
stroke diagnosis model and must not be used as one.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

import cv2
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset


CLASSES = ["1_Lifting an Object", "2_Extending the Elbow", "3_Lifting the Wrist", "4_Opening the Hand"]
STATUSES = ["Complete", "Incomplete"]


def read_records(root: Path, split: str) -> list[tuple[Path, int, int]]:
    records = []
    for exercise_id, exercise in enumerate(CLASSES):
        for status_id, status in enumerate(STATUSES):
            folder = root / exercise / status / split
            for path in sorted(folder.glob("*.mp4")):
                records.append((path, exercise_id, status_id))
    return records


def limit_records(records, limit: int):
    if limit <= 0 or len(records) <= limit:
        return records
    buckets = {}
    for record in records:
        buckets.setdefault((record[1], record[2]), []).append(record)
    selected = []
    while len(selected) < limit:
        progressed = False
        for bucket in buckets.values():
            if bucket and len(selected) < limit:
                selected.append(bucket.pop(0))
                progressed = True
        if not progressed:
            break
    return selected


def subject_key(record):
    match = re.fullmatch(r"(\d+)_\d+_\d+_\d+", record[0].stem)
    if match is None:
        raise ValueError(f"Missing dataset subject prefix in filename: {record[0].name}")
    return match[1]


def split_training(records, fraction=.2, seed=42):
    """Hold out whole people from Train; Test never selects a checkpoint."""
    if not 0 < fraction < 1:
        raise ValueError("validation-fraction must be between 0 and 1")
    subjects = sorted({subject_key(record) for record in records})
    if len(subjects) < 2:
        raise ValueError("Need at least two training subjects for validation")
    random.Random(seed).shuffle(subjects)
    count = min(len(subjects) - 1, max(1, round(len(subjects) * fraction)))
    validation_subjects = set(subjects[:count])
    train = [record for record in records if subject_key(record) not in validation_subjects]
    validation = [record for record in records if subject_key(record) in validation_subjects]
    expected = {(exercise, status) for _, exercise, status in records}
    for name, subset in (("training", train), ("validation", validation)):
        if {(exercise, status) for _, exercise, status in subset} != expected:
            raise ValueError(f"{name} subjects do not cover all exercise/status groups; review the split")
    return train, validation


def sample_video(path: Path, frames: int, size: int) -> torch.Tensor:
    if frames < 1 or size < 1:
        raise ValueError("frames and size must be positive")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Cannot open {path}")
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total < 1:
            raise RuntimeError(f"Invalid frame count: {path}")
        indices = [round(i * (total - 1) / (frames - 1)) if frames > 1 else 0 for i in range(frames)]
        wanted, decoded = set(indices), {}
        for index in range(max(indices) + 1):
            if not cap.grab():
                break
            if index not in wanted:
                continue
            ok, frame = cap.retrieve()
            if not ok:
                break
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (size, size), interpolation=cv2.INTER_AREA)
            decoded[index] = torch.from_numpy(frame).permute(2, 0, 1).to(torch.uint8)
        if wanted - decoded.keys():
            raise RuntimeError(f"Could not decode all requested frames from {path}")
        # Preserve uniform sample indices for short clips, including repeats.
        return torch.stack([decoded[index] for index in indices])
    finally:
        cap.release()


class RehabDataset(Dataset):
    def __init__(self, records, frames: int, size: int, cache: Path | None = None):
        self.records = records
        self.frames = frames
        self.size = size
        signature = [(str(path.resolve()), path.stat().st_size, path.stat().st_mtime_ns, exercise, status)
                     for path, exercise, status in records]
        if cache and cache.exists():
            saved = torch.load(cache, map_location="cpu", weights_only=True)
            if (saved.get("signature") == signature and saved.get("frames") == frames and saved.get("size") == size
                    and saved.get("sampling") == "uniform-index-v2"):
                self.videos = saved["videos"]
                print(f"loaded_cache={cache}", flush=True)
                return
        videos = []
        for index, (path, _, _) in enumerate(records, start=1):
            videos.append(sample_video(path, frames, size))
            if index % 50 == 0 or index == len(records):
                print(f"decoded={index}/{len(records)}", flush=True)
        self.videos = torch.stack(videos)
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"signature": signature, "frames": frames, "size": size,
                        "sampling": "uniform-index-v2", "videos": self.videos}, cache)
            print(f"saved_cache={cache}", flush=True)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        _, exercise, status = self.records[index]
        return self.videos[index].float().div_(255.0), exercise, status


class VideoNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(3, 8, 5, stride=2, padding=2), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(8, 16, 3, stride=2, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, stride=2, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d(1),
        )
        self.shared = nn.Sequential(nn.Linear(96, 64), nn.ReLU(), nn.Dropout(0.25))
        self.exercise = nn.Linear(64, len(CLASSES))
        self.status = nn.Linear(64, len(STATUSES))

    def forward(self, video):
        batch, time, channels, height, width = video.shape
        features = self.encoder(video.reshape(batch * time, channels, height, width))
        features = features.reshape(batch, time, -1)
        temporal_mean = features.mean(dim=1)
        temporal_std = features.std(dim=1, unbiased=False)
        temporal_change = (features[:, -1] - features[:, 0]).abs()
        features = torch.cat((temporal_mean, temporal_std, temporal_change), dim=1)
        features = self.shared(features)
        return self.exercise(features), self.status(features)


def accuracy(logits, target):
    return (logits.argmax(1) == target).float().mean().item()


def evaluate(model, loader, device):
    model.eval()
    total = 0
    correct_exercise = 0.0
    correct_status = 0.0
    exercise_matrix = torch.zeros(len(CLASSES), len(CLASSES), dtype=torch.int64)
    status_matrix = torch.zeros(len(STATUSES), len(STATUSES), dtype=torch.int64)
    with torch.no_grad():
        for video, exercise, status in loader:
            exercise, status = exercise.to(device), status.to(device)
            ex_logits, st_logits = model(video.to(device))
            batch = len(exercise)
            total += batch
            correct_exercise += accuracy(ex_logits, exercise) * batch
            correct_status += accuracy(st_logits, status) * batch
            for labels, logits, matrix in ((exercise, ex_logits, exercise_matrix), (status, st_logits, status_matrix)):
                for actual, predicted in zip(labels.cpu().tolist(), logits.argmax(1).cpu().tolist()):
                    matrix[actual, predicted] += 1
    return {"exercise_accuracy": correct_exercise / max(total, 1), "status_accuracy": correct_status / max(total, 1),
            "samples": total, "exercise_confusion_matrix": exercise_matrix.tolist(),
            "status_confusion_matrix": status_matrix.tolist()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("models/stroke_rehab_classifier.pt"))
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--frames", type=int, default=6)
    parser.add_argument("--size", type=int, default=48)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validation-fraction", type=float, default=.2)
    parser.add_argument("--max-train", type=int, default=0)
    parser.add_argument("--max-test", type=int, default=0)
    parser.add_argument("--cache-dir", type=Path, default=Path("datasets/stroke_rehab/cache"))
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.frames < 1 or args.size < 32:
        parser.error("epochs, batch-size and frames must be positive; size must be at least 32")
    if args.output.exists() or args.output.with_suffix(".metrics.json").exists():
        parser.error("Output already exists; choose a new checkpoint path")
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(2)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_records = read_records(args.root, "Train")
    test_records = read_records(args.root, "Test")
    if not train_records or not test_records:
        raise SystemExit("Expected Train and Test folders with MP4 files")
    try:
        if {subject_key(r) for r in train_records} & {subject_key(r) for r in test_records}:
            raise ValueError("Subject leakage between source Train and Test")
        train_records, validation_records = split_training(train_records, args.validation_fraction, args.seed)
    except ValueError as exc:
        parser.error(str(exc))
    train_records = limit_records(train_records, args.max_train)
    test_records = limit_records(test_records, args.max_test)
    cache_tag = f"f{args.frames}_s{args.size}_tr{len(train_records)}_te{len(test_records)}"
    train_data = RehabDataset(train_records, args.frames, args.size, args.cache_dir / f"train_{cache_tag}.pt")
    validation_data = RehabDataset(validation_records, args.frames, args.size, args.cache_dir / f"validation_{cache_tag}.pt")
    test_data = RehabDataset(test_records, args.frames, args.size, args.cache_dir / f"test_{cache_tag}.pt")
    train_loader = DataLoader(train_data, batch_size=args.batch_size, shuffle=True, num_workers=0)
    validation_loader = DataLoader(validation_data, batch_size=args.batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_data, batch_size=args.batch_size, shuffle=False, num_workers=0)
    model = VideoNet().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()
    history = []
    best_status = -1.0
    best_epoch = 0
    best_state = None
    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        for video, exercise, status in train_loader:
            exercise, status = exercise.to(device), status.to(device)
            ex_logits, st_logits = model(video.to(device))
            loss = criterion(ex_logits, exercise) + criterion(st_logits, status)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
        metrics = evaluate(model, validation_loader, device)
        metrics["split"] = "validation"
        metrics.update({"epoch": epoch, "train_loss": running_loss / max(len(train_loader), 1)})
        history.append(metrics)
        if metrics["status_accuracy"] > best_status:
            best_status = metrics["status_accuracy"]
            best_epoch = epoch
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        print(json.dumps(metrics), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    model.load_state_dict(best_state)
    test_metrics = evaluate(model, test_loader, device)
    torch.save({"model": best_state, "classes": CLASSES, "statuses": STATUSES, "frames": args.frames, "size": args.size,
                "best_epoch": best_epoch, "validation_status_accuracy": best_status,
                "test_status_accuracy": test_metrics["status_accuracy"]}, args.output)
    report = args.output.with_suffix(".metrics.json")
    report.write_text(json.dumps({"device": str(device), "train_samples": len(train_records), "test_samples": len(test_records),
                                  "validation_samples": len(validation_records), "seed": args.seed,
                                  "subjects": {name: sorted({subject_key(r) for r in rows}) for name, rows in
                                               (("train", train_records), ("validation", validation_records), ("test", test_records))},
                                  "best_epoch": best_epoch, "selection_metric": "validation_status_accuracy",
                                  "best_validation_status_accuracy": best_status, "test": test_metrics, "history": history,
                                  "warning": "Volunteer rehabilitation dataset; not a clinical stroke diagnosis model."}, indent=2), encoding="utf-8")
    print(f"saved={args.output}")
    print(f"metrics={report}")


if __name__ == "__main__":
    main()
