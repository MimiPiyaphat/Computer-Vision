"""Thai display and mode transitions, testable without Tk or a camera."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from ui.thai import customer_assessment, display_text, select_font, CARE_TH, SAFETY_TH
from ui.visit_state import MODES, can_change_mode
from ui.preview import PreviewSession
from ui.content import STEPS
from src.protocol import CARE_MESSAGE


class ProgressStub(dict):
    def __init__(self):
        super().__init__()
        self.pack = Mock()
        self.pack_forget = Mock()


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

    def test_safety_copy_never_frames_low_or_missing_result_as_clearance(self):
        self.assertIn('ไม่ได้วินิจฉัย', SAFETY_TH)
        self.assertIn('ไม่ใช่ผลปกติ', SAFETY_TH)
        self.assertIn('ฉุกเฉิน', CARE_TH)
        self.assertIn('ไม่สามารถตัดโรค', display_text('Below demo rules; NOT medical clearance'))

    def test_customer_incomplete_result_hides_research_diagnostics(self):
        assessment = {
            'level': 'Research comparison incomplete',
            'reasons': ['Face delta 0.0802 / rule 0.1000',
                        '2D arm angle unavailable; forearm pronation is not measured.'],
            'disclaimer': CARE_MESSAGE,
        }
        title, body = customer_assessment(assessment, {'status': 'research_incomplete', 'alert': False})
        self.assertEqual(title, 'ข้อมูลไม่ครบ · ติดต่อเจ้าหน้าที่')
        self.assertIn('ข้อมูลสำหรับเปรียบเทียบไม่ครบ', body)
        for internal in ('วิจัย', '0.0802', '0.1000', '2D', 'pronation'):
            self.assertNotIn(internal, title + body)
        fallback_title, fallback_body = customer_assessment(assessment, {})
        self.assertEqual((fallback_title, fallback_body), (title, body))

    def test_unavailable_results_request_staff_help_without_claiming_success(self):
        for status in ('inconclusive', 'research_incomplete', 'threshold_unconfigured'):
            with self.subTest(status=status):
                title, body = customer_assessment({'level': 'Comparison inconclusive'}, {'status': status})
                self.assertIn('ติดต่อเจ้าหน้าที่', title)
                self.assertNotIn('กรุณาตรวจใหม่', body)
                self.assertNotIn('เรียบร้อย', title + body)
                self.assertNotIn(CARE_TH, body)
                _, symptomatic_body = customer_assessment(
                    {'level': 'Comparison inconclusive'},
                    {'status': status, 'symptoms_reported': True})
                self.assertIn(CARE_TH, symptomatic_body)

    def test_customer_alert_uses_non_diagnostic_wording(self):
        title, body = customer_assessment({'level': 'Research rule exceeded'},
                                          {'status': 'research_alert', 'alert': True})
        self.assertIn('ค่าหลังนวดเปลี่ยน', title)
        self.assertIn('แจ้งเจ้าหน้าที่ทันที', title)
        self.assertIn('ไม่ใช่การวินิจฉัย', body)

    def test_replaced_baseline_explains_that_same_ids_can_be_reused(self):
        title, body = customer_assessment({}, {'status': 'baseline_saved', 'baseline_replaced': True})
        self.assertEqual(title, 'อัปเดตข้อมูลก่อนนวดแล้ว')
        self.assertIn('รหัสผู้รับบริการและรหัสครั้งเดิม', body)
        self.assertIn('ประวัติ', body)

    def test_retry_copy_preserves_timeout_reason_and_prior_alert(self):
        result = {'status': 'acquisition_failed', 'reason': 'Both wrists are not visible'}
        title, body = customer_assessment({}, result)
        self.assertIn('เก็บข้อมูลใหม่ได้', title)
        self.assertIn('ยังไม่เห็นข้อมือทั้งสองข้าง', body)
        self.assertIn('ขั้นตอนแรก', body)
        title, body = customer_assessment({}, dict(result, alert=True))
        self.assertIn('ค่าที่เปลี่ยนมาก', title)
        self.assertTrue(body.startswith('ระบบพบค่าที่เปลี่ยน'))

    def test_research_alert_names_only_flagged_regions(self):
        for face, arm, expected in ((True, False, 'ความไม่สมมาตรของใบหน้าหลังนวดเพิ่มขึ้น'),
                                    (False, True, 'การเคลื่อนไหวแขนหลังนวดเพิ่มขึ้น'),
                                    (True, True, 'ความไม่สมมาตรของใบหน้าและการเคลื่อนไหวแขนหลังนวดเพิ่มขึ้น')):
            with self.subTest(face=face, arm=arm):
                _, body = customer_assessment({}, {'status': 'research_alert', 'alert': True,
                    'research_measurement': {'face_alert': face, 'arm_alert': arm}})
                self.assertIn(expected, body)
                self.assertIn('แจ้งเจ้าหน้าที่ทันที', body)
        _, body = customer_assessment({}, {'status': 'delta_alert', 'alert': True})
        self.assertNotIn('ค่าความสมมาตรของใบหน้าเปลี่ยน', body)

    def test_result_categories_have_distinct_meanings_and_next_actions(self):
        statuses = ('baseline_saved', 'research_alert', 'research_below_placeholder',
                    'research_incomplete', 'inconclusive', 'threshold_unconfigured', 'identity_rejected')
        titles = [customer_assessment({}, {'status': status})[0] for status in statuses]
        self.assertEqual(len(titles), len(set(titles)))
        for status in ('research_below_placeholder', 'below_threshold'):
            _, body = customer_assessment({}, {'status': status})
            self.assertIn('ไม่สามารถยืนยันว่าไม่มีโรค', body)
            self.assertIn('ตรวจติดตามหลังนวดเสร็จแล้ว', body)
            self.assertNotIn('คุณระบุว่ามีอาการผิดปกติ', body)
            _, symptomatic_body = customer_assessment({}, {'status': status, 'symptoms_reported': True})
            self.assertIn('คุณระบุว่ามีอาการผิดปกติ', symptomatic_body)

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
    def test_summary_progress_distinguishes_ended_capture_from_usable_result(self):
        for status, level, expected in (
            ('inconclusive', 'Comparison inconclusive', 0),
            ('research_incomplete', 'Research comparison incomplete', 0),
            ('threshold_unconfigured', 'Delta measured; threshold unconfigured', 0),
            ('baseline_saved', 'Baseline saved', 100),
            ('research_alert', 'Research rule exceeded; seek medical attention for symptoms', 100),
            ('acquisition_failed', 'เก็บข้อมูลไม่ครบ · ติดต่อเจ้าหน้าที่', 0),
        ):
            with self.subTest(status=status):
                dashboard = self.dashboard()
                dashboard.theme = {key: key for key in ('text', 'warning', 'danger', 'muted', 'accent')}
                dashboard.research = dashboard.preview = False
                dashboard.alert_notified = False
                dashboard.visit_mode.get.return_value = 'recheck'
                dashboard.visit_controls = []
                dashboard.stage_labels = {'summary': Mock()}
                dashboard.progress = ProgressStub()
                for name in ('set_ready', 'update_care_notice', 'camera_input', 'connect_button',
                             'connection', 'video', 'instruction', 'mode_panel', 'setup_check',
                             'stop_button', 'detail', 'result_title', 'set_result_text', 'root'):
                    setattr(dashboard, name, Mock())
                comparison = {'status': status, 'alert': status == 'research_alert'}
                assessment = {'level': level}
                type(dashboard).render(dashboard, {'status': 'ready', 'state': 'summary',
                                                  'comparison': comparison, 'assessment': assessment})
                self.assertEqual(dashboard.progress['value'], expected)
                if status == 'acquisition_failed':
                    dashboard.start_button.configure.assert_called_with(text='เก็บข้อมูลใหม่อีกครั้ง')
                    dashboard.instruction.configure.assert_called_with(text='กด ‘เก็บข้อมูลใหม่อีกครั้ง’ เมื่อพร้อม')
                    self.assertIn('ขั้นตอนที่ 1', dashboard.detail.configure.call_args.kwargs['text'])
                    self.assertIn('รหัสเดิม', dashboard.detail.configure.call_args.kwargs['text'])
                else:
                    dashboard.instruction.configure.assert_called_with(text='จบขั้นตอนแล้ว · ดูผลและสิ่งที่ควรทำด้านล่าง')
                dashboard.progress.pack_forget.assert_called_once()
                if expected == 0 and status != 'acquisition_failed':
                    self.assertIn('เจ้าหน้าที่', dashboard.detail.configure.call_args.kwargs['text'])

    def test_latched_alert_never_overwrites_actions_and_is_visible_before_summary(self):
        dashboard = self.dashboard()
        dashboard.theme = {key: key for key in ('text', 'warning', 'danger', 'muted', 'accent')}
        dashboard.research = dashboard.preview = False
        dashboard.alert_notified = False
        dashboard.visit_mode.get.return_value = 'recheck'
        dashboard.visit_controls = []
        dashboard.stage_labels = {step[0]: Mock() for step in STEPS}
        dashboard.progress = ProgressStub()
        for name in ('set_ready', 'update_care_notice', 'camera_input', 'connect_button',
                     'connection', 'video', 'instruction', 'mode_panel', 'setup_check',
                     'stop_button', 'detail', 'result_title', 'set_result_text', 'root'):
            setattr(dashboard, name, Mock())
        alert = {'status': 'research_alert', 'alert': True, 'research_only': True,
                 'research_measurement': {'face_alert': True, 'arm_alert': False}}
        for state, instruction in (
            ('quality_gate', 'Keep exactly one complete face visible, close enough to the camera.'),
            ('neutral_capture', 'Relax your face and look at the camera'),
            ('mouth_test', 'Smile as wide as you can and hold'),
            ('eye_closure', 'Gently close both eyes and hold'),
            ('eye_test', 'Blink both eyes naturally several times'),
            ('arm_test', 'Keep both arms raised'),
            ('identity_check', 'Identity check: hold still while confirming the returning person.'),
        ):
            with self.subTest(state=state):
                dashboard.instruction.reset_mock()
                type(dashboard).render(dashboard, {'status': 'ready', 'state': state, 'elapsed': .4,
                    'acquisition_state': 'arm_test' if state == 'identity_check' else state,
                    'visit_mode': 'recheck',
                    'instruction': instruction, 'assessment': None, 'comparison': alert})
                dashboard.instruction.configure.assert_called_once_with(text=display_text(instruction))
                expected_state = 'arm_test' if state == 'identity_check' else state
                step_index = next(i for i, step in enumerate(STEPS) if step[0] == expected_state)
                self.assertIn(f'หลังนวด · ขั้นตอนที่ {step_index + 1} / 7',
                              dashboard.current_step.configure.call_args.kwargs['text'])
                self.assertIn('พัก' if state == 'identity_check' else 'กำลังทำ',
                              dashboard.stage_labels[expected_state].configure.call_args.kwargs['text'])
                if state != 'identity_check':
                    self.assertIn('ขั้นตอนถัดไป: ' + STEPS[step_index + 1][1],
                                  dashboard.detail.configure.call_args.kwargs['text'])
                self.assertIn('แจ้งเจ้าหน้าที่ทันที', dashboard.result_title.configure.call_args.kwargs['text'])
                self.assertIn('พบค่าที่เปลี่ยนมากระหว่างตรวจ', dashboard.set_result_text.call_args.args[0])
        dashboard.root.bell.assert_called_once()
        dashboard.progress.pack_forget.assert_not_called()
        type(dashboard).render(dashboard, {'status': 'ready', 'state': 'idle',
                                          'assessment': None, 'comparison': None})
        self.assertEqual(dashboard.result_title.configure.call_args.kwargs['text'], 'ยังไม่ได้เริ่มตรวจ')

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
        dashboard.symptom_check = Mock()
        dashboard.symptom_notice_latched = True
        dashboard.command = Mock()
        dashboard.render = Mock()
        dashboard.start_button = Mock()
        dashboard.current_step = Mock()
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

    def test_baseline_hides_symptom_field_and_ignores_retained_recheck_value(self):
        dashboard = self.dashboard()
        dashboard.worker = Mock()
        dashboard.visit_mode.get.return_value = 'baseline'
        dashboard.symptoms_reported.get.return_value = True
        dashboard.update_symptom_visibility()
        dashboard.symptom_check.grid_remove.assert_called_once()
        dashboard.start_visit()
        self.assertFalse(dashboard.worker.send.call_args.args[0]['request']['symptoms_reported'])
        self.assertTrue(dashboard.symptom_notice_latched)
        dashboard.visit_mode.get.return_value = 'recheck'
        dashboard.update_symptom_visibility()
        dashboard.symptom_check.grid.assert_called_once()
        dashboard.start_visit()
        self.assertTrue(dashboard.worker.send.call_args.args[0]['request']['symptoms_reported'])


if __name__ == '__main__':
    unittest.main()
