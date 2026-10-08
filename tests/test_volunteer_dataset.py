"""Volunteer data, split, replay confinement and password regression tests."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

from datasets.volunteers.prepare import action_from_name, prepare
from datasets.volunteers.evaluate import clip_features, evaluate, fit_centroids
from src.dev_access import DevAccess
from ui.volunteer_replay import video_path


class VolunteerTests(unittest.TestCase):
    def test_labels_are_tasks_not_clinical_classes(self):
        self.assertEqual(action_from_name('person/ยิ้ม(1).mp4'), 'smile')
        self.assertEqual(action_from_name('person/หน้านิ่ง.mp4'), 'neutral')
        self.assertEqual(action_from_name('person/stroke.mp4'), 'unreviewed')

    def test_zip_path_traversal_and_existing_destination_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with zipfile.ZipFile(root / 'p01.zip', 'w') as z:
                z.writestr('../ยิ้ม.mp4', b'bad')
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                prepare(root, root / 'out')
            self.assertFalse((root / 'out').exists())
            with self.assertRaises(ValueError):
                prepare(root, root)

    def test_duplicate_clips_rejected_before_split(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for subject in ('p01', 'p02'):
                with zipfile.ZipFile(root / f'{subject}.zip', 'w') as z:
                    z.writestr('ยิ้ม.mp4', b'same-video')
            with patch('datasets.volunteers.prepare.probe', return_value=({}, np.zeros((10, 10, 3), np.uint8))):
                with self.assertRaisesRegex(ValueError, 'Duplicate'):
                    prepare(root, root / 'out')
            self.assertFalse((root / 'out').exists())

    def test_features_reject_too_few_samples_and_ignore_missing_time_gaps(self):
        samples = [dict(time=i / 15, mouth_width=1., mouth_open=.1, mouth_lift=.2, ear=.3) for i in range(20)]
        with self.assertRaises(ValueError):
            clip_features(samples[:4])
        self.assertAlmostEqual(clip_features(samples)[4], 0.)
        samples[-1].update(time=10., ear=.1)
        self.assertAlmostEqual(clip_features(samples)[4], 0.)

    def test_subject_disjoint_folds_predict_every_clip_once(self):
        rows = [dict(sample_id=f'{s}-{k}', subject_key=s, action=label, features=[k, k*2])
                for s in ('p01', 'p02', 'p03') for k, label in enumerate(('neutral', 'smile', 'blink'))]
        result = evaluate(rows)
        self.assertEqual(result['metrics']['samples'], 9)
        self.assertEqual(result['metrics']['accuracy'], 1.)
        self.assertEqual(len({p['sample_id'] for p in result['predictions']}), 9)
        for fold in result['folds']:
            self.assertNotIn(fold['test_subject'], fold['train_subjects'])
        with self.assertRaises(ValueError):
            fit_centroids([[0], [1]], [0, 1])

    def test_scaler_fitted_only_to_supplied_training_data(self):
        result = fit_centroids([[0.], [2.], [4.]], [0, 1, 2])
        self.assertEqual(result['mean'], [2.])
        self.assertAlmostEqual(result['scale'][0], np.std([0., 2., 4.]))

    def test_replay_path_confined_to_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(video_path(directory, 'videos/p01.mp4').is_relative_to(Path(directory)))
            for path in ('../outside.mp4', 'not-a-video.exe'):
                with self.assertRaises(ValueError):
                    video_path(directory, path)

    def test_reports_remain_password_gated_and_optional(self):
        access = DevAccess()
        with patch.object(Path, 'exists') as exists, patch.object(Path, 'read_text') as read:
            with self.assertRaises(PermissionError):
                access.unlock_reports('wrong')
            exists.assert_not_called()
            read.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = {'schema': 'volunteer-gesture-report-v1'}
            (root / 'volunteers.json').write_text(json.dumps(report), encoding='utf-8')
            legacy, volunteers = DevAccess(root / 'missing.json').unlock_reports('676767', root / 'volunteers.json')
            self.assertIsNone(legacy)
            self.assertEqual(volunteers, report)


if __name__ == '__main__':
    unittest.main()
