"""Local developer-view password gate. Does not encrypt files on disk."""

import hashlib
import hmac
import json
from pathlib import Path
import time

REPORT_PATH = Path(__file__).resolve().parents[1] / 'models' / 'stroke_rehab_transfer.metrics.json'
VOLUNTEER_REPORT_PATH = Path(__file__).resolve().parents[1] / 'data/volunteers-20261007/evaluation-v2/report.json'
ROBOFLOW_REPORT_PATH = Path(__file__).resolve().parents[1] / 'models/roboflow_stroke_yolov8n.metrics.json'
SALT = bytes.fromhex('3a4100703ac59b19b964384e44ec36c0')
DIGEST = '87a0f28f97a93797250c9bd49c68bf780fd7590aee61a68a340a9fd3957385c2'


class DevAccess:
    def __init__(self, report_path=REPORT_PATH, clock=time.monotonic):
        self.report_path = Path(report_path)
        self.clock = clock
        self.failed = 0
        self.blocked_until = 0

    def _authenticate(self, password):
        if self.clock() < self.blocked_until:
            raise PermissionError('ใส่รหัสผิดหลายครั้ง กรุณารอ 60 วินาทีก่อนลองใหม่')
        candidate = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), SALT, 300000).hex()
        if not hmac.compare_digest(candidate, DIGEST):
            self.failed += 1
            if self.failed >= 5:
                self.blocked_until = self.clock() + 60
                self.failed = 0
            raise PermissionError('รหัสผ่านไม่ถูกต้อง')
        self.failed = 0
    @staticmethod
    def _read_report(path, schema):
        # No report is read before password verification succeeds.
        if not path.exists():
            return None
        report = json.loads(path.read_text(encoding='utf-8'))
        if report.get('schema') != schema:
            raise ValueError('รูปแบบรายงานไม่รองรับ')
        return report

    def unlock(self, password):
        self._authenticate(password)
        return self._read_report(self.report_path, 'rehab-transfer-report-v1')

    def unlock_reports(self, password, volunteer_path=VOLUNTEER_REPORT_PATH):
        self._authenticate(password)
        return (self._read_report(self.report_path, 'rehab-transfer-report-v1'),
                self._read_report(Path(volunteer_path), 'volunteer-gesture-report-v1'))

    def unlock_all_reports(self, password, volunteer_path=VOLUNTEER_REPORT_PATH,
                           roboflow_path=ROBOFLOW_REPORT_PATH):
        """Authenticate once, then load every independent developer report."""
        self._authenticate(password)
        return (
            self._read_report(self.report_path, 'rehab-transfer-report-v1'),
            self._read_report(Path(volunteer_path), 'volunteer-gesture-report-v1'),
            self._read_report(Path(roboflow_path), 'roboflow-object-detection-report-v1'),
        )
