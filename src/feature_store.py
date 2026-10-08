"""Local measurements and separate biometric embeddings; never accepts media."""

from contextlib import closing
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import re
import sqlite3
import time
import unicodedata

from src.features import FEATURE_KEYS, SETUP_KEYS, SCHEMA, numeric_map
from src.research import validate_angles
from src.arm_features import validate_arm_function
from src.face_identity import identity_payload


def validate_record(record):
    required = {"schema", "features", "setup", "context"}
    if (not isinstance(record, dict) or not required.issubset(record) or
            set(record) - required - {"research_angles", "arm_function"} or record["schema"] != SCHEMA):
        raise ValueError("Unsupported feature record schema.")
    numeric_map(record["features"], FEATURE_KEYS)
    numeric_map(record["setup"], SETUP_KEYS)
    if "research_angles" in record:
        validate_angles(record["research_angles"])
    if "arm_function" in record:
        validate_arm_function(record["arm_function"])
    context = record["context"]
    if not isinstance(context, dict) or set(context) != {"pipeline", "camera", "width", "height", "station"}:
        raise ValueError("Invalid capture context.")
    if any(type(context[k]) is not int or context[k] < (0 if k == "camera" else 1)
           for k in ("camera", "width", "height")):
        raise ValueError("Invalid camera geometry.")
    if any(not isinstance(context[k], str) or not context[k].strip() or len(context[k]) > 128
           for k in ("pipeline", "station")):
        raise ValueError("Invalid model or station signature.")
    return record


class FeatureStore:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "visits.sqlite3"
        key_path = directory / "identity.key"
        if self.path.exists() and not key_path.exists():
            raise ValueError("Identity key is missing; restore it before using the existing feature store.")
        try:
            with key_path.open("xb") as stream:
                stream.write(secrets.token_bytes(32))
        except FileExistsError:
            pass
        self._key = key_path.read_bytes()
        if len(self._key) != 32:
            raise ValueError("Invalid identity key.")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS baselines (subject TEXT, visit TEXT, created REAL, record TEXT, PRIMARY KEY(subject, visit))")
            db.execute("CREATE TABLE IF NOT EXISTS rechecks (id INTEGER PRIMARY KEY, subject TEXT, visit TEXT, created REAL, record TEXT, comparison TEXT)")
            # 2026-09-11: additive migration; never reinterpret or overwrite old rows.
            columns = {row[1] for row in db.execute("PRAGMA table_info(baselines)")}
            for column in ("identity_embedding", "identity_model"):
                if column not in columns:
                    db.execute(f"ALTER TABLE baselines ADD COLUMN {column} TEXT")

    def _token(self, namespace, value):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 128:
            raise ValueError("Enter a customer ID and a visit reference (1-128 characters each).")
        normalized = unicodedata.normalize("NFKC", value.strip())
        return hmac.new(self._key, (namespace + ":" + normalized).encode("utf-8"), hashlib.sha256).hexdigest()

    def keys(self, user_id, visit_id):
        subject = self._token("customer", user_id)
        return subject, self._token("visit:" + subject, visit_id)

    def baseline(self, keys):
        self._validate_keys(keys)
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT created, record, identity_embedding, identity_model FROM baselines WHERE subject=? AND visit=?", keys).fetchone()
        if row is None:
            raise ValueError("No baseline for this customer and visit. Symptoms still require prompt medical attention.")
        identity = identity_payload(json.loads(row[2]), row[3]) if row[2] is not None else None
        return {"created": row[0], "record": validate_record(json.loads(row[1])), "identity": identity}

    def save_baseline(self, keys, record, identity=None):
        self._validate_keys(keys)
        payload = json.dumps(validate_record(record), allow_nan=False)
        identity = identity_payload(**identity) if identity is not None else None
        try:
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute("INSERT INTO baselines(subject, visit, created, record, identity_embedding, identity_model) VALUES (?, ?, ?, ?, ?, ?)",
                           (*keys, time.time(), payload,
                            json.dumps(identity["embedding"], allow_nan=False) if identity else None,
                            identity["model"] if identity else None))
        except sqlite3.IntegrityError as exc:
            raise ValueError("A baseline already exists for this visit; it cannot be overwritten.") from exc

    def save_recheck(self, keys, record, comparison):
        self._validate_keys(keys)
        # Store only allowlisted numeric deltas and decision provenance.
        safe = {key: comparison.get(key) for key in ("status", "threshold", "policy_id")}
        if safe["status"] not in ("delta_alert", "threshold_unconfigured", "below_threshold", "research_alert", "research_below_placeholder", "research_incomplete"):
            raise ValueError("Invalid comparison status.")
        if safe["threshold"] is not None:
            numeric_map({"threshold": safe["threshold"]}, ("threshold",))
        if safe["policy_id"] is not None and (not isinstance(safe["policy_id"], str) or len(safe["policy_id"]) > 128):
            raise ValueError("Invalid policy reference.")
        if comparison.get("measurement"):
            measurement = comparison["measurement"]
            safe["deltas"] = numeric_map(measurement["deltas"], FEATURE_KEYS)
            safe.update(numeric_map({key: measurement[key] for key in ("face_delta", "arm_delta", "score")},
                                    ("face_delta", "arm_delta", "score")))
        if comparison.get("research_only") is True:
            safe["research_only"] = True
            research = comparison["research_measurement"]
            safe["research_measurement"] = numeric_map(
                {k: research[k] for k in ("face_delta_threshold", "arm_angle_delta_threshold_deg")},
                ("face_delta_threshold", "arm_angle_delta_threshold_deg"))
            if research["arm_angle_delta_deg"] is not None:
                safe["research_measurement"].update(numeric_map({"arm_angle_delta_deg": research["arm_angle_delta_deg"]}, ("arm_angle_delta_deg",)))
            arm_status = research.get("arm_function_status")
            if arm_status is not None:
                safe["research_measurement"]["arm_function_status"] = validate_arm_function(
                    comparison["arm_function"])["status"]
                safe["research_measurement"]["arm_function_alert"] = bool(research.get("arm_function_alert"))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO rechecks(subject, visit, created, record, comparison) VALUES (?, ?, ?, ?, ?)",
                       (*keys, time.time(), json.dumps(validate_record(record), allow_nan=False), json.dumps(safe, allow_nan=False)))

    @staticmethod
    def _validate_keys(keys):
        if len(keys) != 2 or any(not isinstance(k, str) or not re.fullmatch(r"[0-9a-f]{64}", k) for k in keys):
            raise ValueError("Only keyed customer and visit identifiers may be stored.")

    def delete_customer(self, user_id):
        subject = self._token("customer", user_id)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("PRAGMA secure_delete=ON")
            db.execute("DELETE FROM rechecks WHERE subject=?", (subject,))
            db.execute("DELETE FROM baselines WHERE subject=?", (subject,))
