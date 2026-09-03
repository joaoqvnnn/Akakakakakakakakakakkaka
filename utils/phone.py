import re


def normalize_phone_flexible(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    if digits.startswith("0"):
        digits = digits.lstrip("0")
    if digits.startswith("55") and len(digits) >= 12:
        return digits
    if len(digits) in (10, 11):
        return "55" + digits
    if len(digits) >= 12:
        return digits
    return digits


def is_valid_phone_flexible(raw: str) -> bool:
    d = normalize_phone_flexible(raw)
    if not d:
        return False
    if d.startswith("55") and len(d) in (12, 13):
        return True
    return 10 <= len(d) <= 15
