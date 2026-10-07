# Production Readiness Gates

เอกสารนี้เป็นรายการ gate ไม่ใช่ใบรับรองความพร้อม การทำเครื่องหมายต้องมีหลักฐานอ้างอิงและผู้รับผิดชอบลงนาม

| Gate | หลักฐานขั้นต่ำ | สถานะปัจจุบัน |
| --- | --- | --- |
| Intended use | เอกสารที่ clinical/regulatory owner อนุมัติ | Draft เท่านั้น |
| Ethics | Protocol, consent, REC/IRB approval | ยังไม่มี approval |
| Clinical data | Prospective symptomatic cohort และ independent adjudication | ยังไม่มีข้อมูลจริง |
| Clinical performance | Locked external holdout, sensitivity/specificity/CI และ failure analysis | ยังไม่วัด |
| Regulatory | Thai FDA classification และ registration/authorization ตามที่ใช้บังคับ | ยังไม่ดำเนินการ |
| Privacy | Lawful basis/explicit consent, DPIA, retention/deletion, DPO/owner | ยังไม่ครบ |
| Security | Encryption, RBAC, key management, audit trail, SBOM, vulnerability/penetration testing | ยังไม่ครบ |
| Quality system | Requirements traceability, risk file, change control, release approval | ยังไม่ครบ |
| Human factors | Usability test กับผู้ใช้เป้าหมายและ critical-task validation | ยังไม่ทำ |
| Operations | SOP, training, emergency escalation, support, incident/recall process | ยังไม่ครบ |

## หลักฐานที่มีแล้ว

- แอป fail closed เมื่อไม่มี threshold ที่ผ่านการอนุมัติ
- มี baseline/recheck compatibility checks และ subject identity gate
- ไม่บันทึกภาพ วิดีโอ หรือเสียงจาก workflow ปัจจุบัน
- มี exporter, adjudication workflow, subject-disjoint splitter และ offline validation tools
- มีข้อความเตือนว่า low score ไม่สามารถตัดโรคได้
- automated test suite ครอบคลุม software behavior แต่ไม่ใช่ clinical validation

## Definition of done

คำว่า “พร้อมใช้งานจริง” ใช้ได้เมื่อ gate ทุกข้อมีหลักฐาน ตรวจสอบย้อนกลับได้ และไม่มี open unacceptable risk การที่โปรแกรมเปิดได้หรือ unit tests ผ่านไม่ถือเป็น clinical readiness
