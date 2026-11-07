"""Acceso a una empresa: dueño, miembro con permiso, o dispositivo TPV de esa empresa.

Hasta ahora solo el dueño (owner_user_id) podía operar. Un restaurante necesita
que camareros y cocina trabajen sin la contraseña del dueño: miembros con rol
(CompanyMembership) o personal con PIN desde un TPV emparejado.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import ALGORITHM, SECRET_KEY
from app.db.dependencies import get_db
from app.models.company import Company
from app.models.membership import CompanyMembership
from app.models.user import User

POS_TOKEN_HOURS = 14  # un turno largo de hostelería


@dataclass
class Actor:
    """Quién hace la acción. `label` va a los tickets y al registro de eventos."""

    company_id: UUID
    label: str
    user_id: UUID | None = None
    employee_id: UUID | None = None
    device_id: UUID | None = None
    register_id: UUID | None = None
    role: str = "owner"  # owner | member | manager | cashier

    @property
    def is_manager(self) -> bool:
        return self.role in ("owner", "manager", "member")


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_secret(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def create_pos_token(*, company_id: UUID, register_id: UUID, label: str, role: str,
                     device_id: UUID | None = None, employee_id: UUID | None = None,
                     user_id: UUID | None = None) -> str:
    payload = {
        "typ": "pos",
        "cid": str(company_id),
        "rid": str(register_id),
        "did": str(device_id) if device_id else None,
        "eid": str(employee_id) if employee_id else None,
        "uid": str(user_id) if user_id else None,
        "name": label,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=POS_TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Sesión caducada o no válida")


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta la cabecera Authorization: Bearer <token>")
    return authorization[len("Bearer "):].strip()


def _permissions(membership: CompanyMembership) -> set[str]:
    return {p.code for role in membership.roles for p in role.permissions}


def require_user_company(db: Session, company_id: UUID, user: User, permission: str | None = None) -> Company:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    if company.owner_user_id == user.id:
        return company
    membership = (
        db.query(CompanyMembership)
        .filter(CompanyMembership.company_id == company_id, CompanyMembership.user_id == user.id,
                CompanyMembership.status == "active")
        .first()
    )
    if not membership or (permission and permission not in _permissions(membership)):
        raise HTTPException(status_code=403, detail="No tienes permiso en esta empresa")
    return company


def resolve_actor(db: Session, authorization: str | None, company_id: UUID | None = None,
                  permission: str | None = None, manager_only: bool = False) -> Actor:
    """Acepta el token del dueño/miembro o el token del TPV."""
    payload = _decode(_bearer(authorization))
    if payload.get("typ") == "pos":
        cid = UUID(payload["cid"])
        if company_id and cid != company_id:
            raise HTTPException(status_code=403, detail="Este TPV es de otra empresa")
        if payload.get("did"):
            from app.models.pos import PosDevice  # import local: evita ciclos

            device = db.get(PosDevice, UUID(payload["did"]))
            if not device or not device.is_active:
                raise HTTPException(status_code=401, detail="Este dispositivo se ha desvinculado")
        actor = Actor(
            company_id=cid, label=payload.get("name") or "TPV",
            user_id=UUID(payload["uid"]) if payload.get("uid") else None,
            employee_id=UUID(payload["eid"]) if payload.get("eid") else None,
            device_id=UUID(payload["did"]) if payload.get("did") else None,
            register_id=UUID(payload["rid"]) if payload.get("rid") else None,
            role=payload.get("role") or "cashier",
        )
        if manager_only and not actor.is_manager:
            raise HTTPException(status_code=403, detail="Hace falta un encargado")
        return actor

    if company_id is None:
        raise HTTPException(status_code=401, detail="Inicia sesión en el TPV")
    try:
        user_id = UUID(str(payload.get("sub")))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Sesión no válida")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    company = require_user_company(db, company_id, user, permission)
    role = "owner" if company.owner_user_id == user.id else "member"
    return Actor(company_id=company_id, label=user.full_name or user.email, user_id=user.id, role=role)


def pos_actor(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> Actor:
    """Dependencia para /pos/*: exige token de TPV (de dispositivo o del dueño)."""
    actor = resolve_actor(db, authorization)
    if actor.register_id is None:
        raise HTTPException(status_code=401, detail="Inicia sesión en el TPV")
    return actor
