"""Thai presentation copy; backend protocol keys and stored records stay unchanged.

Unknown technical errors remain visible verbatim, so diagnostics are not hidden.
Text is Unicode rendered by Tk widgets, never painted onto saved camera frames.
"""

SAFETY_TH = "ต้นแบบเพื่อการวิจัย ไม่สามารถวินิจฉัยหรือยืนยันว่าไม่เป็นโรคหลอดเลือดสมอง ค่าที่ไม่เกินเกณฑ์หรือข้อมูลที่วัดไม่ครบไม่ใช่ผลปกติ หากมีอาการเฉียบพลัน ให้ขอความช่วยเหลือฉุกเฉินทันที อย่ารอผลจากระบบ"
CARE_TH = "หากมีหน้าเบี้ยว แขนอ่อนแรง พูดผิดปกติ หรืออาการเฉียบพลันอื่น ให้ติดต่อบริการฉุกเฉินในพื้นที่ทันที อย่ารอผลจากกล้องหรือคะแนน AI"

TEXT = {
    "Baseline saved": "บันทึกข้อมูลก่อนนวดแล้ว",
    "Identity mismatch": "ยืนยันบุคคลไม่สำเร็จ",
    "Identity mismatch: does not match registered user": "บุคคลไม่ตรงกับผู้ลงทะเบียน (Identity mismatch: does not match registered user)",
    "Comparison inconclusive": "ไม่มีผลที่ใช้ได้ · ต้องตรวจซ้ำ",
    "Seek medical attention immediately": "ไปโรงพยาบาลทันที",
    "Delta measured; threshold unconfigured": "คำนวณการเปลี่ยนแปลงแล้ว ยังไม่ได้กำหนดเกณฑ์ทางคลินิก",
    "Below delta threshold; symptoms still need care": "ต่ำกว่าเกณฑ์ แต่อาการผิดปกติยังต้องได้รับการดูแล",
    "Research rule exceeded; seek medical attention for symptoms": "พบความเสี่ยงจากการทดสอบ · แจ้งเจ้าหน้าที่",
    "Below demo rules; NOT medical clearance": "ผลอยู่ในเกณฑ์ปกติของการทดสอบ",
    "Research comparison incomplete": "ข้อมูลไม่ครบ · ต้องตรวจซ้ำ",
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
    "Keep both arms raised for 3 seconds": "ยกแขนทั้งสองข้างค้างไว้ต่อเนื่อง 3 วินาที",
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
    "Unvalidated university demo: one or more measurements are unavailable; this is inconclusive.": "ระบบวัดข้อมูลที่จำเป็นได้ไม่ครบ กรุณาตรวจท่าและมุมกล้อง แล้วเริ่มตรวจใหม่ตั้งแต่ขั้นตอนแรก",
    "Arm function: normal raise and hold completed.": "การยกแขน: ยกแขนทั้งสองข้างและค้างไว้ได้ตามเวลาที่กำหนด",
    "Arm function: both arms did not reach the required raised position within the test time.": "พบความเสี่ยง: ยกแขนทั้งสองข้างไม่ถึงตำแหน่งที่กำหนดภายในเวลา",
    "Arm function: both arms reached the raised position but were not held for the required time.": "พบความเสี่ยง: ยกแขนขึ้นได้แต่ค้างไว้ไม่ถึงเวลาที่กำหนด",
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


INCOMPLETE_LEVELS = frozenset(("Comparison inconclusive", "Research comparison incomplete"))


def customer_assessment(assessment, save_status=""):
    """Customer copy must not turn missing measurements into a low-risk result."""
    level = assessment.get("level", "")
    if level in INCOMPLETE_LEVELS:
        title = display_text(level)
        body = ("การตรวจครั้งนี้ไม่มีข้อมูลที่ใช้เปรียบเทียบได้ครบ "
                "จึงห้ามตีความว่าเป็นผลปกติหรือความเสี่ยงต่ำ\n\n"
                "สิ่งที่ควรทำ: แจ้งเจ้าหน้าที่ให้ตรวจสอบท่าและมุมกล้อง "
                "แล้วเริ่มตรวจใหม่ตั้งแต่ขั้นตอนแรก")
        disclaimer = display_text(assessment.get("disclaimer", ""))
        if disclaimer:
            body += "\n\n" + disclaimer
        if save_status:
            body += "\n\n" + display_text(save_status)
        return title, body
    title = display_text(level)
    reasons = "\n".join(display_text(reason) for reason in assessment.get("reasons", ()))
    disclaimer = display_text(assessment.get("disclaimer", ""))
    saved = display_text(save_status)
    return title, "\n\n".join(part for part in (reasons, disclaimer, saved) if part)


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
