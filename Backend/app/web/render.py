"""Plantillas HTML (Jinja2) y utilidades para las páginas servidas por el backend."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.core.config import PUBLIC_BASE_URL

WEB_DIR = Path(__file__).parent
STATIC_DIR = WEB_DIR / "static"
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def eur(value) -> str:
    """7 → «7,00 €», -3.5 → «-3,50 €» (formato español)."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    sign = "-" if d < 0 else ""
    whole, frac = f"{abs(d):.2f}".split(".")
    whole = f"{int(whole):,}".replace(",", ".")
    return f"{sign}{whole},{frac} €"


def num(value) -> str:
    """Cantidad sin ceros sobrantes: 2.000 → «2», 0.500 → «0,5»."""
    d = Decimal(str(value)).normalize()
    return f"{d:f}".replace(".", ",")


templates.env.filters["eur"] = eur
templates.env.filters["num"] = num


def public_base(request: Request) -> str:
    """URL pública del backend para imprimir en QR y enlaces (respeta proxies)."""
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"
