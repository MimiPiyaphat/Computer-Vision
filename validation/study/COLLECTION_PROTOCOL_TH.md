# โปรโตคอลเก็บข้อมูล Baseline/Recheck สำหรับงานวิจัย

สถานะเอกสาร: **ฉบับร่างสำหรับการทบทวนโดยอาจารย์ ที่ปรึกษาสถิติ คณะกรรมการจริยธรรม และผู้เชี่ยวชาญทางคลินิก** ไม่ใช่แนวทางวินิจฉัยหรือดูแลผู้ป่วย

## 1. วัตถุประสงค์

ประเมินว่า feature delta จากการวัดบุคคลเดียวกันระหว่าง `baseline` และ `recheck` มีความสัมพันธ์กับผลลัพธ์เป้าหมายที่กำหนดไว้ล่วงหน้าหรือไม่ ระบบนี้ไม่ใช้เพื่อยืนยันหรือตัดโรค และต้องไม่ทำให้การส่งต่อฉุกเฉินล่าช้า

ก่อนเริ่มเก็บข้อมูล ทีมวิจัยต้องระบุเป็นลายลักษณ์อักษร:

- ผลลัพธ์เป้าหมายทางคลินิกและช่วงเวลาที่ใช้ยืนยันผล
- เกณฑ์รับเข้า/คัดออก ประชากรเป้าหมาย และสถานที่ศึกษา
- วิธี adjudication และคุณสมบัติผู้ประเมิน
- ขนาดตัวอย่าง เป้าหมาย sensitivity และช่วงความเชื่อมั่นที่ยอมรับได้
- แผนวิเคราะห์กลุ่มย่อยและ repeated visits
- ระยะเวลาเก็บรักษา ผู้มีสิทธิ์เข้าถึง และวิธีทำลายข้อมูล

## 2. ขอบเขตข้อมูล

แอปปัจจุบันบันทึกเฉพาะค่าตัวเลขและ identity embedding แบบ pseudonymous ไม่บันทึกภาพ วิดีโอ เสียง หรือ raw customer ID หากการศึกษาจำเป็นต้องใช้วิดีโอเพื่อ adjudication ต้องใช้ระบบจัดเก็บที่ได้รับอนุมัติแยกต่างหาก พร้อม consent และ access control; ห้ามใส่วิดีโอผู้เข้าร่วมใน Git repository

ข้อมูลที่ส่งให้ทีมวิเคราะห์ควรมีเพียง `pair_id`, `subject_key`, สถานะรายงานอาการ, feature records และ label ที่ adjudicate แล้ว ห้ามใส่ชื่อ เบอร์โทร เลขบัตร ที่อยู่ หรือข้อความอิสระที่ระบุตัวบุคคลได้

## 3. ขั้นตอนต่อหนึ่งคู่การวัด

1. ตรวจ consent เวอร์ชันที่อนุมัติและกำหนด study subject ID นอกแอป
2. เก็บ `baseline` ตามคำสั่งในแอป: ใบหน้าเป็นกลาง ยิ้ม หลับตา กะพริบตา และยกแขนค้าง
3. เก็บ `recheck` เฉพาะตาม cohort/protocol ที่กำหนด โดยใช้คนเดิม กล้องเดิม ความละเอียดเดิม จุดติดตั้งเดิม และท่าทางเดียวกัน
4. บันทึกเหตุขัดข้อง เช่น identity mismatch, มองไม่ตรง, landmark หาย หรือ capture ไม่ครบ เป็นความล้มเหลวของการวัด ห้ามแทนค่าหรือเลือกเฉพาะรอบที่ดูดี
5. การดูแลทางคลินิกเกิดขึ้นโดยอิสระจากผลกล้อง หากมีอาการเฉียบพลันให้ดำเนินการตามแนวทางฉุกเฉินโดยไม่รอผลวิจัย
6. ผู้ประเมิน outcome ต้องไม่ใช้ model score, provisional alert หรือ symptom checkbox เป็นเหตุผลกำหนด label

## 4. Adjudication

- ผู้ประเมินอิสระสองคนให้ label `0/1` ตามนิยาม outcome ที่อนุมัติ
- หากเห็นตรงกัน `final_label` ต้องตรงกับทั้งสองคน
- หากไม่ตรงกัน ต้องมีการทบทวนโดยผู้ตัดสินที่กำหนดไว้และใส่ `review_reference`
- `1` หมายถึงยืนยันผลลัพธ์เป้าหมายตามนิยามที่กำหนดไว้ล่วงหน้า
- `0` หมายถึงไม่ยืนยันผลลัพธ์เป้าหมาย ไม่ได้แปลว่าไม่มีอาการหรือปลอดภัย
- ใช้รหัสผู้ประเมิน ไม่ใส่ชื่อหรือข้อมูลส่วนตัวในไฟล์วิเคราะห์

## 5. การแบ่งข้อมูล

แบ่งตาม `subject_key` ก่อนปรับ threshold บุคคลหนึ่งต้องอยู่เพียง tuning หรือ holdout เท่านั้น เก็บ holdout ไว้ untouched จนกว่าจะล็อก feature schema, pipeline และ threshold แล้ว ทั้ง tuning และ symptomatic holdout ต้องมี label ทั้งสอง class

## 6. ลำดับคำสั่ง

```powershell
python export_feature_pairs.py data/features-research/visits.sqlite3 data/unlabeled-pairs.jsonl
python validation/study/prepare_adjudication.py data/unlabeled-pairs.jsonl data/adjudication.csv
# ผู้ประเมินกรอกไฟล์ CSV โดยไม่ดู model score
python validation/study/merge_adjudication.py data/unlabeled-pairs.jsonl data/adjudication.csv data/labeled-pairs.jsonl
python validation/study/split_labeled_pairs.py data/labeled-pairs.jsonl data/tuning.jsonl data/holdout.jsonl --holdout-fraction 0.2 --seed 20261006
python validate_threshold.py data/tuning.jsonl data/holdout.jsonl --minimum-sensitivity 0.95 --output validation/research-report.json
```

ค่า `0.95` เป็นเพียงตัวอย่าง syntax ต้องใช้ค่าที่กำหนดไว้ใน protocol จริง รายงานที่ได้ยังคงเป็นงานวิจัยและไม่อนุมัติ deployment โดยอัตโนมัติ
