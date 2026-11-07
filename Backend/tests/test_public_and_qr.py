"""QR dinámicos con analítica, página pública (SEO, idiomas, sin JS) y migración desde Studio 42."""
import json
import re
from pathlib import Path

from app.db.session import SessionLocal
from app.models.company import Company
from app.services.studio42_import import apply_translations, import_carta, import_hub

SEED = Path(__file__).resolve().parent.parent / "seed" / "ankara"


def test_qr_de_mesa_redirige_y_cuenta_sin_bots(client, venue):
    cid, h = venue["company_id"], venue["h"]
    t = client.post(f"/my/venues/{cid}/tables", headers=h, json={"name": "Terraza 1", "zone": "Terraza"}).json()
    code = t["qr"]["code"]
    assert re.fullmatch(r"[2-9a-z]{7}", code) and not set(code) & set("01lio")
    r = client.get(f"/q/{code}", headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == f"/r/{venue['slug']}?q={code}"
    client.get(f"/q/{code}", headers={"User-Agent": "WhatsApp/2.23"}, follow_redirects=False)  # vista previa: no cuenta
    qrs = client.get(f"/my/venues/{cid}/qr-codes", headers=h).json()
    mine = next(q for q in qrs if q["code"] == code)
    assert mine["scan_count"] == 1 and mine["url"].endswith(f"/q/{code}")
    page = client.get(f"/r/{venue['slug']}?q={code}").text
    assert "Terraza 1" in page  # «Estás en Terraza 1»

    # Rotar el QR: el viejo deja de llevar a la mesa
    new = client.post(f"/my/venues/{cid}/tables/{t['id']}/rotate-qr", headers=h).json()["qr"]["code"]
    old = client.get(f"/q/{code}", follow_redirects=False)
    assert old.headers["location"] == f"/r/{venue['slug']}" and new != code


def test_qr_de_resena_y_destino_cambiable_sin_reimprimir(client, venue):
    cid, h = venue["company_id"], venue["h"]
    q = client.post(f"/my/venues/{cid}/qr-codes", headers=h, json={"kind": "bag", "label": "Bolsa", "target": "review"}).json()
    r = client.get(f"/q/{q['code']}", follow_redirects=False)
    assert r.headers["location"].startswith("https://search.google.com/local/writereview?placeid=ChIJ")
    client.patch(f"/my/venues/{cid}/qr-codes/{q['id']}", headers=h, json={"target": "url", "target_url": "https://example.org/promo"})
    assert client.get(f"/q/{q['code']}", follow_redirects=False).headers["location"] == "https://example.org/promo"
    svg = client.get(f"/qr/{q['code']}.svg")
    assert svg.status_code == 200 and svg.headers["content-type"] == "image/svg+xml" and "<svg" in svg.text
    sheet = client.get(f"/my/venues/{cid}/qr-sheet", headers=h)
    assert sheet.status_code == 200 and "Escanea y pide" in sheet.text and q["code"] in sheet.text


def test_pagina_publica_seo_idiomas_y_sin_javascript(client, venue):
    r = client.get(f"/r/{venue['slug']}", headers={"Accept-Language": "fr-FR,fr;q=0.9"})
    assert r.status_code == 200
    html = r.text
    assert '<html lang="fr"' in html and "Voir la carte" in html  # idioma del móvil
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
    assert ld["@type"] == "Restaurant" and ld["hasMenu"]["hasMenuSection"][0]["hasMenuItem"]
    assert all(s["closes"] != "24:00" for s in ld["openingHoursSpecification"])
    assert "aggregateRating" not in ld  # nada de notas inventadas
    # La carta está en el HTML (Google y móviles sin JS la ven)
    assert "Kebab" in html and "5,00 €" in html and 'hreflang="en"' in html
    es = client.get(f"/r/{venue['slug']}?lang=es").text
    assert "Agua del grifo gratis" in es and "Precios con IVA incluido" in es
    assert client.get("/r/no-existe").status_code == 404


def test_opinion_privada_vcard_y_analitica(client, venue):
    r = client.post(f"/api/public/venues/{venue['slug']}/feedback", json={"message": "El dürüm, de diez. El pan, algo frío."})
    assert r.status_code == 201
    fb = client.get(f"/my/venues/{venue['company_id']}/feedback", headers=venue["h"]).json()
    assert fb[0]["message"].startswith("El dürüm")
    v = client.get(f"/api/public/venues/{venue['slug']}/vcard")
    assert v.headers["content-type"].startswith("text/vcard") and "FN:Ankara Kebab" in v.text and "TEL;" in v.text
    a = client.get(f"/my/venues/{venue['company_id']}/analytics", headers=venue["h"]).json()
    assert a["days"] == 30 and isinstance(a["pieces"], list)


def test_migracion_studio42_de_ankara(client, owner):
    """La carta real de Ankara (42 platos) entra en BUHOS con un comando."""
    slug = "ankara-mig-" + owner["email"][6:12]
    cid = client.post("/companies", json={"name": "Ankara Kebab", "slug": slug}, headers=owner["h"]).json()["id"]
    with SessionLocal() as db:
        company = db.query(Company).filter(Company.slug == slug).one()
        hub = import_hub(db, company, json.loads((SEED / "hub_studio42.json").read_text(encoding="utf-8")))
        stats = import_carta(db, company, json.loads((SEED / "carta_studio42.json").read_text(encoding="utf-8")),
                             json.loads((SEED / "allergen_hints.json").read_text(encoding="utf-8")))
        n = apply_translations(db, company.id, json.loads((SEED / "translations.json").read_text(encoding="utf-8")))
        db.commit()
    assert hub["hours"]["tue"] == [["19:00", "01:30"]] and hub["hours"]["sun"] == [["13:30", "24:00"]]
    assert stats == {"categories": 10, "products": 42, "groups": 8, "upsells": 4, "tables": 4, "delivery": True,
                     "payment_methods": ["cash", "card", "bizum"]} and n > 150
    prof = client.get(f"/my/venues/{cid}/profile", headers=owner["h"]).json()
    assert prof["google_place_id"] == "ChIJUQUjoe1VRQ0RoEKpuucdgF0" and prof["delivery_min_order"] == "10.00"
    assert prof["whatsapp"] == "34602552973" and prof["accent_color"] == "#FA8405"
    menu = client.get(f"/my/venues/{cid}/menu?lang=en", headers=owner["h"]).json()
    by_name = {p["name"]: p for c in menu for p in c["products"]}
    assert by_name["Kebab meal"]["price"] == "7.00" and by_name["Kebab"]["upsell"]["extra"] == "2.00"
    lahmacun = by_name["Lahmacun"]
    tuna = next(o for g in lahmacun["groups"] for o in g["options"] if o["name"] == "Tuna")
    assert tuna["price_delta"] == "-0.50" and tuna["allergens"] == ["fish"]
    assert all("allergens_unverified" in p["tags"] for p in by_name.values())  # hasta que el dueño lo revise
    drinks = next(c for c in menu if c["name"] == "Drinks")
    kebab_cat = next(c for c in menu if c["name"] == "Kebab, dürüm & lahmacun")
    meals = next(c for c in menu if c["name"] == "Kebab meals")
    assert kebab_cat["suggest_category_id"] == drinks["id"] and meals["suggest_category_id"] is None


def test_nombres_con_html_no_se_ejecutan(client, venue):
    cid, h = venue["company_id"], venue["h"]
    cat = client.get(f"/my/venues/{cid}/menu", headers=h).json()[0]["id"]
    evil = "</script><script>alert(1)</script>"
    r = client.post(f"/my/venues/{cid}/menu/products", headers=h, json={"category_id": cat, "name": evil, "price": "1"})
    assert r.status_code == 201
    html = client.get(f"/r/{venue['slug']}").text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in html  # en la carta, como texto
    cfg = re.search(r'<script id="buhos-config" type="application/json">(.*?)</script>', html, re.S).group(1)
    assert evil in json.dumps(json.loads(cfg), ensure_ascii=False)  # el JSON sigue íntegro
