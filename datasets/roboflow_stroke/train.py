"""Train a developer-only YOLO detector and export a reproducible report."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from datasets.roboflow_stroke.audit import audit_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = PROJECT_ROOT / "data/roboflow-stroke/v3-yolov8"
DEFAULT_RUNS = PROJECT_ROOT / "data/roboflow-stroke/runs"
DEFAULT_MODEL = PROJECT_ROOT / "models/roboflow_stroke_yolov8n.pt"
DEFAULT_REPORT = PROJECT_ROOT / "models/roboflow_stroke_yolov8n.metrics.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _absolute_yaml(dataset: Path, run_dir: Path) -> Path:
    path = run_dir / "data.local.yaml"
    original = (dataset / "data.yaml").read_text(encoding="utf-8-sig").splitlines()
    kept = [line for line in original if not line.strip().startswith(("train:", "val:", "test:"))]
    prefix = [
        f"path: {dataset.as_posix()}",
        "train: train/images",
        "val: valid/images",
        "test: test/images",
    ]
    path.write_text("\n".join(prefix + kept) + "\n", encoding="utf-8")
    return path


def _number(value) -> float:
    return float(value.item() if hasattr(value, "item") else value)


def train(args: argparse.Namespace) -> dict:
    from ultralytics import YOLO

    dataset = args.dataset.resolve()
    args.runs = args.runs.resolve()
    args.model_output = args.model_output.resolve()
    args.report = args.report.resolve()
    audit = audit_dataset(dataset)
    if audit["issues"]:
        raise ValueError("Dataset audit failed:\n" + "\n".join(audit["issues"]))

    args.runs.mkdir(parents=True, exist_ok=True)
    run_dir = args.runs / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    data_yaml = _absolute_yaml(dataset, run_dir)
    model = YOLO(args.base_model)
    train_result = model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        patience=args.patience,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=0,
        seed=args.seed,
        deterministic=True,
        project=str(args.runs),
        name=args.name,
        exist_ok=True,
        cache=False,
        freeze=args.freeze,
        plots=True,
        verbose=True,
    )
    save_dir = Path(train_result.save_dir)
    best = save_dir / "weights/best.pt"
    if not best.exists():
        raise FileNotFoundError(f"Training did not produce {best}")

    evaluated = YOLO(str(best)).val(
        data=str(data_yaml), split="test", imgsz=args.imgsz, batch=args.batch,
        device=args.device, workers=0, plots=True, project=str(args.runs),
        name=f"{args.name}-test", exist_ok=True, verbose=True,
    )
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, args.model_output)

    names = [evaluated.names[index] for index in sorted(evaluated.names)]
    precision = list(evaluated.box.p)
    recall = list(evaluated.box.r)
    f1 = list(evaluated.box.f1)
    ap50 = list(evaluated.box.ap50)
    maps = list(evaluated.box.maps)
    support = audit["splits"]["test"]["class_instances"]
    raw_matrix = evaluated.confusion_matrix.matrix.tolist()
    # Ultralytics stores rows=predicted, columns=actual; the UI convention is the transpose.
    matrix = [list(row) for row in zip(*raw_matrix)]
    labels = names + ["background"]
    results_csv = save_dir / "results.csv"
    epochs_completed = 0
    if results_csv.exists():
        epochs_completed = max(0, len(results_csv.read_text(encoding="utf-8").splitlines()) - 1)
    per_class = []
    for index, name in enumerate(names):
        per_class.append({
            "label": name,
            "precision": _number(precision[index]),
            "recall": _number(recall[index]),
            "f1": _number(f1[index]),
            "ap50": _number(ap50[index]),
            "map50_95": _number(maps[index]),
            "support": int(support[name]),
        })

    report = {
        "schema": "roboflow-object-detection-report-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "developer-only research; disconnected from customer decisions",
        "dataset": {
            "source": audit["source"],
            "license": audit["license"],
            "total_images": audit["total_images"],
            "splits": {key: audit["splits"][key]["images"] for key in ("train", "valid", "test")},
            "class_instances": audit["class_instances"],
        },
        "model": {
            "architecture": "YOLOv8n object detector",
            "base_model": args.base_model,
            "model_file": str(args.model_output.relative_to(PROJECT_ROOT)
                              if args.model_output.is_relative_to(PROJECT_ROOT)
                              else args.model_output),
            "sha256": _sha256(args.model_output),
        },
        "training": {
            "epochs_requested": args.epochs,
            "epochs_completed": epochs_completed,
            "patience": args.patience,
            "image_size": args.imgsz,
            "batch": args.batch,
            "device": str(args.device),
            "seed": args.seed,
            "frozen_layers": args.freeze,
            "run_directory": str(save_dir),
        },
        "test": {
            "labels": labels,
            "matrix_axes": "rows=actual, columns=predicted; background included",
            "confusion_matrix": matrix,
            "precision": _number(evaluated.box.mp),
            "recall": _number(evaluated.box.mr),
            "map50": _number(evaluated.box.map50),
            "map50_95": _number(evaluated.box.map),
            "per_class": per_class,
        },
        "audit": {
            "issues": audit["issues"],
            "exact_duplicate_hashes_across_splits": len(audit["exact_duplicate_hashes_across_splits"]),
            "overlapping_source_families": sorted(audit["source_families_across_splits"]),
        },
        "limitations": audit["limitations"],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--name", default="yolov8n-v3")
    parser.add_argument("--base-model", default="yolov8n.pt")
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--freeze", type=int, default=10,
                        help="Freeze the first N layers for faster CPU fine-tuning")
    args = parser.parse_args()
    report = train(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
