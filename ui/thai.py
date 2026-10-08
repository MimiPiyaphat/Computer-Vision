"""Thai presentation copy; backend protocol keys and stored records stay unchanged.

Unknown technical errors remain visible verbatim, so diagnostics are not hidden.
Text is Unicode rendered by Tk widgets, never painted onto saved camera frames.
"""

SAFETY_TH = "ระบบช่วยตรวจสอบเพื่อการวิจัย ไม่ได้วินิจฉัยหรือยืนยันว่าไม่มีโรคหลอดเลือดสมอง ผลต่ำหรือสรุปไม่ได้ไม่ใช่ผลปกติ หากมีอาการเฉียบพลันให้ขอความช่วยเหลือฉุกเฉินทันทีโดยไม่รอระบบ"
CARE_TH = "อาการหน้าเบี้ยว แขนอ่อนแรง พูดผิดปกติ หรืออาการทางระบบประสาทที่เกิดฉับพลันอาจเข้าข่ายภาวะฉุกเฉิน ควรติดต่อบริการฉุกเฉินทันที อย่ารอผลจากกล้องหรือคะแนน AI"

CUSTOMER_RESULTS = {
    "acquisition_failed": (
        "เก็บข้อมูลไม่ครบ · เก็บข้อมูลใหม่ได้",
        "ระบบยังวัดข้อมูลได้ไม่ครบภายในเวลาที่กำหนด\n\nสาเหตุ: ",
    ),
    "save_failed": (
        "บันทึกข้อมูลไม่สำเร็จ · ติดต่อเจ้าหน้าที่",
        "ระบบวัดข้อมูลได้แล้ว แต่บันทึกข้อมูลไม่สำเร็จ กรุณาแจ้งเจ้าหน้าที่และอย่าใช้ผลนี้ตัดสินใจด้านสุขภาพ\n\n",
    ),
    "baseline_saved": (
        "บันทึกก่อนนวดแล้ว",
        "สิ่งที่บันทึก: ข้อมูลใบหน้าและแขนของคุณ เพื่อเปรียบเทียบในการตรวจซ้ำ\n\n"
        "ขั้นตอนต่อไป: แจ้งเจ้าหน้าที่ว่าบันทึกเสร็จแล้ว\n\nข้อมูลนี้ยังไม่ได้บอกความเสี่ยงโรค และไม่ใช่การรับรองความปลอดภัยในการนวด",
    ),
    "research_alert": (
        "พบความเสี่ยงจากการทดสอบ: ค่าหลังนวดเปลี่ยน · แจ้งเจ้าหน้าที่ทันที",
        "สิ่งที่พบ: ค่าที่ระบบวัดหลังนวดเปลี่ยนจากก่อนนวดมากกว่าระดับทดลอง\n\n"
        "สิ่งที่ควรทำ: แจ้งเจ้าหน้าที่ทันทีเพื่อช่วยประเมินอาการร่วมกัน ผลจากกล้องนี้ไม่ใช่การวินิจฉัยโรค\n\n" + CARE_TH,
    ),
    "delta_alert": (
        "ค่าหลังนวดเปลี่ยนมากกว่าระดับที่กำหนด · แจ้งเจ้าหน้าที่ทันที",
        "สิ่งที่พบ: ค่ารวมที่ระบบวัดจากใบหน้าและแขนหลังนวดเปลี่ยนจากก่อนนวดมากกว่าระดับที่กำหนด\n\n"
        "สิ่งที่ควรทำ: แจ้งเจ้าหน้าที่ทันทีเพื่อช่วยประเมินอาการร่วมกัน ผลจากกล้องนี้ไม่ใช่การวินิจฉัยโรค\n\n" + CARE_TH,
    ),
    "research_below_placeholder": (
        "ผลอยู่ในเกณฑ์ปกติของการทดสอบ",
        "สิ่งที่พบ: ค่าที่เปรียบเทียบกับก่อนนวดยังไม่เกินเกณฑ์ทดลอง\n\n"
        "ขั้นตอนต่อไป: แจ้งเจ้าหน้าที่ว่าตรวจติดตามหลังนวดเสร็จแล้ว\n\n"
        "ผลนี้ไม่สามารถยืนยันว่าไม่มีโรคหลอดเลือดสมอง",
    ),
    "below_threshold": (
        "ไม่พบการเปลี่ยนแปลงเกินเกณฑ์",
        "สิ่งที่พบ: ค่าที่เปรียบเทียบกับก่อนนวดยังไม่เกินเกณฑ์ที่กำหนด\n\n"
        "ขั้นตอนต่อไป: แจ้งเจ้าหน้าที่ว่าตรวจติดตามหลังนวดเสร็จแล้ว\n\n"
        "ผลนี้ไม่สามารถยืนยันว่าไม่มีโรคหลอดเลือดสมอง",
    ),
    "threshold_unconfigured": (
        "ระบบยังไม่พร้อมประเมิน · ติดต่อเจ้าหน้าที่",
        "ระบบยังไม่พร้อมประเมินผลการเปรียบเทียบ กรุณาแจ้งเจ้าหน้าที่เพื่อช่วยตรวจสอบ",
    ),
    "research_incomplete": (
        "ข้อมูลไม่ครบ · ติดต่อเจ้าหน้าที่",
        "ระบบได้รับข้อมูลสำหรับเปรียบเทียบไม่ครบ กรุณาให้เจ้าหน้าที่ช่วยตรวจสอบขั้นตอนการเก็บข้อมูล",
    ),
    "inconclusive": (
        "ประเมินผลไม่ได้ · ติดต่อเจ้าหน้าที่",
        "ระบบยังประเมินผลครั้งนี้ไม่ได้ กรุณาแจ้งเจ้าหน้าที่เพื่อช่วยตรวจสอบข้อมูลและขั้นตอนการตรวจ",
    ),
    "identity_rejected": (
        "ไม่สามารถยืนยันผู้รับบริการได้",
        "ระบบไม่สามารถยืนยันว่าเป็นผู้รับบริการคนเดิม กรุณาเริ่มใหม่หรือติดต่อเจ้าหน้าที่",
    ),
}

