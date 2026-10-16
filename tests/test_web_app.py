import json
import threading
import unittest
import urllib.error
import urllib.request

import cv2
import numpy as np

from web_app import WebRuntime, create_server, snapshot_payload


class FakeSession:
    def __init__(self):
        self.opened = None
        self.request = None
        self.closed = False
        self.stopped = False

    def open_frames(self, width, height, station=None):
        self.opened = (width, height, station)

    def start(self, request):
        self.request = request

    def read_frame(self, frame, mirror=True):
        return {"state": "neutral_capture", "acquisition_state": "neutral_capture",
                "instruction": "Relax your face and look straight ahead.", "elapsed": 1.0,
                "extra": {"detected": True}, "frame": np.zeros((2, 2, 3), dtype=np.uint8),
                "assessment": None, "comparison": None, "save_status": "", "care_message": "",
                "visit_mode": "baseline"}

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


class WebPayloadTests(unittest.TestCase):
    def test_snapshot_removes_frame_and_builds_progress(self):
        payload = snapshot_payload(FakeSession().read_frame(None))
        self.assertNotIn("frame", payload)
        self.assertEqual(payload["stage_index"], 1)
        self.assertEqual(payload["stages"][1]["status"], "active")
        self.assertGreater(payload["progress"], 0)

    def test_customer_result_is_localized(self):
        payload = snapshot_payload({"state": "summary", "acquisition_state": "summary",
                                    "instruction": "", "elapsed": 0, "extra": {},
                                    "assessment": {"level": "Baseline saved", "reasons": [], "disclaimer": ""},
                                    "comparison": {"status": "baseline_saved", "alert": False},
                                    "save_status": "บันทึกข้อมูลแล้ว", "care_message": "", "visit_mode": "baseline"})
        self.assertIn("ก่อนนวด", payload["result"]["title"])
        self.assertEqual(payload["progress"], 1.0)


class WebRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.created = []
        self.runtime = WebRuntime(lambda: self._make_session())

    def _make_session(self):
        session = FakeSession()
        self.created.append(session)
        return session

    def test_runtime_connect_start_frame_stop_and_disconnect(self):
        self.runtime.connect(640, 480, "browser-test-01")
        session = self.created[-1]
        self.assertEqual(session.opened, (640, 480, "station-01-web-browser-test-01"))
        request = {"mode": "baseline", "user_id": "u", "visit_id": "v", "setup_confirmed": True}
        self.runtime.start(request)
        ok, encoded = cv2.imencode(".jpg", np.zeros((480, 640, 3), dtype=np.uint8))
        self.assertTrue(ok)
        self.assertEqual(self.runtime.frame(encoded.tobytes())["state"], "neutral_capture")
        self.runtime.stop()
        self.assertTrue(session.stopped)
        self.runtime.disconnect()
        self.assertTrue(session.closed)

    def test_connect_closes_previous_session(self):
        self.runtime.connect(640, 480, "browser-test-01")
        first = self.created[-1]
        self.runtime.connect(640, 480, "browser-test-01")
        self.assertTrue(first.closed)


class WebServerTests(unittest.TestCase):
    def setUp(self):
        self.server = create_server("127.0.0.1", 0, "test-key", WebRuntime(lambda: FakeSession()))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_static_page_is_served(self):
        with urllib.request.urlopen(self.base + "/", timeout=2) as response:
            text = response.read().decode("utf-8")
        self.assertIn("StrokeVision", text)
        self.assertIn("viewport", text)

    def test_health_check_does_not_require_access_key(self):
        with urllib.request.urlopen(self.base + "/healthz", timeout=2) as response:
            data = json.loads(response.read())
        self.assertEqual(data, {"status": "ok"})

    def test_api_requires_access_key(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.base + "/api/status", timeout=2)
        self.assertEqual(caught.exception.code, 401)

    def test_connect_api(self):
        request = urllib.request.Request(self.base + "/api/connect", method="POST",
                                         data=json.dumps({"width": 640, "height": 480,
                                                          "client_id": "browser-test-01"}).encode(),
                                         headers={"Content-Type": "application/json", "X-Access-Key": "test-key"})
        with urllib.request.urlopen(request, timeout=2) as response:
            data = json.loads(response.read())
        self.assertTrue(data["connected"])


if __name__ == "__main__":
    unittest.main()
