"""Identity-gated pre/post workflow. No delta can override a symptom report."""

import time
from config import BASELINE_MAX_AGE_HOURS, DELTA_POLICY_PATH, IDENTITY_COSINE_THRESHOLD
from src.features import SCHEMA, delta_features, numeric_map, FEATURE_KEYS, SETUP_KEYS
from src.protocol import CARE_MESSAGE, check_setup, load_policy
from src.research import load_parameters, compare_research
from src.face_identity import identity_payload, cosine_similarity, IdentityMismatch, MISMATCH_MESSAGE


class VisitWorkflow:
    def __init__(self, store, context, policy_path=DELTA_POLICY_PATH, research=False):
        self.store, self.context, self.policy_path = store, context, policy_path
        self.request = None
        self.baseline = None
        self.policy = None
        self.policy_error = ""
        self.keys = None
        self.research = research
        self.research_parameters = load_parameters() if research else None
        self.identity = None
        self.identity_verified = False
        self.identity_rejected = False
        self.identity_similarity = None

    def begin(self, request):
        self.request = self.baseline = self.keys = self.identity = None
        self.identity_verified = self.identity_rejected = False
        self.identity_similarity = None
        if not isinstance(request, dict) or request.get("mode") not in ("baseline", "recheck"):
            raise ValueError("Choose baseline or symptom-triggered recheck.")
        if request.get("setup_confirmed") is not True:
            raise ValueError("Confirm the same camera/station and instructed posture; keep your head facing forward.")
        if request["mode"] == "recheck" and request.get("symptoms_reported") is not True:
            raise ValueError("Rechecks require a customer-reported abnormal symptom.")
        if request["mode"] == "baseline" and request.get("symptoms_reported") is True:
            raise ValueError("Do not establish a routine pre-massage baseline during reported symptoms. " + CARE_MESSAGE)
        keys = self.store.keys(request.get("user_id"), request.get("visit_id"))
        baseline = None
        if request["mode"] == "recheck":
            baseline = self.store.baseline(keys)
            age = time.time() - baseline["created"]
            if not 0 <= age <= BASELINE_MAX_AGE_HOURS * 3600:
                raise ValueError("Baseline is expired or future-dated. Comparison is inconclusive. " + CARE_MESSAGE)
            if baseline["record"]["context"] != self.context:
                raise ValueError("Model, camera, resolution or capture station changed. Comparison is inconclusive. " + CARE_MESSAGE)
            if baseline["identity"] is None:
                raise ValueError("Baseline has no identity embedding. Capture a new baseline under a new visit reference. " + CARE_MESSAGE)
        else:
            try:
                self.store.baseline(keys)
            except ValueError as exc:
                if not str(exc).startswith("No baseline"):
                    raise
            else:
                raise ValueError("A baseline already exists for this visit; use a recheck or a new visit reference.")
        self.policy_error = ""
        try:
            self.policy = load_policy(self.policy_path, self.context["pipeline"])
        except (ValueError, OSError) as exc:
            self.policy = None
            self.policy_error = str(exc)
        # Keep keyed identifiers only, never the phone/QR text in session state.
        self.request = {"mode": request["mode"], "symptoms_reported": request.get("symptoms_reported") is True}
        self.keys, self.baseline = keys, baseline

    def accept_identity(self, embedding, model):
        """Gate every live capture frame; mismatch stays rejected until begin().

        2026-09-11: enrollment remains separate from asymmetry vectors. Baseline
        frames also match the initial embedding to detect a mid-capture swap.
        """
        self.identity_verified = False
        if self.request is None:
            raise ValueError("No visit acquisition is active.")
        if self.identity_rejected:
            raise IdentityMismatch(MISMATCH_MESSAGE)
        current = identity_payload(embedding, model)
        reference = self.baseline["identity"] if self.baseline else self.identity
        if reference is not None:
            self.identity_similarity = cosine_similarity(reference["embedding"], current["embedding"])
            if reference["model"] != model or self.identity_similarity < IDENTITY_COSINE_THRESHOLD:
                self.identity_rejected = True
                raise IdentityMismatch(MISMATCH_MESSAGE)
        else:
            self.identity = current
        self.identity_verified = True
        return self.identity_similarity

    def require_identity(self):
        if self.identity_rejected:
            raise IdentityMismatch(MISMATCH_MESSAGE)
        if not self.identity_verified:
            raise ValueError("Identity verification required before measurement comparison.")

    def compare(self, features, setup, partial=False, research_angles=None):
        if self.request is None or self.request["mode"] != "recheck":
            raise ValueError("No symptom-triggered recheck is active.")
        self.require_identity()  # Must precede clinical and research delta functions.
        numeric_map(features, FEATURE_KEYS, complete=not partial)
        check_setup(self.baseline["record"]["setup"], setup, partial)
        # Facial and arm measurements require their corresponding setup data.
        required = {key for key in SETUP_KEYS if key.startswith("face_")} if any(k not in ("left_arm_drift", "right_arm_drift", "arm_lift_skew") for k in features) else set()
        if any(k in features for k in ("left_arm_drift", "right_arm_drift", "arm_lift_skew")):
            required.update(key for key in SETUP_KEYS if key.startswith("body_"))
        if not required.issubset(setup):
            raise ValueError("Missing capture alignment measurements.")
        if research_angles:
            required_body = {key for key in SETUP_KEYS if key.startswith("body_")}
            if not required_body.issubset(setup):
                raise ValueError("Missing body setup for angular measurements.")
        if self.research:
            return compare_research(self.baseline["record"]["features"], features,
                                    self.baseline["record"].get("research_angles", {}), research_angles or {},
                                    self.research_parameters, partial)
        measurement = delta_features(self.baseline["record"]["features"], features, partial)
        threshold = self.policy["threshold"] if self.policy else None
        exceeded = threshold is not None and measurement["score"] > threshold
        return {"status": "delta_alert" if exceeded else ("threshold_unconfigured" if threshold is None else "below_threshold"),
                "measurement": measurement, "threshold": threshold,
                "policy_id": self.policy["policy_id"] if self.policy else None,
                "alert": exceeded, "care_message": CARE_MESSAGE,
                "reason": self.policy_error or ("No validated threshold configured." if threshold is None else
                           "A below-threshold measurement cannot exclude stroke or dismiss symptoms.")}

    def finish(self, features, setup, research_angles=None):
        if self.request is None:
            raise ValueError("No visit acquisition is active.")
        self.require_identity()
        record = {"schema": SCHEMA, "features": numeric_map(features, FEATURE_KEYS),
                  "setup": numeric_map(setup, SETUP_KEYS), "context": dict(self.context)}
        if self.research:
            record["research_angles"] = research_angles or {}
        if self.request["mode"] == "baseline":
            from src.protocol import check_head_pose
            check_head_pose(setup)
            self.store.save_baseline(self.keys, record, self.identity)
            return {"status": "baseline_saved", "alert": False, "reason": "Baseline measurements and separate face identity embedding saved for this customer and visit." +
                    (" Research angle measurement unavailable. Capture a new baseline under a new visit reference with a visible sideways arm hold before comparing angles."
                     if self.research and len(record["research_angles"]) != 2 else "")}
        result = self.compare(features, setup, research_angles=research_angles)
        self.store.save_recheck(self.keys, record, result)
        return result
