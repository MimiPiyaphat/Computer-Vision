"""Local file replay for the unlocked developer window; never creates a visit."""

from pathlib import Path
import time
import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

from ui.components import button, label

ACTION_THAI = {'neutral': 'หน้านิ่ง', 'smile': 'ยิ้ม', 'blink': 'กระพริบตา', 'arms': 'ยกแขน'}
REPO_ROOT = Path(__file__).resolve().parents[1]


def video_path(root, relative):
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root) or candidate.suffix.lower() not in ('.mp4', '.mov', '.avi'):
        raise ValueError('Video path must remain inside the local dataset')
    return candidate


class VolunteerReplay:
    def __init__(self, parent, theme, report):
        self.report, self.theme = report, theme
        self.cap = self.timer = None
        self.playing = False
        self.window = tk.Toplevel(parent)
        self.window.title('วิดีโออาสาสมัคร · เดโมท่าทาง ไม่ใช่ผลตรวจโรค')
        self.window.geometry('800x800')
        self.window.configure(bg=theme['background'])
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        label(self.window, 'เล่นไฟล์เดิม · ไม่บันทึก baseline / ไม่วินิจฉัยโรค', theme, bold=True).pack(pady=8)
        self.selector = ttk.Combobox(self.window, state='readonly', width=65,
                                    values=[f"{r['sample_id']} · {ACTION_THAI.get(r['action'], r['action'])}" for r in report['clips']])
        self.selector.pack(pady=5)
        self.selector.bind('<<ComboboxSelected>>', lambda _: self.load())
        self.info = label(self.window, '', theme, wraplength=760)
        self.info.pack(pady=6)
        controls = tk.Frame(self.window, bg=theme['background'])
        controls.pack()
        button(controls, 'เล่น / พัก', self.toggle, theme).pack(side='left', padx=4)
        button(controls, 'เริ่มคลิปใหม่', self.load, theme).pack(side='left', padx=4)
        self.display = tk.Label(self.window, bg=theme['preview'])
        self.display.pack(fill='both', expand=True, padx=12, pady=12)
        self.selector.current(0)
        self.load()

    def stop(self):
        self.playing = False
        if self.timer is not None:
            self.window.after_cancel(self.timer)
            self.timer = None

    def close(self):
        self.stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.window.destroy()

    def load(self):
        self.stop()
        if self.cap is not None:
            self.cap.release()
        row = self.report['clips'][self.selector.current()]
        try:
            dataset = Path(self.report['dataset_directory'])
            if not dataset.is_absolute():
                dataset = REPO_ROOT / dataset
            path = video_path(dataset, row['path'])
            self.cap = cv2.VideoCapture(str(path))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if not self.cap.isOpened() or not 0 < self.fps < 1000:
                raise ValueError('เปิดวิดีโอไม่ได้')
        except (OSError, ValueError) as exc:
            self.info.configure(text=str(exc))
            return
        result = next((p['predicted'] for p in self.report['predictions'] if p['sample_id'] == row['sample_id']), None)
        prediction = ACTION_THAI.get(result, 'ไม่ประเมินคลิปนี้')
        self.info.configure(text=f"{row['duration_sec']:.1f} วินาที · วัดใบหน้าได้ {row['face_coverage']:.0%} ของเฟรมที่สุ่ม\n"
                                 f"ผลจำแนกแบบแยกคนทดสอบ: {prediction} · label ท่าทางมาจากชื่อไฟล์")
        self.frame_index = 0
        self.started = time.monotonic()
        self.playing = True
        self.tick()

    def toggle(self):
        if self.cap is None or not self.cap.isOpened():
            return
        if self.playing:
            self.stop()
        else:
            self.playing = True
            self.started = time.monotonic() - self.frame_index / self.fps
            self.tick()

    def tick(self):
        self.timer = None
        if not self.playing:
            return
        ok, frame = self.cap.read()
        if not ok:
            self.stop()
            return
        self.frame_index += 1
        h, w = frame.shape[:2]
        scale = min(max(320, self.display.winfo_width()) / w,
                    max(480, self.display.winfo_height()) / h)
        frame = cv2.resize(frame, (max(1, round(w * scale)), max(1, round(h * scale))))
        photo = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        self.display.configure(image=photo)
        self.display.image = photo
        delay = max(1, round((self.started + self.frame_index / self.fps - time.monotonic()) * 1000))
        self.timer = self.window.after(delay, self.tick)
