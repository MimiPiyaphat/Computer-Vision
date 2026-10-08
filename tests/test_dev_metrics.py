"""Access boundaries and metric arithmetic, without camera or GUI."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.dev_access import DevAccess
from src.model_metrics import classification_metrics
from ui.dev_dashboard import matrix_canvas_height


class MetricsTests(unittest.TestCase):
    def test_matrix_height_tracks_class_count(self):
        self.assertEqual(matrix_canvas_height({'labels': ['a', 'b']}), 140)
        self.assertEqual(matrix_canvas_height({'labels': ['a', 'b', 'c', 'd']}), 224)

    def test_actual_rows_precision_recall_and_f1(self):
        result = classification_metrics([0, 0, 1, 1], [0, 1, 1, 1], ['Complete', 'Incomplete'])
        self.assertEqual(result['confusion_matrix'], [[1, 1], [0, 2]])
        self.assertEqual(result['accuracy'], .75)
        self.assertAlmostEqual(result['per_class'][1]['precision'], 2/3)
        self.assertEqual(result['per_class'][1]['recall'], 1)
        self.assertAlmostEqual(result['per_class'][1]['f1'], .8)
        self.assertAlmostEqual(result['macro_f1'], (2/3 + .8)/2)
        low, high = result['accuracy_wilson_95ci']
        self.assertLess(low, .75)
        self.assertGreater(high, .75)

    def test_missing_class_is_explicit_and_invalid_data_rejected(self):
        result = classification_metrics([0, 0], [0, 0], ['a', 'b'])
        self.assertEqual(result['per_class'][1]['support'], 0)
        self.assertEqual(result['per_class'][1]['f1'], 0)
        for actual, predicted in [([], []), ([0], []), ([0], [2]), ([True], [0])]:
            with self.assertRaises(ValueError):
                classification_metrics(actual, predicted, ['a', 'b'])


class AccessTests(unittest.TestCase):
    def test_wrong_password_never_reads_report(self):
        access = DevAccess()
        with patch.object(Path, 'read_text') as read, patch.object(Path, 'exists') as exists:
            with self.assertRaises(PermissionError):
                access.unlock('wrong')
            read.assert_not_called()
            exists.assert_not_called()

    def test_password_cooldown_then_valid_login_and_missing_report(self):
        clock = Mock(return_value=100)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            access = DevAccess(path, clock)
            for _ in range(5):
                with self.assertRaises(PermissionError):
                    access.unlock('wrong')
            with self.assertRaises(PermissionError):
                access.unlock('676767')
            clock.return_value = 161
            self.assertIsNone(access.unlock('676767'))
            report = {'schema': 'rehab-transfer-report-v1'}
            path.write_text(json.dumps(report), encoding='utf-8')
            self.assertEqual(access.unlock('676767'), report)


class TransferTests(unittest.TestCase):
    def test_temporal_heads_roundtrip_and_prediction_dimensions(self):
        import torch
        from datasets.stroke_rehab.train_transfer import TemporalHead
        torch.set_num_threads(2)
        x = torch.randn(2, 4, 512)
        for kind in ('linear', 'mlp', 'gru'):
            model = TemporalHead(kind).eval()
            ex, st = model(x)
            self.assertEqual(tuple(ex.shape), (2, 4))
            self.assertEqual(tuple(st.shape), (2, 2))
            restored = TemporalHead(kind).eval()
            restored.load_state_dict(model.state_dict(), strict=True)
            self.assertTrue(torch.equal(ex, restored(x)[0]))


if __name__ == '__main__':
    unittest.main()
