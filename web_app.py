"""Responsive browser UI for the existing StrokeVision research pipeline.

The browser owns the camera and sends one JPEG frame at a time. All feature
extraction, identity checks, storage and before/after decisions remain in the
same Python modules used by the desktop application.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import secrets
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import cv2
import numpy as np

from config import CAPTURE_STATION_ID, FRAME_HEIGHT, FRAME_WIDTH
from ui.content import STEPS
from ui.thai import customer_assessment, customer_result_status, display_text


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
MAX_FRAME_BYTES = 3 * 1024 * 1024


def _jsonable(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items() if key != "frame"}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def snapshot_payload(snapshot):
    """Return browser-safe state without returning or storing camera pixels."""
    state = snapshot.get("state", "idle")
    acquisition_state = snapshot.get("acquisition_state", state)
    stage_key = acquisition_state if acquisition_state in {item[0] for item in STEPS} else state
    stage_index = next((index for index, item in enumerate(STEPS) if item[0] == stage_key), None)
    duration = STEPS[stage_index][3] if stage_index is not None else 0
    elapsed = float(snapshot.get("elapsed") or 0)
    if state == "summary":
        overall_progress = 1.0
    elif stage_index is None:
        overall_progress = 0.0
    else:
        within = min(1.0, elapsed / duration) if duration else 0.0
        overall_progress = min(1.0, (stage_index + within) / max(1, len(STEPS) - 1))

    stages = []
    for index, (key, label, instruction, seconds) in enumerate(STEPS):
        status = "waiting"
        if stage_index is not None:
            status = "done" if index < stage_index else "active" if index == stage_index else "waiting"
        if state == "summary":
            status = "done"
        stages.append({"key": key, "label": label, "instruction": instruction,
                       "duration": seconds, "status": status})

    assessment = snapshot.get("assessment")
    comparison = snapshot.get("comparison")
    result = None
    if isinstance(assessment, dict):
        title, body = customer_assessment(assessment, comparison)
        result = {"title": title, "body": body,
                  "status": customer_result_status(assessment, comparison)}

    instruction = display_text(snapshot.get("instruction", ""))
    if not instruction and stage_index is not None:
        instruction = STEPS[stage_index][2]
    payload = {
        "state": state,
        "acquisition_state": acquisition_state,
        "visit_mode": snapshot.get("visit_mode"),
        "instruction": instruction,
        "elapsed": elapsed,
        "duration": duration,
        "progress": overall_progress,
        "stage_index": stage_index,
        "stages": stages,
        "extra": snapshot.get("extra") or {},
        "result": result,
        "save_status": snapshot.get("save_status", ""),
        "care_message": display_text(snapshot.get("care_message", "")),
    }
    return _jsonable(payload)


class WebRuntime:
    """Single-station session manager; requests are serialized for CV safety."""

    def __init__(self, session_factory=None):
        self._session_factory = session_factory
        self._session = None
        self._lock = threading.RLock()

    def _new_session(self):
        if self._session_factory is not None:
            return self._session_factory()
        from src.session import ScreeningSession
        return ScreeningSession(research=True)

    def connect(self, width=FRAME_WIDTH, height=FRAME_HEIGHT, client_id=""):
        width, height = int(width), int(height)
        if not isinstance(client_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{8,64}", client_id):
            raise ValueError("Browser station ID is invalid. Reload the page and try again.")
        station = f"{CAPTURE_STATION_ID}-web-{client_id}"
        with self._lock:
            self._close_unlocked()
            session = self._new_session()
            try:
                session.open_frames(width, height, station=station)
            except Exception:
                try:
                    session.close()
                finally:
                    raise
            self._session = session
            return {"connected": True, "width": width, "height": height}

    def start(self, request):
        with self._lock:
            session = self._require_session()
            session.start(request)
            return {"started": True, "mode": request.get("mode")}

    def frame(self, encoded):
        if not encoded or len(encoded) > MAX_FRAME_BYTES:
            raise ValueError("Camera frame is empty or too large.")
        frame = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Camera frame could not be decoded.")
        with self._lock:
            return snapshot_payload(self._require_session().read_frame(frame, mirror=True))

    def stop(self):
        with self._lock:
            self._require_session().stop()
            return {"stopped": True}

    def disconnect(self):
        with self._lock:
            self._close_unlocked()
            return {"connected": False}

    def status(self):
        with self._lock:
            return {"connected": self._session is not None}

    def _require_session(self):
        if self._session is None:
            raise RuntimeError("กรุณาเชื่อมต่อกล้องก่อนเริ่มตรวจ")
        return self._session

    def _close_unlocked(self):
        if self._session is not None:
            try:
                self._session.close()
            finally:
                self._session = None


class StrokeVisionHandler(BaseHTTPRequestHandler):
    runtime = None
    access_key = ""
    static_files = {
        "/": ("index.html", "text/html; charset=utf-8"),
        "/index.html": ("index.html", "text/html; charset=utf-8"),
        "/app.js": ("app.js", "text/javascript; charset=utf-8"),
        "/style.css": ("style.css", "text/css; charset=utf-8"),
    }

    def log_message(self, format_, *args):
        print(f"[web] {self.address_string()} - {format_ % args}")

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self'; script-src 'self'")

    def _authorized(self):
        supplied = self.headers.get("X-Access-Key", "")
        return bool(supplied) and hmac.compare_digest(supplied, self.access_key)

    def _send_json(self, status, value):
        encoded = json.dumps(_jsonable(value), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 64 * 1024:
            raise ValueError("Invalid request size.")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/healthz":
            return self._send_json(200, {"status": "ok"})
        if path == "/api/status":
            if not self._authorized():
                return self._send_json(401, {"error": "Access key ไม่ถูกต้อง"})
            return self._send_json(200, self.runtime.status())
        target = self.static_files.get(path)
        if target is None:
            return self._send_json(404, {"error": "Not found"})
        filename, content_type = target
        encoded = (WEB_ROOT / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        path = urlsplit(self.path).path
        if not self._authorized():
            return self._send_json(401, {"error": "Access key ไม่ถูกต้อง กรุณาเปิดลิงก์ที่โปรแกรมแสดง"})
        try:
            if path == "/api/connect":
                body = self._read_json()
                result = self.runtime.connect(body.get("width", FRAME_WIDTH), body.get("height", FRAME_HEIGHT),
                                              body.get("client_id", ""))
            elif path == "/api/start":
                result = self.runtime.start(self._read_json())
            elif path == "/api/frame":
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_FRAME_BYTES:
                    raise ValueError("Camera frame is empty or too large.")
                result = self.runtime.frame(self.rfile.read(length))
            elif path == "/api/stop":
                result = self.runtime.stop()
            elif path == "/api/disconnect":
                result = self.runtime.disconnect()
            else:
                return self._send_json(404, {"error": "Not found"})
            self._send_json(200, result)
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": display_text(str(exc))})
        except RuntimeError as exc:
            self._send_json(409, {"error": display_text(str(exc))})
        except Exception as exc:
            self._send_json(500, {"error": f"ระบบทำงานผิดพลาด: {exc}"})


def create_server(host, port, access_key, runtime=None):
    handler = type("ConfiguredStrokeVisionHandler", (StrokeVisionHandler,), {
        "runtime": runtime or WebRuntime(),
        "access_key": access_key,
    })
    return ThreadingHTTPServer((host, port), handler)


def main():
    parser = argparse.ArgumentParser(description="Run the StrokeVision browser interface.")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                        help="Bind address; use 0.0.0.0 only with HTTPS or a trusted host.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--key", default=os.environ.get("STROKEVISION_ACCESS_KEY", ""),
                        help="Optional access key; a random key is generated by default.")
    parser.add_argument("--certfile", help="TLS certificate PEM for direct HTTPS.")
    parser.add_argument("--keyfile", help="TLS private key PEM for direct HTTPS.")
    args = parser.parse_args()
    if bool(args.certfile) != bool(args.keyfile):
        parser.error("--certfile and --keyfile must be supplied together")
    if os.environ.get("RENDER") and not args.key:
        parser.error("STROKEVISION_ACCESS_KEY must be set on Render")
    access_key = args.key or secrets.token_urlsafe(18)
    server = create_server(args.host, args.port, access_key)
    scheme = "https" if args.certfile else "http"
    if args.certfile:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.certfile, args.keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    display_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    print("StrokeVision web พร้อมใช้งาน")
    print(f"เปิดบนคอม: {scheme}://{display_host}:{args.port}/?key={access_key}")
    print("กล้องมือถือจำเป็นต้องเปิดผ่าน HTTPS โปรดดูวิธีใน README.md")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nกำลังปิด StrokeVision web...")
    finally:
        server.RequestHandlerClass.runtime.disconnect()
        server.server_close()


if __name__ == "__main__":
    main()
