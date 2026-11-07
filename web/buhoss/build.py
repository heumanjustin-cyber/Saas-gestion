"""Genera index.html (web desplegable de BUHOSS) a partir de src.html.

src.html es la misma página que se publica como Artifact en claude.ai (sin <html>/<head>).
Aquí se envuelve en un documento completo, con metadatos para Google y WhatsApp, y con las
tipografías alojadas junto a la página en vez de cargarlas de Google Fonts (sin peticiones a
terceros: mejor para la privacidad de los visitantes y más rápido).

    python web/buhoss/build.py
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

FONTS = """<style>
@font-face { font-family: "Bricolage Grotesque"; src: url("fonts/bricolage-grotesque.woff2") format("woff2"); font-weight: 200 800; font-display: swap; }
@font-face { font-family: "Atkinson Hyperlegible"; src: url("fonts/atkinson-hyperlegible-400.woff2") format("woff2"); font-weight: 400; font-display: swap; }
@font-face { font-family: "Atkinson Hyperlegible"; src: url("fonts/atkinson-hyperlegible-700.woff2") format("woff2"); font-weight: 700; font-display: swap; }
@font-face { font-family: "IBM Plex Mono"; src: url("fonts/ibm-plex-mono-400.woff2") format("woff2"); font-weight: 400; font-display: swap; }
@font-face { font-family: "IBM Plex Mono"; src: url("fonts/ibm-plex-mono-500.woff2") format("woff2"); font-weight: 500; font-display: swap; }
@font-face { font-family: "IBM Plex Mono"; src: url("fonts/ibm-plex-mono-600.woff2") format("woff2"); font-weight: 600; font-display: swap; }
</style>"""

DESCRIPTION = ("Reservas, pedidos, cobros, avisos y automatizaciones para peluquerías, bares, restaurantes, "
               "clínicas, tiendas y empresas. Tú atiendes; BUHOSS se encarga del resto.")

FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 38 30'%3E"
           "%3Crect width='38' height='30' rx='7' fill='%230E1828'/%3E"
           "%3Ccircle cx='12' cy='15' r='8' fill='%23EAF0F8'/%3E%3Ccircle cx='26' cy='15' r='8' fill='%23EAF0F8'/%3E"
           "%3Ccircle cx='12' cy='15' r='4' fill='%23EFA03A'/%3E%3Ccircle cx='26' cy='15' r='4' fill='%23EFA03A'/%3E%3C/svg%3E")


def build() -> Path:
    src = (HERE / "src.html").read_text(encoding="utf-8")
    title = re.search(r"<title>(.*?)</title>", src, re.S).group(1).strip()
    body = re.sub(r"<title>.*?</title>\s*", "", src, count=1, flags=re.S)
    body = re.sub(r'<meta name="claude:viewport-fit-sides"[^>]*>\s*', "", body)
    body = re.sub(r'<link rel="preconnect"[^>]*>\s*', "", body)
    body = re.sub(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com[^>]*>\s*', "", body)
    style = re.search(r"<style>.*?</style>", body, re.S).group(0)
    body = body.replace(style, "", 1)
    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title} · Sistemas para negocios que atienden</title>
<meta name="description" content="{DESCRIPTION}">
<meta name="theme-color" content="#0E1828">
<meta property="og:type" content="website">
<meta property="og:locale" content="es_ES">
<meta property="og:title" content="{title} · Tú atiendes. BUHOSS se encarga del resto.">
<meta property="og:description" content="{DESCRIPTION}">
<link rel="icon" href="{FAVICON}">
<link rel="preload" href="fonts/bricolage-grotesque.woff2" as="font" type="font/woff2" crossorigin>
{FONTS}
{style}
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
