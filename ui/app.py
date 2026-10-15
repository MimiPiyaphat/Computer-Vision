"""Tk dashboard. Presentation only; all inference lives behind SessionWorker."""

import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from config import CAMERA_INDEX, ARM_RAISE_NORMAL_MIN_PERCENT, ARM_REQUIRED_RAISED_HOLD_SEC
from ui.components import Card, VideoPanel, button, label
from ui.content import STEPS
from ui.thai import (SAFETY_TH, CARE_TH, customer_assessment, customer_result_status,
                     STAFF_REVIEW_STATUSES, display_text, configure_fonts)
from ui.visit_panel import VisitModePanel
from ui.visit_state import MODES, can_change_mode
from ui.theme import load_theme
from ui.worker import SessionWorker
from src.protocol import CARE_MESSAGE


def blend(c1, c2, ratio):
    """Mix two #RRGGBB colours; ratio is the weight of c1."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * ratio + y * (1 - ratio)):02X}" for x, y in zip(a, b))


class ThinProgress(tk.Canvas):
    """Slim rounded progress bar; supports progress["value"] = 0..100 like ttk.Progressbar."""

    def __init__(self, master, track, fill, bg, height=8):
        super().__init__(master, height=height, bg=bg, highlightthickness=0, bd=0)
        self._track, self._fill, self._value, self._h = track, fill, 0.0, height
        self.bind("<Configure>", lambda _e: self._draw())

    def __setitem__(self, key, value):
        if key == "value":
            self._value = max(0.0, min(100.0, float(value)))
            self._draw()
        else:
            super().__setitem__(key, value)

    def _draw(self):
        self.delete("all")
        w, h = max(self.winfo_width(), self._h), self._h
        r = h / 2
        self.create_line(r, r, w - r, r, width=h, capstyle="round", fill=self._track)
        if self._value > 0:
            self.create_line(r, r, r + (w - h) * self._value / 100, r, width=h, capstyle="round", fill=self._fill)


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
        root.title("StrokeVision" + (" [ตัวอย่างหน้าจอ]" if preview else ""))
        root.geometry("1280x1000")
        root.minsize(1080, 900)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<F5>", lambda _: self.reload_theme())
        root.bind("<Control-Shift-D>", lambda _: self.open_dev())
        root.bind("<MouseWheel>", self.scroll_page)
        self.build()
        self.poll()

    # ------------------------------------------------------------------ widgets
    def style_button(self, btn, kind, enabled=True):
        """Flat button styles: primary (filled), outline (accent border), ghost (neutral border), link (red text)."""
        t = self.theme
        common = dict(relief="flat", bd=0, disabledforeground=t["muted"], activeforeground=t["accent"])
        if kind == "primary" and enabled:
            btn.configure(bg=t["accent"], fg=t["accent_text"], activebackground=blend(t["accent"], "#000000", 0.85),
                          activeforeground=t["accent_text"], highlightthickness=0, **{k: v for k, v in common.items()
                          if k not in ("activeforeground",)})
        elif kind == "link":
            btn.configure(bg=btn.master.cget("bg"), fg=t["danger"], activebackground=btn.master.cget("bg"),
                          activeforeground=t["danger"], highlightthickness=0,
                          **{k: v for k, v in common.items() if k != "activeforeground"})
        else:
            accent = kind == "outline" and enabled
            btn.configure(bg=t["surface"], fg=t["accent"] if accent else (t["text"] if enabled else t["muted"]),
                          activebackground=t["preview"], highlightthickness=1,
                          highlightbackground=t["accent"] if accent else self.border,
                          highlightcolor=t["accent"] if accent else self.border, **common)

    def flat_button(self, parent, text, command, kind="outline"):
        t = self.theme
        btn = tk.Button(parent, text=text, command=command, cursor="hand2", takefocus=0,
                        font=(t["font"], t["font_size"], "bold" if kind in ("primary", "link") else "normal"),
                        padx=18, pady=9)
        self.style_button(btn, kind, True)
        return btn

    def set_overlay(self, visible, title="เชื่อมต่อกล้องเพื่อเริ่มต้น", status="", error=False):
        """Placeholder shown inside the preview area while the camera is not streaming."""
        if not visible:
            self.overlay.place_forget()
            return
        self.overlay_title.configure(text=title)
        self.overlay_status.configure(text=status, fg=self.theme["danger"] if error else self.theme["muted"])
        self.overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.overlay.lift()

    def toggle_settings(self, _event=None):
        self.settings_open = not self.settings_open
        if self.settings_open:
            self.settings_row.pack(fill="x", padx=12, pady=(10, 0), before=self.video_stage)
        else:
            self.settings_row.pack_forget()
        self.settings_toggle.configure(text=("▾" if self.settings_open else "▸") + " ตั้งค่าเพิ่มเติม (กล้อง, จุดอ้างอิง)")

    def paint_stage(self, key, kind):
        """kind: active | done | wait | warn"""
        t = self.theme
        badge, title = self.stage_badges[key], self.stage_labels[key]
        number = self.stage_numbers[key]
        fill, num_fg, title_fg, bold, text = {
            "active": (t["accent"], t["accent_text"], t["text"], True, number),
            "done": (blend(t["accent"], t["surface"], 0.18), t["accent"], t["text"], False, "✓"),
            "warn": (t["warning"], "#FFFFFF", t["text"], True, number),
            "wait": (blend(t["muted"], t["surface"], 0.18), t["muted"], t["muted"], False, number),
        }[kind]
        badge.itemconfigure("bg", fill=fill)
        badge.itemconfigure("num", fill=num_fg, text=text)
        title.configure(fg=title_fg, font=(t["font"], t["font_size"], "bold" if bold else "normal"))

    def paint_stages_idle(self):
        for index, step in enumerate(STEPS):
            if step[0] in self.stage_labels:
                self.paint_stage(step[0], "active" if index == 0 else "wait")

    # ------------------------------------------------------------------ layout
    def build(self):
        t = self.theme
        self.border = blend(t["muted"], t["surface"], 0.35)
        self.settings_open = True
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

        # ---- header: title + subtitle on the left; Dev / reload theme / mode switch on the right
        header = tk.Frame(self.container, bg=t["background"])
        header.pack(fill="x", pady=(0, 18))
        title = label(header, "StrokeVision", t, size=24, bold=True)
        title.configure(fg=t["accent"])
        title.pack(side="left")
        label(header, "บันทึกก่อนนวดและตรวจซ้ำ", t, muted=True, size=10).pack(side="left", padx=(12, 0), anchor="s", pady=(0, 6))
        self.mode_panel = VisitModePanel(header, self.visit_mode, self.change_mode, t)
        self.mode_panel.pack(side="right")
        self.flat_button(header, "โหลดธีมใหม่", self.reload_theme, "ghost").pack(side="right", padx=(0, 10))
        self.flat_button(header, "Dev", self.open_dev, "ghost").pack(side="right", padx=(0, 10))

        if self.research:
            from src.research import load_parameters
            parameters = load_parameters()
            self.research_banner = label(self.container, "", t, bold=True, size=10, wraplength=1100)
            self.research_banner.pack(anchor="w", pady=(0, 12))
            self.show_research_rules(parameters)

        body = tk.Frame(self.container, bg=t["background"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=65, uniform="body")
        body.columnconfigure(1, weight=35, uniform="body")
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=t["background"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        right = tk.Frame(body, bg=t["background"])
        right.grid(row=0, column=1, sticky="nsew")

        # ---- left column, card 1: customer
        visit = tk.Frame(left, bg=t["surface"], padx=20, pady=16)
        visit.pack(fill="x", pady=(0, 16))
        visit_header = tk.Frame(visit, bg=t["surface"])
        visit_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        label(visit_header, "ผู้รับบริการ", t, size=14, bold=True).pack(side="left")
        self.flat_button(visit_header, "+ ผู้รับบริการใหม่", self.new_customer, "outline").pack(side="right")
        self.visit_controls = []
        for column, (caption, variable) in enumerate((("รหัสผู้รับบริการ / QR สมาชิก", self.user_id), ("รหัสครั้งรับบริการ", self.visit_id))):
            label(visit, caption, t, muted=True, size=10).grid(row=1, column=column, sticky="w")
            entry = tk.Entry(visit, textvariable=variable, show="*" if column == 0 else "", font=(t["font"], t["font_size"]),
                             relief="flat", bg=t["surface"], fg=t["text"], insertbackground=t["text"],
                             disabledbackground=t["preview"], highlightthickness=1,
                             highlightbackground=self.border, highlightcolor=t["accent"])
            entry.grid(row=2, column=column, sticky="ew", padx=(0, 16 if column == 0 else 0), pady=(4, 12), ipady=8)
            visit.columnconfigure(column, weight=1, uniform="visit")
            self.visit_controls.append(entry)
        self.symptom_check = tk.Checkbutton(visit, text="มีอาการผิดปกติ (ถ้ามี กรุณาเลือกเพื่อแสดงคำแนะนำฉุกเฉิน)", variable=self.symptoms_reported,
                       command=self.symptom_changed, bg=t["surface"], fg=t["text"], selectcolor=t["surface"],
                       activebackground=t["surface"], activeforeground=t["text"], font=(t["font"], 10))
        self.symptom_check.grid(row=3, column=0, columnspan=2, sticky="w")
        self.visit_controls.append(self.symptom_check)
        self.update_symptom_visibility()
        self.setup_check = tk.Checkbutton(visit, text="ยืนยันกล้องและจุดตรวจเดิม ทำตามท่าที่กำหนด และมองตรง",
                       variable=self.setup_confirmed, bg=t["surface"], fg=t["text"], selectcolor=t["surface"],
                       activebackground=t["surface"], activeforeground=t["text"], font=(t["font"], 10))
        self.setup_check.grid(row=4, column=0, columnspan=2, sticky="w")

        # ---- left column, card 2: camera preview + actions
        card = tk.Frame(left, bg=t["surface"], padx=20, pady=16)
        card.pack(fill="both", expand=True)
        self.video_holder = tk.Frame(card, bg=t["preview"])
        self.video_holder.pack(fill="both", expand=True)

        # Camera number (left) and reference points (right) sit on the top edge of the preview area.
        self.settings_row = tk.Frame(self.video_holder, bg=t["preview"])
        self.settings_row.pack(fill="x", padx=12, pady=(10, 0))
        if not self.preview:
            cam = label(self.settings_row, "กล้อง", t)
            cam.configure(bg=t["preview"], fg=t["text"])
            cam.pack(side="left")
            self.camera_input = tk.Spinbox(self.settings_row, from_=0, to=9, width=3, textvariable=self.camera_index,
                                          font=(t["font"], t["font_size"]), relief="flat", bg=t["surface"],
                                          highlightthickness=1, highlightbackground=self.border)
            self.camera_input.pack(side="left", padx=(8, 0))
        self.debug_button = self.flat_button(self.settings_row, self.debug_text(), self.toggle_debug, "ghost")
        self.debug_button.configure(padx=12, pady=4)
        self.debug_button.pack(side="right")

        self.video_stage = tk.Frame(self.video_holder, bg=t["preview"])
        self.video_stage.pack(fill="both", expand=True)
        self.video = VideoPanel(self.video_stage, t, self.preview)
        self.video.pack(fill="both", expand=True)

        # Placeholder drawn over the preview while the camera is off.
        self.overlay = tk.Frame(self.video_stage, bg=t["preview"])
        inner = tk.Frame(self.overlay, bg=t["preview"])
        inner.place(relx=0.5, rely=0.5, anchor="center")
        icon = tk.Canvas(inner, width=112, height=114, bg=t["preview"], highlightthickness=0)
        icon.create_oval(31, 4, 81, 54, outline=t["muted"], width=2)
        icon.create_arc(8, 64, 104, 164, start=0, extent=180, style="arc", outline=t["muted"], width=2)
        icon.pack()
        self.overlay_title = label(inner, "เชื่อมต่อกล้องเพื่อเริ่มต้น", t, bold=True)
        self.overlay_title.configure(bg=t["preview"], fg=t["text"])
        self.overlay_title.pack(pady=(14, 4))
        self.overlay_status = label(inner, "", t, muted=True, size=10, wraplength=480)
        self.overlay_status.configure(bg=t["preview"])
        self.overlay_status.pack()

        # Shown only while streaming (FPS readout); idle/error text lives in the placeholder.
        self.connection = label(card, "", t, muted=True, size=10)

        actions = tk.Frame(card, bg=t["surface"])
        actions.pack(fill="x", pady=(16, 0))
        actions.columnconfigure(0, weight=1, uniform="actions")
        actions.columnconfigure(1, weight=1, uniform="actions")
        self.connect_button = self.flat_button(actions, "เปิดตัวอย่าง" if self.preview else "เชื่อมต่อกล้อง", self.connect, "primary")
        self.connect_button.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.start_button = self.flat_button(actions, MODES[self.visit_mode.get()][3], self.start_visit, "outline")
        self.start_button.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        self.stop_button = self.flat_button(actions, "หยุด", lambda: self.command("stop"), "link")
        self.stop_button.grid(row=0, column=2, padx=(0, 4))

        self.settings_toggle = label(card, "▾ ตั้งค่าเพิ่มเติม (กล้อง, จุดอ้างอิง)", t, muted=True, size=10)
        self.settings_toggle.configure(cursor="hand2")
        self.settings_toggle.bind("<Button-1>", self.toggle_settings)
        self.settings_toggle.pack(anchor="w", pady=(14, 0))

        # ---- right column, card 2 (displayed below steps): current step (accent background)
        current = tk.Frame(right, bg=t["accent"], padx=20, pady=18)
        self.current_step = label(current, "ขั้นตอนปัจจุบัน", t, size=10)
        self.current_step.configure(bg=t["accent"], fg=t["accent_text"], anchor="w", justify="left")
        self.current_step.pack(fill="x")
        self.instruction = label(current, "เชื่อมต่อกล้องเพื่อเริ่มต้น", t, size=16, bold=True, wraplength=360)
        self.instruction.configure(bg=t["accent"], fg=t["accent_text"], anchor="w", justify="left")
        self.instruction.pack(fill="x", pady=(8, 0))
        self.progress = ThinProgress(current, track=blend(t["accent_text"], t["accent"], 0.3),
                                     fill=t["accent_text"], bg=t["accent"])
        self.progress.pack(fill="x", pady=(14, 0))
        self.detail = label(current, "", t, size=10, wraplength=360)
        self.detail.configure(bg=t["accent"], fg=t["accent_text"], anchor="w", justify="left")
        self.detail.pack(fill="x", pady=(8, 0))

        # ---- right column, card 1: numbered steps
        stages = Card(right, t, "ขั้นตอนการเก็บข้อมูล")
        stages.configure(padx=20, pady=16)
        stages.pack(fill="x", pady=(0, 16))
        current.pack(fill="x", pady=(0, 16))  # shown below the steps card
        self.stage_labels, self.stage_badges, self.stage_numbers = {}, {}, {}
        for index, (state, step_title, _, _) in enumerate(STEPS):
            row = tk.Frame(stages, bg=t["surface"])
            row.pack(fill="x", pady=5)
            badge = tk.Canvas(row, width=24, height=24, bg=t["surface"], highlightthickness=0)
            badge.create_oval(1, 1, 23, 23, outline="", tags="bg")
            badge.create_text(12, 12, text=str(index + 1), font=(t["font"], 9, "bold"), tags="num")
            badge.pack(side="left")
            item = label(row, step_title, t)
            item.configure(bg=t["surface"], anchor="w")
            item.pack(side="left", padx=(12, 0))
            self.stage_labels[state] = item
            self.stage_badges[state] = badge
            self.stage_numbers[state] = str(index + 1)
        self.paint_stages_idle()

        # ---- right column, card 3: result
        result = Card(right, t, "ผลของคุณ")
        result.configure(padx=20, pady=16)
        result.pack(fill="x")
        self.result_title = label(result, "ยังไม่มีผล", t, bold=True, wraplength=360)
        self.result_title.pack(fill="x")
        self.result_body = ScrolledText(result, height=4, width=28, wrap="word", relief="flat",
                                       bg=t["surface"], fg=t["muted"],
                                       font=(t["font"], t["font_size"]), borderwidth=0)
        self.result_body.vbar.pack_forget()  # wheel scrolling still works; no scrollbar chrome
        self.result_body.pack(fill="x", pady=(6, 0))
        self.set_result_text("ทำตามขั้นตอนให้ครบเพื่อดูผลสรุป")

        # Keep symptom guidance visible even when the main page is scrolled.
        self.footer = label(self.root, SAFETY_TH, t, muted=True, size=10, wraplength=1120)
        self.footer.pack(side="bottom", fill="x", padx=t["spacing"], pady=(8, 12))
        self.update_care_notice()
        self.set_overlay(True, status="ยังไม่เชื่อมต่อ - กล้องปิดอยู่")
        self.set_ready(False)
        self.video.render()
        if self.snapshot:
            self.render(self.snapshot)

    def debug_text(self):
        return "จุดอ้างอิง : เปิด" if self.debug_enabled else "จุดอ้างอิง : ปิด"

    # ----------------------------------------------------------------------------------------------------
    def open_color_picker(self):
        from tkinter import colorchooser
        # เปิดหน้าต่างให้ผู้ใช้เลือกสี
        color_code = colorchooser.askcolor(title="เลือกสีธีม", parent=self.root)
        
        # ถ้าผู้ใช้กดเลือกสีและไม่ได้กดยกเลิก
        if color_code and color_code[1]:
            hex_color = color_code[1]
            print(f"รหัสสีที่เลือก: {hex_color}")
            # สามารถเขียนโค้ดเพื่อนำ hex_color ไปบันทึกลงไฟล์ theme.json ต่อได้ที่นี่
    # ----------------------------------------------------------------------------------------------------   

    def resize_page(self, _event=None):
        width = max(1, self.page_canvas.winfo_width())
        height = max(self.page_canvas.winfo_height(), self.container.winfo_reqheight())
        self.page_canvas.itemconfigure(self.page_window, width=width, height=height)
        self.page_canvas.configure(scrollregion=(0, 0, width, height))
        self.footer.configure(wraplength=max(200, width - 2 * self.theme["spacing"]))
        if self.research:
            self.research_banner.configure(wraplength=max(200, width - 2 * self.theme["spacing"]))

    def open_dev(self):
        if self.dev_window and self.dev_window.window.winfo_exists():
            self.dev_window.window.lift()
            return
        from ui.dev_dashboard import DevDashboard
        self.dev_window = DevDashboard(self.root, self.theme, self.dev_access)

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
        self.update_symptom_visibility()
        self.setup_confirmed.set(False)
        # Keep IDs for the same visit, and preserve symptom reports/care notices.
        self.command("stop")
        if self.snapshot:
            self.snapshot = {**self.snapshot, "state": "idle", "assessment": None,
                             "comparison": None, "extra": {}, "visit_mode": None,
                             "save_status": "", "command_error": "", "elapsed": 0}
            self.render(self.snapshot)
        self.start_button.configure(text=MODES[mode][3])

    def update_symptom_visibility(self):
        if self.visit_mode.get() == "recheck":
            self.symptom_check.grid()
        else:
            self.symptom_check.grid_remove()

    def set_ready(self, ready):
        for control in (self.start_button, self.stop_button, self.debug_button):
            control.configure(state="normal" if ready else "disabled")
        self.style_button(self.start_button, "primary" if ready else "outline", ready)
        self.style_button(self.stop_button, "link", ready)
        self.style_button(self.debug_button, "ghost", ready)

    def show_research_rules(self, parameters):
        self.research_banner.configure(
            text=(f"โหมดวิจัย • ยังไม่ผ่านการรับรอง | เกณฑ์ใบหน้า {parameters['face_delta_threshold']:.2f} | "
                  f"ยกแขน {ARM_RAISE_NORMAL_MIN_PERCENT:.0f}% ค้าง {ARM_REQUIRED_RAISED_HOLD_SEC:.0f} วินาที | "
                  f"มุมแขน 2D {parameters['arm_angle_delta_threshold_deg']:.1f}° | ยังไม่ได้ยืนยันประสิทธิภาพ"))

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
        self.update_symptom_visibility()
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
                   "symptoms_reported": self.visit_mode.get() == "recheck" and self.symptoms_reported.get(),
                   "setup_confirmed": self.setup_confirmed.get()}
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

    # ----------------------------------------------------------------------------------------------------
    def change_theme_color(self, hex_color):
        import json
        from ui.theme import THEME_PATH

        try:
            # อ่านไฟล์ theme.json เดิม
            with open(THEME_PATH, "r", encoding="utf-8") as f:
                theme_data = json.load(f)
            
            # เปลี่ยนสี accent เป็นสีที่ผู้ใช้เลือก
            theme_data["accent"] = hex_color
            
            # บันทึกทับไฟล์เดิม
            with open(THEME_PATH, "w", encoding="utf-8") as f:
                json.dump(theme_data, f, indent=2)
                
            # โหลด UI ใหม่เพื่อแสดงสีที่เปลี่ยน
            self.reload_theme()
        except Exception as exc:
            messagebox.showerror("ไม่สามารถเปลี่ยนสีได้", str(exc), parent=self.root)
    # ----------------------------------------------------------------------------------------------------

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
        self.debug_button.configure(text=self.debug_text())

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
                       "disconnected": "ยังไม่เชื่อมต่อ - กล้องปิดอยู่"}.get(status, data.get("message", "ไม่สามารถใช้กล้องได้"))
            self.connection.pack_forget()
            self.set_overlay(True, "ไม่สามารถใช้กล้องได้" if status == "error" else "เชื่อมต่อกล้องเพื่อเริ่มต้น",
                             message, error=status == "error")
            self.video.render(message="ไม่สามารถใช้กล้องได้" if status == "error" else None)
            self.current_step.configure(text="ขั้นตอนปัจจุบัน", fg=t["accent_text"])
            self.instruction.configure(text="เชื่อมต่อกล้องเพื่อเริ่มต้น" if status != "error" else "เชื่อมต่อใหม่เพื่อลองอีกครั้ง")
            self.progress["value"] = 0
            self.detail.configure(text="")
            self.result_title.configure(text="ยังไม่มีผล", fg=t["text"])
            self.set_result_text("ทำตามขั้นตอนให้ครบเพื่อดูผลสรุป")
            self.paint_stages_idle()
            return
        self.set_overlay(False)
        if not self.connection.winfo_manager():
            self.connection.pack(fill="x", pady=(8, 0), after=self.video_holder)
        self.connection.configure(text=("กำลังแสดงตัวอย่าง · ข้อมูลจำลอง" if self.preview else f"เชื่อมต่อกล้องแล้ว · {data.get('fps', 0):.0f} FPS"), fg=t["muted"])
        self.video.render(data.get("frame"))
        state = data.get("state", "idle")
        # Identity checks pause acquisition without changing its numbered step.
        stage_state = data.get("acquisition_state", state) if state == "identity_check" else state
        stage_index = next((i for i, step in enumerate(STEPS) if step[0] == stage_state), None)
        mode_title = "หลังนวด" if (data.get("visit_mode") or self.visit_mode.get()) == "recheck" else "ก่อนนวด"
        step_heading = (f"{mode_title} · ขั้นตอนที่ {stage_index + 1} / {len(STEPS)} · {STEPS[stage_index][1]}"
                        if stage_index is not None else f"{mode_title} · เตรียมเริ่มตรวจ")
        if state == "identity_check":
            step_heading += " · พักเพื่อยืนยันบุคคล"
        elif state == "identity_rejected":
            step_heading = f"{mode_title} · หยุดการตรวจเพื่อยืนยันบุคคล"
        if data.get("command_error"):
            step_heading = f"{mode_title} · ยังเริ่มตรวจไม่ได้"
        self.current_step.configure(text=step_heading, fg=t["accent_text"])
        if state == "summary":
            self.progress.pack_forget()  # A full green bar could be read as a normal result.
        else:
            self.progress.pack(fill="x", pady=(14, 0), before=self.detail)
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
        for index, (key, title, _, _) in enumerate(STEPS):
            if key not in self.stage_labels:
                continue
            # A failed summary must not mark every measurement as completed.
            passed = stage_index is not None and index < stage_index and state != "summary"
            if key == stage_state:
                kind = "warn" if state == "identity_check" else "active"
            else:
                kind = "done" if passed else "wait"
            self.paint_stage(key, kind)
        if stage_index is None and state == "idle":
            self.paint_stages_idle()
        extra = data.get("extra", {})
        stage = next((step for step in STEPS if step[0] == state), None)
        detail = (f"{stage[1]} · เหลืออีก {max(0, duration - elapsed):.1f} วินาที"
                  if duration else "ทำตามคำแนะนำบนหน้าจอ")
        if extra.get("detected") is False or extra.get("pose_found") is False:
            detail += " · กำลังรอจุดอ้างอิง"
        if extra.get("capture_paused"):
            detail += " · หยุดจับเวลาไว้จนกว่าจะเห็นจุดอ้างอิงครบ"
        if data.get("timeout_remaining") is not None and active:
            detail += f"\nเวลาสูงสุดของขั้นตอนนี้ {data['timeout_remaining']:.0f} วินาที"
        if state == "eye_test":
            detail += f"\nกะพริบตา · ซ้าย {extra.get('left', 0)} / ขวา {extra.get('right', 0)}"
        if state == "arm_test":
            arm = extra.get("arm_function") or {}
            if arm.get("raise_percent") is not None:
                detail += (f"\nยกแขนได้ {arm['raise_percent']:.0f}% / เกณฑ์ {arm['required_raise_percent']:.0f}%"
                           f" · ค้าง {arm['hold_sec']:.1f}/{arm['required_hold_sec']:.1f} วินาที")
        if state == "identity_check":
            detail = "พักการเก็บข้อมูลชั่วคราว · ทำตามคำแนะนำเพื่อกลับไปยังขั้นตอนเดิม"
        elif stage_index is not None and state != "summary":
            detail += f"\nขั้นตอนถัดไป: {STEPS[stage_index + 1][1]}"
        elif state == "idle":
            detail = "กดเริ่มเมื่อพร้อม ระบบจะพาทำทีละขั้นตอนโดยอัตโนมัติ"
        self.detail.configure(text=detail)
        comparison = data.get("comparison") or {}
        if comparison.get("alert"):
            # Alerts persist in the result card/footer, never over the current
            # action (including identity pauses and missing-landmark guidance).
            self.update_care_notice(CARE_MESSAGE)
            if not self.alert_notified:
                self.root.bell()
                self.alert_notified = True
        if data.get("command_error"):
            self.instruction.configure(text="กรุณาแจ้งเจ้าหน้าที่ · ดูสาเหตุและวิธีแก้ไขในช่องผลด้านล่าง")
            self.detail.configure(text="ยังไม่ได้เริ่มขั้นตอนการตรวจ")
            self.progress.pack_forget()
        assessment = data.get("assessment")
        if assessment or comparison.get("alert"):
            level = assessment.get("level", "") if assessment else ""
            customer_title, customer_body = customer_assessment(assessment or {}, comparison)
            if not assessment:
                customer_body = "พบค่าที่เปลี่ยนมากระหว่างตรวจ\n" + customer_body
            result_status = customer_result_status(assessment or {}, comparison)
            color = t["danger"] if level == "Seek medical attention immediately" or comparison.get("alert") else (
                t["accent"] if result_status == "baseline_saved" else t["warning"])
            self.result_title.configure(text=customer_title, fg=color)
            self.set_result_text(customer_body)
            if state == "summary":
                # Finishing the capture sequence does not guarantee a usable
                # assessment. Keep the current-step card consistent with it.
                if not data.get("command_error"):
                    self.instruction.configure(text="จบขั้นตอนแล้ว · ดูผลและสิ่งที่ควรทำด้านล่าง")
                needs_review = customer_result_status(assessment, comparison) in STAFF_REVIEW_STATUSES
                self.progress["value"] = 0 if needs_review else 100
                self.detail.configure(text="สิ้นสุดขั้นตอนแล้ว · กรุณาตรวจใหม่อีกครั้ง" if needs_review else
                                      "สิ้นสุดขั้นตอนแล้ว · อ่านรายละเอียดผลด้านล่าง")
                if "summary" in self.stage_labels:
                    self.paint_stage("summary", "warn" if needs_review else "active")
                if result_status == "acquisition_failed" and not data.get("command_error"):
                    self.start_button.configure(text="เก็บข้อมูลใหม่อีกครั้ง")
                    self.current_step.configure(text=f"{mode_title} · กรุณาตรวจใหม่", fg=t["accent_text"])
                    self.instruction.configure(text="กด ‘เก็บข้อมูลใหม่อีกครั้ง’ เมื่อพร้อม")
                    self.detail.configure(text="เริ่มตั้งแต่ขั้นตอนที่ 1 · ใช้รหัสเดิมได้")
                    if comparison.get("alert") or comparison.get("prior_alert"):
                        self.instruction.configure(text="แจ้งเจ้าหน้าที่ทันที · ไม่ต้องรอเก็บข้อมูลใหม่ให้ครบ")
        else:
            if data.get("command_error"):
                self.result_title.configure(text="เริ่มการตรวจไม่ได้ · กรุณาแก้ไขก่อน", fg=t["warning"])
                self.set_result_text(display_text(data["command_error"]) +
                                     "\n\nขั้นตอนต่อไป: แก้ไขข้อมูลหรือการตั้งค่าตามคำแนะนำ แล้วกดเริ่มตรวจอีกครั้ง")
            else:
                self.result_title.configure(text="กำลังเก็บข้อมูล" if active else "ยังไม่ได้เริ่มตรวจ", fg=t["text"])
                self.set_result_text("ทำตามคำแนะนำในช่องขั้นตอนปัจจุบัน ระบบจะแสดงผลเมื่อเก็บข้อมูลเสร็จ" if active else
                                     "เริ่มบันทึกข้อมูลเพื่อใช้เปรียบเทียบก่อนและหลังนวด")

    def close(self):
        self.closing = True
        if self.dev_window and self.dev_window.window.winfo_exists():
            self.dev_window.close()
        if self.worker:
            self.worker.close()
            if self.worker.thread.is_alive():
                self.set_overlay(True, status="กำลังปิดกล้องและโมเดล…")
                self.root.after(50, self.close)
                return
        self.root.destroy()