"""UI-independent session boundary. Only the worker calls this object."""

import sqlite3
from src.acquisition import SaveFailure

from config import (CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT,
                    FEATURE_STORE_DIR, CAPTURE_STATION_ID,
                    IDENTITY_REACQUIRE_MATCH_FRAMES, IDENTITY_REJECT_MISMATCH_FRAMES)


class ScreeningSession:
    def __init__(self, camera_index=CAMERA_INDEX, debug=False, research=False):
        self.camera_index = camera_index
        self.debug = debug
        self.cap = self.face = self.arm = self.flow = None
        self.identity_model = None
        self._identity_failure = None
        self._identity_reacquiring = False
        self._identity_match_streak = 0
        self._identity_mismatch_streak = 0
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
        self.arm = ArmPoseAnalyzer(require_angles=self.research)
        self.flow = ScreeningFlow(self.face, self.arm, require_angles=self.research)
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
        # A new start attempt must never retain the previous visit's result,
        # including when validation rejects the request before acquisition.
        self.assessment = None
        self.save_status = ""
        self.comparison = None
        self._latched_alert = None
        self._evaluated_features = None
        try:
            self.workflow.begin(request)
        except Exception:
            # Keep lightweight controller doubles intact, while a real flow is
            # reset so an invalid start cannot fall through to the old summary.
            if isinstance(getattr(self.flow, "state", None), str):
                from src.screening_flow import ScreeningFlow
                self.flow = ScreeningFlow(self.face, self.arm, require_angles=self.research)
            raise
        self.care_message = CARE_MESSAGE if request.get("symptoms_reported") else ""
        self._identity_failure = None
        self._identity_reacquiring = False
        self._identity_match_streak = 0
        self._identity_mismatch_streak = 0
        self.flow.start()

    def stop(self):
        from src.screening_flow import ScreeningFlow
        self.flow = ScreeningFlow(self.face, self.arm, require_angles=self.research)
        self.assessment = None
        self.save_status = ""
        self.comparison = None
        self._identity_failure = None
        self._identity_reacquiring = False
        self._identity_match_streak = 0
        self._identity_mismatch_streak = 0
        if self.workflow:
            self.workflow.request = None
            self.workflow.identity_verified = False
        # Stopping a test must not dismiss a symptom message.

    def _identity_gate(self, frame):
        """Verify before each paired acquisition frame, including the arm hold.

        Missing faces pause acquisition. Re-entry requires several matching
        frames; rejection requires several consecutive nonmatching frames.
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
                self.workflow.accept_identity(vector, self.identity_model.signature, latch_mismatch=False)
                self._identity_mismatch_streak = 0
                if self._identity_reacquiring:
                    self._identity_match_streak += 1
                    if self._identity_match_streak < IDENTITY_REACQUIRE_MATCH_FRAMES:
                        self.workflow.identity_verified = False
                        reason = "Identity check: hold still while confirming the returning person."
                    else:
                        self._identity_reacquiring = False
                        self._identity_match_streak = 0
                        return None
                else:
                    self._identity_match_streak = 0
                    return None
            except IdentityMismatch:
                self._identity_reacquiring = True
                self._identity_match_streak = 0
                self._identity_mismatch_streak += 1
                if self._identity_mismatch_streak < IDENTITY_REJECT_MISMATCH_FRAMES:
                    reason = "Identity check: hold still while confirming the returning person."
                else:
                    self.workflow.reject_identity()
                    reason = self._identity_failure = MISMATCH_MESSAGE
                    self._latched_alert = None
                    self.comparison = {"status": "identity_rejected", "reason": reason, "alert": False}
                    self.assessment = {"level": "Identity mismatch", "reasons": [reason],
                                       "disclaimer": self.care_message or "Restart with the registered customer. Face matching does not establish liveness."}
                    self.save_status = "Capture rejected; no recheck or delta saved."
                    # Remove measurements from the confirmed failed attempt without writing them.
                    self.flow.features.clear()
                    self.flow.research_angles.clear()
                    if hasattr(self.flow, "arm_function") and isinstance(self.flow.arm_function, dict):
                        self.flow.arm_function.clear()
            except ValueError as exc:
                self._identity_reacquiring = True
                self._identity_match_streak = 0
                self._identity_mismatch_streak = 0
                reason = str(exc)
        # Paused wall-clock time must not advance detected-time acquisition.
        self.flow._last_detected_at = None
        if self.flow.state == "arm_test":
            # Arm hold uses its own clock: restart that hold after identity loss.
            self.arm.start_test()
            for key in ("left_arm_drift", "right_arm_drift", "arm_lift_skew"):
                self.flow.features.pop(key, None)
            self.flow.research_angles.clear()
            if hasattr(self.flow, "arm_function") and isinstance(self.flow.arm_function, dict):
                self.flow.arm_function.clear()
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
        # The gate acquired this frame's mesh before accepting identity. Reuse
        # that exact observation, never a cache from a previous camera frame.
        face_observed = bool(self.workflow.request and self.flow.is_active() and identity_ui is None)
        if identity_ui is not None:
            timeout_ui = self.flow.check_timeout(reason_code="identity_unavailable")
            ui = timeout_ui if isinstance(timeout_ui, dict) else identity_ui
        else:
            ui = self.flow.update(frame, face_observed=face_observed)
        if self.debug:
            if ui["state"] in ("quality_gate", "neutral_capture", "mouth_test", "eye_closure", "eye_test"):
                frame = self.face.draw_debug(frame)
            elif ui["state"] == "arm_test":
                frame = self.arm.draw_debug(frame)
        if identity_ui is None and self.workflow.request and self.workflow.request["mode"] == "recheck" and self.flow.features:
            angles = self.flow.research_angles if self.research else None
            arm_function = getattr(self.flow, "arm_function", None)
            if not isinstance(arm_function, dict):
                arm_function = None
            signature = repr((self.flow.features, angles, arm_function))
            if signature != self._evaluated_features:
                self._evaluated_features = signature
                try:
                    self.comparison = self.workflow.compare(self.flow.features, self.flow.setup, partial=True,
                                                            research_angles=angles, arm_function=arm_function)
                    if self.comparison["alert"]:
                        self._latched_alert = self.comparison
                except ValueError as exc:
                    self.comparison = {"status": "inconclusive", "reason": str(exc), "alert": False}
        if ui["state"] == "summary" and self.assessment is None:
            from src.protocol import CARE_MESSAGE
            if isinstance(self.flow.failure, dict):
                self.comparison = {"status": "acquisition_failed", "reason": self.flow.failure["reason"], "alert": False,
                                   "reason_code": self.flow.failure["reason_code"],
                                   "symptoms_reported": self.workflow.request.get("symptoms_reported") is True}
                if self._latched_alert:
                    self.comparison["prior_alert"] = self._latched_alert
                    self.comparison["alert"] = True
                self.save_status = "ยังไม่มีการบันทึกข้อมูล เนื่องจากเก็บข้อมูลไม่ครบ"
            else:
                try:
                    arm_function = getattr(self.flow, "arm_function", None)
                    if not isinstance(arm_function, dict):
                        arm_function = None
                    self.comparison = self.workflow.finish(self.flow.features, self.flow.setup,
                                                           research_angles=self.flow.research_angles if self.research else None,
                                                           arm_function=arm_function)
                    self.save_status = "บันทึกข้อมูลแล้ว"
                except SaveFailure as exc:
                    measured = exc.comparison or {"reason": str(exc), "alert": False}
                    self.comparison = {**measured, "status": "save_failed", "save_failed": True,
                                       "save_reason": str(exc), "measurement_result": measured.get("status")}
                    self.save_status = "บันทึกข้อมูลไม่สำเร็จ"
                except (ValueError, OSError, sqlite3.Error) as exc:
                    self.comparison = {"status": "inconclusive", "reason": str(exc), "alert": False,
                                       "symptoms_reported": self.workflow.request.get("symptoms_reported") is True}
                    self.save_status = "บันทึกข้อมูลไม่สำเร็จ" if isinstance(exc, (OSError, sqlite3.Error)) else "ยังไม่สามารถประเมินผลได้"
            result = (self.comparison if self.comparison.get("status") in ("acquisition_failed", "save_failed")
                      else self._latched_alert or self.comparison)
            labels = {"baseline_saved": "Baseline saved", "delta_alert": "Seek medical attention immediately",
                      "threshold_unconfigured": "Delta measured; threshold unconfigured",
                      "below_threshold": "Below delta threshold; symptoms still need care",
                      "inconclusive": "Comparison inconclusive",
                      "research_alert": "Research rule exceeded; seek medical attention for symptoms",
                      "research_below_placeholder": "Below demo rules; NOT medical clearance",
                      "research_incomplete": "Research comparison incomplete",
                      "acquisition_failed": "เก็บข้อมูลไม่ครบ · ติดต่อเจ้าหน้าที่",
                      "save_failed": "บันทึกข้อมูลไม่สำเร็จ · ติดต่อเจ้าหน้าที่"}
            reasons = [result.get("reason", "Feature change exceeded the configured threshold.")]
            if result.get("research_only"):
                m = result["research_measurement"]
                angle = m["arm_angle_delta_deg"]
                reasons.append(f"Face asymmetry increase {m['face_asymmetry_increase']:.4f} / rule {m['face_delta_threshold']:.4f}")
                reasons.append(f"2D arm-angle delta: {angle:.1f} degrees / rule {m['arm_angle_delta_threshold_deg']:.1f}" if angle is not None else "2D arm angle unavailable; forearm pronation is not measured.")
                arm_status = m.get("arm_function_status")
                if arm_status == "normal":
                    reasons.append("Arm function: normal raise and hold completed.")
                elif arm_status == "unable_to_raise":
                    reasons.append("Arm function: both arms did not reach the required raised position within the test time.")
                elif arm_status == "unable_to_hold":
                    reasons.append("Arm function: both arms reached the raised position but were not held for the required time.")
            elif result.get("measurement"):
                m = result["measurement"]
                reasons.append(f"Face delta {m['face_delta']:.4f} + arm delta {m['arm_delta']:.4f} = {m['score']:.4f}")
            urgent = self.workflow.request.get("symptoms_reported") is True or result.get("alert") is True
            self.assessment = {"level": labels.get(result["status"], result["status"]), "reasons": reasons,
                               "disclaimer": CARE_MESSAGE if urgent else
                               "This comparison is a monitoring aid, not a diagnosis or medical clearance for massage."}
        visible_comparison = (self.comparison if isinstance(self.comparison, dict) and
                              self.comparison.get("status") in ("acquisition_failed", "save_failed")
                              else self._latched_alert or self.comparison)
        return {**ui, "acquisition_state": self.flow.state, "frame": cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                "assessment": self.assessment, "save_status": self.save_status,
                "comparison": visible_comparison, "care_message": self.care_message,
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
