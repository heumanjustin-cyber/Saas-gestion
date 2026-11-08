"""Genera index.html (web desplegable de Trébol Barber) a partir de src.html.

src.html es la misma página que se publica como Artifact en claude.ai (sin <html>/<head>).
Aquí se envuelve en un documento completo con metadatos para Google y WhatsApp.

    python web/trebol/build.py
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

DESCRIPTION = ("Trébol Barber, barbería en la calle Portillejo, 11 (Logroño). Degradados, diseños a navaja, barba y color. "
               "Entra en el local y pide tu cita online.")

FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
           "%3Crect width='32' height='32' rx='7' fill='%230A0C0B'/%3E%3Cg fill='%233FD46F'%3E"
           "%3Ccircle cx='16' cy='10' r='5.4'/%3E%3Ccircle cx='10' cy='16.4' r='5.4'/%3E%3Ccircle cx='22' cy='16.4' r='5.4'/%3E%3C/g%3E"
           "%3Cpath d='M16.4 18c.6 4 2 7.4 4.6 10' fill='none' stroke='%233FD46F' stroke-width='2.2' stroke-linecap='round'/%3E%3C/svg%3E")


def build() -> Path:
    src = (HERE / "src.html").read_text(encoding="utf-8")
    title = re.search(r"<title>(.*?)</title>", src, re.S).group(1).strip()
    body = re.sub(r"<title>.*?</title>\s*", "", src, count=1, flags=re.S)
    body = re.sub(r'<meta name="claude:viewport-fit-sides"[^>]*>\s*', "", body)
    head_links = "".join(re.findall(r"<link [^>]*>\s*", body))
    body = re.sub(r"<link [^>]*>\s*", "", body)
    style = re.search(r"<style>.*?</style>", body, re.S).group(0)
    body = body.replace(style, "", 1)
    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{DESCRIPTION}">
<meta name="theme-color" content="#0A0C0B">
<meta property="og:type" content="website">
<meta property="og:locale" content="es_ES">
<meta property="og:title" content="Trébol Barber · Calle Portillejo, 11 · Logroño">
<meta property="og:description" content="{DESCRIPTION}">
<meta property="og:image" content="fotos/fachada.webp">
<link rel="icon" href="{FAVICON}">
<link rel="preload" href="film/000.webp" as="image">
{head_links.strip()}
{style}
<style>[hidden]{{display:none!important}}</style>
</head>
<body>
{body.strip()}
</body>
</html>
"""
    out = HERE / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    path = build()
    print(f"Generado {path} ({path.stat().st_size // 1024} KB)")
