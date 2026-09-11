"""Single owner for camera/models; bounded snapshots keep the UI responsive."""

from queue import Empty, Queue
from threading import Event, Thread
import time


class SessionWorker:
    def __init__(self, session):
        self.session = session
        self.commands = Queue()
        self.snapshots = Queue(maxsize=1)
        self.closed = Event()
        self.thread = Thread(target=self._run, daemon=True, name="screening")

    def start(self):
        self.thread.start()

    def send(self, command):
        self.commands.put(command)

    def close(self):
        self.closed.set()

    def latest(self):
        try:
            return self.snapshots.get_nowait()
        except Empty:
            return None

    def _publish(self, snapshot):
        try:
            self.snapshots.get_nowait()
        except Empty:
            pass
        self.snapshots.put_nowait(snapshot)

    def _run(self):
        command_error = ""
        try:
            self._publish({"status": "loading"})
            self.session.open()
            previous = time.monotonic()
            while not self.closed.is_set():
                try:
                    while True:
                        command = self.commands.get_nowait()
                        try:
                            if isinstance(command, dict) and command.get("action") == "start":
                                self.session.start(command.get("request"))
                            elif command == "start":
                                self.session.start()
                            elif command == "stop":
                                self.session.stop()
                            elif command == "debug":
                                self.session.debug = not self.session.debug
                            command_error = ""
                        except ValueError as exc:
                            command_error = str(exc)  # Keep the camera usable after form errors.
                except Empty:
                    pass
                snapshot = self.session.read()
                snapshot["command_error"] = command_error
                now = time.monotonic()
                snapshot.update(status="ready", fps=round(1 / max(now - previous, .001), 1))
                previous = now
                self._publish(snapshot)
                self.closed.wait(.015)
        except Exception as exc:
            self._publish({"status": "error", "message": str(exc)})
        finally:
            try:
                self.session.close()
            except Exception as exc:
                self._publish({"status": "error", "message": f"Cleanup failed: {exc}"})
