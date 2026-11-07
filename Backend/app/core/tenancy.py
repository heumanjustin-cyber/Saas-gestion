"""Aislamiento entre empresas: cada usuario solo ve y toca lo de sus empresas.

Empresas «suyas» = las que posee (owner_user_id) y aquellas en las que es miembro activo.
Un objeto de otra empresa responde 404 (no se revela que existe).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.company import Company
from app.models.employee import Employee
from app.models.location import Location
from app.models.membership import CompanyMembership
from app.models.resource import Resource
from app.models.service import Service


def my_company_ids(db: Session, user) -> list[UUID]:
    owned = [row[0] for row in db.query(Company.id).filter(Company.owner_user_id == user.id).all()]
    member = [
        row[0]
        for row in db.query(CompanyMembership.company_id)
        .filter(CompanyMembership.user_id == user.id, CompanyMembership.status == "active")
        .all()
    ]
    return list(dict.fromkeys(owned + member))


def require_my_company(db: Session, user, company_id) -> Company:
    try:
        cid = UUID(str(company_id))
    except ValueError:
        raise HTTPException(status_code=422, detail="company_id no válido")
    company = db.get(Company, cid)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if cid not in my_company_ids(db, user):
        raise HTTPException(status_code=403, detail="Not allowed")
    return company


def get_mine_or_404(db: Session, model, obj_id, user, what: str):
    """Objeto con company_id que pertenece a una empresa del usuario; si no, 404."""
    obj = db.get(model, obj_id)
    if not obj or obj.company_id not in my_company_ids(db, user):
        raise HTTPException(status_code=404, detail=f"{what} no encontrado")
    return obj


_REFS = {
    "employee_id": (Employee, "El empleado"),
    "client_id": (Client, "El cliente"),
    "service_id": (Service, "El servicio"),
    "location_id": (Location, "El local"),
    "resource_id": (Resource, "El recurso"),
}


def ensure_same_company(db: Session, company_id, **refs) -> None:
    """Impide enlazar el empleado, cliente o servicio de otra empresa (p. ej. al crear una cita)."""
    for key, value in refs.items():
        if value is None:
            continue
        model, what = _REFS[key]
        obj = db.get(model, value)
        if not obj or obj.company_id != company_id:
            raise HTTPException(status_code=422, detail=f"{what} no pertenece a esta empresa")
