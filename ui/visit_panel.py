"""Dedicated Thai baseline/recheck controls, independent of camera inference."""

import tkinter as tk
from ui.components import label

from ui.visit_state import MODES


class VisitModePanel(tk.Frame):
    def __init__(self, parent, variable, command, theme):
        super().__init__(parent, bg=theme["surface"], padx=14, pady=10)
        self.variable, self.command, self.theme = variable, command, theme
        self.enabled = True
        self.buttons = {}
        for column, (mode, content) in enumerate(MODES.items()):
            self.columnconfigure(column, weight=1, uniform="mode")
            widget = tk.Button(self, text=content[0], command=lambda value=mode: self.select(value),
                               font=(theme["font"], 12, "bold"), relief="flat", borderwidth=0,
                               pady=9, cursor="hand2", takefocus=True, highlightthickness=2,
                               highlightcolor=theme["text"])
            widget.grid(row=0, column=column, sticky="ew", padx=(0, 8) if column == 0 else (8, 0))
            self.buttons[mode] = widget
        self.title = label(self, "", theme, bold=True, size=12)
        self.title.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 2))
        self.description = label(self, "", theme, muted=True, size=10)
        self.description.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.bind("<Configure>", lambda event: self.description.configure(wraplength=max(200, event.width - 32)))
        self.trace_id = variable.trace_add("write", self.refresh)
        self.refresh()

    def select(self, mode):
        if self.enabled and mode != self.variable.get():
            self.command(mode)

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.refresh()

    def refresh(self, *_):
        selected = self.variable.get()
        t = self.theme
        for mode, widget in self.buttons.items():
            active = mode == selected
            widget.configure(bg=t["accent"] if active else t["background"],
                             fg=t["accent_text"] if active else t["text"],
                             activebackground=t["accent"], activeforeground=t["accent_text"],
                             disabledforeground=t["accent_text"] if active else t["muted"],
                             highlightbackground=t["accent"] if active else t["background"],
                             state="normal" if self.enabled else "disabled")
        content = MODES[selected]
        self.title.configure(text=content[1])
        self.description.configure(text=content[2] if self.enabled else "กำลังเก็บข้อมูล — กดหยุดก่อนเปลี่ยนโหมด")

    def destroy(self):
        self.variable.trace_remove("write", self.trace_id)
        super().destroy()
