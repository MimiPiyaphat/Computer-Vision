import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest


STUDY = Path(__file__).resolve().parents[1] / "validation" / "study"
sys.path.insert(0, str(STUDY))

from merge_adjudication import merge
from prepare_adjudication import prepare
from split_labeled_pairs import split


class StudyDatasetTests(unittest.TestCase):
    def test_prepare_and_merge_finalized_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "unlabeled.jsonl"
            sheet = root / "adjudication.csv"
            output = root / "labeled.jsonl"
            source.write_text(json.dumps({"pair_id": "pair-1", "subject_key": "subject-1",
                                          "symptoms_reported": True, "label": None}) + "\n", encoding="utf-8")
            self.assertEqual(prepare(source, sheet), 1)
            with sheet.open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.DictWriter(stream, fieldnames=("pair_id", "adjudicator_a_label",
                    "adjudicator_b_label", "final_label", "adjudication_status",
                    "review_reference", "adjudicated_at_utc"))
                writer.writeheader()
                writer.writerow({"pair_id": "pair-1", "adjudicator_a_label": "1",
                    "adjudicator_b_label": "1", "final_label": "1",
                    "adjudication_status": "finalized", "review_reference": "",
                    "adjudicated_at_utc": "2026-10-06T12:00:00Z"})
            self.assertEqual(merge(source, sheet, output), 1)
            row = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(row["label"], 1)
            self.assertNotIn("subject_key", row["adjudication"])

    def test_disagreement_requires_review_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "unlabeled.jsonl"
            sheet = root / "adjudication.csv"
            source.write_text(json.dumps({"pair_id": "pair-1", "label": None}) + "\n", encoding="utf-8")
            sheet.write_text("pair_id,adjudicator_a_label,adjudicator_b_label,final_label,adjudication_status,review_reference,adjudicated_at_utc\n"
                             "pair-1,0,1,1,finalized,,2026-10-06T12:00:00Z\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "disagreement"):
                merge(source, sheet, root / "labeled.jsonl")

    def test_split_is_subject_disjoint_and_keeps_both_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "labeled.jsonl"
            rows = []
            for subject in range(4):
                for label in (0, 1):
                    rows.append({"pair_id": f"p-{subject}-{label}", "subject_key": f"s-{subject}",
                                 "symptoms_reported": True, "label": label})
            source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            tuning, holdout = root / "tuning.jsonl", root / "holdout.jsonl"
            report = split(source, tuning, holdout, holdout_fraction=0.5, seed=7)
            tune_rows = [json.loads(line) for line in tuning.read_text(encoding="utf-8").splitlines()]
            hold_rows = [json.loads(line) for line in holdout.read_text(encoding="utf-8").splitlines()]
            self.assertFalse({r["subject_key"] for r in tune_rows} & {r["subject_key"] for r in hold_rows})
            self.assertEqual({r["label"] for r in tune_rows}, {0, 1})
            self.assertEqual({r["label"] for r in hold_rows}, {0, 1})
            self.assertEqual(report["tuning_subjects"], 2)
            self.assertEqual(report["holdout_subjects"], 2)


if __name__ == "__main__":
    unittest.main()
