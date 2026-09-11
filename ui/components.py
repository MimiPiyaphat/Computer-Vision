"""Reusable widgets. Styling comes exclusively from theme tokens."""

import tkinter as tk


def label(parent, text, theme, *, muted=False, size=None, bold=False, **kwargs):
    return tk.Label(parent, text=text, bg=parent.cget("bg"),
                    fg=theme["muted" if muted else "text"],
                    font=(theme["font"], size or theme["font_size"], "bold" if bold else "normal"),
                    anchor="w", justify="left", **kwargs)


def button(parent, text, command, theme, primary=False):
    return tk.Button(parent, text=text, command=command,
                     bg=theme["accent" if primary else "surface"],
                     fg=theme["accent_text" if primary else "text"],
                     activebackground=theme["accent"], activeforeground=theme["accent_text"],
                     disabledforeground=theme["muted"], relief="flat", borderwidth=0,
                     padx=16, pady=10, cursor="hand2", takefocus=True,
                     font=(theme["font"], theme["font_size"], "bold"))


class Card(tk.Frame):
    def __init__(self, parent, theme, title):
        super().__init__(parent, bg=theme["surface"], padx=theme["spacing"], pady=theme["spacing"])
        label(self, title.upper(), theme, muted=True, size=10, bold=True).pack(anchor="w", pady=(0, 12))


class VideoPanel(tk.Canvas):
    def __init__(self, parent, theme, preview=False):
        super().__init__(parent, bg=theme["preview"], highlightthickness=0, width=640, height=400)
        self.theme = theme
        self.preview = preview
        self.photo = None
        self._rgb = None
        self._message = None
        self.bind("<Configure>", lambda _: self.render(self._rgb, self._message))

    def render(self, rgb=None, message=None):
        self._rgb, self._message = rgb, message
        width, height = max(self.winfo_width(), 100), max(self.winfo_height(), 100)
        self.delete("all")
        if rgb is not None:
            from PIL import Image, ImageTk
            picture = Image.fromarray(rgb)
            picture.thumbnail((width, height))
            self.photo = ImageTk.PhotoImage(picture)
            self.create_image(width / 2, height / 2, image=self.photo)
        else:
            self.photo = None
            self.create_oval(width / 2 - 62, height / 2 - 108, width / 2 + 62, height / 2 + 20,
                             outline=self.theme["muted"], width=2)
            self.create_arc(width / 2 - 135, height / 2 + 40, width / 2 + 135, height / 2 + 200,
                            start=0, extent=180, outline=self.theme["muted"], style="arc", width=2)
            self.create_text(width / 2, height - 35, text=message or (
                "ตัวอย่างหน้าจอ / ไม่ได้เชื่อมต่อกล้อง" if self.preview else "เชื่อมต่อกล้องเพื่อเริ่มต้น"),
                fill=self.theme["text"], width=width - 40, font=(self.theme["font"], 11))
