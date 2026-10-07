"""Password-gated developer metrics; independent of camera inference."""

import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from ui.components import button, label


def percent(value):
    return '—' if value is None else f'{value * 100:.2f}%'


class DevDashboard:
    def __init__(self, parent, theme, access):
        self.theme, self.access = theme, access
        self.window = tk.Toplevel(parent)
        self.window.title('StrokeVision · Developer metrics')
        self.window.geometry('1100x820')
        self.window.minsize(900, 680)
        self.window.configure(bg=theme['background'])
        self.window.transient(parent)
        self.lock_timer = None
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.login()

    def close(self):
        if self.lock_timer is not None:
            self.window.after_cancel(self.lock_timer)
            self.lock_timer = None
        self.window.destroy()

    def clear(self):
        for child in self.window.winfo_children():
            child.destroy()

    def login(self):
        if self.lock_timer is not None:
            self.window.after_cancel(self.lock_timer)
            self.lock_timer = None
        self.clear()
        self.window.unbind('<Return>')
        panel = tk.Frame(self.window, bg=self.theme['surface'], padx=32, pady=32)
        panel.place(relx=.5, rely=.5, anchor='center')
        label(panel, 'สำหรับผู้พัฒนา', self.theme, size=22, bold=True).pack(anchor='w')
        label(panel, 'ใส่รหัสผ่านเพื่อดูผลการเทรนและ confusion matrix', self.theme, muted=True).pack(pady=16)
        self.password = tk.Entry(panel, show='●', font=(self.theme['font'], 16), width=28)
        self.password.pack(fill='x')
        self.error = label(panel, '', self.theme, wraplength=500)
        self.error.pack(pady=12)
        button(panel, 'เข้าสู่หน้า dev', self.unlock, self.theme, primary=True).pack(fill='x')
        self.window.bind('<Return>', lambda _: self.unlock())
        self.password.focus_set()

    def unlock(self):
        password = self.password.get()
        self.password.delete(0, 'end')
        try:
            report = self.access.unlock(password)
        except (PermissionError, ValueError, OSError) as exc:
            self.error.configure(text=str(exc), fg=self.theme['danger'])
            return
        self.window.unbind('<Return>')
        self.render(report)

    def render(self, report):
        self.clear()
        self.lock_timer = self.window.after(300000, self.login)
        t = self.theme
        header = tk.Frame(self.window, bg=t['background'], padx=16, pady=12)
        header.pack(fill='x')
        label(header, 'Developer · Model evaluation', t, size=20, bold=True).pack(side='left')
        button(header, 'ล็อก / ออกจากหน้า dev', self.login, t).pack(side='right')
        if report is None:
            label(self.window, 'ยังไม่มีรายงานการเทรนใหม่\nเมื่อเทรนเสร็จ ให้ล็อกแล้วเข้าสู่หน้านี้อีกครั้ง',
                  t, size=16).pack(pady=40)
            return
        label(self.window, 'โมเดลท่ากายภาพบำบัด · ผลเหล่านี้ไม่ใช่ความแม่นยำในการตรวจ stroke',
              t, bold=True, wraplength=1000).pack(anchor='w', padx=16, pady=4)
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=16, pady=12)
        for split, name in [('test', 'Test · ผลทดสอบ'), ('validation', 'Validation · เลือกโมเดล'), ('train', 'Train · ชุดฝึก')]:
            panel = tk.Frame(notebook, bg=t['background'])
            notebook.add(panel, text=name)
            self.split_panel(panel, report[split], report['subjects'][split])
        curves = tk.Frame(notebook, bg=t['background'])
        notebook.add(curves, text='กราฟการเทรน')
        self.curves(curves, report)
        provenance = tk.Frame(notebook, bg=t['background'])
        notebook.add(provenance, text='ข้อมูลการทดลอง / Stroke')
        text = ScrolledText(provenance, wrap='word', bg=t['surface'], fg=t['text'], font=(t['font'], 12), relief='flat')
        text.pack(fill='both', expand=True, padx=12, pady=12)
        lines = [f"สร้างรายงาน: {report['created_at']}", f"โมเดล: {report['selected_kind']} · epoch {report['best_epoch']}",
                 f"เลือกจาก: {report['selection_metric']}", f"ไฟล์: {report['model_file']}",
                 f"SHA256: {report['model_sha256']}", '',
                 'การประเมิน StrokeVision จากใบหน้าและแขน:',
                 'ยังไม่มีชุดข้อมูลก่อน–หลังพร้อมผลกำกับ จึงยังไม่มี accuracy, confusion matrix หรือเปอร์เซ็นต์ความเสี่ยง stroke', '',
                 'ชุด Train / Validation / Test แยกคนกันทั้งหมด',
                 'ช่วงความเชื่อมั่นบนหน้า Test คิดระดับคลิป; คลิปจากคนเดียวกันมีความสัมพันธ์กัน',
                 'Test นี้เคยถูกดูในงานทดลองรุ่นเก่าแล้ว จึงไม่ใช่ external validation ใหม่', '', 'ข้อจำกัด:']
        lines.extend(report.get('limitations', []))
        lines.append('\nผล validation ของตัวเลือกที่ลอง:')
        for trial in report['trials']:
            lines.append(f"{trial['kind']}: status macro F1 {percent(trial['validation']['status']['macro_f1'])}, epoch {trial['best_epoch']}")
        text.insert('1.0', '\n'.join(lines))
        text.configure(state='disabled')

    def split_panel(self, parent, metrics, subjects):
        t = self.theme
        label(parent, f"{metrics['status']['samples']} คลิป · {len(subjects)} คน · subject IDs: {', '.join(subjects)}",
              t, muted=True).pack(anchor='w', padx=12, pady=10)
        tasks = ttk.Notebook(parent)
        tasks.pack(fill='both', expand=True, padx=10, pady=5)
        for key, title in [('status', 'ทำท่าครบ / ไม่ครบ'), ('exercise', 'ชนิดท่ากายภาพ')]:
            panel = tk.Frame(tasks, bg=t['background'])
            tasks.add(panel, text=title)
            self.task_panel(panel, metrics[key])

    def task_panel(self, panel, metrics):
        t = self.theme
        summary = ('Accuracy ' + percent(metrics['accuracy']) + '     Macro precision ' + percent(metrics['macro_precision']) +
                   '\nMacro recall ' + percent(metrics['macro_recall']) + '     Macro F1 ' + percent(metrics['macro_f1']))
        label(panel, summary, t, size=14, bold=True).pack(anchor='w', padx=12, pady=10)
        lo, hi = metrics['accuracy_wilson_95ci']
        label(panel, f'Accuracy 95% CI (รายคลิป): {percent(lo)} – {percent(hi)}', t, muted=True).pack(anchor='w', padx=12)
        label(panel, 'Confusion matrix · แถว = จริง / คอลัมน์ = ทำนาย · ตัวเลขคือจำนวนคลิป', t).pack(anchor='w', padx=12, pady=8)
        canvas = tk.Canvas(panel, bg=t['surface'], highlightthickness=0, height=240)
        canvas.pack(fill='x', padx=12)
        canvas.bind('<Configure>', lambda _: self.matrix(canvas, metrics))
        table = ttk.Treeview(panel, columns=('class', 'precision', 'recall', 'f1', 'support'), show='headings', height=4)
        for col, title in zip(table['columns'], ('Class', 'Precision', 'Recall', 'F1', 'Support')):
            table.heading(col, text=title)
            table.column(col, width=240 if col == 'class' else 100, anchor='w')
        for row in metrics['per_class']:
            table.insert('', 'end', values=(row['label'], percent(row['precision']), percent(row['recall']), percent(row['f1']), row['support']))
        table.pack(fill='x', padx=12, pady=10)

    def matrix(self, canvas, metrics):
        canvas.delete('all')
        labels = metrics['labels']
        n = len(labels)
        left, top = 175, 48
        width = max(500, canvas.winfo_width())
        cell_w, cell_h = (width - left - 15) / n, 42
        maximum = max(max(row) for row in metrics['confusion_matrix']) or 1
        for i, name in enumerate(labels):
            short = name.replace('_', ' ')
            canvas.create_text(left + (i + .5) * cell_w, 22, text=short, width=cell_w - 8, fill=self.theme['text'], font=(self.theme['font'], 9))
            canvas.create_text(8, top + (i + .5) * cell_h, anchor='w', text=short, width=160, fill=self.theme['text'], font=(self.theme['font'], 9))
            for j, value in enumerate(metrics['confusion_matrix'][i]):
                intensity = value / maximum
                color = f'#{int(28+28*intensity):02x}{int(48+110*intensity):02x}{int(60+86*intensity):02x}'
                x, y = left + j * cell_w, top + i * cell_h
                canvas.create_rectangle(x, y, x + cell_w - 3, y + cell_h - 3, fill=color, outline='')
                canvas.create_text(x + cell_w / 2, y + cell_h / 2, text=str(value), fill='#ffffff', font=(self.theme['font'], 13, 'bold'))

    def curves(self, parent, report):
        t = self.theme
        label(parent, f"โมเดลที่เลือก: {report['selected_kind']} · เลือก epoch {report['best_epoch']} จาก validation",
              t, bold=True).pack(anchor='w', padx=12, pady=12)
        canvas = tk.Canvas(parent, bg=t['surface'], highlightthickness=0)
        canvas.pack(fill='both', expand=True, padx=12, pady=12)
        def draw(_event=None):
            canvas.delete('all')
            history = report['history']
            w, h = max(500, canvas.winfo_width()), max(350, canvas.winfo_height())
            for region, title, series in [(0, 'Loss', [('train_loss', '#60d4bd'), ('validation_loss', '#f8bd66')]),
                                          (1, 'Validation · accuracy / macro F1', [('validation_status_accuracy', '#60d4bd'), ('validation_status_macro_f1', '#91aaff')])]:
                top, bottom = 35 + region * h / 2, (region + 1) * h / 2 - 30
                maximum = max([row[key] for row in history for key, _ in series] + [1.0])
                canvas.create_text(55, top - 20, text=title, anchor='w', fill=t['text'])
                canvas.create_line(55, top, 55, bottom, w - 20, bottom, fill=t['muted'])
                for key, color in series:
                    coords = []
                    for i, row in enumerate(history):
                        coords.extend((55 + i * (w - 80) / max(len(history) - 1, 1), bottom - row[key] / maximum * (bottom - top)))
                    if len(coords) >= 4:
                        canvas.create_line(*coords, fill=color, width=2)
                    canvas.create_text(w - 25, top + 12 * series.index((key, color)), text=key, anchor='e', fill=color)
                canvas.create_text(8, top, text=f'{maximum:.2f}', anchor='w', fill=t['muted'])
                canvas.create_text(55, bottom + 12, text='1', fill=t['muted'])
                canvas.create_text(w - 25, bottom + 12, text=f"epoch {len(history)}", anchor='e', fill=t['muted'])
        canvas.bind('<Configure>', draw)
