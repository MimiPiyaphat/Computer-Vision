"""Create a blinded adjudication CSV from exported unlabeled feature pairs."""

import argparse
import csv
import json
from pathlib import Path


FIELDS = ("pair_id", "adjudicator_a_label", "adjudicator_b_label", "final_label",
          "adjudication_status", "review_reference", "adjudicated_at_utc")


def prepare(source, output):
    pair_ids, seen = [], set()
    for number, line in enumerate(Path(source).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        pair_id = row.get("pair_id") if isinstance(row, dict) else None
        if not isinstance(pair_id, str) or not pair_id or pair_id in seen:
            raise ValueError(f"Line {number}: pair_id must be nonempty and unique.")
        if row.get("label") is not None:
            raise ValueError(f"Line {number}: input must remain unlabeled.")
        seen.add(pair_id)
        pair_ids.append(pair_id)
    if not pair_ids:
        raise ValueError("No exported pairs found.")
    with Path(output).open("x", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for pair_id in pair_ids:
            writer.writerow({"pair_id": pair_id, "adjudication_status": "pending"})
    return len(pair_ids)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()
    try:
        print(f"Prepared {prepare(args.source, args.output)} adjudication rows.")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Adjudication preparation failed: {exc}\n")
