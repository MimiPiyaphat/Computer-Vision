# วิธีติดตั้งและรันโปรเจกต์ (Setup Guide)

## 1. สร้าง Virtual Environment

```bash
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

## 2. ติดตั้ง Dependencies

```bash
pip install -r requirements.txt
```

## 3. รันโปรแกรม

```bash
python main.py
```

- กด `q` เพื่อออกจากโปรแกรม
- ตอนนี้กล้องจะแสดงผลพร้อม FPS counter ได้ปกติ แต่โมดูลวิเคราะห์ (Face / Arm) ยังเป็น skeleton
  ที่ยังไม่ implement logic จริง (จะทำใน step ถัดไป)

## โครงสร้างโปรเจกต์

```
stroke-vision-ai/
├── main.py                 # entry point หลัก, เดินลูปกล้อง
├── config.py                # ค่าคงที่/threshold ทั้งหมด
├── requirements.txt
├── .gitignore
├── SETUP.md
├── src/
│   ├── __init__.py
│   ├── face_analytics.py    # โมดูล F - ตรวจหน้าเบี้ยว/ตาปรือ (skeleton)
│   ├── arm_pose.py          # โมดูล A - ตรวจแขนอ่อนแรง (skeleton)
│   └── utils.py             # ฟังก์ชันช่วย เช่น calculate_ear, FPSCounter
├── tests/                    # (ว่าง รอเขียน unit test)
└── assets/                   # (ว่าง รอเก็บไฟล์ภาพ/โมเดลเพิ่มเติม)
```

## Checklist ความคืบหน้า

- [x] โครงสร้างโปรเจกต์ + config
- [x] main.py เดินลูปกล้องได้ (แสดง FPS)
- [ ] Face Analytics: คำนวณ EAR จริงจาก Face Mesh
- [ ] Face Analytics: ตรวจ mouth asymmetry
- [ ] Arm Pose: ตรวจ arm drift จริงจาก Pose landmarks
- [ ] Interactive flow: เชื่อม step ยิ้ม → กะพริบตา → ยกแขน
- [ ] Alert system แบบ real-time
- [ ] บันทึกผล screening ลง log
