"""Validación de NIF españoles (DNI, NIE y CIF) para facturas completas."""
from __future__ import annotations

import re

_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def normalize(value: str) -> str:
    return re.sub(r"[\s\-.]", "", value or "").upper()


def is_valid_nif(value: str) -> bool:
    v = normalize(value)
    if re.fullmatch(r"\d{8}[A-Z]", v):  # DNI
        return _LETTERS[int(v[:8]) % 23] == v[8]
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", v):  # NIE
        num = "XYZ".index(v[0]) * 10_000_000 + int(v[1:8])
        return _LETTERS[num % 23] == v[8]
    if re.fullmatch(r"[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]", v):  # CIF
        digits = v[1:8]
        even = sum(int(d) for d in digits[1::2])
        odd = sum(sum(divmod(int(d) * 2, 10)) for d in digits[0::2])
        control = (10 - (even + odd) % 10) % 10
        if v[0] in "PQRSNW":  # siempre letra
            return v[8] == "JABCDEFGHI"[control]
        if v[0] in "ABEH":  # siempre número
            return v[8] == str(control)
        return v[8] in (str(control), "JABCDEFGHI"[control])
    return False
