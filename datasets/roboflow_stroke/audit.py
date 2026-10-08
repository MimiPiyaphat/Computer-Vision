"""Audit the downloaded Roboflow YOLO dataset before any training run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


SPLITS = ("train", "valid", "test")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def source_name(path: Path) -> str:
    """Return the original filename before Roboflow's content hash."""
    return re.sub(r"\.rf\.[0-9a-f]{32}$", "", path.stem, flags=re.IGNORECASE)


def source_family(path: Path) -> str:
    """Group related captures while retaining a human-readable family name."""
    name = re.sub(r"[-_ ]?\d+$", "", source_name(path)).strip("-_ ")
    match = re.match(r"[A-Za-z]+", name)
    return (match.group(0) if match else name or source_name(path)).lower()


def _parse_yaml(path: Path) -> dict:
    """Parse the small Roboflow data.yaml without adding a PyYAML dependency."""
    result: dict[str, object] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        if key == "nc":
            result[key] = int(value)
        elif key == "names":
            result[key] = [item.strip(" '\"") for item in value.strip("[]").split(",")]
        elif key in {"train", "val", "test"}:
            result[key] = value
    return result


def audit_dataset(root: str | Path) -> dict:
    root = Path(root).resolve()
    yaml_path = root / "data.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Missing dataset config: {yaml_path}")
    config = _parse_yaml(yaml_path)
    names = list(config.get("names", []))
    nc = int(config.get("nc", len(names)))
    if len(names) != nc:
        raise ValueError("data.yaml nc does not match names")

    issues: list[str] = []
    split_reports: dict[str, dict] = {}
    hash_splits: dict[str, set[str]] = defaultdict(set)
    family_splits: dict[str, set[str]] = defaultdict(set)
    dimensions: Counter[str] = Counter()
    total_class_instances = Counter()

    for split in SPLITS:
        image_dir, label_dir = root / split / "images", root / split / "labels"
        images = sorted(p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
        labels = sorted(label_dir.glob("*.txt"))
        image_stems, label_stems = {p.stem for p in images}, {p.stem for p in labels}
        missing_labels = sorted(image_stems - label_stems)
        orphan_labels = sorted(label_stems - image_stems)
        class_instances = Counter()
        family_counts = Counter()
        family_class_instances: dict[str, Counter] = defaultdict(Counter)
        boxes = 0
        empty_labels = 0

        for image in images:
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            hash_splits[digest].add(split)
            family = source_family(image)
            family_splits[family].add(split)
            family_counts[family] += 1
            try:
                with Image.open(image) as loaded:
                    dimensions[f"{loaded.width}x{loaded.height}"] += 1
            except OSError as exc:
                issues.append(f"Unreadable image {image.name}: {exc}")

            label_path = label_dir / f"{image.stem}.txt"
            if not label_path.exists():
                continue
            rows = [row.strip() for row in label_path.read_text(encoding="utf-8-sig").splitlines() if row.strip()]
            if not rows:
                empty_labels += 1
            for line_number, row in enumerate(rows, 1):
                fields = row.split()
                if len(fields) != 5:
                    issues.append(f"{label_path.name}:{line_number} expected 5 YOLO values")
                    continue
                try:
                    class_id = int(fields[0])
                    coords = [float(value) for value in fields[1:]]
                except ValueError:
                    issues.append(f"{label_path.name}:{line_number} contains a non-numeric value")
                    continue
                if not 0 <= class_id < nc:
                    issues.append(f"{label_path.name}:{line_number} class {class_id} is outside 0..{nc - 1}")
                if any(value < 0 or value > 1 for value in coords) or coords[2] <= 0 or coords[3] <= 0:
                    issues.append(f"{label_path.name}:{line_number} has invalid normalized box coordinates")
                class_instances[class_id] += 1
                family_class_instances[family][class_id] += 1
                total_class_instances[class_id] += 1
                boxes += 1

        if missing_labels:
            issues.append(f"{split}: {len(missing_labels)} images have no label file")
        if orphan_labels:
            issues.append(f"{split}: {len(orphan_labels)} labels have no image")
        split_reports[split] = {
            "images": len(images),
            "labels": len(labels),
            "boxes": boxes,
            "empty_labels": empty_labels,
            "missing_labels": len(missing_labels),
            "orphan_labels": len(orphan_labels),
            "class_instances": {names[i]: class_instances[i] for i in range(nc)},
            "source_families": dict(family_counts.most_common()),
            "source_family_class_instances": {
                family: {names[i]: counts[i] for i in range(nc)}
                for family, counts in sorted(family_class_instances.items())
            },
        }

    duplicate_hashes = {digest: sorted(splits) for digest, splits in hash_splits.items() if len(splits) > 1}
    overlapping_families = {name: sorted(splits) for name, splits in family_splits.items() if len(splits) > 1}
    return {
        "schema": "roboflow-stroke-audit-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_root": str(root),
        "source": "Roboflow Universe air-a2axo/stroke-2-0-lu7ua version 3",
        "license": "CC BY 4.0",
        "task": "YOLO object detection",
        "names": names,
        "splits": split_reports,
        "total_images": sum(row["images"] for row in split_reports.values()),
        "total_boxes": sum(row["boxes"] for row in split_reports.values()),
        "class_instances": {names[i]: total_class_instances[i] for i in range(nc)},
        "exact_duplicate_hashes_across_splits": duplicate_hashes,
        "source_families_across_splits": overlapping_families,
        "unique_image_dimensions": len(dimensions),
        "most_common_dimensions": dict(dimensions.most_common(20)),
        "issues": issues,
        "limitations": [
            "ภาพไม่ใช่ข้อมูลคู่ก่อนและหลังนวด และไม่มีผลวินิจฉัยทางคลินิกกำกับ",
            "แต่ละคลาสมาจากกลุ่มภาพที่มีรูปแบบต่างกันอย่างชัดเจน จึงเสี่ยงเรียนรู้แหล่งที่มาของภาพแทนอาการ",
            "source family เดียวกันปรากฏข้าม train/valid/test ทำให้คะแนนทดสอบอาจสูงเกินจริง",
            "โมเดลนี้เป็นงานทดลอง object detection สำหรับหน้า dev และไม่ใช้ตัดสินผลลูกค้า",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_dataset(args.root)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
