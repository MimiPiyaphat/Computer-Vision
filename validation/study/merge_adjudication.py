"""Merge independently adjudicated labels into exported feature pairs."""

import argparse
import csv
import json
from pathlib import Path


REQUIRED = {"pair_id", "adjudicator_a_label", "adjudicator_b_label", "final_label",
            "adjudication_status", "review_reference", "adjudicated_at_utc"}


def binary(value, field, pair_id):
    if value not in ("0", "1"):
        raise ValueError(f"{pair_id}: {field} must be 0 or 1.")
    return int(value)


def load_labels(path):
    labels = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError("Adjudication CSV columns do not match the template.")
        for row in reader:
            pair_id = row["pair_id"].strip()
            if not pair_id or pair_id in labels:
                raise ValueError("Adjudication pair_id must be nonempty and unique.")
            if row["adjudication_status"].strip().lower() != "finalized":
                raise ValueError(f"{pair_id}: adjudication_status must be finalized.")
            a = binary(row["adjudicator_a_label"].strip(), "adjudicator_a_label", pair_id)
            b = binary(row["adjudicator_b_label"].strip(), "adjudicator_b_label", pair_id)
            final = binary(row["final_label"].strip(), "final_label", pair_id)
            review = row["review_reference"].strip()
            timestamp = row["adjudicated_at_utc"].strip()
            if not timestamp:
                raise ValueError(f"{pair_id}: adjudicated_at_utc is required.")
            if a == b and final != a:
                raise ValueError(f"{pair_id}: final label conflicts with agreeing adjudicators.")
            if a != b and not review:
                raise ValueError(f"{pair_id}: disagreement requires review_reference.")
            labels[pair_id] = {"label": final, "adjudicator_a_label": a, "adjudicator_b_label": b,
                               "review_reference": review, "adjudicated_at_utc": timestamp}
    return labels


def merge(source, adjudication, output):
    labels = load_labels(adjudication)
    rows, seen = [], set()
    for number, line in enumerate(Path(source).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        pair_id = row.get("pair_id") if isinstance(row, dict) else None
        if not isinstance(pair_id, str) or not pair_id or pair_id in seen:
            raise ValueError(f"Line {number}: pair_id must be nonempty and unique.")
        if row.get("label") is not None:
            raise ValueError(f"Line {number}: refusing to overwrite an existing label.")
        if pair_id not in labels:
            raise ValueError(f"{pair_id}: missing finalized adjudication.")
        seen.add(pair_id)
        decision = labels[pair_id]
        row["label"] = decision["label"]
        row["adjudication"] = {key: decision[key] for key in decision if key != "label"}
        rows.append(row)
    extras = set(labels) - seen
    if extras:
        raise ValueError(f"Adjudication contains unknown pair_id: {sorted(extras)[0]}")
    if not rows:
        raise ValueError("No pairs found.")
    with Path(output).open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("adjudication")
    parser.add_argument("output")
    args = parser.parse_args()
    try:
        print(f"Merged {merge(args.source, args.adjudication, args.output)} adjudicated pairs.")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Adjudication merge failed: {exc}\n")
