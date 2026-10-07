"""Synthetic engineering fixtures only; these are NOT clinical validation data."""

import importlib.util
from contextlib import closing
import json
import math
import sqlite3
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.arm_features import ArmFeatures
from src.feature_store import FeatureStore, validate_record
from src.features import FEATURE_KEYS, SETUP_KEYS, SCHEMA, SCORE, face_geometry, delta_features
from src.protocol import load_policy
from src.threshold_validation import load_pairs, validate_threshold, write_report
from src.visit_workflow import VisitWorkflow
from src.session import ScreeningSession
from export_feature_pairs import export_pairs


EMBEDDING = [1.0] + [0.0] * 511
IDENTITY_MODEL = "synthetic-facenet-fixture"


def record(score=0):
    return {"schema": SCHEMA, "features": dict.fromkeys(FEATURE_KEYS, 0.0) | {"neutral_mouth_ratio": score},
            "setup": dict.fromkeys(SETUP_KEYS, 0.0),
            "context": {"pipeline": "a" * 64, "camera": 0, "width": 640, "height": 480, "station": "station-01"}}


def request(mode="baseline", user="0801234567", visit="visit-001"):
    return {"mode": mode, "user_id": user, "visit_id": visit, "setup_confirmed": True,
            "symptoms_reported": mode == "recheck"}


def approved_test_policy():
    return {"schema": SCHEMA, "score_definition": SCORE, "pipeline": "a" * 64,
            "cohort": "self_reported_symptoms", "deployment_approved": True, "threshold": .2,
            "policy_id": "synthetic-test-only", "clinical_review_reference": "test fixture, not a clinical review",
            "validation_report_sha256": "0" * 64, "holdout_counts": {"positive": 2, "negative": 2}}


class GeometryTests(unittest.TestCase):
    def mesh(self, transform=lambda x, y: (x, y)):
        coords = {33: (30, 30), 133: (42, 30), 160: (33, 28), 158: (39, 28), 153: (39, 32), 144: (33, 32),
                  362: (58, 30), 263: (70, 30), 385: (61, 28), 387: (67, 28), 373: (67, 32), 380: (61, 32),
                  61: (38, 65), 291: (62, 65), 70: (30, 22), 63: (35, 22), 105: (40, 22),
                  300: (70, 22), 293: (65, 22), 334: (60, 22), 1: (50, 50), 468: (36, 30), 473: (64, 30)}
        points = []
        for index in range(478):
            x, y = transform(*coords.get(index, (50, 50)))
            points.append(SimpleNamespace(x=x / 100, y=y / 100))
        return points

    def test_scale_translation_and_roll_do_not_create_asymmetry(self):
        before = face_geometry(self.mesh(), 100, 100)
        angle = .2
        after = face_geometry(self.mesh(lambda x, y: (1.2 * (x * math.cos(angle) - y * math.sin(angle)) + 8,
                                                      1.2 * (x * math.sin(angle) + y * math.cos(angle)) + 4)), 100, 100)
        for key in ("mouth_ratio", "brow_ratio", "eyelid_ratio", "left_ear", "right_ear"):
            self.assertAlmostEqual(before[key], after[key])

    def test_mouth_droop_uses_ratio_not_signed_pixel_difference(self):
        points = self.mesh()
        points[61].y += .04
        self.assertAlmostEqual(face_geometry(points, 100, 100)["mouth_ratio"], 1 - 35 / 39)

    def test_reject_wrong_landmark_count(self):
        with self.assertRaises(ValueError):
            face_geometry(self.mesh()[:467], 100, 100)

    def test_degenerate_eye_is_invalid_not_closed(self):
        mesh = self.mesh()
        mesh[133] = mesh[33]
        with self.assertRaisesRegex(ValueError, "degenerate"):
            face_geometry(mesh, 100, 100)

    def test_delta_aggregates_ratio_change_and_increased_drift(self):
        before = record(.1)["features"]
        after = dict(before, neutral_mouth_ratio=.3, left_arm_drift=.3)
        measurement = delta_features(before, after)
        self.assertAlmostEqual(measurement["score"], .5)
        self.assertEqual(delta_features(after, before)["arm_delta"], 0)

    def test_missing_or_nonfinite_features_are_not_zero_filled(self):
        for vector in ({}, dict(record()["features"], closed_eyelid_ratio=float("nan"))):
            with self.assertRaises(ValueError):
                delta_features(record()["features"], vector)


