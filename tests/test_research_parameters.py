"""Research-mode engineering tests. No test fixture is clinical/YFP evidence."""

import json
import math
from pathlib import Path
import tempfile
import unittest

from src.features import FEATURE_KEYS, SCHEMA, SETUP_KEYS
from src.feature_store import FeatureStore, validate_record
from src.projected_arm_angle import ProjectedArmAngle
from src.protocol import load_policy
from src.research import load_parameters, compare_research, assess_targets
from src.visit_workflow import VisitWorkflow
from src.yfp_benchmark import (BENCHMARK_SCHEMA, load_manifest, load_scores,
                               benchmark, choose_threshold, prediction_metrics)
from research_demo import run_demo
from evaluate_research_pairs import evaluate


def vector():
    return dict.fromkeys(FEATURE_KEYS, 0.0)


def angles(value=0):
    return {"left_projected_drift_deg": value, "right_projected_drift_deg": 0.0}


def context():
    return {"pipeline": "test-research-pipeline", "camera": 0, "width": 640, "height": 480, "station": "test"}


def rows():
    return [{"schema": BENCHMARK_SCHEMA, "pipeline": "test", "sample_id": f"sample-{i}",
             "subject_key": f"subject-{i}", "split": "lopo", "source": "yfp" if label else "control",
             "label": label, "score": score}
            for i, (label, score) in enumerate(((0, .01), (0, .03), (1, .2), (1, .3)))]