CUSTOMER_LEVEL_STATUS = {
    "Baseline saved": "baseline_saved",
    "Seek medical attention immediately": "delta_alert",
    "Delta measured; threshold unconfigured": "threshold_unconfigured",
    "Below delta threshold; symptoms still need care": "below_threshold",
    "Comparison inconclusive": "inconclusive",
    "Research rule exceeded; seek medical attention for symptoms": "research_alert",
    "Below demo rules; NOT medical clearance": "research_below_placeholder",
    "Research comparison incomplete": "research_incomplete",
    "Identity mismatch": "identity_rejected",
    "เก็บข้อมูลไม่ครบ · ติดต่อเจ้าหน้าที่": "acquisition_failed",
    "บันทึกข้อมูลไม่สำเร็จ · ติดต่อเจ้าหน้าที่": "save_failed",
}

TEXT = {
    "Baseline saved": "บันทึกข้อมูลก่อนนวดแล้ว",
    "Identity mismatch": "ยืนยันบุคคลไม่สำเร็จ",
    "Identity mismatch: does not match registered user": "บุคคลไม่ตรงกับผู้ลงทะเบียน (Identity mismatch: does not match registered user)",
    "Comparison inconclusive": "ไม่มีผลที่ใช้ได้ · ต้องตรวจซ้ำ",
    "Seek medical attention immediately": "ไปโรงพยาบาลทันที",
    "Delta measured; threshold unconfigured": "คำนวณการเปลี่ยนแปลงแล้ว ยังไม่ได้กำหนดเกณฑ์ทางคลินิก",
    "Below delta threshold; symptoms still need care": "ต่ำกว่าเกณฑ์ แต่อาการผิดปกติยังต้องได้รับการดูแล",
    "Research rule exceeded; seek medical attention for symptoms": "พบความเสี่ยงจากการทดสอบ · แจ้งเจ้าหน้าที่",
    "Below demo rules; NOT medical clearance": "ผลอยู่ในเกณฑ์ปกติของการทดสอบ แต่ไม่สามารถตัดโรคได้",
    "Research comparison incomplete": "ข้อมูลไม่ครบ · ต้องตรวจซ้ำ",
    "Model, camera, resolution or capture station changed.": "ข้อมูลอ้างอิงไม่ตรงกับการตรวจครั้งนี้ กรุณาใช้กล้อง จุดตรวจ และการตั้งค่าเดิม หรือบันทึก baseline ใหม่",
    "A baseline already exists for this visit; use a recheck or a new visit reference.": "มีข้อมูลก่อนนวดของรหัสครั้งนี้อยู่แล้ว กรุณาใช้การตรวจซ้ำหรือสร้างรหัสครั้งใหม่",
    "Baseline is expired or future-dated.": ("ข้อมูลก่อนนวดหมดอายุหรือเวลาไม่ถูกต้อง หากขณะนี้ไม่มีอาการผิดปกติ ให้เลือก ‘ก่อนนวด’ "
                                               "แล้วบันทึกข้อมูลใหม่ด้วยรหัสผู้รับบริการและรหัสครั้งเดิม หากมีอาการอยู่ ให้แจ้งเจ้าหน้าที่และอย่าบันทึก baseline ใหม่เพื่อให้ตรวจผ่าน"),
    "The baseline has no complete arm angles; contact staff to collect a new baseline": "ข้อมูลก่อนนวดไม่มีค่ามุมแขนครบ กรุณาให้เจ้าหน้าที่บันทึก baseline ใหม่",
    "Preview only": "ตัวอย่างหน้าจอเท่านั้น",
    "Simulated summary for interface development.": "ผลจำลองสำหรับพัฒนาหน้าจอ",
    "No screening was performed.": "ไม่มีการตรวจจริง",
    "Preview data is never saved.": "ไม่บันทึกข้อมูลจากโหมดตัวอย่าง",
    "Relax your face and look at the camera": "ผ่อนคลายใบหน้า ลืมตาตามธรรมชาติ และมองตรงไปที่กล้อง",
    "Face the camera to calibrate": "มองตรงไปที่กล้องเพื่อเก็บข้อมูลอ้างอิง",
    "Step into view so the camera can see you": "กรุณาเข้ามาอยู่ในกรอบภาพ ให้กล้องเห็นคุณชัดเจน",
    "Keep only one person in the camera view": "กรุณาให้มีผู้รับบริการเพียงหนึ่งคนในภาพ",
    "Both wrists are not visible": "ยังไม่เห็นข้อมือทั้งสองข้าง กรุณาขยับให้อยู่ในกรอบภาพ",
    "One wrist is not visible": "ยังไม่เห็นข้อมือข้างหนึ่ง กรุณาขยับแขนให้อยู่ในกรอบภาพ",
    "Keep both shoulders visible": "กรุณาให้เห็นหัวไหล่ทั้งสองข้าง",
    "Move closer while keeping both wrists visible": "กรุณาขยับเข้าใกล้กล้องขึ้น โดยให้เห็นข้อมือทั้งสองข้าง",
    "Start with both arms down": "เริ่มต้นด้วยการวางแขนทั้งสองข้างลงข้างลำตัว",
    "Return to the starting body position and keep still": "กลับไปยังท่าเริ่มต้นและอยู่นิ่ง ๆ",
    "Raise both arms together from a lowered position": "ค่อย ๆ ยกแขนทั้งสองข้างพร้อมกันจากท่าแขนลง",
    "Spread both arms out to the sides so the camera can measure them": "กรุณากางแขนออกด้านข้าง เพื่อให้กล้องวัดการเคลื่อนไหวได้",
    "Keep both arms raised": "ยกแขนทั้งสองข้างค้างไว้และอยู่นิ่ง ๆ",
    "A complete forward-facing face could not be measured": "ยังวัดใบหน้าได้ไม่ครบ กรุณามองตรงและให้ใบหน้าอยู่ในกรอบภาพ",
    "Improve uneven lighting before continuing.": "กรุณาปรับแสงให้สม่ำเสมอก่อนดำเนินการต่อ",
    "Identity could not be confirmed within the capture time limit": "ยืนยันผู้รับบริการไม่สำเร็จภายในเวลาที่กำหนด กรุณาติดต่อเจ้าหน้าที่",
    "Not enough valid samples were collected": "เก็บตัวอย่างที่ใช้วัดได้ไม่เพียงพอ กรุณาติดต่อเจ้าหน้าที่",
    "Incomplete required face or arm measurements": "ข้อมูลใบหน้าหรือแขนที่จำเป็นยังไม่ครบ กรุณาติดต่อเจ้าหน้าที่",
    "Both projected arm angles are required": "ยังวัดมุมแขนทั้งสองข้างไม่ได้ กรุณากางแขนออกด้านข้าง",
    "Resting eye opening is too small to measure closure.": "วัดค่าลืมตาอ้างอิงไม่ได้ กรุณาเริ่มเก็บข้อมูลใหม่ โดยลืมตาตามธรรมชาติในขั้นตอนใบหน้าผ่อนคลาย",
    "The baseline has no complete arm angles; contact staff to collect a new baseline": "ข้อมูลก่อนนวดไม่มีค่ามุมแขนครบ กรุณาให้เจ้าหน้าที่บันทึกข้อมูลก่อนนวดใหม่",
    "Hold both arms raised": "ยกแขนทั้งสองข้างค้างไว้",
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
    "Identity check: hold still while confirming the returning person.": "อยู่นิ่งและมองตรงสักครู่ ระบบกำลังยืนยันว่าเป็นผู้รับบริการคนเดิม",
    "Demo angle: start arms down, then lift OUT TO THE SIDES to shoulder height and hold; keep wrists visible": "ท่าทดลอง: เริ่มจากวางแขนลง กางแขนออกด้านข้างระดับหัวไหล่แล้วค้างไว้ ให้เห็นข้อมือและใบหน้า",
    "Capture rejected; no recheck or delta saved.": "ยกเลิกการเก็บข้อมูล ไม่บันทึกผลตรวจซ้ำหรือค่าการเปลี่ยนแปลง",
    "Saved numeric measurements; baseline identity embedding is stored separately. No images or video saved.": "บันทึกค่าตัวเลขแล้ว เวกเตอร์ยืนยันบุคคลจัดเก็บแยกต่างหาก ไม่บันทึกภาพหรือวิดีโอ",
    "No complete feature record was saved.": "ยังไม่ได้บันทึกข้อมูลที่ครบถ้วน",
    "This is a reference measurement, not medical clearance for massage.": "ข้อมูลนี้เป็นค่าอ้างอิง ไม่ใช่การรับรองความปลอดภัยในการนวด",
    "Confirm the same camera/station and instructed posture; keep your head facing forward.": "กรุณายืนยันกล้องและจุดตรวจเดิม ทำตามท่าที่กำหนด และมองตรง",
    "Enter a customer ID and a visit reference (1-128 characters each).": "กรุณากรอกรหัสผู้รับบริการและรหัสครั้งรับบริการ (ช่องละ 1–128 ตัวอักษร)",
    "No baseline": "ยังไม่พบข้อมูลก่อนนวดสำหรับรหัสนี้ กรุณาบันทึกข้อมูลก่อนนวดก่อน",
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
    prefixes = (
        ("Model, camera, resolution or capture station changed.", TEXT["Model, camera, resolution or capture station changed."]),
        ("A baseline already exists for this visit;", TEXT["A baseline already exists for this visit; use a recheck or a new visit reference."]),
        ("Baseline is expired or future-dated.", TEXT["Baseline is expired or future-dated."]),
        ("The baseline has no complete arm angles;", TEXT["The baseline has no complete arm angles; contact staff to collect a new baseline"]),
        ("No baseline", TEXT["No baseline"]),
    )
    for prefix, translated_prefix in prefixes:
        if text.startswith(prefix):
            suffix = (text[len(prefix):].replace("Comparison is inconclusive.", "การเปรียบเทียบจึงสรุปผลไม่ได้")
                      .replace(CARE_MESSAGE, CARE_TH))
            return translated_prefix + suffix
    # Preserve detailed numeric/technical diagnostics; localize common score labels.
    return (text.replace(CARE_MESSAGE, CARE_TH)
            .replace("Face delta ", "การเปลี่ยนแปลงใบหน้า ")
            .replace(" + arm delta ", " + การเปลี่ยนแปลงแขน ")
            .replace("2D arm-angle delta: ", "การเปลี่ยนแปลงมุมแขน 2D: ")
            .replace(" / rule ", " / เกณฑ์ ").replace(" degrees", " องศา"))


def customer_result_status(assessment, comparison):
    """Resolve the outcome consistently for result copy and summary progress."""
    if isinstance(comparison, dict) and comparison.get("save_failed"):
        return "save_failed"
    status = comparison.get("status") if isinstance(comparison, dict) else None
    return status or CUSTOMER_LEVEL_STATUS.get(assessment.get("level"))


STAFF_REVIEW_STATUSES = frozenset(("inconclusive", "research_incomplete", "threshold_unconfigured", "identity_rejected", "acquisition_failed", "save_failed"))


def customer_assessment(assessment, comparison):
    """Return customer-safe copy while backend diagnostics remain available."""
    status = customer_result_status(assessment, comparison)
    if status in CUSTOMER_RESULTS:
        title, body = CUSTOMER_RESULTS[status]
        symptoms_reported = isinstance(comparison, dict) and comparison.get("symptoms_reported") is True
        if status == "baseline_saved" and isinstance(comparison, dict) and comparison.get("baseline_replaced"):
            title = "อัปเดตข้อมูลก่อนนวดแล้ว"
            body = ("แทนที่ข้อมูลก่อนนวดชุดเดิมที่ใช้เปรียบเทียบไม่ได้แล้ว\n\n"
                    "ขั้นตอนต่อไป: สามารถใช้รหัสผู้รับบริการและรหัสครั้งเดิมในการตรวจซ้ำได้\n\n"
                    "ระบบเก็บข้อมูลชุดเดิมไว้ในประวัติ และจะไม่ใช้ผลตรวจซ้ำเก่ามาเปรียบเทียบกับ baseline ชุดใหม่นี้")
        if status == "acquisition_failed" and isinstance(comparison, dict):
            body += display_text(comparison.get("reason", "ไม่พบสาเหตุที่วัดได้ครบ"))
            body += ("\n\nกดปุ่ม ‘เก็บข้อมูลใหม่อีกครั้ง’ เพื่อเริ่มตั้งแต่ขั้นตอนแรก "
                     "ใช้รหัสผู้รับบริการและรหัสครั้งเดิมได้\nปรับท่าหรือมุมกล้องตามสาเหตุก่อนเริ่มใหม่")
            if comparison.get("alert") or comparison.get("prior_alert"):
                title = "เก็บข้อมูลไม่ครบ · พบค่าที่เปลี่ยนมากระหว่างตรวจ"
                body = "ระบบพบค่าที่เปลี่ยนจากก่อนนวดมากระหว่างตรวจ กรุณาแจ้งเจ้าหน้าที่ทันที ไม่ต้องรอเก็บข้อมูลใหม่ให้ครบ\n\n" + body + "\n\n" + CARE_TH
        if status == "save_failed" and isinstance(comparison, dict) and comparison.get("save_reason"):
            body += "รายละเอียดสำหรับเจ้าหน้าที่: " + display_text(comparison["save_reason"])
            original = comparison.get("measurement_result")
            if original in ("delta_alert", "research_alert"):
                body += "\n\nผลการวัดพบค่าหลังนวดเปลี่ยนมากกว่าระดับที่กำหนด แต่ยังบันทึกผลไม่สำเร็จ กรุณาแจ้งเจ้าหน้าที่ทันที"
        if status == "research_alert" and isinstance(comparison, dict):
            # Name only regions explicitly flagged by the research OR-rule.
            # The combined deployment score does not identify a triggering region.
            measured = comparison.get("research_measurement") or {}
            regions = []
            if measured.get("face_alert") is True:
                regions.append("ความไม่สมมาตรของใบหน้า")
            if measured.get("arm_alert") is True:
                regions.append("การเคลื่อนไหวแขน")
            region_text = "และ".join(regions) if regions else "ค่าจากใบหน้าและแขน"
            details = {"neutral_mouth_ratio": "มุมปากขณะผ่อนคลาย", "neutral_brow_ratio": "แนวคิ้วขณะผ่อนคลาย",
                       "neutral_eyelid_ratio": "การลืมตาขณะผ่อนคลาย", "smile_mouth_ratio": "มุมปากขณะยิ้ม",
                       "closed_eyelid_ratio": "ความต่างของการหลับตาซ้าย–ขวา"}
            affected = [details[key] for key in measured.get("face_trigger_features", ()) if key in details]
            detail_text = "รายการที่เปลี่ยน: " + ", ".join(affected) + "\n\n" if affected else ""
            arm_status = measured.get("arm_function_status")
            if arm_status == "unable_to_raise":
                arm_detail = "การทดสอบแขน: ไม่สามารถยกแขนทั้งสองข้างถึงระดับที่กำหนดภายในเวลา\n\n"
            elif arm_status == "unable_to_hold":
                arm_detail = "การทดสอบแขน: ยกแขนขึ้นได้ แต่ค้างไว้ไม่ครบ 3 วินาที\n\n"
            else:
                arm_detail = ""
            body = (f"สิ่งที่พบ: ระบบวัดพบว่า{region_text}หลังนวดเพิ่มขึ้นหรือผิดปกติจากก่อนนวดเกินระดับทดลอง\n\n"
                    + arm_detail
                    + detail_text +
                    "สิ่งที่ควรทำ: แจ้งเจ้าหน้าที่ทันทีเพื่อช่วยประเมินอาการร่วมกัน "
                    "ผลจากกล้องนี้ไม่ใช่การวินิจฉัยโรค\n\n" + CARE_TH)
        if symptoms_reported and status not in ("research_alert", "delta_alert") and CARE_TH not in body:
            body += ("\n\nคุณระบุว่ามีอาการผิดปกติ กรุณาบอกอาการแก่เจ้าหน้าที่ แม้ค่าที่วัดจะไม่เกินเกณฑ์"
                     "หรือระบบประเมินไม่ได้\n\n" + CARE_TH)
        return title, body
    title = display_text(assessment.get("level", "ยังไม่มีผล"))
    reasons = "\n".join(display_text(reason) for reason in assessment.get("reasons", ()))
    disclaimer = display_text(assessment.get("disclaimer", ""))
    body = "\n\n".join(part for part in (reasons, disclaimer) if part)
    return title, body


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
