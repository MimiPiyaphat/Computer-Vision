"""Dataset audit and password-gated report tests without running YOLO."""

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from datasets.roboflow_stroke.audit import audit_dataset, source_family, source_name
from src.dev_access import DevAccess


class RoboflowAuditTests(unittest.TestCase):
    def make_dataset(self, root: Path):
        (root / 'data.yaml').write_text("nc: 2\nnames: ['no stroke', 'stroke']\n", encoding='utf-8')
        for split, class_id in (('train', 0), ('valid', 1), ('test', 1)):
            (root / split / 'images').mkdir(parents=True)
            (root / split / 'labels').mkdir(parents=True)
            stem = f'Screenshot_{split}_1.rf.' + ('a' * 32)
            Image.new('RGB', (20, 10), 'white').save(root / split / 'images' / f'{stem}.jpg')
            (root / split / 'labels' / f'{stem}.txt').write_text(
                f'{class_id} 0.5 0.5 0.4 0.4\n', encoding='utf-8')

    def test_source_names_remove_roboflow_hash(self):
        path = Path('Screenshot_12.rf.0123456789abcdef0123456789abcdef.jpg')
        self.assertEqual(source_name(path), 'Screenshot_12')
        self.assertEqual(source_family(path), 'screenshot')

    def test_audit_counts_splits_classes_and_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_dataset(root)
            report = audit_dataset(root)
            self.assertEqual(report['total_images'], 3)
            self.assertEqual(report['total_boxes'], 3)
            self.assertEqual(report['class_instances'], {'no stroke': 1, 'stroke': 2})
            self.assertEqual(report['issues'], [])
            self.assertEqual(report['source_families_across_splits']['screenshot'],
                             ['test', 'train', 'valid'])


class RoboflowAccessTests(unittest.TestCase):
    def test_third_report_is_loaded_only_after_password(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            roboflow = root / 'roboflow.json'
            expected = {'schema': 'roboflow-object-detection-report-v1', 'test': {}}
            roboflow.write_text(json.dumps(expected), encoding='utf-8')
            access = DevAccess(root / 'missing-rehab.json')
            with self.assertRaises(PermissionError):
                access.unlock_all_reports('wrong', root / 'missing-volunteer.json', roboflow)
            rehab, volunteers, actual = access.unlock_all_reports(
                '676767', root / 'missing-volunteer.json', roboflow)
            self.assertIsNone(rehab)
            self.assertIsNone(volunteers)
            self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
