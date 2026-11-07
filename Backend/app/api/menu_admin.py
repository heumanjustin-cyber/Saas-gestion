"""Gestión de la carta: categorías, platos, modificadores, agotados e importación."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.venue_admin import actor
from app.core.company_access import Actor
from app.db.dependencies import get_db
from app.models.menu import MenuCategory, MenuProduct, ModifierGroup, ModifierOption
from app.schemas.hospitality import (
    AvailabilityIn,
    CategoryIn,
    CategoryPatch,
    GroupIn,
    OptionIn,
    ProductIn,
    ProductPatch,
)
from app.services.menu_service import load_menu, menu_dict, product_dict

router = APIRouter(prefix="/my/venues/{company_id}/menu", tags=["Hostelería · carta"])


def _owned(db: Session, model, obj_id: UUID, company_id: UUID, what: str):
    obj = db.get(model, obj_id)
    owner = getattr(obj, "company_id", None) if obj else None
    if model is ModifierOption and obj:
        owner = obj.group.company_id
    if not obj or owner != company_id:
        raise HTTPException(status_code=404, detail=f"{what} no encontrado")
    return obj


def _groups(db: Session, company_id: UUID, ids: list[UUID]) -> list[ModifierGroup]:
    groups = []
    for gid in ids:
        groups.append(_owned(db, ModifierGroup, gid, company_id, "Grupo de opciones"))
    return groups


def _set_product_groups(db: Session, product: MenuProduct, groups: list[ModifierGroup]) -> None:
    from app.models.menu import product_modifier_groups as pmg

    db.execute(pmg.delete().where(pmg.c.product_id == product.id))
    for i, g in enumerate(groups):
        db.execute(pmg.insert().values(product_id=product.id, group_id=g.id, position=i))


@router.get("")
def get_menu(company_id: UUID, lang: str = Query("es"), a: Actor = Depends(actor()), db: Session = Depends(get_db)):
    return menu_dict(load_menu(db, company_id, include_inactive=True), lang, include_inactive=True)


# ------------------------------------------------------------------ categorías
@router.post("/categories", status_code=201)
def create_category(company_id: UUID, data: CategoryIn, a: Actor = Depends(actor("services.create", True)),
                    db: Session = Depends(get_db)):
    if data.suggest_category_id:
        _owned(db, MenuCategory, data.suggest_category_id, company_id, "Categoría sugerida")
    c = MenuCategory(company_id=company_id, **data.model_dump())
    db.add(c)
    db.commit()
    return {"id": str(c.id), "name": c.name}


@router.patch("/categories/{category_id}")
def update_category(company_id: UUID, category_id: UUID, data: CategoryPatch,
                    a: Actor = Depends(actor("services.edit", True)), db: Session = Depends(get_db)):
    c = _owned(db, MenuCategory, category_id, company_id, "Categoría")
    values = data.model_dump(exclude_unset=True)
    if values.get("suggest_category_id"):
        _owned(db, MenuCategory, values["suggest_category_id"], company_id, "Categoría sugerida")
    for k, v in values.items():
        setattr(c, k, v)
    db.commit()
    return {"id": str(c.id), "name": c.name, "is_active": c.is_active}


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(company_id: UUID, category_id: UUID, a: Actor = Depends(actor("services.delete", True)),
                    db: Session = Depends(get_db)):
    c = _owned(db, MenuCategory, category_id, company_id, "Categoría")
    db.delete(c)
    db.commit()


# ------------------------------------------------------------------ grupos de opciones
def group_dict(g: ModifierGroup) -> dict:
    return {"id": str(g.id), "name": g.name, "min_select": g.min_select, "max_select": g.max_select,
            "options": [{"id": str(o.id), "name": o.name, "price_delta": f"{o.price_delta:.2f}",
                         "is_available": o.is_available, "is_default": o.is_default, "allergens": o.allergens}
                        for o in g.options]}


@router.get("/groups")
def list_groups(company_id: UUID, a: Actor = Depends(actor()), db: Session = Depends(get_db)):
    rows = db.query(ModifierGroup).filter(ModifierGroup.company_id == company_id).order_by(ModifierGroup.position).all()
    return [group_dict(g) for g in rows]


@router.post("/groups", status_code=201)
def create_group(company_id: UUID, data: GroupIn, a: Actor = Depends(actor("services.create", True)),
                 db: Session = Depends(get_db)):
    if data.max_select and data.min_select > data.max_select:
        raise HTTPException(status_code=422, detail="El mínimo no puede ser mayor que el máximo.")
    g = ModifierGroup(company_id=company_id, name=data.name, min_select=data.min_select, max_select=data.max_select,
                      position=data.position, i18n=data.i18n)
    for i, o in enumerate(data.options):
        g.options.append(ModifierOption(position=i, **o.model_dump()))
    db.add(g)
    db.commit()
    return group_dict(g)


@router.post("/groups/{group_id}/options", status_code=201)
def add_option(company_id: UUID, group_id: UUID, data: OptionIn, a: Actor = Depends(actor("services.edit", True)),
               db: Session = Depends(get_db)):
    g = _owned(db, ModifierGroup, group_id, company_id, "Grupo de opciones")
    g.options.append(ModifierOption(position=len(g.options), **data.model_dump()))
    db.commit()
    return group_dict(g)


@router.patch("/options/{option_id}/availability")
def option_availability(company_id: UUID, option_id: UUID, data: AvailabilityIn,
                        a: Actor = Depends(actor("orders.manage")), db: Session = Depends(get_db)):
    """«Se acabó el falafel»: lo marca agotado en todos los platos que lo usan."""
    o = _owned(db, ModifierOption, option_id, company_id, "Opción")
    o.is_available = data.is_available
    db.commit()
    return {"id": str(o.id), "name": o.name, "is_available": o.is_available}


# ------------------------------------------------------------------ platos
@router.post("/products", status_code=201)
def create_product(company_id: UUID, data: ProductIn, a: Actor = Depends(actor("services.create", True)),
                   db: Session = Depends(get_db)):
    _owned(db, MenuCategory, data.category_id, company_id, "Categoría")
    if data.upsell_product_id:
        _owned(db, MenuProduct, data.upsell_product_id, company_id, "Plato de menú")
    groups = _groups(db, company_id, data.group_ids)
    values = data.model_dump(exclude={"group_ids"})
    p = MenuProduct(company_id=company_id, **values)
    db.add(p)
    db.flush()
    _set_product_groups(db, p, groups)
    db.commit()
    db.refresh(p)
    return product_dict(p)


@router.patch("/products/{product_id}")
def update_product(company_id: UUID, product_id: UUID, data: ProductPatch,
                   a: Actor = Depends(actor("services.edit", True)), db: Session = Depends(get_db)):
    p = _owned(db, MenuProduct, product_id, company_id, "Plato")
    values = data.model_dump(exclude_unset=True)
    if values.get("category_id"):
        _owned(db, MenuCategory, values["category_id"], company_id, "Categoría")
    if values.get("upsell_product_id"):
        _owned(db, MenuProduct, values["upsell_product_id"], company_id, "Plato de menú")
    group_ids = values.pop("group_ids", None)
    for k, v in values.items():
        setattr(p, k, v)
    if group_ids is not None:
        _set_product_groups(db, p, _groups(db, company_id, group_ids))
    db.commit()
    db.refresh(p)
    return product_dict(p)


@router.patch("/products/{product_id}/availability")
def product_availability(company_id: UUID, product_id: UUID, data: AvailabilityIn,
                         a: Actor = Depends(actor("orders.manage")), db: Session = Depends(get_db)):
    """Agotado / disponible en un toque (desde cocina o TPV). La web lo refleja al momento."""
    p = _owned(db, MenuProduct, product_id, company_id, "Plato")
    p.is_available = data.is_available
    db.commit()
    return {"id": str(p.id), "name": p.name, "is_available": p.is_available}


@router.delete("/products/{product_id}", status_code=204)
def delete_product(company_id: UUID, product_id: UUID, a: Actor = Depends(actor("services.delete", True)),
                   db: Session = Depends(get_db)):
    p = _owned(db, MenuProduct, product_id, company_id, "Plato")
    db.delete(p)
    db.commit()
