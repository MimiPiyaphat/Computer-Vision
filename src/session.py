"""UI-independent session boundary. Only the worker calls this object."""

import sqlite3

from config import (CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT,
                    FEATURE_STORE_DIR, CAPTURE_STATION_ID)


class ScreeningSession:
    def __init__(self, camera_index=CAMERA_INDEX, debug=False, research=False):
        self.camera_index = camera_index
        self.debug = debug
        self.cap = self.face = self.arm = self.flow = None
        self.identity_model = None
        self._identity_failure = None
        self.assessment = None
        self.save_status = ""
        self.research = research
        self.workflow = None
        self.comparison = None
        self.care_message = ""
        self._latched_alert = None
        self._evaluated_features = None

    def open(self):
        # Lazy imports allow UI preview and controller tests without CV packages.
        import cv2
        from src.face_analytics import FaceAnalyzer
        from src.arm_pose import ArmPoseAnalyzer
        from src.screening_flow import ScreeningFlow
        self.cap = cv2.VideoCapture(self.camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        if not self.cap.isOpened():
            raise RuntimeError("Camera unavailable. Close other camera apps or change the camera index.")
        self.face = FaceAnalyzer()
        self.arm = ArmPoseAnalyzer()
        self.flow = ScreeningFlow(self.face, self.arm)
        from src.face_identity import FaceIdentity
        from src.feature_store import FeatureStore
        from src.protocol import pipeline_signature
        from src.visit_workflow import VisitWorkflow
        context = {"pipeline": pipeline_signature(), "camera": self.camera_index,
                   "width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                   "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), "station": CAPTURE_STATION_ID}
        if self.research:
            context["pipeline"] += "-research-sideways-arms-v1"
        directory = FEATURE_STORE_DIR + "-research" if self.research else FEATURE_STORE_DIR
        self.workflow = VisitWorkflow(FeatureStore(directory), context, research=self.research)
        self.identity_model = FaceIdentity()

    def start(self, request=None):
        from src.protocol import CARE_MESSAGE
        # Set the care message even if the requested comparison is blocked.
        if request and request.get("symptoms_reported") is True:
            self.care_message = CARE_MESSAGE
        self.workflow.begin(request)
        self.care_message = CARE_MESSAGE if request.get("symptoms_reported") else ""
        self.assessment = None
        self.save_status = ""
        self.comparison = None
        self._latched_alert = None
        self._evaluated_features = None
        self._identity_failure = None
        self.flow.start()

    def stop(self):
        from src.screening_flow import ScreeningFlow
        self.flow = ScreeningFlow(self.face, self.arm)
        self.assessment = None
        self.save_status = ""
        self.comparison = None
        self._identity_failure = None
        if self.workflow:
            self.workflow.request = None
            self.workflow.identity_verified = False
        # Stopping a test must not dismiss a symptom message.

    def _identity_gate(self, frame):
        """Verify before each paired acquisition frame, including the arm hold.

        2026-09-11: missing faces pause acquisition; a nonmatch latches rejection.
        This checks identity consistency, not liveness or replay resistance.
        """
        if not self.workflow.request or not self.flow.is_active():
            return None
        from src.face_identity import IdentityMismatch, MISMATCH_MESSAGE
        reason = self._identity_failure
        if reason is None:
            self.workflow.identity_verified = False
            try:
                if self.face._observe(frame) is None:
                    raise ValueError("Identity check: keep one complete face visible, facing forward (within 18 degrees), including during the arm hold.")
                vector = self.identity_model.embed(frame, self.face._last_landmarks)
                self.workflow.accept_identity(vector, self.identity_model.signature)
                return None
            except IdentityMismatch:
                reason = self._identity_failure = MISMATCH_MESSAGE
                self._latched_alert = None
                self.comparison = {"status": "identity_rejected", "reason": reason, "alert": False}
                self.assessment = {"level": "Identity mismatch", "reasons": [reason],
                                   "disclaimer": self.care_message or "Restart with the registered customer. Face matching does not establish liveness."}
                self.save_status = "Capture rejected; no recheck or delta saved."
                # Remove measurements from the failed attempt without writing them.
                self.flow.features.clear()
                self.flow.research_angles.clear()
            except ValueError as exc:
                reason = str(exc)
        # Paused wall-clock time must not advance detected-time acquisition.
        self.flow._last_detected_at = None
        if self.flow.state == "arm_test":
            # Arm hold uses its own clock: restart that hold after identity loss.
            self.arm.start_test()
            for key in ("left_arm_drift", "right_arm_drift", "arm_lift_skew"):
                self.flow.features.pop(key, None)
            self.flow.research_angles.clear()
        return {"state": "identity_rejected" if self._identity_failure else "identity_check",
                "instruction": reason, "elapsed": 0, "extra": {"detected": False}}

    def read(self):
        import cv2
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("Camera disconnected or failed to return a frame. Reconnect to try again.")
        frame = cv2.flip(frame, 1)
        if (frame.shape[1] != self.workflow.context["width"] or frame.shape[0] != self.workflow.context["height"]):
            raise RuntimeError("Camera resolution changed during acquisition. Reconnect; comparison is inconclusive.")
        identity_ui = self._identity_gate(frame)
        ui = identity_ui or self.flow.update(frame)
        if self.research and ui["state"] == "arm_test":
            ui["instruction"] = "Demo angle: start arms down, then lift OUT TO THE SIDES to shoulder height and hold; keep wrists visible"
        if self.debug:
            if ui["state"] in ("quality_gate", "neutral_capture", "mouth_test", "eye_closure", "eye_test"):
                frame = self.face.draw_debug(frame)
            elif ui["state"] == "arm_test":
                frame = self.arm.draw_debug(frame)
        if identity_ui is None and self.workflow.request and self.workflow.request["mode"] == "recheck" and self.flow.features:
            angles = self.flow.research_angles if self.research else None
            signature = repr((self.flow.features, angles))
            if signature != self._evaluated_features:
                self._evaluated_features = signature
                try:
                    self.comparison = self.workflow.compare(self.flow.features, self.flow.setup, partial=True, research_angles=angles)
                    if self.comparison["alert"]:
                        self._latched_alert = self.comparison
                except ValueError as exc:
                    self.comparison = {"status": "inconclusive", "reason": str(exc), "alert": False}
        if ui["state"] == "summary" and self.assessment is None:
            from src.protocol import CARE_MESSAGE
            try:
                self.comparison = self.workflow.finish(self.flow.features, self.flow.setup,
                                                       research_angles=self.flow.research_angles if self.research else None)
                self.save_status = "Saved numeric measurements; baseline identity embedding is stored separately. No images or video saved."
            except (ValueError, OSError, sqlite3.Error) as exc:
                self.comparison = {"status": "inconclusive", "reason": str(exc), "alert": False}
                self.save_status = "No complete feature record was saved."
            result = self._latched_alert or self.comparison
            labels = {"baseline_saved": "Baseline saved", "delta_alert": "Seek medical attention immediately",
                      "threshold_unconfigured": "Delta measured; threshold unconfigured",
                      "below_threshold": "Below delta threshold; symptoms still need care",
                      "inconclusive": "Comparison inconclusive",
                      "research_alert": "Research rule exceeded; seek medical attention for symptoms",
                      "research_below_placeholder": "Below demo rules; NOT medical clearance",
                      "research_incomplete": "Research comparison incomplete"}
            reasons = [result.get("reason", "Feature change exceeded the configured threshold.")]
            if result.get("research_only"):
                m = result["research_measurement"]
                angle = m["arm_angle_delta_deg"]
                reasons.append(f"Face delta {result['measurement']['face_delta']:.4f} / rule {m['face_delta_threshold']:.4f}")
                reasons.append(f"2D arm-angle delta: {angle:.1f} degrees / rule {m['arm_angle_delta_threshold_deg']:.1f}" if angle is not None else "2D arm angle unavailable; forearm pronation is not measured.")
            elif result.get("measurement"):
                m = result["measurement"]
                reasons.append(f"Face delta {m['face_delta']:.4f} + arm delta {m['arm_delta']:.4f} = {m['score']:.4f}")
            self.assessment = {"level": labels[result["status"]], "reasons": reasons,
                               "disclaimer": CARE_MESSAGE if self.workflow.request["mode"] == "recheck" else
                               "This is a reference measurement, not medical clearance for massage."}
        return {**ui, "frame": cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                "assessment": self.assessment, "save_status": self.save_status,
                "comparison": self._latched_alert or self.comparison, "care_message": self.care_message,
                "research_rules": self.workflow.research_parameters if self.research and self.workflow else None,
                "visit_mode": self.workflow.request["mode"] if self.workflow and self.workflow.request else None}

    def close(self):
        # Attempt every cleanup even if an individual native resource fails.
        errors = []
        for name, method in (("cap", "release"), ("face", "close"), ("arm", "close"), ("identity_model", "close")):
            resource = getattr(self, name)
            if resource is not None:
                try:
                    getattr(resource, method)()
                except Exception as exc:
                    errors.append(exc)
                finally:
                    setattr(self, name, None)
        if errors:
            raise RuntimeError("; ".join(str(error) for error in errors))
