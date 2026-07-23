# 🧠 StrokeVision AI (stroke-vision-ai)
> **Early Stroke Risk Screening System using Computer Vision**  
> *ระบบปัญญาประดิษฐ์คัดกรองความเสี่ยงโรคหลอดเลือดสมองเบื้องต้นด้วย Computer Vision*

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg)](https://opencv.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10.x-orange.svg)](https://google.github.io/mediapipe/)
[![License](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)

---

## 📌 1. ที่มาและความสำคัญ (Background & Problem)

* **ที่มา:** เคสผู้ป่วยเกิดภาวะเส้นเลือดในสมองอุดตัน (Cervical Artery Dissection) หลังได้รับการนวดคอ ทำให้เนื้อสมองขาดเลือดเฉียบพลัน
* **Pain Point:** ผู้ป่วยส่วนใหญ่มัก "ไม่รู้ตัว" ว่ากำลังมีอาการ Stroke (เข้าใจผิดว่าแค่เพลีย ลมจับ หรือนอนตกหมอน) จึงเลือกที่จะนอนพัก ทำให้เสียเวลาวิกฤต Golden Period (4.5 ชั่วโมง) ส่งผลให้เซลล์สมองตายถาวรและกลายเป็นอัมพฤกษ์-อัมพาต
* **แนวทางแก้ไข:** สร้างระบบคัดกรองเบื้องต้นแบบ Real-time เพื่อช่วยยืนยันอาการและเตือนให้ผู้ป่วยไปโรงพยาบาลทันทีภายใน 10–15 นาทีแรก (ลด Time to Recognition)

---

## 🛠️ 2. หลักการและฟังก์ชั่นการทำงาน (Core Features)

อ้างอิงหลักการประเมินทางการแพทย์ **FAST (Face, Arm, Speech, Time)** โดยใช้กล้อง Webcam/Smartphone ร่วมกับ MediaPipe และ OpenCV:

### 👁️ Face Analytics (ตรวจจับหน้าเบี้ยว & ตาปรือ - F)
* **Facial Symmetry:** ใช้ MediaPipe Face Mesh เทียบความสมมาตรของมุมปาก ปีกจมูก และเปลือกตา
* **Ptosis & Blinking (EAR - Eye Aspect Ratio):** คำนวณอัตราส่วนความเปิดกว้างของตา เพื่อตรวจจับภาวะหนังตาตกครึ่งซีก (Eyelid Drooping) และการกะพริบตาที่ไม่เท่ากัน/มีความหน่วง (Asymmetric Blink)

### 🦾 Arm Pose Estimation (ตรวจจับแขนอ่อนแรง - A)
* ใช้ MediaPipe Pose / YOLOv8-Pose จับจุดข้อต่อ (ไหล่, ศอก, ข้อมือ)
* สั่งให้ผู้ใช้ยกแขนค้างไว้ 10 วินาที เพื่อเช็คอาการแขนค่อย ๆ ตก (Arm Drift) จากการเปลี่ยนแปลงของพิกเซลในแนวแกน Y

### ⏱️ Interactive & Clinical Logic (S & T)
* ออกแบบระบบการตรวจคัดกรองเป็นสเต็ป (ยิ้ม $\rightarrow$ กะพริบตา $\rightarrow$ ยกแขน) พร้อมระบบแจ้งเตือนแบบทันที (Real-time Alert)

---

## ✨ 3. จุดเด่นและประโยชน์ของโครงการ (Project Highlights)

* **Real-time & Accessible:** ใช้เพียงกล้องทั่วไป ไม่ต้องใช้อุปกรณ์ทางการแพทย์ราคาแพง
* **Edge Computing Friendly:** โมเดลมีความเบา ทำงานได้เร็ว (High FPS) ประมวลผลบนคอมพิวเตอร์ทั่วไป หรือบอร์ดประมวลผลขนาดเล็กได้
* **Social Impact:** ช่วยลดระยะเวลาตัดสินใจของผู้ป่วย เพิ่มโอกาสการเข้าถึงยารักษาทันท่วงที เซฟชีวิตและลดโอกาสการพิการตลอดชีวิต

## ✨ 4. การรันโปรแกรม 
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py