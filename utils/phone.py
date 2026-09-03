import re


def normalize_phone_flexible(raw: str) -> str:
    """
    Aceita vários formatos e devolve só dígitos com DDI 55 quando for BR.
    Exemplos válidos:
      449986915568
      (44) 99869-1556
      +55 44 99869-1556
      55449986915568
    """
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
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
    # BR celular/fix: 12 ou 13 dígitos com 55
    if d.startswith("55") and len(d) in (12, 13):
        return True
    # internacional genérico
    return 10 <= len(d) <= 15
