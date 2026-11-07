"""Migración desde Studio 42 a BUHOS en un comando.

Lee los dos formatos que publica Studio 42 para cada cliente:
- el «hub» del QR (https://studio42.es/c/<código>.json, versión 2): nombre, colores,
  ficha (dirección, teléfono, horario OSM, coordenadas), botón de reseña y alérgenos;
- la carta con pedidos (el objeto `window.PEDIDO_VE` de su carta.js, exportado a JSON):
  categorías, platos, grupos de elección con suplemento, extras, «quitar», menús,
  domicilio, formas de pago y número de mesas.

Lo que no existe en Studio 42 (alérgenos plato a plato) se marca como «sin confirmar»
para que el filtro de alérgenos no dé por seguro un plato que nadie ha revisado.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.dining import DiningTable, QrCode
from app.models.menu import MenuCategory, MenuProduct, ModifierGroup, ModifierOption, product_modifier_groups
from app.models.venue import VenueProfile
from app.services import qr_service
from app.services.allergens import normalize_allergens
from app.services.hours import parse_osm_hours

UNVERIFIED = "allergens_unverified"
_PAY = {"efectivo": "cash", "tarjeta": "card", "bizum": "bizum", "punto": "card"}


def _slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _nice_name(name: str) -> str:
    return name.title() if name and name.isupper() else name


def _digits(value: str | None) -> str | None:
    d = re.sub(r"\D", "", value or "")
    return d or None


def _venue(db: Session, company: Company) -> VenueProfile:
    v = db.query(VenueProfile).filter(VenueProfile.company_id == company.id).first()
    if not v:
        v = VenueProfile(company_id=company.id)
        db.add(v)
        db.flush()
    return v


def import_hub(db: Session, company: Company, hub: dict) -> dict:
    """Ficha del local desde el JSON del hub de Studio 42."""
    v = _venue(db, company)
    ficha = hub.get("ficha") or {}
    v.display_name = _nice_name(hub.get("nombre") or company.name)
    v.tagline = hub.get("subtitulo") or v.tagline
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", hub.get("colorPrincipal") or ""):
        v.brand_color = hub["colorPrincipal"]
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", hub.get("colorAcento") or ""):
        v.accent_color = hub["colorAcento"]
    wa = hub.get("whatsapp") or ""
    v.whatsapp = _digits(urlparse(wa).path) if "wa.me" in wa else _digits(wa) or v.whatsapp
    v.address = ficha.get("direccion") or v.address
    v.postal_code = ficha.get("cp") or v.postal_code
    v.city = ficha.get("ciudad") or v.city
    v.province = ficha.get("provincia") or v.province
    v.phone = ficha.get("telefono") or v.phone
    if ficha.get("lat") is not None and ficha.get("lng") is not None:
        v.latitude, v.longitude = Decimal(str(ficha["lat"])), Decimal(str(ficha["lng"]))
    v.google_maps_url = ficha.get("mapsUrl") or v.google_maps_url
    v.price_range = ficha.get("precio") if re.fullmatch(r"€{1,4}", ficha.get("precio") or "") else v.price_range
    if ficha.get("categoria"):
        v.cuisine = [ficha["categoria"]]
    warnings: list[str] = []
    if ficha.get("horario"):
        v.opening_hours = parse_osm_hours(ficha["horario"])

    allergen_cards: list[str] = []
    for section in hub.get("secciones") or []:
        for btn in section.get("botones") or []:
            if btn.get("tipo") == "opinion" and btn.get("urlGoogle"):
                place = parse_qs(urlparse(btn["urlGoogle"]).query).get("placeid", [None])[0]
                if place:
                    v.google_place_id = place
            if btn.get("tipo") == "info" and btn.get("tarjetas"):
                for card in btn["tarjetas"]:
                    allergen_cards.append(f"{card.get('titulo', '').strip()}: {card.get('texto', '').strip()}")
                if btn.get("aviso"):
                    allergen_cards.append(btn["aviso"].strip())
    if allergen_cards:
        v.allergen_notice = (" ".join(allergen_cards) + " Información pendiente de confirmar plato a plato: "
                             "si tienes una alergia, pregunta al personal antes de pedir.")
    db.flush()
    return {"venue": v.display_name, "hours": v.opening_hours, "warnings": warnings}


def _group_key(title: str, options: list[tuple[str, Decimal]], min_s: int, max_s: int) -> tuple:
    return (title, tuple(options), min_s, max_s)


def import_carta(db: Session, company: Company, carta: dict, allergen_hints: dict | None = None,
                 replace: bool = True, create_tables: bool = True) -> dict:
    """Carta y reglas de pedido desde `window.PEDIDO_VE` (JSON). `allergen_hints` = {external_ref: [códigos]}
    y {"option:<nombre>": [códigos]} para precargar alérgenos conocidos (siguen marcados «sin confirmar»)."""
    hints = allergen_hints or {}
    v = _venue(db, company)

    # Reglas de pedido
    d = carta.get("delivery")
    if d:
        v.delivery_enabled = True
        if isinstance(d, dict):
            v.delivery_fee = Decimal(str(d.get("precio") or 0))
            v.delivery_min_order = Decimal(str(d.get("minimo") or 0))
    if carta.get("notaDelivery"):
        v.delivery_note = carta["notaDelivery"][:255]
    methods = [_PAY[m[0]] for m in carta.get("metodos") or [] if m and m[0] in _PAY]
    if methods:
        v.payment_methods = list(dict.fromkeys(methods))
    v.dine_in_enabled = carta.get("mesas") is not False
    if isinstance(carta.get("cambioDeDia"), int):
        v.day_change_hour = carta["cambioDeDia"]

    if replace:
        for c in db.query(MenuCategory).filter(MenuCategory.company_id == company.id).all():
            db.delete(c)
        for g in db.query(ModifierGroup).filter(ModifierGroup.company_id == company.id).all():
            db.delete(g)
        db.flush()

    groups: dict[tuple, ModifierGroup] = {}

    def group_for(title: str, raw: list, min_s: int, max_s: int, price_field: str) -> ModifierGroup:
        opts: list[tuple[str, Decimal]] = []
        for o in raw or []:
            if isinstance(o, str):
                opts.append((o, Decimal("0")))
            else:
                opts.append((o.get("n"), Decimal(str(o.get(price_field) or 0))))
        key = _group_key(title, opts, min_s, max_s)
        if key not in groups:
            g = ModifierGroup(company_id=company.id, name=title, min_select=min_s, max_select=max_s,
                              position=len(groups), external_ref=_slug(title))
            for i, (name, delta) in enumerate(opts):
                g.options.append(ModifierOption(name=name, price_delta=delta, position=i,
                                                allergens=normalize_allergens(hints.get(f"option:{name}", []))))
            db.add(g)
            db.flush()
            groups[key] = g
        return groups[key]

    created_products: dict[str, MenuProduct] = {}
    upsells: list[tuple[MenuProduct, str]] = []
    drinks_cat: MenuCategory | None = None
    cats: list[tuple[MenuCategory, dict]] = []
    for ci, cat in enumerate(carta.get("categorias") or []):
        mc = MenuCategory(company_id=company.id, name=cat["nombre"], note=cat.get("nota"), position=ci,
                          external_ref=_slug(cat["nombre"]))
        db.add(mc)
        db.flush()
        cats.append((mc, cat))
        if cat.get("esBebida"):
            drinks_cat = mc
        extras = cat.get("extras")
        extra_group = group_for(extras.get("titulo") or "Extras", extras.get("opciones"), 0, 0, "precio") if extras else None
        for pi, prod in enumerate(cat.get("productos") or []):
            p = MenuProduct(
                company_id=company.id, category_id=mc.id, name=prod["nombre"], description=prod.get("ingredientes"),
                price=Decimal(str(prod["precio"])), position=pi, external_ref=prod.get("id"),
                removable_ingredients=list(prod.get("quitar") or []), tags=[UNVERIFIED],
                allergens=normalize_allergens(hints.get(prod.get("id"), [])),
            )
            db.add(p)
            db.flush()
            pgroups = [group_for(g.get("titulo"), g.get("opciones"), 1, 1, "mas") for g in prod.get("grupos") or []]
            if extra_group:
                pgroups.append(extra_group)
            for i, g in enumerate(pgroups):
                db.execute(product_modifier_groups.insert().values(product_id=p.id, group_id=g.id, position=i))
            if prod.get("id"):
                created_products[prod["id"]] = p
            if prod.get("menu"):
                upsells.append((p, prod["menu"]))
    for p, ref in upsells:
        target = created_products.get(ref)
        if target:
            p.upsell_product_id = target.id
    # «¿Algo de beber?» en las categorías que no llevan ya bebida
    if drinks_cat:
        for mc, cat in cats:
            if mc.id != drinks_cat.id and not cat.get("sinBebidas"):
                mc.suggest_category_id = drinks_cat.id

    tables_created = 0
    n_tables = carta.get("mesas")
    if create_tables and isinstance(n_tables, int) and n_tables > 0:
        existing = db.query(DiningTable).filter(DiningTable.company_id == company.id).count()
        for n in range(existing + 1, n_tables + 1):
            t = DiningTable(company_id=company.id, name=f"Mesa {n}", position=n)
            db.add(t)
            db.flush()
            db.add(QrCode(company_id=company.id, code=qr_service.new_code(db), kind="table", label=t.name, table_id=t.id))
            tables_created += 1
    db.flush()
    return {"categories": len(cats), "products": len(created_products), "groups": len(groups),
            "upsells": sum(1 for p, ref in upsells if ref in created_products), "tables": tables_created,
            "delivery": bool(d), "payment_methods": v.payment_methods}


def apply_translations(db: Session, company_id, mapping: dict) -> int:
    """Traducciones por texto en español: {"Bebidas": {"en": "Drinks", "fr": "Boissons"}, ...}."""
    def tr_fields(entity, fields: tuple[str, ...]) -> int:
        data = dict(entity.i18n or {})
        n = 0
        for f in fields:
            src = getattr(entity, f, None)
            for lang, text in (mapping.get(src) or {}).items():
                data.setdefault(lang, {})[f] = text
                n += 1
        entity.i18n = data
        return n

    count = 0
    for c in db.query(MenuCategory).filter(MenuCategory.company_id == company_id).all():
        count += tr_fields(c, ("name", "note", "description"))
        for p in c.products:
            count += tr_fields(p, ("name", "description"))
    for g in db.query(ModifierGroup).filter(ModifierGroup.company_id == company_id).all():
        count += tr_fields(g, ("name",))
        for o in g.options:
            count += tr_fields(o, ("name",))
    db.flush()
    return count
