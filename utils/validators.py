import re
from typing import Optional


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def is_valid_email(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def is_valid_cpf(cpf: str) -> bool:
    cpf = only_digits(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    s = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d = (s * 10) % 11
    if d == 10:
        d = 0
    if d != int(cpf[9]):
        return False
    s = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d = (s * 10) % 11
    if d == 10:
        d = 0
    return d == int(cpf[10])


def format_cpf(cpf: str) -> str:
    c = only_digits(cpf)
    if len(c) != 11:
        return cpf
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"


def is_valid_phone_br(phone: str) -> bool:
    d = only_digits(phone)
    if d.startswith("55") and len(d) in (12, 13):
        return True
    return len(d) in (10, 11)


def normalize_phone_br(phone: str) -> str:
    d = only_digits(phone)
    if d.startswith("55"):
        return d
    if len(d) in (10, 11):
        return "55" + d
    return d


def detect_pix_key_type(key: str) -> str:
    k = (key or "").strip()
    if is_valid_email(k):
        return "email"
    digits = only_digits(k)
    if len(digits) == 11 and is_valid_cpf(digits):
        return "cpf"
    if len(digits) in (10, 11, 12, 13) and is_valid_phone_br(k):
        return "phone"
    if len(k) >= 20:
        return "random"
    return "random"
