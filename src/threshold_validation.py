"""Symptomatic-cohort threshold tuning and untouched subject-held-out evaluation."""

import hashlib
import json
import math
from pathlib import Path

from src.feature_store import validate_record
from src.features import SCHEMA, SCORE, delta_features
from src.protocol import check_setup
from src.research import load_parameters, assess_targets


def load_pairs(path):
    rows = []
    seen = set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"Line {number}: expected a JSON object.")
        if not isinstance(row.get("subject_key"), str) or not row["subject_key"].strip():
            raise ValueError(f"Line {number}: a pseudonymous subject_key is required.")
        pair_id = row.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id or pair_id in seen:
            raise ValueError(f"Line {number}: pair_id must be nonempty and unique.")
        seen.add(pair_id)
        if type(row.get("symptoms_reported")) is not bool or type(row.get("label")) is not int or row["label"] not in (0, 1):
            raise ValueError(f"Line {number}: provide symptoms_reported boolean and independently adjudicated label 0/1.")
        before, after = validate_record(row["before"]), validate_record(row["after"])
        if before["context"] != after["context"]:
            raise ValueError(f"Line {number}: pre/post model or capture context differs.")
        check_setup(before["setup"], after["setup"])
        score = delta_features(before["features"], after["features"])["score"]
        rows.append({"subject": row["subject_key"], "pair_id": pair_id, "symptomatic": row["symptoms_reported"],
                     "label": row["label"], "pipeline": before["context"]["pipeline"], "score": score})
    if not rows:
        raise ValueError("Dataset is empty.")
    return rows


def confusion(rows, threshold):
    tp = sum(row["label"] == 1 and row["score"] > threshold for row in rows)
    fn = sum(row["label"] == 1 and row["score"] <= threshold for row in rows)
    fp = sum(row["label"] == 0 and row["score"] > threshold for row in rows)
    tn = sum(row["label"] == 0 and row["score"] <= threshold for row in rows)
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "sensitivity": tp / (tp + fn) if tp + fn else None,
            "specificity": tn / (tn + fp) if tn + fp else None,
            "ppv": tp / (tp + fp) if tp + fp else None,
            "npv": tn / (tn + fn) if tn + fn else None}


def wilson(successes, total):
    if not total:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0, center - half), min(1, center + half)]


def validate_threshold(tuning, holdout, minimum_sensitivity):
    if not 0 < minimum_sensitivity <= 1:
        raise ValueError("Minimum sensitivity must be in (0, 1].")
    if {row["subject"] for row in tuning} & {row["subject"] for row in holdout}:
        raise ValueError("Subject leakage: tuning and holdout customers must be disjoint.")
    if {row["pair_id"] for row in tuning} & {row["pair_id"] for row in holdout}:
        raise ValueError("Pair leakage across tuning and holdout.")
    pipelines = {row["pipeline"] for row in tuning + holdout}
    if len(pipelines) != 1:
        raise ValueError("Use one exact feature/model pipeline per validation study.")
    tune = [row for row in tuning if row["symptomatic"]]
    test = [row for row in holdout if row["symptomatic"]]
    for name, rows in (("tuning", tune), ("holdout", test)):
        if {row["label"] for row in rows} != {0, 1}:
            raise ValueError(f"The symptomatic {name} cohort requires positive and negative adjudicated cases.")
    thresholds = sorted({value for row in tune for value in (row["score"], math.nextafter(row["score"], -math.inf))})
    roc = [{"threshold": value, **confusion(tune, value)} for value in thresholds]
    for point in roc:
        point.update(tpr=point["sensitivity"], fpr=1 - point["specificity"])
    coordinates = sorted({(point["fpr"], point["tpr"]) for point in roc})
    auc = sum((x2 - x1) * (y1 + y2) / 2 for (x1, y1), (x2, y2) in zip(coordinates, coordinates[1:]))
    eligible = [point for point in roc if point["threshold"] > 0 and point["sensitivity"] >= minimum_sensitivity]
    if not eligible:
        raise ValueError("No positive cutoff meets the specified tuning sensitivity. Collect/review data; do not invent a threshold.")
    chosen = max(eligible, key=lambda point: (point["specificity"], point["sensitivity"], point["threshold"]))
    metrics = confusion(test, chosen["threshold"])
    metrics["sensitivity_95ci"] = wilson(metrics["tp"], metrics["tp"] + metrics["fn"])
    metrics["specificity_95ci"] = wilson(metrics["tn"], metrics["tn"] + metrics["fp"])
    return {
        "schema": SCHEMA, "score_definition": SCORE, "pipeline": next(iter(pipelines)),
        "cohort": "self_reported_symptoms", "deployment_approved": False,
        "threshold": chosen["threshold"], "minimum_tuning_sensitivity": minimum_sensitivity,
        "tuning": {"n": len(tune), "subjects": len({r["subject"] for r in tune}), "roc": roc, "auc": auc, "selected": chosen},
        "holdout": {"n": len(test), "subjects": len({r["subject"] for r in test}), **metrics},
        "holdout_counts": {"positive": metrics["tp"] + metrics["fn"], "negative": metrics["tn"] + metrics["fp"]},
        "holdout_meets_point_sensitivity_target": metrics["sensitivity"] >= minimum_sensitivity,
        "project_performance_targets": assess_targets(metrics, load_parameters()["targets"], "overall"),
        "asymptomatic_excluded_from_tuning": sum(not row["symptomatic"] for row in tuning),
        "asymptomatic_holdout_separate": confusion([row for row in holdout if not row["symptomatic"]], chosen["threshold"]),
        "limitations": ["Research report, not clinical validation or deployment approval.",
                        "Wilson intervals assume independent observations; use a prespecified subject-clustered analysis for repeated visits.",
                        "Labels must be independently clinically adjudicated, not derived from this model or symptom checkbox.",
                        "Delta performance in symptomatic customers does not validate use in asymptomatic customers.",
                        "Use prospective external validation and clinical review before enabling a deployment threshold."]}


def write_report(tune_path, holdout_path, output, minimum_sensitivity):
    report = validate_threshold(load_pairs(tune_path), load_pairs(holdout_path), minimum_sensitivity)
    report["input_sha256"] = {"tuning": hashlib.sha256(Path(tune_path).read_bytes()).hexdigest(),
                              "holdout": hashlib.sha256(Path(holdout_path).read_bytes()).hexdigest()}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report_text = json.dumps(report, indent=2, allow_nan=False)
    output.write_text(report_text, encoding="utf-8")
    candidate = {key: report[key] for key in ("schema", "score_definition", "pipeline", "cohort", "threshold", "holdout_counts")}
    candidate.update(deployment_approved=False, clinical_review_reference="", policy_id="",
                     validation_report_sha256=hashlib.sha256(report_text.encode()).hexdigest())
    output.with_name(output.stem + "-candidate.json").write_text(json.dumps(candidate, indent=2), encoding="utf-8")
    return report