class ResearchRuleTests(unittest.TestCase):
    def test_actual_or_rule_evaluator_checks_floor_and_counts_failed_acquisition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pairs.jsonl"
            before = {"schema": SCHEMA, "features": vector(), "setup": dict.fromkeys(SETUP_KEYS, 0),
                      "context": dict(context(), pipeline="test-research-sideways-arms-v1"), "research_angles": angles()}
            samples = []
            for index, label, post_angle in ((0, 1, 33), (1, 1, None), (2, 0, 0)):
                after = dict(before, research_angles={} if post_angle is None else angles(post_angle))
                samples.append({"pair_id": str(index), "subject_key": str(index), "symptoms_reported": True,
                                "label": label, "before": before, "after": after})
            path.write_text("\n".join(json.dumps(row) for row in samples), encoding="utf-8")
            report = evaluate(path)
            self.assertEqual(report["metrics"]["failure_adjusted_worst_case"]["sensitivity"], .5)
            self.assertEqual(report["project_targets"]["status"], "not_met")
            self.assertEqual(report["metrics"]["failures"], 1)
            self.assertFalse(report["clinical_validation"])

    def test_actual_or_rule_evaluator_does_not_score_unreported_symptoms(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pairs.jsonl"
            path.write_text(json.dumps({"pair_id": "p", "subject_key": "s", "label": 1, "symptoms_reported": False}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "No labeled symptomatic"):
                evaluate(path)

    def test_requested_values_are_targets_or_research_rules_not_approval(self):
        p = load_parameters()
        self.assertEqual(p["arm_angle_delta_threshold_deg"], 28.9)
        self.assertEqual(p["arm_angle_alternative_deg"], 33.0)
        self.assertEqual(p["targets"]["face_sensitivity"], .878)
        self.assertEqual(p["targets"]["face_specificity"], .993)
        self.assertEqual(p["targets"]["overall_sensitivity_minimum"], .77)
        self.assertEqual(p["targets"]["overall_sensitivity_stretch"], .86)
        self.assertFalse(p["deployment_approved"])

    def test_degree_boundary_is_not_mixed_with_dimensionless_arm_score(self):
        p = load_parameters()
        before = dict(vector(), left_arm_drift=.4)
        after = dict(before, left_arm_drift=100)
        # A normalized number is never interpreted as degrees.
        result = compare_research(before, after, angles(), angles(28.9), p)
        self.assertFalse(result["alert"])
        self.assertTrue(compare_research(before, after, angles(), angles(29), p)["alert"])
        self.assertFalse(compare_research(before, after, angles(20), angles(30), p)["alert"])

    def test_missing_angle_is_inconclusive_not_zero(self):
        result = compare_research(vector(), vector(), {}, {}, load_parameters())
        self.assertEqual(result["status"], "research_incomplete")
        self.assertIsNone(result["research_measurement"]["arm_angle_delta_deg"])
        facial = compare_research(vector(), dict(vector(), neutral_mouth_ratio=.11), {}, {}, load_parameters())
        self.assertTrue(facial["alert"])

    def test_bad_parameters_cannot_enable_clinical_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            for changes in ({"deployment_approved": True}, {"face_delta_threshold": float("nan")},
                            {"arm_angle_delta_threshold_deg": -1}):
                path.write_text(json.dumps(dict(load_parameters(), **changes)), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_parameters(path)
            path.write_text(json.dumps(load_parameters()), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_policy(path, "test")

    def test_demo_never_reports_fixture_passes_as_sensitivity(self):
        report = run_demo()
        self.assertEqual(len(report["scenarios"]), 4)
        self.assertIsNone(report["measured_sensitivity"])
        self.assertFalse(report["yfp_evaluated"])

    def test_research_workflow_round_trip_persists_numeric_angles(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FeatureStore(directory)
            workflow = VisitWorkflow(store, context(), research=True)
            request = {"mode": "baseline", "user_id": "member", "visit_id": "visit", "setup_confirmed": True, "symptoms_reported": False}
            workflow.begin(request)
            workflow.accept_identity([1.0] + [0.0] * 511, "fixture")
            workflow.finish(vector(), dict.fromkeys(SETUP_KEYS, 0), angles(2))
            workflow.begin(dict(request, mode="recheck", symptoms_reported=True))
            workflow.accept_identity([1.0] + [0.0] * 511, "fixture")
            result = workflow.finish(vector(), dict.fromkeys(SETUP_KEYS, 0), angles(33))
            self.assertEqual(result["status"], "research_alert")
            baseline = store.baseline(store.keys("member", "visit"))["record"]
            self.assertEqual(baseline["research_angles"], angles(2))
            with self.assertRaises(ValueError):
                validate_record(dict(baseline, research_angles={"frame": "image"}))


class ProjectedAngleTests(unittest.TestCase):
    def test_sideways_descent_is_measured_in_degrees(self):
        tracker = ProjectedArmAngle()
        shoulders = {"left": (200, 100), "right": (300, 100)}
        tracker.observe({"left": (100, 100), "right": (400, 100)}, shoulders, 1)
        tracker.observe({"left": (200 - 100 * math.cos(math.radians(30)), 150), "right": (400, 100)}, shoulders, 3)
        self.assertAlmostEqual(tracker.vector()["left_projected_drift_deg"], 30)
        self.assertEqual(tracker.vector()["right_projected_drift_deg"], 0)

    def test_forward_pointing_arms_and_missing_reference_stay_unavailable(self):
        tracker = ProjectedArmAngle()
        shoulders = {"left": (200, 100), "right": (300, 100)}
        tracker.observe({"left": (200, 160), "right": (300, 160)}, shoulders, 1)
        tracker.observe({"left": (100, 130), "right": (400, 130)}, shoulders, 3)
        self.assertEqual(tracker.vector(), {})

    def test_resolution_and_roll_do_not_change_angle(self):
        shoulders = {"left": (200, 100), "right": (300, 100)}
        wrists = {"left": (100, 150), "right": (400, 150)}
        before = ProjectedArmAngle.angles(wrists, shoulders)
        def transform(points):
            a = .2
            return {side: (2 * (x * math.cos(a) - y * math.sin(a)), 2 * (x * math.sin(a) + y * math.cos(a)))
                    for side, (x, y) in points.items()}
        after = ProjectedArmAngle.angles(transform(wrists), transform(shoulders))
        for side in before:
            self.assertAlmostEqual(before[side], after[side])


class BenchmarkTests(unittest.TestCase):
    def test_yfp_positives_alone_do_not_establish_specificity(self):
        positives = [row for row in rows() if row["label"]]
        result = benchmark(positives, "fixed")
        self.assertEqual(result["metrics"]["evaluable_only"]["sensitivity"], 1)
        self.assertIsNone(result["metrics"]["evaluable_only"]["specificity"])
        self.assertEqual(result["targets"]["status"], "not_evaluable")
        self.assertIsNone(result["overall_stroke_sensitivity"])
        self.assertEqual(choose_threshold(positives, load_parameters()["targets"])[1], "both_training_classes_required")

    def test_lopo_keeps_all_clips_from_same_person_out(self):
        samples = rows()
        samples.append(dict(samples[-1], sample_id="another-clip"))
        result = benchmark(samples, "lopo")
        self.assertEqual(len(result["folds"]), 4)
        self.assertEqual(result["folds"][-1]["testing_samples"], 2)
        self.assertTrue(all(f["training_subjects"] == 3 for f in result["folds"]))
        self.assertFalse(result["deployment_approved"])

    def test_unachievable_dual_target_is_reported(self):
        samples = rows()
        for row in samples:
            row["score"] = .2
        threshold, status, _ = choose_threshold(samples, load_parameters()["targets"])
        self.assertIsNotNone(threshold)
        self.assertEqual(status, "tuning_targets_not_met")

    def test_failed_extractions_are_not_dropped_from_performance_denominator(self):
        predictions = [{"label": 1, "prediction": True}, {"label": 1, "prediction": None},
                       {"label": 0, "prediction": None}]
        result = prediction_metrics(predictions)
        self.assertEqual(result["failure_adjusted_worst_case"]["sensitivity"], .5)
        self.assertEqual(result["failure_adjusted_worst_case"]["specificity"], 0)
        self.assertEqual(result["failures"], 2)

    def test_manifest_rejects_path_escape_subject_leakage_and_fabricated_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.jsonl"
            row = dict(rows()[-1], path="clips/authorized.mp4", kind="video")
            for samples in ([dict(row, path="../outside.mp4")],
                            [dict(row, split="tuning"), dict(row, sample_id="another", split="holdout")],
                            [dict(row, label=0)]):
                manifest.write_text("\n".join(json.dumps(sample) for sample in samples), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_manifest(manifest, directory)

    def test_benchmark_refuses_paired_data_as_single_video_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.jsonl"
            path.write_text(json.dumps({"schema": SCHEMA, "features": vector()}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_scores(path)

    def test_overall_goal_floor_and_stretch_are_independent(self):
        targets = load_parameters()["targets"]
        result = assess_targets({"sensitivity": .8}, targets, "overall")
        self.assertEqual(result["status"], "met_on_this_sample")
        self.assertFalse(result["overall_stretch_met"])
        self.assertEqual(assess_targets({"sensitivity": .7}, targets, "overall")["status"], "not_met")


if __name__ == "__main__":
    unittest.main()
