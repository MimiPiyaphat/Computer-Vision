"""Evaluate the actual fixed research OR-rule on labeled symptomatic pairs."""

import argparse
import hashlib
import json
from pathlib import Path

from src.feature_store import validate_record
from src.protocol import check_setup
from src.research import load_parameters, compare_research, assess_targets
from src.yfp_benchmark import prediction_metrics


def evaluate(path, parameters=None):
    parameters = parameters or load_parameters()
    predictions, seen, excluded = [], set(), 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("Expected paired JSON records.")
        for key in ("pair_id", "subject_key"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError(f"Missing {key}.")
        if row["pair_id"] in seen:
            raise ValueError("Duplicate pair ID.")
        seen.add(row["pair_id"])
        if type(row.get("label")) is not int or row["label"] not in (0, 1) or type(row.get("symptoms_reported")) is not bool:
            raise ValueError("Explicit adjudicated 0/1 outcome and boolean symptom report are required.")
        if not row["symptoms_reported"]:
            excluded += 1
            continue
        prediction, status, error = None, "inconclusive", ""
        try:
            before, after = validate_record(row["before"]), validate_record(row["after"])
            if before["context"] != after["context"] or not before["context"]["pipeline"].endswith("-research-sideways-arms-v1"):
                raise ValueError("Capture context does not match the research arm protocol.")
            check_setup(before["setup"], after["setup"])
            result = compare_research(before["features"], after["features"], before.get("research_angles", {}),
                                      after.get("research_angles", {}), parameters)
            status = result["status"]
            if status != "research_incomplete":
                prediction = result["alert"]
        except (ValueError, KeyError, TypeError) as exc:
            error = str(exc)
        predictions.append({"pair_id": row["pair_id"], "subject_key": row["subject_key"], "label": row["label"],
                            "prediction": prediction, "status": status, "error": error})
    if not predictions:
        raise ValueError("No labeled symptomatic pairs are available.")
    metrics = prediction_metrics(predictions)
    return {"task": "fixed research face-delta OR projected-arm-angle-delta rule", "clinical_validation": False,
            "deployment_approved": False, "parameters": parameters, "input_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "subjects": len({row["subject_key"] for row in predictions}), "asymptomatic_excluded": excluded,
            "metrics": metrics, "project_targets": assess_targets(metrics["failure_adjusted_worst_case"], parameters["targets"], "overall"),
            "predictions": predictions,
            "limitations": ["Use prespecified rules on an independently adjudicated held-out cohort; this command never tunes them.",
                            "Both outcome classes and an adequate prospective study are needed to characterize system performance.",
                            "Intervals assume independent pairs; repeated-person inference requires clustered analysis.",
                            "False-negative/false-positive penalties include unavailable measurements; successful-case-only accuracy is shown separately."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pairs")
    parser.add_argument("--output", required=True)
    parser.add_argument("--check-project-targets", action="store_true")
    args = parser.parse_args()
    try:
        report = evaluate(args.pairs)
        Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Research evaluation failed: {exc}\n")
    print("Overall research-rule sensitivity target: " + report["project_targets"]["status"])
    if args.check_project_targets and report["project_targets"]["status"] != "met_on_this_sample":
        parser.exit(3)


if __name__ == "__main__":
    main()
