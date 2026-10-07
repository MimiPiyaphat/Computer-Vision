"""Create deterministic subject-disjoint tuning and holdout JSONL files."""

import argparse
import json
import random
from pathlib import Path


def write_new(path, rows):
    with Path(path).open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")


def split(source, tuning_output, holdout_output, holdout_fraction=0.2, seed=20261006):
    if not 0 < holdout_fraction < 1:
        raise ValueError("holdout_fraction must be between 0 and 1.")
    rows, pair_ids = [], set()
    for number, line in enumerate(Path(source).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        subject, pair_id, label = row.get("subject_key"), row.get("pair_id"), row.get("label")
        if not isinstance(subject, str) or not subject or not isinstance(pair_id, str) or not pair_id:
            raise ValueError(f"Line {number}: subject_key and pair_id are required.")
        if pair_id in pair_ids or type(label) is not int or label not in (0, 1):
            raise ValueError(f"Line {number}: unique pair_id and final label 0/1 are required.")
        pair_ids.add(pair_id)
        rows.append(row)
    subjects = sorted({row["subject_key"] for row in rows})
    if len(subjects) < 4:
        raise ValueError("At least four subjects are required for a meaningful split check.")
    random.Random(seed).shuffle(subjects)
    holdout_count = max(1, round(len(subjects) * holdout_fraction))
    holdout_subjects = set(subjects[:holdout_count])
    tuning = [row for row in rows if row["subject_key"] not in holdout_subjects]
    holdout = [row for row in rows if row["subject_key"] in holdout_subjects]
    for name, cohort in (("tuning", tuning), ("holdout", holdout)):
        symptomatic = [row for row in cohort if row.get("symptoms_reported") is True]
        if {row["label"] for row in symptomatic} != {0, 1}:
            raise ValueError(f"Symptomatic {name} split needs both labels; change seed or collect more subjects.")
    write_new(tuning_output, tuning)
    try:
        write_new(holdout_output, holdout)
    except Exception:
        Path(tuning_output).unlink(missing_ok=True)
        raise
    return {"tuning_pairs": len(tuning), "tuning_subjects": len(set(subjects) - holdout_subjects),
            "holdout_pairs": len(holdout), "holdout_subjects": len(holdout_subjects), "seed": seed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("tuning_output")
    parser.add_argument("holdout_output")
    parser.add_argument("--holdout-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20261006)
    args = parser.parse_args()
    try:
        print(json.dumps(split(args.source, args.tuning_output, args.holdout_output,
                               args.holdout_fraction, args.seed), indent=2))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Dataset split failed: {exc}\n")
