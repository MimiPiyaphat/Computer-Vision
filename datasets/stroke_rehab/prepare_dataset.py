"""Create a reproducible 30 x 5-second subset from downloaded source videos."""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import random
import tempfile
from pathlib import Path

import cv2


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_group(path: Path, root: Path) -> tuple[str, str, str]:
    parts = path.relative_to(root).parts
    if len(parts) != 4 or parts[1] not in ("Complete", "Incomplete") or parts[2] not in ("Train", "Test"):
        raise ValueError(f"Expected exercise/Complete|Incomplete/Train|Test/video: {path}")
    return parts[0], parts[2], parts[1].lower()


def select_sources(sources, root: Path, count: int, seed: int = 42):
    """Seeded round-robin over exercise/split/status; retain source provenance."""
    if count <= 0 or len(sources) < count:
        raise ValueError(f"Need {count} videos (positive count); found {len(sources)}")
    buckets = {}
    for source in sorted(sources):
        buckets.setdefault(source_group(source, root), []).append(source)
    rng = random.Random(seed)
    for bucket in buckets.values():
        rng.shuffle(bucket)
    selected = []
    while len(selected) < count:
        for key in sorted(buckets):
            if buckets[key] and len(selected) < count:
                selected.append(buckets[key].pop())
    return selected


def make_clip(source: Path, destination: Path) -> dict[str, object]:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"Cannot open video: {source}")
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    except (ValueError, OverflowError) as exc:
        capture.release()
        raise RuntimeError(f"Invalid video metadata: {source}") from exc
    if not math.isfinite(fps) or fps <= 0 or frame_count <= 0 or width <= 0 or height <= 0:
        capture.release()
        raise RuntimeError(f"Invalid video metadata: {source}")

    target_frames = round(fps * 5.0)
    if frame_count < target_frames:
        capture.release()
        raise RuntimeError(f"Video is shorter than 5 seconds: {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(destination),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        writer.release()
        raise RuntimeError(f"Cannot create output video: {destination}")

    written = 0
    try:
        while written < target_frames:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"Video ended before 5 seconds: {source}")
            writer.write(frame)
            written += 1
    finally:
        capture.release()
        writer.release()

    return {
        "fps": round(float(fps), 3),
        "frames": written,
        "width": width,
        "height": height,
        "duration_seconds": round(written / fps, 6),
    }


def prepare(source_root: Path, output: Path, count: int = 30, seed: int = 42):
    source_root, output = source_root.resolve(), output.resolve()
    if output.exists():
        raise ValueError("Output already exists; choose a new directory to preserve the existing dataset.")
    if output.is_relative_to(source_root) or source_root.is_relative_to(output):
        raise ValueError("Source and output directories must not contain each other.")
    sources = sorted(
        path for path in source_root.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )
    selected = select_sources(sources, source_root, count, seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Publish only a complete set. Failed encodes never leave a partial dataset
    # at the requested destination, and existing output is never overwritten.
    with tempfile.TemporaryDirectory(prefix=".clips-", dir=output.parent) as temporary:
        staging = Path(temporary) / "clips"
        staging.mkdir()
        rows = []
        for index, source in enumerate(selected, start=1):
            exercise, split, label = source_group(source, source_root)
            clip_name = f"clip_{index:03d}.mp4"
            destination = staging / clip_name
            info = make_clip(source, destination)
            rows.append({
                "clip_id": f"clip_{index:03d}", "file": clip_name,
                "exercise": exercise, "label": label, "source_split": split,
                "subject_key": source.stem.split("_")[0], "selection_seed": seed,
                "source_type": "volunteer_rehabilitation",
                "source_file": source.relative_to(source_root).as_posix(),
                "license": "CC BY 4.0", **info, "sha256": sha256(destination),
            })
        with (staging / "metadata.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        with (staging / "checksums.sha256").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(f"{row['sha256']}  {row['file']}\n")
        staging.rename(output)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        rows = prepare(args.source, args.output, args.count, args.seed)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(2, f"Dataset preparation failed: {exc}\n")
    print(f"Prepared {len(rows)} clips in {args.output}")


if __name__ == "__main__":
    main()
