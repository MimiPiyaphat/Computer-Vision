"""Presentation mode metadata and acquisition lock; no GUI dependencies."""

MODES = {
    "baseline": ("01  ก่อนนวด · Baseline", "บันทึกข้อมูลอ้างอิงก่อนนวด",
                 "ใช้รหัสผู้รับบริการและรหัสครั้งรับบริการใหม่ เพื่อบันทึกข้อมูลใบหน้าและแขนก่อนนวด",
                 "เริ่มบันทึกก่อนนวด"),
    "recheck": ("02  หลังนวด · Recheck", "ตรวจซ้ำเมื่อมีอาการผิดปกติ",
                "ใช้รหัสเดิมจากการบันทึกก่อนนวด และยืนยันว่าผู้รับบริการแจ้งอาการผิดปกติ",
                "เริ่มตรวจซ้ำ"),
}


def can_change_mode(snapshot):
    """Never change an in-flight acquisition's mode or enrollment identity."""
    if not snapshot:
        return True
    if snapshot.get("status") in ("loading", "disconnecting"):
        return False
    return snapshot.get("status") != "ready" or snapshot.get("state", "idle") in (
        "idle", "summary", "identity_rejected")
