"""Offline single-video facial-asymmetry benchmark; not a paired stroke test."""

import hashlib
import json
import math
from pathlib import Path

from src.research import load_parameters, assess_targets
from src.threshold_validation import confusion, wilson

BENCHMARK_SCHEMA = "facemesh478-ipd-ratios-single-video-q90-v2"


def load_manifest(path, root):
    root = Path(root).resolve()
    rows, ids, splits = [], set(), {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("Manifest rows must be JSON objects.")
        for key in ("sample_id", "subject_key", "path"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"Manifest requires {key}.")
        if row["sample_id"] in ids:
            raise ValueError("Duplicate sample ID.")
        ids.add(row["sample_id"])
        if row.get("source") not in ("yfp", "control") or row.get("kind") not in ("video", "image_sequence"):
            raise ValueError("Use source yfp/control and kind video/image_sequence.")
        if type(row.get("label")) is not int or row["label"] not in (0, 1):
            raise ValueError("Explicit independently reviewed video labels 0/1 are required; region intensity is not a binary label.")
        if row["source"] == "yfp" and row["label"] == 0:
            raise ValueError("Do not invent healthy controls from unannotated YFP frames; supply independently reviewed control videos.")
        if row.get("split") not in ("tuning", "holdout", "lopo"):
            raise ValueError("Manifest split must be tuning, holdout or lopo.")
        subject = row["subject_key"]
        if subject in splits and splits[subject] != row["split"]:
            raise ValueError("The same person cannot appear in different splits.")
        splits[subject] = row["split"]
        relative = Path(row["path"])
        if relative.is_absolute() or relative.drive:
            raise ValueError("Dataset paths must be relative to the authorized data root.")
        resolved = (root / relative).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("Dataset paths must remain within the authorized data root.")
        rows.append({**row, "resolved": resolved})
    if not rows:
        raise ValueError("Manifest is empty.")
    return rows


def sample_frames(path, kind, cv):
    if kind == "image_sequence":
        if not path.is_dir():
            raise ValueError("Image-sequence directory is missing.")
        images = sorted(p for p in path.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"))
        if not images:
            raise ValueError("Image sequence contains no supported frames.")
        for image in images:
            yield cv.imread(str(image))
        return
    cap = cv.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError("Video could not be opened.")
        fps = cap.get(cv.CAP_PROP_FPS)
        expected_frames = cap.get(cv.CAP_PROP_FRAME_COUNT)
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("Video FPS is unavailable; export a reviewed 6 FPS image sequence.")
        index, next_sample = 0, 0.0
        while True:
            ok, frame = cap.read()
            if not ok:
                if math.isfinite(expected_frames) and expected_frames > 0 and index < expected_frames - 1:
                    raise ValueError("Video decoding stopped before the declared end.")
                break
            if index >= next_sample:
                yield frame
                next_sample += max(1.0, fps / 6.0)
            index += 1
    finally:
        cap.release()


def extract(manifest, root, output):
    # Lazy imports keep report generation usable without native vision packages.
    import cv2
    import mediapipe
    from src.face_analytics import FaceAnalyzer
    rows = load_manifest(manifest, root)
    code_root = Path(__file__).resolve().parent
    assets = [code_root / "features.py", code_root / "face_analytics.py", Path(__file__),
              Path(mediapipe.__file__).parent / "modules/face_landmark/face_landmark.tflite"]
    signature = hashlib.sha256(b"".join(path.read_bytes() for path in assets) + mediapipe.__version__.encode()).hexdigest()
    records = []
    for row in rows:
        scores, sampled, invalid, error = [], 0, 0, ""
        analyzer = FaceAnalyzer()  # Reset temporal tracking between people/clips.
        try:
            for frame in sample_frames(row["resolved"], row["kind"], cv2):
                sampled += 1
                values = None if frame is None else analyzer._observe(cv2.flip(frame, 1))
                if values is None:
                    invalid += 1
                    continue
                scores.append(max(values[k] for k in ("mouth_ratio", "brow_ratio", "eyelid_ratio")))
        except (ValueError, OSError, cv2.error) as exc:
            error = str(exc)
        finally:
            analyzer.close()
        enough_coverage = sampled > 0 and len(scores) / sampled >= .5
        score = sorted(scores)[math.ceil(.9 * len(scores)) - 1] if len(scores) >= 3 and enough_coverage and not error else None
        record = {k: row[k] for k in ("sample_id", "subject_key", "source", "label", "split")}
        record.update(schema=BENCHMARK_SCHEMA, pipeline=signature, score=score,
                      sampled_frames=sampled, valid_frames=len(scores), rejected_frames=invalid,
                      extraction_error=error or ("Insufficient valid frames or less than 50% coverage" if score is None else ""))
        records.append(record)
    with Path(output).open("x", encoding="utf-8") as stream:
        for row in records:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    return records


def load_scores(path):
    rows, ids, splits = [], set(), {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or row.get("schema") != BENCHMARK_SCHEMA:
            raise ValueError("Not a single-video facial-asymmetry benchmark score file.")
        for key in ("sample_id", "subject_key", "pipeline"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"Missing {key}.")
        if row["sample_id"] in ids:
            raise ValueError("Duplicate sample ID.")
        ids.add(row["sample_id"])
        if row.get("split") not in ("tuning", "holdout", "lopo"):
            raise ValueError("Unknown split.")
        subject = row["subject_key"]
        if subject in splits and splits[subject] != row["split"]:
            raise ValueError("Subject leakage between splits.")
        splits[subject] = row["split"]
        if type(row.get("label")) is not int or row["label"] not in (0, 1):
            raise ValueError("Explicit binary labels are required.")
        if row.get("source") not in ("yfp", "control") or (row["source"] == "yfp" and row["label"] == 0):
            raise ValueError("Invalid cohort labeling.")
        score = row.get("score")
        if score is not None and (type(score) not in (int, float) or not math.isfinite(score) or score < 0):
            raise ValueError("Scores must be finite, nonnegative numbers or null for failures.")
        rows.append(row)
    if not rows or len({row["pipeline"] for row in rows}) != 1:
        raise ValueError("A nonempty dataset from one extraction pipeline is required.")
    return rows


def choose_threshold(rows, targets):
    valid = [row for row in rows if row["score"] is not None]
    if {row["label"] for row in valid} != {0, 1}:
        return None, "both_training_classes_required", []
    thresholds = sorted({v for row in valid for v in (row["score"], math.nextafter(row["score"], -math.inf)) if v >= 0})
    roc = [{"threshold": t, **confusion(valid, t)} for t in thresholds]
    for point in roc:
        point.update(tpr=point["sensitivity"], fpr=1 - point["specificity"])
    feasible = [p for p in roc if p["sensitivity"] >= targets["face_sensitivity"] and p["specificity"] >= targets["face_specificity"]]
    if feasible:
        chosen = max(feasible, key=lambda p: (p["specificity"], p["sensitivity"], p["threshold"]))
        return chosen["threshold"], "both_targets_met_on_tuning", roc
    # A best-available operating point is reported as a failed target, never
    # relabeled as successful tuning. The holdout still remains untouched.
    sensitive = [p for p in roc if p["sensitivity"] >= targets["face_sensitivity"]]
    chosen = max(sensitive or roc, key=lambda p: (p["specificity"] if sensitive else p["sensitivity"], p["threshold"]))
    return chosen["threshold"], "tuning_targets_not_met", roc


def prediction_metrics(predictions):
    valid = [{"label": row["label"], "score": int(row["prediction"])} for row in predictions if row["prediction"] is not None]
    metrics = confusion(valid, .5)
    failures = [row for row in predictions if row["prediction"] is None]
    worst = {key: metrics[key] for key in ("tp", "tn", "fp", "fn")}
    worst["fn"] += sum(row["label"] == 1 for row in failures)
    worst["fp"] += sum(row["label"] == 0 for row in failures)
    positives, negatives = worst["tp"] + worst["fn"], worst["tn"] + worst["fp"]
    worst.update(sensitivity=worst["tp"] / positives if positives else None,
                 specificity=worst["tn"] / negatives if negatives else None,
                 sensitivity_95ci=wilson(worst["tp"], positives), specificity_95ci=wilson(worst["tn"], negatives))
    return {"evaluable_only": metrics, "failure_adjusted_worst_case": worst,
            "samples": len(predictions), "failures": len(failures),
            "coverage": len(valid) / len(predictions) if predictions else 0}


def benchmark(rows, mode, fixed_threshold=.1, parameters=None):
    parameters = parameters or load_parameters()
    targets = parameters["targets"]
    folds, predictions = [], []
    if not rows:
        raise ValueError("No benchmark rows supplied.")
    if mode == "fixed":
        if not math.isfinite(fixed_threshold) or fixed_threshold < 0:
            raise ValueError("Invalid fixed threshold.")
        groups = [("fixed-placeholder", [], rows)]
    elif mode == "holdout":
        training = [r for r in rows if r["split"] == "tuning"]
        testing = [r for r in rows if r["split"] == "holdout"]
        if not training or not testing or len(training) + len(testing) != len(rows):
            raise ValueError("Holdout mode needs only tuning and holdout records, both nonempty.")
        if {r["subject_key"] for r in training} & {r["subject_key"] for r in testing}:
            raise ValueError("Subject leakage between tuning and holdout.")
        groups = [("heldout", training, testing)]
    elif mode == "lopo":
        if any(r["split"] != "lopo" for r in rows):
            raise ValueError("LOPO mode requires split=lopo for every sample.")
        subjects = sorted({row["subject_key"] for row in rows})
        if len(subjects) < 2:
            raise ValueError("LOPO requires at least two people.")
        groups = [(subject, [r for r in rows if r["subject_key"] != subject],
                   [r for r in rows if r["subject_key"] == subject]) for subject in subjects]
    else:
        raise ValueError("Unknown benchmark mode.")
    for name, training, testing in groups:
        threshold, status, roc = (fixed_threshold, "fixed_unfitted_placeholder", []) if mode == "fixed" else choose_threshold(training, targets)
        folds.append({"fold": name, "threshold": threshold, "tuning_status": status, "roc": roc,
                      "training_subjects": len({r["subject_key"] for r in training}), "testing_samples": len(testing)})
        for row in testing:
            prediction = None if threshold is None or row["score"] is None else row["score"] > threshold
            predictions.append({"sample_id": row["sample_id"], "subject_key": row["subject_key"],
                                "label": row["label"], "prediction": prediction})
    metrics = prediction_metrics(predictions)
    return {"schema": BENCHMARK_SCHEMA, "task": "single-video facial asymmetry, NOT stroke or pre/post change",
            "mode": mode, "deployment_approved": False, "subjects": len({r["subject_key"] for r in rows}),
            "source_counts": {source: sum(row["source"] == source for row in rows) for source in ("yfp", "control")},
            "metrics": metrics, "targets": assess_targets(metrics["failure_adjusted_worst_case"], targets, "face"),
            "folds": folds, "predictions": predictions,
            "overall_stroke_sensitivity": None,
            "limitations": ["YFP-only positives cannot estimate healthy-control specificity.",
                            "Single-video thresholds must not be loaded as pre/post delta thresholds.",
                            "All clips from a person are held out together; published patient counts are inconsistent, so verify author metadata.",
                            "95% intervals treat clips as independent; repeated-person clinical inference requires clustered analysis.",
                            "Failure-adjusted results count every unavailable positive as a miss and every unavailable negative as a false alarm."]}
