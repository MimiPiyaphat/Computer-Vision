"""Behavioral checks that work without CV libraries, camera, or a display."""

import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from src.session import ScreeningSession
from ui.preview import PreviewSession
from ui.theme import load_theme
from ui.worker import SessionWorker


class ThemeTests(unittest.TestCase):
    def test_invalid_reload_does_not_mutate_existing_tokens(self):
        original = load_theme()
        invalid = dict(original, accent="not a color")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "theme.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "accent"):
                load_theme(path)
        self.assertEqual(original, load_theme())

    def test_spacing_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "theme.json"
            path.write_text(json.dumps(dict(load_theme(), spacing=-1)), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "spacing"):
                load_theme(path)


class PreviewTests(unittest.TestCase):
    def test_preview_reaches_summary_and_can_restart_and_stop(self):
        session = PreviewSession()
        session.open()
        self.assertEqual(session.read()["state"], "idle")
        with patch("ui.preview.time.monotonic", return_value=10) as clock:
            session.start()
            for expected in ("neutral_capture", "mouth_test", "eye_closure", "eye_test", "arm_test", "summary"):
                clock.return_value += 3
                snapshot = session.read()
                self.assertEqual(snapshot["state"], expected)
            self.assertEqual(snapshot["assessment"]["level"], "Preview only")
            session.start()
            self.assertIsNone(session.read()["assessment"])
            session.stop()
            self.assertEqual(session.read()["state"], "idle")


class SessionTests(unittest.TestCase):
    def make_session(self):
        session = ScreeningSession()
        session.cap = Mock()
        frame = SimpleNamespace(shape=(480, 640, 3))
        session.cap.read.return_value = (True, frame)
        session.flow = Mock(features={}, research_angles={})
        session.flow.is_active.return_value = False
        session.flow.update.return_value = {"state": "summary"}
        session.workflow = Mock(context={"width": 640, "height": 480}, request={"mode": "baseline"})
        session.workflow.finish.return_value = {"status": "baseline_saved", "alert": False, "reason": "Saved"}
        cv = Mock()
        cv.flip.return_value = frame
        return session, cv

    def test_paired_summary_saves_once_until_restart(self):
        session, cv = self.make_session()
        with patch.dict("sys.modules", {"cv2": cv}):
            self.assertEqual(session.read()["assessment"]["level"], "Baseline saved")
            session.read()
            session.workflow.finish.assert_called_once()
            session.start({"mode": "baseline"})
            session.read()
            self.assertEqual(session.workflow.finish.call_count, 2)

    def test_save_failure_preserves_inconclusive_summary_without_retry(self):
        session, cv = self.make_session()
        session.workflow.finish.side_effect = OSError("disk full")
        with patch.dict("sys.modules", {"cv2": cv}):
            result = session.read()
            session.read()
        self.assertEqual(result["assessment"]["level"], "Comparison inconclusive")
        self.assertIn("disk full", result["assessment"]["reasons"])
        session.workflow.finish.assert_called_once()

    def test_cleanup_attempts_every_resource_after_failure(self):
        session = ScreeningSession()
        cap, face, arm = Mock(), Mock(), Mock()
        session.cap, session.face, session.arm = cap, face, arm
        face.close.side_effect = RuntimeError("native cleanup failed")
        with self.assertRaises(RuntimeError):
            session.close()
        cap.release.assert_called_once()
        arm.close.assert_called_once()
        self.assertIsNone(session.face)
        session.close()  # Cleanup is idempotent.

    def test_camera_read_failure_is_reported(self):
        session = ScreeningSession()
        session.cap = Mock()
        session.cap.read.return_value = (False, None)
        with patch.dict("sys.modules", {"cv2": Mock()}):
            with self.assertRaisesRegex(RuntimeError, "Camera disconnected"):
                session.read()


class WorkerTests(unittest.TestCase):
    def test_partial_startup_failure_closes_resources_and_reports_error(self):
        session = Mock()
        session.open.side_effect = RuntimeError("model failed")
        worker = SessionWorker(session)
        worker.start()
        worker.thread.join(2)
        self.assertFalse(worker.thread.is_alive())
        self.assertEqual(worker.latest(), {"status": "error", "message": "model failed"})
        session.close.assert_called_once()

    def test_commands_and_shutdown_run_on_worker(self):
        session = Mock()
        session.read.return_value = {"state": "idle"}
        worker = SessionWorker(session)
        worker.send("start")
        worker.send("stop")
        worker.start()
        deadline = time.monotonic() + 2
        snapshot = None
        while time.monotonic() < deadline:
            snapshot = worker.latest()
            if snapshot and snapshot.get("status") == "ready":
                break
            time.sleep(.01)
        worker.close()
        worker.thread.join(2)
        self.assertFalse(worker.thread.is_alive())
        self.assertEqual(snapshot["status"], "ready")
        session.start.assert_called_once()
        session.stop.assert_called_once()
        session.close.assert_called_once()

    def test_only_latest_snapshot_is_kept(self):
        worker = SessionWorker(Mock())
        for value in range(100):
            worker._publish({"value": value})
        self.assertEqual(worker.latest(), {"value": 99})
        self.assertIsNone(worker.latest())


class FlowRegressionTests(unittest.TestCase):
    def test_ear_and_blink_transition(self):
        from src.utils import calculate_ear
        from src.screening_flow import ScreeningFlow
        self.assertAlmostEqual(calculate_ear([(0, 0), (1, 1), (3, 1), (4, 0), (3, -1), (1, -1)]), .5)
        flow = ScreeningFlow(None, None)
        flow._update_blink_counts({"left_closed": True, "right_closed": False})
        flow._update_blink_counts({"left_closed": False, "right_closed": False})
        self.assertEqual(flow._blink_counts, {"left": 1, "right": 0})

    def test_first_summary_frame_contains_every_test(self):
        path = Path(__file__).resolve().parents[1] / "src" / "screening_flow.py"
        spec = importlib.util.spec_from_file_location("flow_under_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"src.face_analytics": Mock()}):
            spec.loader.exec_module(module)
        arm = Mock()
        arm.analyze.return_value = {"test_complete": True}
        flow = module.ScreeningFlow(Mock(), arm)
        flow.results = {"eye": {"ratio": 0}, "mouth": {"ratio": 1}}
        flow.state = module.STATE_ARM_TEST
        snapshot = flow.update(None)
        self.assertEqual(snapshot["state"], "summary")
        self.assertEqual(set(snapshot["extra"]), {"eye", "mouth", "arm"})


if __name__ == "__main__":
    unittest.main()
