"""Lectura de la carta para la web pública, la cocina y el TPV."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.models.menu import MenuCategory, MenuProduct, ModifierGroup
from app.services.allergens import normalize_allergens


def tr(entity, field: str, lang: str) -> str | None:
    """Texto traducido con vuelta al original si falta la traducción."""
    base = getattr(entity, field, None)
    if not lang or lang == "es":
        return base
    data = (getattr(entity, "i18n", None) or {}).get(lang) or {}
    return data.get(field) or base


def price_str(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def load_menu(db: Session, company_id: UUID, include_inactive: bool = False) -> list[MenuCategory]:
    q = (
        db.query(MenuCategory)
        .options(
            selectinload(MenuCategory.products)
            .selectinload(MenuProduct.modifier_groups)
            .selectinload(ModifierGroup.options)
        )
        .filter(MenuCategory.company_id == company_id)
        .order_by(MenuCategory.position, MenuCategory.name)
    )
    if not include_inactive:
        q = q.filter(MenuCategory.is_active.is_(True))
    return q.all()


def product_dict(p: MenuProduct, lang: str = "es", by_id: dict | None = None) -> dict:
    upsell = None
    if p.upsell_product_id and by_id and p.upsell_product_id in by_id:
        target = by_id[p.upsell_product_id]
        if target.is_active and target.is_available:
            upsell = {
                "product_id": str(target.id),
                "name": tr(target, "name", lang),
                "price": price_str(target.price),
                "extra": price_str(Decimal(target.price) - Decimal(p.price)),
            }
    return {
        "id": str(p.id),
        "category_id": str(p.category_id),
        "name": tr(p, "name", lang),
        "description": tr(p, "description", lang),
        "price": price_str(p.price),
        "tax_rate": price_str(p.tax_rate),
        "takeaway_tax_rate": price_str(p.takeaway_tax_rate) if p.takeaway_tax_rate is not None else None,
        "image_url": p.image_url,
        "allergens": normalize_allergens(p.allergens),
        "may_contain": normalize_allergens(p.may_contain),
        "tags": list(p.tags or []),
        "removable": list(p.removable_ingredients or []),
        "available": bool(p.is_available),
        "active": bool(p.is_active),
        "upsell": upsell,
        "kitchen_station": p.kitchen_station,
        "groups": [
            {
                "id": str(g.id),
                "name": tr(g, "name", lang),
                "min": g.min_select,
                "max": g.max_select,
                "options": [
                    {
                        "id": str(o.id),
                        "name": tr(o, "name", lang),
                        "price_delta": price_str(o.price_delta),
                        "available": bool(o.is_available),
                        "default": bool(o.is_default),
                        "allergens": normalize_allergens(o.allergens),
                    }
                    for o in g.options
                ],
            }
            for g in p.modifier_groups
        ],
    }


def menu_dict(categories: list[MenuCategory], lang: str = "es", include_inactive: bool = False) -> list[dict]:
    by_id = {p.id: p for c in categories for p in c.products}
    out = []
    for c in categories:
        products = [p for p in c.products if include_inactive or p.is_active]
        if not products and not include_inactive:
            continue
        out.append({
            "id": str(c.id),
            "name": tr(c, "name", lang),
            "description": tr(c, "description", lang),
            "note": tr(c, "note", lang),
            "image_url": c.image_url,
            "suggest_category_id": str(c.suggest_category_id) if c.suggest_category_id else None,
            "active": bool(c.is_active),
            "products": [product_dict(p, lang, by_id) for p in products],
        })
    return out
