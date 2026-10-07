"""Dataset balance, lossless failure handling, and evaluation split boundaries."""

from collections import Counter
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("cv2"), "OpenCV missing")
class DatasetPreparationTests(unittest.TestCase):
    def sources(self, root):
        return [root / f"{exercise}_Exercise" / status / split / f"{subject:02d}_01_01_01.mp4"
                for exercise in range(1, 5) for status in ("Complete", "Incomplete")
                for split in ("Train", "Test") for subject in range(1, 6)]

    def test_selection_covers_every_group_is_reproducible_and_balanced(self):
        from datasets.stroke_rehab.prepare_dataset import select_sources, source_group
        root = Path("source")
        sources = self.sources(root)
        chosen = select_sources(sources, root, 30, seed=42)
        self.assertEqual(chosen, select_sources(list(reversed(sources)), root, 30, seed=42))
        self.assertEqual(len(set(chosen)), 30)
        groups = Counter(source_group(p, root) for p in chosen)
        self.assertEqual(len(groups), 16)
        self.assertEqual(set(groups.values()), {1, 2})
        self.assertEqual(Counter(source_group(p, root)[2] for p in chosen), {"complete": 15, "incomplete": 15})

    def test_failure_never_publishes_partial_output_and_existing_data_is_preserved(self):
        from datasets.stroke_rehab.prepare_dataset import prepare
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            video = self.sources(source)[0]
            video.parent.mkdir(parents=True)
            video.touch()
            output = root / "clips"
            with patch("datasets.stroke_rehab.prepare_dataset.make_clip", side_effect=RuntimeError("bad video")):
                with self.assertRaisesRegex(RuntimeError, "bad video"):
                    prepare(source, output, 1)
            self.assertFalse(output.exists())
            self.assertEqual(list(root.glob(".clips-*")), [])
            output.mkdir()
            marker = output / "existing.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already exists"):
                prepare(source, output, 1)
            self.assertEqual(marker.read_text(), "keep")

    def test_clip_has_five_seconds_of_decodable_frames(self):
        import cv2
        import numpy as np
        from datasets.stroke_rehab.prepare_dataset import make_clip
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "source.mp4", Path(folder) / "clip.mp4"
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 64))
            self.assertTrue(writer.isOpened())
            try:
                for i in range(60):
                    writer.write(np.full((64, 64, 3), i * 3, dtype=np.uint8))
            finally:
                writer.release()
            result = make_clip(source, output)
            cap = cv2.VideoCapture(str(output))
            count = 0
            try:
                while cap.read()[0]:
                    count += 1
            finally:
                cap.release()
            self.assertEqual(count, 50)
            self.assertEqual(result["duration_seconds"], 5)


@unittest.skipUnless(all(importlib.util.find_spec(n) for n in ("torch", "cv2")), "Training dependencies missing")
class TrainingSplitTests(unittest.TestCase):
    def test_training_cli_saves_validation_selected_checkpoint_and_final_test_report(self):
        import cv2
        import numpy as np
        import torch
        from datasets.stroke_rehab.train_classifier import CLASSES, STATUSES, main, VideoNet
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for split, people in (("Train", (1, 2)), ("Test", (3,))):
                for person in people:
                    for status, name in enumerate(STATUSES):
                        path = root / "source" / CLASSES[0] / name / split / f"{person:02d}_01_{status:02d}_01.mp4"
                        path.parent.mkdir(parents=True, exist_ok=True)
                        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 32))
                        self.assertTrue(writer.isOpened())
                        try:
                            for value in (20, 200):
                                writer.write(np.full((32, 32, 3), value, dtype=np.uint8))
                        finally:
                            writer.release()
            output = root / "model.pt"
            arguments = ["train", "--root", str(root / "source"), "--output", str(output),
                         "--epochs", "2", "--frames", "6", "--size", "32", "--cache-dir", str(root / "cache")]
            with patch("sys.argv", arguments), contextlib.redirect_stdout(io.StringIO()):
                main()
            report = json.loads(output.with_suffix(".metrics.json").read_text())
            self.assertEqual(report["selection_metric"], "validation_status_accuracy")
            self.assertEqual([item["split"] for item in report["history"]], ["validation", "validation"])
            self.assertEqual(report["test"]["samples"], 2)
            self.assertFalse(set(report["subjects"]["train"]) & set(report["subjects"]["validation"]))
            checkpoint = torch.load(output, weights_only=True)
            model = VideoNet()
            model.load_state_dict(checkpoint["model"], strict=True)
            self.assertEqual(checkpoint["test_status_accuracy"], report["test"]["status_accuracy"])

    def test_short_video_sampling_retains_uniform_indices_and_rejects_decode_failure(self):
        import numpy as np
        from unittest.mock import Mock
        from datasets.stroke_rehab.train_classifier import sample_video
        cap = Mock()
        cap.get.return_value = 2
        cap.retrieve.side_effect = [(True, np.full((32, 32, 3), value, dtype=np.uint8)) for value in (20, 200)]
        with patch("datasets.stroke_rehab.train_classifier.cv2.VideoCapture", return_value=cap):
            sample = sample_video(Path("short.mp4"), 6, 32)
        self.assertEqual(sample[:, 0, 0, 0].tolist(), [20, 20, 20, 200, 200, 200])
        cap.release.assert_called_once()
        cap = Mock()
        cap.get.return_value = 2
        cap.grab.return_value = False
        with patch("datasets.stroke_rehab.train_classifier.cv2.VideoCapture", return_value=cap):
            with self.assertRaisesRegex(RuntimeError, "decode all"):
                sample_video(Path("broken.mp4"), 6, 32)
        cap.release.assert_called_once()

    def test_all_clips_from_one_person_stay_in_one_partition(self):
        from datasets.stroke_rehab.train_classifier import split_training, subject_key
        records = [(Path(f"{person:02d}_{exercise:02d}_{status:02d}_{clip:02d}.mp4"), exercise, status)
                   for person in range(1, 7) for exercise in range(4) for status in range(2) for clip in range(2)]
        train, validation = split_training(records)
        self.assertFalse({subject_key(r) for r in train} & {subject_key(r) for r in validation})
        self.assertEqual(len(train) + len(validation), len(records))
        self.assertEqual((train, validation), split_training(records))
        with self.assertRaisesRegex(ValueError, "subject"):
            split_training(records[:16])
        with self.assertRaisesRegex(ValueError, "prefix"):
            split_training([(Path("unknown.mp4"), 0, 0)])

    def test_confusion_matrix_uses_actual_rows_and_predicted_columns(self):
        import torch
        from datasets.stroke_rehab.train_classifier import evaluate
        class FixedModel(torch.nn.Module):
            def forward(self, video):
                return torch.tensor([[9., 0, 0, 0], [0., 0, 9, 0]]), torch.tensor([[0., 9], [0., 9]])
        metrics = evaluate(FixedModel(), [(torch.zeros(2, 1), torch.tensor([0, 1]), torch.tensor([0, 1]))], "cpu")
        self.assertEqual(metrics["exercise_accuracy"], .5)
        self.assertEqual(metrics["status_confusion_matrix"], [[0, 1], [0, 1]])
        self.assertEqual(metrics["exercise_confusion_matrix"][1][2], 1)


if __name__ == "__main__":
    unittest.main()
