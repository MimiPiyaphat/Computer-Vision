"""Thai presentation copy; backend protocol keys and stored records stay unchanged.

Unknown technical errors remain visible verbatim, so diagnostics are not hidden.
Text is Unicode rendered by Tk widgets, never painted onto saved camera frames.
"""

SAFETY_TH = "ต้นแบบเพื่อการวิจัย ไม่สามารถวินิจฉัยหรือยืนยันว่าไม่เป็นโรคหลอดเลือดสมอง หากมีอาการเฉียบพลัน ให้ขอความช่วยเหลือฉุกเฉินทันที อย่ารอผลจากระบบ"
CARE_TH = "หากมีหน้าเบี้ยว แขนอ่อนแรง พูดผิดปกติ หรืออาการเฉียบพลันอื่น ให้ติดต่อบริการฉุกเฉินในพื้นที่ทันที อย่ารอผลจากกล้องหรือคะแนน AI"

TEXT = {
    "Baseline saved": "บันทึกข้อมูลก่อนนวดแล้ว",
    "Identity mismatch": "ยืนยันบุคคลไม่สำเร็จ",
    "Identity mismatch: does not match registered user": "บุคคลไม่ตรงกับผู้ลงทะเบียน (Identity mismatch: does not match registered user)",
    "Comparison inconclusive": "ยังสรุปผลการเปรียบเทียบไม่ได้",
    "Seek medical attention immediately": "ไปโรงพยาบาลทันที",
    "Delta measured; threshold unconfigured": "คำนวณการเปลี่ยนแปลงแล้ว ยังไม่ได้กำหนดเกณฑ์ทางคลินิก",
    "Below delta threshold; symptoms still need care": "ต่ำกว่าเกณฑ์ แต่อาการผิดปกติยังต้องได้รับการดูแล",
    "Research rule exceeded; seek medical attention for symptoms": "เกินเกณฑ์ทดลอง — อาการผิดปกติต้องได้รับการดูแล",
    "Below demo rules; NOT medical clearance": "ต่ำกว่าเกณฑ์ทดลอง ไม่ใช่การรับรองความปลอดภัย",
    "Research comparison incomplete": "ข้อมูลเปรียบเทียบเพื่อการวิจัยไม่ครบ",
    "Preview only": "ตัวอย่างหน้าจอเท่านั้น",
    "Simulated summary for interface development.": "ผลจำลองสำหรับพัฒนาหน้าจอ",
    "No screening was performed.": "ไม่มีการตรวจจริง",
    "Preview data is never saved.": "ไม่บันทึกข้อมูลจากโหมดตัวอย่าง",
    "Relax your face and look at the camera": "ผ่อนคลายใบหน้าและมองตรงไปที่กล้อง",
    "Face the camera to calibrate": "มองตรงไปที่กล้องเพื่อเก็บข้อมูลอ้างอิง",
    "Smile as wide as you can and hold": "ยิ้มให้กว้างเท่าที่ทำได้ แล้วค้างไว้",
    "Gently close both eyes and hold": "หลับตาทั้งสองข้างเบา ๆ แล้วค้างไว้",
    "Blink both eyes naturally several times": "กะพริบตาทั้งสองข้างตามธรรมชาติหลายครั้ง",
    "Start with arms down, then raise both arms together": "เริ่มจากวางแขนลง แล้วค่อยยกแขนทั้งสองข้างพร้อมกัน",
    "Raise both arms together from a lowered position": "เริ่มจากวางแขนลง แล้วยกแขนทั้งสองข้างพร้อมกัน",
    "Keep both arms raised": "ยกแขนทั้งสองข้างค้างไว้",
    "Keep shoulders and wrists visible; start with arms down and keep your body still": "ให้กล้องเห็นหัวไหล่และข้อมือ เริ่มจากวางแขนลง และรักษาท่าทางให้คงที่",
    "Step into view so the camera can see you": "ขยับเข้ามาในมุมกล้องให้เห็นตัวคุณ",
    "Screening complete": "เก็บข้อมูลครบแล้ว",
    "Start a new visit step when ready": "พร้อมแล้วสามารถเริ่มบันทึกครั้งใหม่ได้",
    "Keep your face visible and face the camera without turning or tilting": "ให้กล้องเห็นใบหน้าครบ มองตรง ไม่หันหรือเอียงศีรษะ",
    "Keep exactly one complete face visible, close enough to the camera.": "ให้เห็นใบหน้าครบเพียงหนึ่งคน และอยู่ใกล้กล้องพอสมควร",
    "Improve uneven lighting before continuing.": "ปรับแสงบนใบหน้าให้สม่ำเสมอก่อนดำเนินการต่อ",
    "Identity check: keep one complete face visible, facing forward (within 18 degrees), including during the arm hold.": "กำลังยืนยันบุคคล: ให้เห็นใบหน้าครบ มองตรง ไม่เอียงเกิน 18° รวมถึงขณะยกแขน",
    "Demo angle: start arms down, then lift OUT TO THE SIDES to shoulder height and hold; keep wrists visible": "ท่าทดลอง: เริ่มจากวางแขนลง กางแขนออกด้านข้างระดับหัวไหล่แล้วค้างไว้ ให้เห็นข้อมือและใบหน้า",
    "Capture rejected; no recheck or delta saved.": "ยกเลิกการเก็บข้อมูล ไม่บันทึกผลตรวจซ้ำหรือค่าการเปลี่ยนแปลง",
    "Saved numeric measurements; baseline identity embedding is stored separately. No images or video saved.": "บันทึกค่าตัวเลขแล้ว เวกเตอร์ยืนยันบุคคลจัดเก็บแยกต่างหาก ไม่บันทึกภาพหรือวิดีโอ",
    "No complete feature record was saved.": "ยังไม่ได้บันทึกข้อมูลที่ครบถ้วน",
    "This is a reference measurement, not medical clearance for massage.": "ข้อมูลนี้เป็นค่าอ้างอิง ไม่ใช่การรับรองความปลอดภัยในการนวด",
    "Rechecks require a customer-reported abnormal symptom.": "ตรวจซ้ำได้เมื่อผู้รับบริการแจ้งอาการผิดปกติ กรุณายืนยันในช่องอาการ",
    "Confirm the same camera/station and instructed posture; keep your head facing forward.": "กรุณายืนยันกล้องและจุดตรวจเดิม ทำตามท่าที่กำหนด และมองตรง",
    "Enter a customer ID and a visit reference (1-128 characters each).": "กรุณากรอกรหัสผู้รับบริการและรหัสครั้งรับบริการ (ช่องละ 1–128 ตัวอักษร)",
    "A baseline already exists for this visit; use a recheck or a new visit reference.": "ครั้งรับบริการนี้มีข้อมูลก่อนนวดแล้ว ให้เลือกตรวจซ้ำหรือใช้รหัสครั้งรับบริการใหม่",
    "No validated threshold configured.": "ยังไม่ได้กำหนดเกณฑ์ที่ผ่านการตรวจสอบทางคลินิก",
    "A below-threshold measurement cannot exclude stroke or dismiss symptoms.": "ค่าที่ต่ำกว่าเกณฑ์ไม่สามารถยืนยันว่าไม่เป็นโรคหรือใช้ปฏิเสธอาการผิดปกติได้",
    "Baseline measurements and separate face identity embedding saved for this customer and visit.": "บันทึกข้อมูลก่อนนวดและเวกเตอร์ยืนยันบุคคลแยกกัน สำหรับผู้รับบริการและครั้งรับบริการนี้แล้ว",
    "Unvalidated university demo: a provisional rule was exceeded.": "การทดลองสำหรับโครงงาน: ค่าเกินเกณฑ์เบื้องต้นที่ยังไม่ผ่านการรับรอง",
    "Unvalidated university demo: rules were not exceeded; this cannot exclude disease.": "การทดลองสำหรับโครงงาน: ค่าไม่เกินเกณฑ์ แต่ไม่สามารถยืนยันว่าไม่มีโรคได้",
    "Unvalidated university demo: one or more measurements are unavailable; this is inconclusive.": "การทดลองสำหรับโครงงาน: ข้อมูลบางส่วนไม่ครบ จึงยังสรุปผลไม่ได้",
}


