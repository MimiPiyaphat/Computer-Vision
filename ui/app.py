"""Tk dashboard. Presentation only; all inference lives behind SessionWorker."""

import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from config import CAMERA_INDEX
from ui.components import Card, VideoPanel, button, label
from ui.content import STEPS
from ui.thai import SAFETY_TH, CARE_TH, customer_assessment, display_text, configure_fonts
from ui.visit_panel import VisitModePanel
from ui.visit_state import MODES, can_change_mode
from ui.theme import load_theme
from ui.worker import SessionWorker
from src.protocol import CARE_MESSAGE


class Dashboard:
    def __init__(self, root, preview=False, research=False):
        self.root = root
        self.preview = preview
        self.research = research
        self.worker = None
        self.snapshot = None
        self.closing = False
        self.camera_index = tk.StringVar(value=str(CAMERA_INDEX))
        self.debug_enabled = False
        self.user_id = tk.StringVar()
        self.visit_id = tk.StringVar()
        self.visit_mode = tk.StringVar(value="baseline")
        self.symptoms_reported = tk.BooleanVar(value=False)
        self.setup_confirmed = tk.BooleanVar(value=False)
        self.symptom_notice_latched = False
        self.alert_notified = False
        from src.dev_access import DevAccess
        self.dev_access = DevAccess()
        self.dev_window = None
        self.theme = configure_fonts(root, load_theme())
        root.title("StrokeVision | บันทึกก่อนนวดและตรวจซ้ำ" + (" [ตัวอย่างหน้าจอ]" if preview else ""))
        root.geometry("1280x1000")
        root.minsize(1080, 900)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<F5>", lambda _: self.reload_theme())
        root.bind("<Control-Shift-D>", lambda _: self.open_dev())
        root.bind("<MouseWheel>", self.scroll_page)
        self.build()
        self.poll()

    def build(self):
        t = self.theme
        self.root.configure(bg=t["background"])
        self.page = tk.Frame(self.root, bg=t["background"])
        self.page.pack(fill="both", expand=True)
        self.page_canvas = tk.Canvas(self.page, bg=t["background"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.page, orient="vertical", command=self.page_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.page_canvas.pack(side="left", fill="both", expand=True)
        self.page_canvas.configure(yscrollcommand=scrollbar.set)
        self.container = tk.Frame(self.page_canvas, bg=t["background"], padx=t["spacing"], pady=t["spacing"])
        self.page_window = self.page_canvas.create_window(0, 0, anchor="nw", window=self.container)
        self.page_canvas.bind("<Configure>", self.resize_page)
        self.container.bind("<Configure>", self.resize_page)
        header = tk.Frame(self.container, bg=t["background"])
        header.pack(fill="x", pady=(0, 18))
        label(header, "StrokeVision", t, size=24, bold=True).pack(side="left")
        label(header, "  /  บันทึกก่อนนวดและตรวจซ้ำ", t, muted=True).pack(side="left")
        button(header, "โหลดธีมใหม่ · F5", self.reload_theme, t).pack(side="right")
        button(header, "Dev", self.open_dev, t).pack(side="right", padx=8)
        button(header, "ผู้รับบริการใหม่", self.new_customer, t).pack(side="right", padx=8)
        label(self.container, "ตัวอย่างหน้าจอ · ใช้ข้อมูลจำลองเท่านั้น" if self.preview else
              "บันทึกและเปรียบเทียบการเปลี่ยนแปลงของใบหน้าและแขน", t, muted=True).pack(anchor="w", pady=(0, 16))
        if self.research:
            from src.research import load_parameters
            parameters = load_parameters()
            self.research_banner = label(self.container, "", t, bold=True, size=10, wraplength=1100)
            self.research_banner.pack(anchor="w", pady=(0, 12))
            self.show_research_rules(parameters)

        self.mode_panel = VisitModePanel(self.container, self.visit_mode, self.change_mode, t)
        self.mode_panel.pack(fill="x", pady=(0, 12))

        visit = tk.Frame(self.container, bg=t["surface"], padx=12, pady=10)
        visit.pack(fill="x", pady=(0, 12))
        self.visit_controls = []
        for column, (title, variable) in enumerate((("รหัสผู้รับบริการ / QR สมาชิก", self.user_id), ("รหัสครั้งรับบริการ", self.visit_id))):
            label(visit, title, t, muted=True, size=10).grid(row=0, column=column, sticky="w")
            entry = tk.Entry(visit, textvariable=variable, show="*" if column == 0 else "", font=(t["font"], t["font_size"]))
            entry.grid(row=1, column=column, sticky="ew", padx=(0, 16), pady=(4, 8))
            visit.columnconfigure(column, weight=1)
            self.visit_controls.append(entry)
        tk.Checkbutton(visit, text="ผู้รับบริการแจ้งว่ามีอาการผิดปกติ", variable=self.symptoms_reported,
                       command=self.symptom_changed, bg=t["surface"], fg=t["text"], selectcolor=t["background"],
                       activebackground=t["surface"], activeforeground=t["text"], font=(t["font"], 10)).grid(row=2, column=0, columnspan=2, sticky="w")
        self.setup_check = tk.Checkbutton(visit, text="ยืนยันกล้องและจุดตรวจเดิม ทำตามท่าที่กำหนด และมองตรง",
                       variable=self.setup_confirmed, bg=t["surface"], fg=t["text"], selectcolor=t["background"],
                       activebackground=t["surface"], activeforeground=t["text"], font=(t["font"], 10))
        self.setup_check.grid(row=3, column=0, columnspan=2, sticky="w")

        body = tk.Frame(self.container, bg=t["background"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=t["background"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        right = tk.Frame(body, bg=t["background"])
        right.grid(row=0, column=1, sticky="nsew")

        self.video = VideoPanel(left, t, self.preview)
        self.connection = label(left, "ยังไม่เชื่อมต่อ · กล้องปิดอยู่", t, muted=True)
        self.connection.pack(fill="x", pady=10)
        controls = tk.Frame(left, bg=t["background"])
        controls.pack(fill="x", pady=(0, 12))
        self.connect_button = button(controls, "เปิดตัวอย่าง" if self.preview else "เชื่อมต่อกล้อง", self.connect, t)
        self.connect_button.pack(side="left")
        if not self.preview:
            label(controls, "  กล้อง ", t, muted=True).pack(side="left")
            self.camera_input = tk.Spinbox(controls, from_=0, to=9, width=3, textvariable=self.camera_index,
                                          font=(t["font"], t["font_size"]))
            self.camera_input.pack(side="left")
        self.debug_button = button(controls, "จุดอ้างอิง: เปิด" if self.debug_enabled else "จุดอ้างอิง: ปิด", self.toggle_debug, t)
        self.debug_button.pack(side="right")

        actions = tk.Frame(left, bg=t["background"])
        actions.pack(fill="x")
        self.start_button = button(actions, MODES[self.visit_mode.get()][3], self.start_visit, t, primary=True)
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.stop_button = button(actions, "หยุด", lambda: self.command("stop"), t)
        self.stop_button.pack(side="left")
        self.video.pack(fill="both", expand=True, pady=(12, 0))

        stages = Card(right, t, "ขั้นตอนการเก็บข้อมูล")
        stages.configure(padx=12, pady=12)
        stages.pack(fill="x", pady=(0, 12))
        stage_grid = tk.Frame(stages, bg=t["surface"])
        stage_grid.pack(fill="x")
        for column in (0, 1):
            stage_grid.columnconfigure(column, weight=1, uniform="stage")
        self.stage_labels = {}
        for index, (state, title, _, _) in enumerate(STEPS):
            item = label(stage_grid, f"{index + 1:02d}   {title}", t, muted=True, size=10)
            item.grid(row=index // 2, column=index % 2, sticky="w", pady=2)
            self.stage_labels[state] = item
        current = Card(right, t, "ขั้นตอนปัจจุบัน")
        current.configure(padx=12, pady=12)
        current.pack(fill="x", pady=(0, 12))
        self.instruction = label(current, "เชื่อมต่อกล้องเพื่อเริ่มต้น", t, size=14, bold=True, wraplength=340)
        self.instruction.pack(fill="x")
        self.progress = ttk.Progressbar(current, maximum=100)
        self.progress.pack(fill="x", pady=12)
        self.detail = label(current, "จับเวลาเมื่อเห็นจุดอ้างอิงที่จำเป็นครบ", t, muted=True, wraplength=340)
        self.detail.pack(fill="x")
        result = Card(right, t, "ผลการบันทึก / ตรวจซ้ำ")
        result.configure(padx=12, pady=12)
        result.pack(fill="both", expand=True)
        self.result_title = label(result, "ยังไม่มีผล", t, bold=True, wraplength=340)
        self.result_title.pack(fill="x")
        self.result_body = ScrolledText(result, height=4, width=28, wrap="word", relief="flat",
                                       bg=t["surface"], fg=t["muted"],
                                       font=(t["font"], t["font_size"]), borderwidth=0)
        self.result_body.pack(fill="both", expand=True, pady=(8, 0))
        self.set_result_text("ทำตามขั้นตอนให้ครบเพื่อดูผลสรุป")
        # Keep symptom guidance visible even when the main page is scrolled.
        self.footer = label(self.root, SAFETY_TH, t, muted=True, size=10, wraplength=1120)
        self.footer.pack(side="bottom", fill="x", padx=t["spacing"], pady=(8, 12))
        self.update_care_notice()
        self.set_ready(False)
        self.video.render()
        if self.snapshot:
            self.render(self.snapshot)

    def resize_page(self, _event=None):
        width = max(1, self.page_canvas.winfo_width())
        height = max(self.page_canvas.winfo_height(), self.container.winfo_reqheight())
        self.page_canvas.itemconfigure(self.page_window, width=width, height=height)
        self.page_canvas.configure(scrollregion=(0, 0, width, height))
        self.footer.configure(wraplength=max(200, width - 2 * self.theme["spacing"]))
        if self.research:
            self.research_banner.configure(wraplength=max(200, width - 2 * self.theme["spacing"]))

    def scroll_page(self, event):
        # The result text box keeps its own wheel scrolling and text selection.
        if isinstance(event.widget, tk.Text):
            return
        if self.page_canvas.yview() != (0.0, 1.0):
            self.page_canvas.yview_scroll(-int(event.delta / 120), "units")

    def open_dev(self):
        if self.dev_window and self.dev_window.window.winfo_exists():
            self.dev_window.window.lift()
            return
        from ui.dev_dashboard import DevDashboard
        self.dev_window = DevDashboard(self.root, self.theme, self.dev_access)

    def change_mode(self, mode):
        if mode not in MODES or not can_change_mode(self.snapshot):
            return
        self.visit_mode.set(mode)
        self.setup_confirmed.set(False)
        # Keep IDs for the same visit, and preserve symptom reports/care notices.
        self.command("stop")
        if self.snapshot:
            self.snapshot = {**self.snapshot, "state": "idle", "assessment": None,
                             "comparison": None, "extra": {}, "visit_mode": None,
                             "save_status": "", "command_error": "", "elapsed": 0}
            self.render(self.snapshot)
        self.start_button.configure(text=MODES[mode][3])

    def set_ready(self, ready):
        for control in (self.start_button, self.stop_button, self.debug_button):
            control.configure(state="normal" if ready else "disabled")
        self.start_button.configure(bg=self.theme["accent"] if ready else self.theme["surface"])

    def show_research_rules(self, parameters):
        self.research_banner.configure(text=f"โหมดวิจัย • ยังไม่ผ่านการรับรอง | เกณฑ์ใบหน้า {parameters['face_delta_threshold']:.2f} | มุมแขน 2D {parameters['arm_angle_delta_threshold_deg']:.1f}° | ยังไม่ได้ยืนยันประสิทธิภาพ")

    def symptom_changed(self):
        if self.symptoms_reported.get():
            self.symptom_notice_latched = True
            self.root.bell()
            self.visit_mode.set("recheck")
            if self.snapshot and self.snapshot.get("visit_mode") == "baseline":
                self.command("stop")
        self.start_button.configure(text=MODES[self.visit_mode.get()][3])
        self.update_care_notice()

    def new_customer(self):
        if self.dev_window and self.dev_window.window.winfo_exists():
            self.dev_window.close()
        # Explicitly end the previous customer's session before clearing its
        # latched care notice and editable identity fields.
        if self.worker and self.worker.thread.is_alive():
            if self.worker.closed.is_set():
                return
            self.worker.close()
            self.snapshot = {"status": "disconnecting"}
            self.render(self.snapshot)
            self.wait_disconnect()
        else:
            self.worker = None
            self.snapshot = {"status": "disconnected"}
            self.render(self.snapshot)
        self.user_id.set("")
        self.visit_id.set("")
        self.visit_mode.set("baseline")
        self.start_button.configure(text=MODES["baseline"][3])
        self.symptoms_reported.set(False)
        self.setup_confirmed.set(False)
        self.symptom_notice_latched = False
        self.alert_notified = False
        self.update_care_notice()

    def update_care_notice(self, message=""):
        if message:
            self.symptom_notice_latched = True
        urgent = self.symptom_notice_latched or self.symptoms_reported.get()
        self.footer.configure(text=CARE_TH if urgent else SAFETY_TH,
                              fg=self.theme["danger"] if urgent else self.theme["muted"],
                              font=(self.theme["font"], 11 if urgent else 10, "bold" if urgent else "normal"))

    def start_visit(self):
        request = {"mode": self.visit_mode.get(), "user_id": self.user_id.get(), "visit_id": self.visit_id.get(),
                   "symptoms_reported": self.symptoms_reported.get(), "setup_confirmed": self.setup_confirmed.get()}
        if self.worker and self.snapshot and self.snapshot.get("status") == "ready":
            self.worker.send({"action": "start", "request": request})

    def set_result_text(self, text):
        # Avoid resetting selection and scroll position on every camera frame.
        if self.result_body.get("1.0", "end-1c") == text:
            return
        self.result_body.configure(state="normal")
        self.result_body.delete("1.0", "end")
        self.result_body.insert("1.0", text)
        self.result_body.configure(state="disabled")

    def reload_theme(self):
        try:
            theme = load_theme()
        except (OSError, ValueError) as exc:
            messagebox.showerror("ไม่สามารถโหลดธีมใหม่ได้", str(exc), parent=self.root)
            return
        self.theme = configure_fonts(self.root, theme)
        self.footer.destroy()
        self.page.destroy()
        self.build()

    def connect(self):
        if self.worker and self.worker.thread.is_alive():
            self.worker.close()
            self.snapshot = {"status": "disconnecting"}
            self.render(self.snapshot)
            self.wait_disconnect()
            return
        try:
            index = int(self.camera_index.get())
            if index < 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("หมายเลขกล้อง", "กรุณาใช้หมายเลขกล้องตั้งแต่ 0 ขึ้นไป", parent=self.root)
            return
        if self.preview:
            from ui.preview import PreviewSession
            session = PreviewSession()
        else:
            from src.session import ScreeningSession
            session = ScreeningSession(index, self.debug_enabled, research=self.research)
        self.snapshot = {"status": "loading"}
        self.render(self.snapshot)
        self.worker = SessionWorker(session)
        self.worker.start()

    def wait_disconnect(self):
        if self.worker.thread.is_alive():
            self.root.after(50, self.wait_disconnect)
            return
        self.worker = None
        self.snapshot = {"status": "disconnected"}
        self.render(self.snapshot)

    def command(self, name):
        if self.worker and self.snapshot and self.snapshot.get("status") == "ready":
            self.worker.send(name)

    def toggle_debug(self):
        self.debug_enabled = not self.debug_enabled
        self.command("debug")
        self.debug_button.configure(text="จุดอ้างอิง: เปิด" if self.debug_enabled else "จุดอ้างอิง: ปิด")

    def poll(self):
        if self.closing:
            return
        if self.worker and not self.worker.closed.is_set():
            latest = self.worker.latest()
            if latest:
                self.snapshot = latest
                self.render(latest)
        self.root.after(33, self.poll)

    def render(self, data):
        t = self.theme
        status = data.get("status")
        if self.research and data.get("research_rules"):
            self.show_research_rules(data["research_rules"])
        self.update_care_notice(data.get("care_message", ""))
        ready = status == "ready"
        self.set_ready(ready)
        if not ready:
            for control in self.visit_controls:
                control.configure(state="normal")
            self.mode_panel.set_enabled(can_change_mode(data))
            self.setup_check.configure(state="normal")
        if not self.preview:
            self.camera_input.configure(state="disabled" if ready or status in ("loading", "disconnecting") else "normal")
        self.connect_button.configure(state="disabled" if status in ("loading", "disconnecting") else "normal",
                                      text="ตัดการเชื่อมต่อ" if ready else ("เปิดตัวอย่าง" if self.preview else "เชื่อมต่อกล้อง"))
        if not ready:
            message = {"loading": "กำลังเตรียมกล้องและโมเดล ครั้งแรกอาจต้องดาวน์โหลดไฟล์…",
                       "disconnecting": "กำลังตัดการเชื่อมต่อกล้อง…",
                       "disconnected": "ยังไม่เชื่อมต่อ · กล้องปิดอยู่"}.get(status, data.get("message", "ไม่สามารถใช้กล้องได้"))
            self.connection.configure(text=message, fg=t["danger"] if status == "error" else t["muted"], wraplength=560)
            self.video.render(message="ไม่สามารถใช้กล้องได้" if status == "error" else None)
            self.instruction.configure(text="เชื่อมต่อกล้องเพื่อเริ่มต้น" if status != "error" else "เชื่อมต่อใหม่เพื่อลองอีกครั้ง")
            self.progress["value"] = 0
            self.detail.configure(text="จับเวลาเมื่อเห็นจุดอ้างอิงที่จำเป็นครบ")
            self.result_title.configure(text="ยังไม่มีผลปัจจุบัน", fg=t["text"])
            self.set_result_text("เก็บข้อมูลให้ครบเพื่อดูผลสรุป")
            for item in self.stage_labels.values():
                item.configure(fg=t["muted"])
            return
        self.connection.configure(text=("กำลังแสดงตัวอย่าง · ข้อมูลจำลอง" if self.preview else f"เชื่อมต่อกล้องแล้ว · {data.get('fps', 0):.0f} FPS"), fg=t["muted"])
        self.video.render(data.get("frame"))
        state = data.get("state", "idle")
        self.instruction.configure(text=MODES[self.visit_mode.get()][1] if state == "idle" else display_text(data.get("instruction", "")))
        self.start_button.configure(text="เริ่มขั้นตอนใหม่" if state not in ("idle", "summary", "identity_rejected") else MODES[self.visit_mode.get()][3])
        active = state not in ("idle", "summary", "identity_rejected")
        for control in self.visit_controls:
            control.configure(state="disabled" if active else "normal")
        self.mode_panel.set_enabled(not active)
        self.setup_check.configure(state="disabled" if active else "normal")
        self.stop_button.configure(state="disabled" if state == "idle" else "normal")
        duration = next((step[3] for step in STEPS if step[0] == state), 0)
        elapsed = data.get("elapsed", 0)
        self.progress["value"] = min(100, elapsed / duration * 100) if duration else (100 if state == "summary" else 0)
        for key, item in self.stage_labels.items():
            item.configure(fg=t["accent"] if key == state else t["muted"])
        extra = data.get("extra", {})
        detail = f"{elapsed:.1f} / {duration:g} วินาที" if duration else "ทำตามคำแนะนำบนหน้าจอ"
        if extra.get("detected") is False or extra.get("pose_found") is False:
            detail += " · กำลังรอจุดอ้างอิง"
        if state == "eye_test":
            detail += f"\nกะพริบตา · ซ้าย {extra.get('left', 0)} / ขวา {extra.get('right', 0)}"
        self.detail.configure(text=detail)
        comparison = data.get("comparison") or {}
        if comparison.get("alert"):
            self.instruction.configure(text="เกินเกณฑ์ทดลองที่ยังไม่ผ่านการรับรอง ผู้มีอาการผิดปกติต้องได้รับการดูแล" if comparison.get("research_only") else
                                       "ค่าการเปลี่ยนแปลงเกินเกณฑ์ ไปโรงพยาบาลทันที")
            self.update_care_notice(CARE_MESSAGE)
            if not self.alert_notified:
                self.root.bell()
                self.alert_notified = True
        if data.get("command_error"):
            self.instruction.configure(text=display_text(data["command_error"]))
        assessment = data.get("assessment")
        if assessment:
            level = assessment["level"]
            customer_title, customer_body = customer_assessment(assessment, data.get("save_status", ""))
            self.result_title.configure(text=customer_title, fg=t["danger"] if level == "Seek medical attention immediately" or comparison.get("alert") else t["warning"])
            self.set_result_text(customer_body)
        else:
            self.result_title.configure(text="ยังไม่มีผล", fg=t["text"])
            self.set_result_text("ทำตามขั้นตอนให้ครบเพื่อดูผลสรุป")

    def close(self):
        self.closing = True
        if self.dev_window and self.dev_window.window.winfo_exists():
            self.dev_window.close()
        if self.worker:
            self.worker.close()
            if self.worker.thread.is_alive():
                self.connection.configure(text="กำลังปิดกล้องและโมเดล…")
                self.root.after(50, self.close)
                return
        self.root.destroy()
