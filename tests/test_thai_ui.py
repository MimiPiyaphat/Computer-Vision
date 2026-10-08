"""Thai display and mode transitions, testable without Tk or a camera."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from ui.thai import customer_assessment, display_text, select_font, CARE_TH, SAFETY_TH
from ui.visit_state import MODES, can_change_mode
from ui.preview import PreviewSession
from src.protocol import CARE_MESSAGE


class ThaiPresentationTests(unittest.TestCase):
    def test_font_choice_and_missing_font_fallback(self):
        self.assertEqual(select_font('Sarabun', ['Sarabun', 'Leelawadee UI']), 'Sarabun')
        self.assertEqual(select_font('missing', ['Leelawadee UI', 'Tahoma']), 'Leelawadee UI')
        self.assertEqual(select_font('missing', ['Tahoma']), 'Tahoma')
        self.assertEqual(select_font('missing', []), 'TkDefaultFont')

    def test_thai_warnings_preserve_identity_message_and_unknown_diagnostics(self):
        self.assertEqual(display_text(CARE_MESSAGE), CARE_TH)
        message = 'Identity mismatch: does not match registered user'
        self.assertIn(message, display_text(message))
        self.assertIn('บุคคล', display_text(message))
        self.assertEqual(display_text('SQLite error 123'), 'SQLite error 123')
        self.assertIn('0.2500', display_text('Face delta 0.2500 / rule 0.1000'))

    def test_missing_measurements_require_retry_and_never_claim_low_risk(self):
        self.assertIn('ไม่ใช่ผลปกติ', SAFETY_TH)
        for level, expected in (("Comparison inconclusive", "ไม่มีผลที่ใช้ได้"),
                                ("Research comparison incomplete", "ข้อมูลไม่ครบ")):
            title, body = customer_assessment({
                "level": level,
                "reasons": ["Unvalidated university demo: one or more measurements are unavailable; this is inconclusive."],
                "disclaimer": CARE_MESSAGE,
            }, "No complete feature record was saved.")
            self.assertIn(expected, title)
            self.assertIn('ต้องตรวจซ้ำ', title)
            self.assertIn('ห้ามตีความว่าเป็นผลปกติหรือความเสี่ยงต่ำ', body)
            self.assertIn('เริ่มตรวจใหม่', body)
            self.assertIn(CARE_TH, body)
            self.assertNotIn('inconclusive', body)

    def test_complete_result_keeps_measured_outcome(self):
        title, body = customer_assessment({
            "level": "Below demo rules; NOT medical clearance",
            "reasons": ["Unvalidated university demo: rules were not exceeded; this cannot exclude disease."],
            "disclaimer": CARE_MESSAGE,
        })
        self.assertIn('เกณฑ์ปกติของการทดสอบ', title)
        self.assertIn('ไม่สามารถยืนยันว่าไม่มีโรค', body)

    def test_mode_lock_covers_loading_capture_and_identity_pause(self):
        for state in ('neutral_capture', 'mouth_test', 'arm_test', 'identity_check'):
            self.assertFalse(can_change_mode({'status': 'ready', 'state': state}))
        for status in ('loading', 'disconnecting'):
            self.assertFalse(can_change_mode({'status': status}))
        for state in ('idle', 'summary', 'identity_rejected'):
            self.assertTrue(can_change_mode({'status': 'ready', 'state': state}))
        self.assertTrue(can_change_mode(None))

    def test_preview_preserves_selected_mode_without_recording(self):
        preview = PreviewSession()
        preview.open()
        for mode in MODES:
            preview.start({'mode': mode})
            self.assertEqual(preview.read()['visit_mode'], mode)
        preview.stop()
        self.assertIsNone(preview.read()['visit_mode'])


class ModeInteractionTests(unittest.TestCase):
    def dashboard(self):
        # Import callbacks with lightweight widget base classes; never initialize Tk.
        tk = Mock(Frame=object, Canvas=object)
        path = Path(__file__).resolve().parents[1] / 'ui/app.py'
        spec = importlib.util.spec_from_file_location('thai_dashboard_under_test', path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules', {'tkinter': tk, 'tkinter.scrolledtext': Mock()}):
            spec.loader.exec_module(module)
        dashboard = module.Dashboard.__new__(module.Dashboard)
        dashboard.snapshot = {'status': 'ready', 'state': 'summary', 'assessment': {'level': 'old'}}
        dashboard.visit_mode = Mock()
        dashboard.setup_confirmed = Mock()
        dashboard.user_id = Mock()
        dashboard.visit_id = Mock()
        dashboard.symptoms_reported = Mock()
        dashboard.symptom_notice_latched = True
        dashboard.command = Mock()
        dashboard.render = Mock()
        dashboard.start_button = Mock()
        return dashboard

    def test_switch_clears_old_summary_keeps_ids_and_does_not_invent_symptoms(self):
        dashboard = self.dashboard()
        dashboard.change_mode('recheck')
        dashboard.visit_mode.set.assert_called_once_with('recheck')
        dashboard.setup_confirmed.set.assert_called_once_with(False)
        dashboard.user_id.set.assert_not_called()
        dashboard.visit_id.set.assert_not_called()
        dashboard.symptoms_reported.set.assert_not_called()
        self.assertTrue(dashboard.symptom_notice_latched)
        self.assertIsNone(dashboard.snapshot['assessment'])
        dashboard.command.assert_called_once_with('stop')

    def test_active_capture_rejects_mode_switch(self):
        dashboard = self.dashboard()
        dashboard.snapshot = {'status': 'ready', 'state': 'neutral_capture'}
        dashboard.change_mode('recheck')
        dashboard.visit_mode.set.assert_not_called()
        dashboard.command.assert_not_called()

    def test_start_sends_backend_mode_keys_and_actual_checkbox_values(self):
        dashboard = self.dashboard()
        dashboard.worker = Mock()
        dashboard.visit_mode.get.return_value = 'recheck'
        dashboard.user_id.get.return_value = 'member'
        dashboard.visit_id.get.return_value = 'visit'
        dashboard.symptoms_reported.get.return_value = False
        dashboard.setup_confirmed.get.return_value = True
        dashboard.start_visit()
        dashboard.worker.send.assert_called_once_with({'action': 'start', 'request': {
            'mode': 'recheck', 'user_id': 'member', 'visit_id': 'visit',
            'symptoms_reported': False, 'setup_confirmed': True}})


if __name__ == '__main__':
    unittest.main()