def display_text(text):
    from src.protocol import CARE_MESSAGE
    if not text:
        return ""
    if text == CARE_MESSAGE:
        return CARE_TH
    translated = TEXT.get(text)
    if translated is not None:
        return translated
    # Preserve detailed numeric/technical diagnostics; localize common score labels.
    return (text.replace(CARE_MESSAGE, CARE_TH)
            .replace("Face delta ", "การเปลี่ยนแปลงใบหน้า ")
            .replace(" + arm delta ", " + การเปลี่ยนแปลงแขน ")
            .replace("2D arm-angle delta: ", "การเปลี่ยนแปลงมุมแขน 2D: ")
            .replace(" / rule ", " / เกณฑ์ ").replace(" degrees", " องศา"))


def select_font(preferred, available):
    """Respect installed theme choice, then use Thai-capable UI fallbacks."""
    fonts = {name.casefold(): name for name in available}
    for name in (preferred, "Leelawadee UI", "Noto Sans Thai", "Sarabun", "Tahoma"):
        if name.casefold() in fonts:
            return fonts[name.casefold()]
    return "TkDefaultFont"


def configure_fonts(root, theme):
    from tkinter import font
    result = dict(theme)
    result["font"] = select_font(theme["font"], font.families(root))
    if result["font"] == "TkDefaultFont":
        result["font"] = font.nametofont("TkDefaultFont", root=root).actual("family")
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont", "TkTooltipFont"):
        font.nametofont(name, root=root).configure(family=result["font"], size=theme["font_size"])
    root.option_add("*Font", (result["font"], theme["font_size"]))
    return result
