"""Synthetic engineering tests, not biometric or clinical performance evidence."""

from contextlib import closing
import math
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.face_identity import IdentityMismatch, MISMATCH_MESSAGE
from src.feature_store import FeatureStore
from src.features import asymmetry_ratio, face_geometry
from src.protocol import check_setup
from src.session import ScreeningSession
from src.visit_workflow import VisitWorkflow
from test_paired_screening import record, request, EMBEDDING, IDENTITY_MODEL
import test_paired_screening as fixtures
from export_feature_pairs import export_pairs


class RatioTests(unittest.TestCase):
    def test_formula_scale_sides_and_zero_cases(self):
        for left, right, expected in ((2, 4, .5), (4, 2, .5), (0, 0, 0), (0, 2, 1), (2, 2, 0)):
            self.assertAlmostEqual(asymmetry_ratio(left, right, 12), expected)
            self.assertAlmostEqual(asymmetry_ratio(left * 3, right * 3, 36), expected)
        for args in ((1, 2, 0), (-1, 2, 3), (1, float('nan'), 3)):
            with self.assertRaises(ValueError):
                asymmetry_ratio(*args)

    def test_nonzero_region_ratios_survive_similarity_transform(self):
        mesh = fixtures.GeometryTests().mesh()
        mesh[61].x -= .04
        mesh[70].y -= .03
        mesh[160].y += .01
        first = face_geometry(mesh, 100, 100)
        angle = math.radians(12)
        transformed = []
        for p in mesh:
            x, y = p.x * 100, p.y * 100
            transformed.append(SimpleNamespace(x=(2 * (x * math.cos(angle) - y * math.sin(angle)) + 20) / 640,
                                               y=(2 * (x * math.sin(angle) + y * math.cos(angle)) + 30) / 480))
        second = face_geometry(transformed, 640, 480)
        for key in ('mouth_ratio', 'brow_ratio', 'eyelid_ratio'):
            self.assertGreater(first[key], 0)
            self.assertAlmostEqual(first[key], second[key])

    def test_one_eye_closure_changes_aperture_ratio(self):
        mesh = fixtures.GeometryTests().mesh()
        for index in (160, 158, 153, 144):
            mesh[index].y = .3
        self.assertAlmostEqual(face_geometry(mesh, 100, 100)['eyelid_ratio'], 1)

    def test_position_and_size_change_pass_but_all_rotation_axes_fail(self):
        base = record()['setup']
        check_setup(base, dict(base, face_x=.5, face_y=.7, face_scale=.3, face_roll=18))
        for axis in ('face_roll', 'face_yaw', 'face_pitch'):
            for angle in (-18.01, 18.01):
                with self.assertRaisesRegex(ValueError, 'Head rotation'):
                    check_setup(base, dict(base, **{axis: angle}))
                with self.assertRaisesRegex(ValueError, 'Head rotation'):
                    check_setup(dict(base, **{axis: angle}), dict(base, **{axis: angle}))
        with self.assertRaisesRegex(ValueError, 'body_y'):
            check_setup(base, dict(base, body_y=.5))

    def test_capture_stage_accepts_face_translation_and_rejects_rotation(self):
        module = fixtures.FullFlowTests().load_flow()
        face = Mock()
        face.latest_features = face_geometry(fixtures.GeometryTests().mesh(), 100, 100, {'face_yaw': 0, 'face_pitch': 0})
        flow = module.ScreeningFlow(face, Mock())
        flow.setup = record()['setup']
        self.assertTrue(flow._capture_features('neutral'))
        face.latest_features.update(face_y=.9, face_scale=.6)
        self.assertTrue(flow._capture_features('neutral'))
        face.latest_features['face_roll'] = 19
        self.assertFalse(flow._capture_features('neutral'))


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = FeatureStore(self.temp.name)
        self.flow = VisitWorkflow(self.store, record()['context'], Path(self.temp.name) / 'missing.json')
        self.flow.begin(request())
        self.flow.accept_identity(EMBEDDING, IDENTITY_MODEL)
        self.flow.finish(record()['features'], record()['setup'])
        self.flow.begin(request('recheck'))

    def test_matching_embeddings_proceed_to_delta(self):
        self.flow.accept_identity([3 * v for v in EMBEDDING], IDENTITY_MODEL)
        result = self.flow.finish(record(.25)['features'], record()['setup'])
        self.assertAlmostEqual(result['measurement']['face_delta'], .25)

    def test_nonmatch_bypasses_all_delta_functions_and_latches(self):
        other = [0.0, 1.0] + [0.0] * 510
        with patch('src.visit_workflow.delta_features') as delta, patch('src.visit_workflow.compare_research') as research:
            with self.assertRaisesRegex(IdentityMismatch, MISMATCH_MESSAGE):
                self.flow.accept_identity(other, IDENTITY_MODEL)
            for action in (lambda: self.flow.compare({}, {}, partial=True),
                           lambda: self.flow.finish({}, {}),
                           lambda: self.flow.accept_identity(EMBEDDING, IDENTITY_MODEL)):
                with self.assertRaisesRegex(IdentityMismatch, MISMATCH_MESSAGE):
                    action()
            delta.assert_not_called()
            research.assert_not_called()
        with closing(sqlite3.connect(self.store.path)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM rechecks').fetchone()[0], 0)

    def test_threshold_inclusive_and_below_rejects(self):
        self.flow.accept_identity([.6, .8] + [0.] * 510, IDENTITY_MODEL)
        self.assertTrue(self.flow.identity_verified)
        self.flow.begin(request('recheck'))
        with self.assertRaises(IdentityMismatch):
            self.flow.accept_identity([.599, math.sqrt(1 - .599 ** 2)] + [0.] * 510, IDENTITY_MODEL)

    def test_missing_invalid_and_changed_model_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'verification required'):
            self.flow.compare({}, {}, partial=True)
        for vector in ([], [0.] * 512, [float('nan')] * 512, [True] * 512, [float('inf')] * 512):
            with self.assertRaises(ValueError):
                self.flow.accept_identity(vector, IDENTITY_MODEL)
            self.assertFalse(self.flow.identity_verified)
        with self.assertRaises(IdentityMismatch):
            self.flow.accept_identity(EMBEDDING, 'changed-model')

    def test_embedding_stored_separately_survives_restart_and_never_exports(self):
        reopened = FeatureStore(self.temp.name)
        baseline = reopened.baseline(reopened.keys(request()['user_id'], request()['visit_id']))
        self.assertEqual(len(baseline['identity']['embedding']), 512)
        self.assertNotIn('identity', baseline['record'])
        self.flow.accept_identity(EMBEDDING, IDENTITY_MODEL)
        self.flow.finish(record()['features'], record()['setup'])
        output = Path(self.temp.name) / 'export.jsonl'
        export_pairs(self.store.path, output)
        self.assertNotIn('embedding', output.read_text())
        self.assertNotIn(IDENTITY_MODEL, output.read_text())

    def test_old_table_migrates_without_overwrite_and_requires_enrollment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'identity.key').write_bytes(b'a' * 32)
            with closing(sqlite3.connect(root / 'visits.sqlite3')) as db, db:
                db.execute('CREATE TABLE baselines(subject TEXT, visit TEXT, created REAL, record TEXT, PRIMARY KEY(subject,visit))')
            store = FeatureStore(root)
            store.save_baseline(store.keys('old', 'visit'), record())
            flow = VisitWorkflow(store, record()['context'])
            with self.assertRaisesRegex(ValueError, 'no identity embedding'):
                flow.begin(request('recheck', 'old', 'visit'))

    def session(self, vector):
        session = ScreeningSession()
        session.workflow = self.flow
        session.flow = Mock(state='neutral_capture', features={}, research_angles={})
        session.face = Mock()
        session.identity_model = Mock(signature=IDENTITY_MODEL)
        session.identity_model.embed.return_value = vector
        session.cap = Mock()
        frame = SimpleNamespace(shape=(480, 640, 3))
        session.cap.read.return_value = (True, frame)
        cv = Mock()
        cv.flip.return_value = frame
        return session, cv

    def test_camera_mismatch_displays_exact_warning_and_never_updates_flow(self):
        session, cv = self.session([0., 1.] + [0.] * 510)
        with patch.dict('sys.modules', {'cv2': cv}), patch.object(self.flow, 'compare') as compare:
            first = session.read()
            second = session.read()
        self.assertEqual(first['instruction'], MISMATCH_MESSAGE)
        self.assertEqual(second['state'], 'identity_rejected')
        session.flow.update.assert_not_called()
        compare.assert_not_called()

    def test_camera_missing_face_pauses_without_using_stale_verification(self):
        session, cv = self.session(EMBEDDING)
        self.flow.accept_identity(EMBEDDING, IDENTITY_MODEL)
        session.face._observe.return_value = None
        with patch.dict('sys.modules', {'cv2': cv}):
            self.assertEqual(session.read()['state'], 'identity_check')
        self.assertFalse(self.flow.identity_verified)
        session.identity_model.embed.assert_not_called()
        session.flow.update.assert_not_called()
        self.assertIsNone(session.flow._last_detected_at)


if __name__ == '__main__':
    unittest.main()