class ArmFeatureTests(unittest.TestCase):
    def test_empty_native_pose_representation_does_not_index_missing_wrists(self):
        path = Path(__file__).resolve().parents[1] / "src/arm_pose.py"
        spec = importlib.util.spec_from_file_location("arm_under_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"ultralytics": Mock()}):
            spec.loader.exec_module(module)
        analyzer = module.ArmPoseAnalyzer()
        analyzer.start_test()
        analyzer._model.predict.return_value = [SimpleNamespace(keypoints=SimpleNamespace(xy=SimpleNamespace(shape=(1, 0, 2))))]
        result = analyzer.analyze(None)
        self.assertFalse(result["person_found"])
        self.assertFalse(result["test_complete"])

    def run_motion(self, scale):
        tracker = ArmFeatures()
        shoulders = {"left": (100 * scale, 100 * scale), "right": (200 * scale, 100 * scale)}
        for elapsed, yleft, yright in ((0, 200, 200), (1, 70, 70), (3, 90, 70)):
            self.assertTrue(tracker.observe({"left": (100 * scale, yleft * scale), "right": (200 * scale, yright * scale)},
                                           shoulders, 640 * scale, 480 * scale, elapsed))
        return tracker

    def test_normalized_drift_is_resolution_independent(self):
        a, b = self.run_motion(1), self.run_motion(2)
        self.assertEqual(a.vector(), b.vector())
        self.assertAlmostEqual(a.vector()["left_arm_drift"], .2)

    def test_missing_shoulders_and_raised_initial_arms_are_rejected(self):
        tracker = ArmFeatures()
        self.assertFalse(tracker.observe({"left": (100, 60), "right": (200, 60)},
                                        {"left": (100, 100), "right": (200, 100)}, 640, 480, 0))
        self.assertFalse(tracker.observe({"left": (100, 200), "right": (200, 200)},
                                        {"left": None, "right": (200, 100)}, 640, 480, 0))

    def test_no_attempted_lift_has_no_complete_vector(self):
        tracker = ArmFeatures()
        for elapsed in (0, 1, 3, 10):
            tracker.observe({"left": (100, 200), "right": (200, 200)},
                            {"left": (100, 100), "right": (200, 100)}, 640, 480, elapsed)
        self.assertIsNone(tracker.vector())


class VisitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = FeatureStore(self.temp.name)
        self.policy_path = Path(self.temp.name) / "policy.json"
        self.workflow = VisitWorkflow(self.store, record()["context"], self.policy_path)

    def baseline(self):
        self.workflow.begin(request())
        self.workflow.accept_identity(EMBEDDING, IDENTITY_MODEL)
        return self.workflow.finish(record()["features"], record()["setup"])

    def test_feature_only_baseline_and_unconfigured_recheck_survive_restart(self):
        self.assertEqual(self.baseline()["status"], "baseline_saved")
        reopened = FeatureStore(self.temp.name)
        flow = VisitWorkflow(reopened, record()["context"], self.policy_path)
        flow.begin(request("recheck"))
        flow.accept_identity(EMBEDDING, IDENTITY_MODEL)
        result = flow.finish(record(.3)["features"], record()["setup"])
        self.assertEqual(result["status"], "threshold_unconfigured")
        self.assertIn("Do not wait", result["care_message"])
        self.assertAlmostEqual(result["measurement"]["score"], .3)
        data = self.store.path.read_bytes()
        for forbidden in (b"0801234567", b"visit-001", b"frame", b"video"):
            self.assertNotIn(forbidden, data)

    def test_no_baseline_overwrite_or_cross_customer_lookup(self):
        self.baseline()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.workflow.begin(request())
        with self.assertRaisesRegex(ValueError, "No baseline"):
            self.workflow.begin(request("recheck", user="different"))
        with self.assertRaisesRegex(ValueError, "No baseline"):
            self.workflow.begin(request("recheck", visit="different"))

    def test_symptom_and_setup_gates(self):
        for data in (dict(request(), setup_confirmed=False), dict(request(), symptoms_reported=True),
                     dict(request(), user_id="")):
            with self.assertRaises(ValueError):
                self.workflow.begin(data)

    def test_routine_recheck_without_reported_symptoms_is_recorded_truthfully(self):
        self.baseline()
        self.workflow.begin(dict(request("recheck"), symptoms_reported=False))
        self.workflow.accept_identity(EMBEDDING, IDENTITY_MODEL)
        result = self.workflow.finish(record(.1)["features"], record()["setup"])
        self.assertEqual(result["status"], "threshold_unconfigured")
        self.assertFalse(result["symptoms_reported"])
        self.assertEqual(result["care_message"], "")
        output = Path(self.temp.name) / "routine.jsonl"
        export_pairs(self.store.path, output)
        self.assertFalse(json.loads(output.read_text())["symptoms_reported"])

    def test_symptomatic_policy_is_not_reused_for_routine_monitoring(self):
        self.policy_path.write_text(json.dumps(approved_test_policy()), encoding="utf-8")
        self.baseline()
        self.workflow.begin(dict(request("recheck"), symptoms_reported=False))
        self.workflow.accept_identity(EMBEDDING, IDENTITY_MODEL)
        result = self.workflow.finish(record(.3)["features"], record()["setup"])
        self.assertEqual(result["status"], "threshold_unconfigured")
        self.assertIsNone(result["threshold"])
        self.assertIsNone(result["policy_id"])
        self.assertIn("only for symptom-reported", result["reason"])

    def test_expired_and_changed_camera_baselines_are_inconclusive(self):
        self.baseline()
        with patch("src.visit_workflow.time.time", return_value=10 ** 12):
            with self.assertRaisesRegex(ValueError, "expired"):
                self.workflow.begin(request("recheck"))
        context = dict(record()["context"], camera=1)
        changed = VisitWorkflow(self.store, context, self.policy_path)
        with self.assertRaisesRegex(ValueError, "changed"):
            changed.begin(request("recheck"))

    def test_changed_measurement_pipeline_requires_fresh_baseline(self):
        self.baseline()
        context = dict(record()["context"], pipeline="b" * 64)
        changed = VisitWorkflow(self.store, context, self.policy_path)
        with self.assertRaisesRegex(ValueError, "changed"):
            changed.begin(request("recheck"))
        changed.begin(request())
        self.assertTrue(changed.replace_baseline)
        changed.accept_identity(EMBEDDING, IDENTITY_MODEL)
        changed.finish(record()["features"], record()["setup"])
        changed.begin(dict(request("recheck"), symptoms_reported=False))
        changed.accept_identity(EMBEDDING, IDENTITY_MODEL)
        result = changed.finish(record()["features"], record()["setup"])
        self.assertEqual(result["measurement"]["score"], 0)

    def test_expired_baseline_can_be_replaced_without_mixing_old_rechecks(self):
        self.baseline()
        self.workflow.begin(request("recheck"))
        self.workflow.accept_identity(EMBEDDING, IDENTITY_MODEL)
        self.workflow.finish(record(.2)["features"], record()["setup"])
        with closing(sqlite3.connect(self.store.path)) as db, db:
            db.execute("UPDATE baselines SET created=0")

        self.workflow.begin(request())
        self.assertTrue(self.workflow.replace_baseline)
        self.workflow.accept_identity(EMBEDDING, IDENTITY_MODEL)
        result = self.workflow.finish(record(.4)["features"], record()["setup"])
        self.assertTrue(result["baseline_replaced"])
        current = self.store.baseline(self.store.keys("0801234567", "visit-001"))
        self.assertAlmostEqual(current["record"]["features"]["neutral_mouth_ratio"], .4)
        with closing(sqlite3.connect(self.store.path)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM baselines").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM rechecks").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM baseline_history").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM recheck_history").fetchone()[0], 1)

    def test_pose_mismatch_and_missing_data_cannot_produce_low_delta(self):
        self.baseline()
        self.workflow.begin(request("recheck"))
        self.workflow.accept_identity(EMBEDDING, IDENTITY_MODEL)
        with self.assertRaisesRegex(ValueError, "Head rotation"):
            self.workflow.finish(record()["features"], dict(record()["setup"], face_roll=30))
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.workflow.finish({}, record()["setup"])

    def test_alert_boundary_and_partial_alert(self):
        self.policy_path.write_text(json.dumps(approved_test_policy()), encoding="utf-8")
        self.baseline()
        self.workflow.begin(request("recheck"))
        self.workflow.accept_identity(EMBEDDING, IDENTITY_MODEL)
        equal = self.workflow.compare(record(.2)["features"], record()["setup"])
        self.assertEqual(equal["status"], "below_threshold")
        self.assertIn("cannot exclude", equal["reason"])
        partial = self.workflow.compare({"neutral_mouth_ratio": .21},
                                        {k: v for k, v in record()["setup"].items() if k.startswith("face_")}, partial=True)
        self.assertTrue(partial["alert"])
        with self.assertRaisesRegex(ValueError, "alignment"):
            self.workflow.compare({"neutral_mouth_ratio": .21}, {}, partial=True)

    def test_unapproved_and_wrong_cohort_policy_fail_closed(self):
        for policy in (dict(approved_test_policy(), deployment_approved=False),
                       dict(approved_test_policy(), cohort="asymptomatic"),
                       dict(approved_test_policy(), pipeline="other")):
            self.policy_path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_policy(self.policy_path, "a" * 64)

    def test_store_rejects_media_and_unknown_fields(self):
        for bad in (dict(record(), frame="secret image"), dict(record(), features=dict(record()["features"], image="raw"))):
            with self.assertRaises(ValueError):
                validate_record(bad)

    def test_export_is_unlabeled_and_customer_deletion_removes_pairs(self):
        self.baseline()
        self.workflow.begin(request("recheck"))
        self.workflow.accept_identity(EMBEDDING, IDENTITY_MODEL)
        self.workflow.finish(record(.1)["features"], record()["setup"])
        output = Path(self.temp.name) / "pairs.jsonl"
        self.assertEqual(export_pairs(self.store.path, output), 1)
        row = json.loads(output.read_text())
        self.assertIsNone(row["label"])
        self.assertTrue(row["symptoms_reported"])
        with self.assertRaises(ValueError):
            load_pairs(output)  # Cannot treat an unlabeled export as evidence.
        self.store.delete_customer("0801234567")
        with self.assertRaises(ValueError):
            self.store.baseline(self.store.keys("0801234567", "visit-001"))
        self.assertEqual(export_pairs(self.store.path, Path(self.temp.name) / "empty.jsonl"), 0)

    def test_session_saves_once_and_latches_early_alert(self):
        self.policy_path.write_text(json.dumps(approved_test_policy()), encoding="utf-8")
        self.baseline()
        session = ScreeningSession()
        session.workflow = self.workflow
        session.cap = Mock()
        frame = SimpleNamespace(shape=(480, 640, 3))
        session.cap.read.return_value = (True, frame)
        session.flow = Mock()
        session.start(request("recheck"))
        session.face = Mock()
        session.identity_model = Mock(signature=IDENTITY_MODEL)
        session.identity_model.embed.return_value = EMBEDDING
        session.flow.features = {"neutral_mouth_ratio": .3}
        session.flow.setup = {k: v for k, v in record()["setup"].items() if k.startswith("face_")}
        session.flow.update.return_value = {"state": "mouth_test"}
        cv = Mock()
        cv.flip.return_value = frame
        with patch.dict("sys.modules", {"cv2": cv}):
            snapshot = session.read()
            self.assertTrue(snapshot["comparison"]["alert"])
            self.assertIn("Do not wait", snapshot["care_message"])
            session.flow.features = record(.3)["features"]
            session.flow.setup = record()["setup"]
            session.flow.update.return_value = {"state": "summary"}
            snapshot = session.read()
            self.assertEqual(snapshot["assessment"]["level"], "Seek medical attention immediately")
            session.read()
        self.assertEqual(export_pairs(self.store.path, Path(self.temp.name) / "once.jsonl"), 1)

    def test_failed_recheck_request_keeps_care_message(self):
        session = ScreeningSession()
        session.workflow = self.workflow
        session.flow = Mock()
        with self.assertRaisesRegex(ValueError, "No baseline"):
            session.start(request("recheck"))
        session.face = Mock()
        session.identity_model = Mock(signature=IDENTITY_MODEL)
        session.identity_model.embed.return_value = EMBEDDING
        self.assertIn("Do not wait", session.care_message)
        session.flow.start.assert_not_called()


