"""Export unlabeled numeric pairs for independent clinical adjudication."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from src.feature_store import validate_record


def export_pairs(database, output):
    # Read-only connection; a typo must not silently create an empty database.
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        rows = db.execute("SELECT r.id, r.subject, b.record, r.record, r.comparison FROM rechecks r JOIN baselines b ON r.subject=b.subject AND r.visit=b.visit ORDER BY r.id").fetchall()
    with Path(output).open("x", encoding="utf-8") as stream:
        for key, subject, before, after, comparison_json in rows:
            comparison = json.loads(comparison_json)
            # Records written before routine post-massage tracking was added
            # came exclusively from the symptom-gated workflow.
            symptoms_reported = comparison.get("symptoms_reported", True)
            if type(symptoms_reported) is not bool:
                raise ValueError("Stored comparison has an invalid symptoms_reported value.")
            row = {"pair_id": f"{subject}:{key}", "subject_key": subject, "symptoms_reported": symptoms_reported, "label": None,
                   "before": validate_record(json.loads(before)), "after": validate_record(json.loads(after))}
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument("output")
    args = parser.parse_args()
    print(f"Exported {export_pairs(args.database, args.output)} unlabeled pairs; no raw IDs or media.")
