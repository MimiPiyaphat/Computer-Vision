"""Reproducible synthetic demonstration. Contains no YFP or clinical results."""

import argparse
import json
from pathlib import Path
from src.features import FEATURE_KEYS
from src.research import load_parameters, compare_research


def run_demo():
    parameters = load_parameters()
    base = dict.fromkeys(FEATURE_KEYS, 0.0)
    before_angles = {"left_projected_drift_deg": 0.0, "right_projected_drift_deg": 0.0}
    examples = []
    for name, face, arm, expected in (
        ("below provisional rules", parameters["face_delta_threshold"] / 2, parameters["arm_angle_delta_threshold_deg"] / 2, False),
        ("face rule exceeded", parameters["face_delta_threshold"] + .01, 0, True),
        ("arm rule exceeded", 0, parameters["arm_angle_delta_threshold_deg"] + 1, True),
        ("exactly at arm rule", 0, parameters["arm_angle_delta_threshold_deg"], False),
    ):
        result = compare_research(base, dict(base, neutral_mouth_ratio=face), before_angles,
                                  dict(before_angles, left_projected_drift_deg=arm), parameters)
        if result["alert"] != expected:
            raise AssertionError("Demonstration rule regression: " + name)
        examples.append({"scenario": name, "synthetic": True, "expected_alert": expected, "result": result})
    return {"data_source": "hand-authored synthetic software fixtures", "clinical_validation": False,
            "yfp_evaluated": False, "measured_sensitivity": None, "measured_specificity": None,
            "research_parameters": parameters, "scenarios": examples}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="validation/research-demo.json")
    args = parser.parse_args()
    report = run_demo()
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Four synthetic rule scenarios passed. Demo saved to {args.output}.")
    print("No clinical or YFP performance has been measured.")