class FullFlowTests(unittest.TestCase):
    def load_flow(self):
        path = Path(__file__).resolve().parents[1] / "src/screening_flow.py"
        spec = importlib.util.spec_from_file_location("paired_flow_under_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"src.face_analytics": Mock()}):
            spec.loader.exec_module(module)
        return module

    def test_arm_change_is_exposed_before_hold_finishes(self):
        module = self.load_flow()
        arm = Mock()
        arm.analyze.return_value = {"test_complete": False, "pose_found": True, "elapsed_sec": 3,
                                   "normalized_features": {"left_arm_drift": .4, "right_arm_drift": 0, "arm_lift_skew": 0},
                                   "capture_setup": {k: 0 for k in SETUP_KEYS if k.startswith("body_")}}
        flow = module.ScreeningFlow(Mock(), arm)
        flow.state = "arm_test"
        self.assertEqual(flow.update(None)["state"], "arm_test")
        self.assertEqual(flow.features["left_arm_drift"], .4)

    def test_each_stage_contributes_to_complete_feature_record(self):
        module = self.load_flow()
        face = Mock()
        face.latest_features = face_geometry(GeometryTests().mesh(), 100, 100, {"face_yaw": 0, "face_pitch": 0})
        face.check_quality.return_value = {"ok": True}
        face.capture_neutral.return_value = (.3, .3)
        face.measure_eyes.return_value = {"left_ear": .3, "right_ear": .3, "left_closed": False, "right_closed": False}
        arm = Mock()
        arm.analyze.return_value = {"test_complete": True,
                                   "normalized_features": {k: 0 for k in ("left_arm_drift", "right_arm_drift", "arm_lift_skew")},
                                   "capture_setup": {k: 0 for k in SETUP_KEYS if k.startswith("body_")}}
        flow = module.ScreeningFlow(face, arm)
        flow.start()
        seen = set()
        with patch.object(module.time, "monotonic", return_value=0) as clock:
            for _ in range(80):
                seen.add(flow.update(None)["state"])
                if flow.state == "summary":
                    break
                clock.return_value += .5
        self.assertIn("eye_closure", seen)
        self.assertEqual(flow.state, "summary")
        self.assertEqual(set(flow.features), set(FEATURE_KEYS))
        self.assertEqual(set(flow.setup), set(SETUP_KEYS))
        arm.start_test.assert_called_once()


class ValidationTests(unittest.TestCase):
    def rows(self, prefix, symptomatic=True):
        return [{"subject": prefix + str(i), "pair_id": prefix + str(i), "symptomatic": symptomatic,
                 "label": int(i > 1), "pipeline": "a" * 64, "score": score}
                for i, score in enumerate((.1, .2, .6, .8))]

    def test_asymptomatic_data_is_not_used_to_tune_and_holdout_is_reported(self):
        tuning = self.rows("t") + self.rows("asym", False)
        result = validate_threshold(tuning, self.rows("h"), .95)
        self.assertFalse(result["deployment_approved"])
        self.assertEqual(result["asymptomatic_excluded_from_tuning"], 4)
        self.assertEqual(result["holdout"]["tp"], 2)
        self.assertEqual(result["holdout"]["tn"], 2)
        self.assertLess(result["holdout"]["sensitivity_95ci"][0], .5)

    def test_leakage_and_missing_symptomatic_negative_cases_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "leakage"):
            validate_threshold(self.rows("same"), self.rows("same"), .9)
        with self.assertRaisesRegex(ValueError, "positive and negative"):
            validate_threshold(self.rows("t")[2:], self.rows("h"), .9)

    def test_heldout_failure_does_not_retune(self):
        holdout = self.rows("h")
        holdout[-1]["score"] = .1
        report = validate_threshold(self.rows("t"), holdout, .95)
        self.assertEqual(report["holdout"]["sensitivity"], .5)
        self.assertFalse(report["holdout_meets_point_sensitivity_target"])
        self.assertFalse(report["deployment_approved"])

    def test_report_and_candidate_from_real_jsonl_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            paths = []
            for prefix in ("t", "h"):
                path = directory / (prefix + ".jsonl")
                pairs = [{"subject_key": row["subject"], "pair_id": row["pair_id"], "symptoms_reported": True,
                          "label": row["label"], "before": record(), "after": record(row["score"])} for row in self.rows(prefix)]
                path.write_text("\n".join(json.dumps(row) for row in pairs), encoding="utf-8")
                paths.append(path)
            report_path = directory / "report.json"
            write_report(*paths, report_path, .95)
            candidate_path = directory / "report-candidate.json"
            candidate = json.loads(candidate_path.read_text())
            self.assertFalse(candidate["deployment_approved"])
            self.assertEqual(len(candidate["validation_report_sha256"]), 64)
            with self.assertRaises(ValueError):
                load_policy(candidate_path, "a" * 64)


if __name__ == "__main__":
    unittest.main()
