from __future__ import annotations

import secrets

import segno
from sqlalchemy.orm import Session

from app.models.dining import QrCode

# Sin 0/O, 1/l/I: se pueden dictar por teléfono sin errores
_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"


def new_code(db: Session, length: int = 7) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        if not db.query(QrCode.id).filter(QrCode.code == code).first():
            return code
    raise RuntimeError("No se pudo generar un código QR único")


def svg(data: str, *, dark: str = "#111111", light: str = "#ffffff", border: int = 2, error: str = "m") -> str:
    """SVG con viewBox y sin tamaño fijo: se dimensiona con CSS (p. ej. width: 35mm al imprimir)."""
    qr = segno.make(data, error=error, micro=False)
    return qr.svg_inline(scale=1, border=border, dark=dark, light=light, omitsize=True)
