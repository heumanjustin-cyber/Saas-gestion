"""Gestión del local: perfil, mesas, QR dinámicos, datos fiscales, opiniones y analítica.

Acepta el token del dueño/miembro o el de un TPV de la misma empresa.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.company_access import Actor, resolve_actor
from app.db.dependencies import get_db
from app.models.company import Company
from app.models.dining import DiningTable, QrCode, QrScan
from app.models.fiscal import FiscalProfile
from app.models.order import Order
from app.models.venue import VenueFeedback, VenueProfile
from app.schemas.hospitality import (
    FiscalProfileIn,
    OfferIn,
    PauseIn,
    QrIn,
    QrPatch,
    TableIn,
    TablesBulkIn,
    VenueProfileIn,
)
from app.services import nif as nif_check
from app.services import qr_service
from app.web.render import public_base, templates

router = APIRouter(prefix="/my/venues/{company_id}", tags=["Hostelería · gestión"])


def actor(permission: str | None = None, manager_only: bool = False):
    def dep(company_id: UUID, authorization: str | None = Header(None), db: Session = Depends(get_db)) -> Actor:
        return resolve_actor(db, authorization, company_id, permission, manager_only)
    return dep


def get_or_create_venue(db: Session, company_id: UUID) -> VenueProfile:
    venue = db.query(VenueProfile).filter(VenueProfile.company_id == company_id).first()
    if not venue:
        venue = VenueProfile(company_id=company_id)
        db.add(venue)
        db.flush()
    return venue


def venue_admin_dict(v: VenueProfile) -> dict:
    cols = [c.key for c in VenueProfile.__table__.columns]
    out = {}
    for k in cols:
        val = getattr(v, k)
        if isinstance(val, Decimal):
            val = f"{val}"
        elif isinstance(val, datetime):
            val = val.isoformat()
        elif isinstance(val, UUID):
            val = str(val)
        out[k] = val
    return out


# ------------------------------------------------------------------ perfil
@router.get("/profile")
def get_profile(company_id: UUID, a: Actor = Depends(actor()), db: Session = Depends(get_db)):
    venue = get_or_create_venue(db, company_id)
    db.commit()
    return venue_admin_dict(venue)


@router.patch("/profile")
def update_profile(company_id: UUID, data: VenueProfileIn, a: Actor = Depends(actor("company.edit", True)),
                   db: Session = Depends(get_db)):
    venue = get_or_create_venue(db, company_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(venue, k, v)
    db.commit()
    db.refresh(venue)
    return venue_admin_dict(venue)


@router.post("/pause")
def pause_orders(company_id: UUID, data: PauseIn, a: Actor = Depends(actor("orders.manage")),
                 db: Session = Depends(get_db)):
    """La cocina va a tope: deja de aceptar pedidos online N minutos (0 = reanudar)."""
    venue = get_or_create_venue(db, company_id)
    venue.ordering_paused_until = (datetime.now(timezone.utc) + timedelta(minutes=data.minutes)) if data.minutes else None
    db.commit()
    return {"ordering_paused_until": venue.ordering_paused_until.isoformat() if venue.ordering_paused_until else None}


@router.post("/offer")
def set_offer(company_id: UUID, data: OfferIn, a: Actor = Depends(actor("company.edit", True)),
              db: Session = Depends(get_db)):
    """Oferta del día: sale arriba de la carta y caduca sola."""
    venue = get_or_create_venue(db, company_id)
    venue.offer_text = (data.text or "").strip() or None
    venue.offer_expires_at = (datetime.now(timezone.utc) + timedelta(hours=data.hours)) if data.text and data.hours else None
    db.commit()
    return {"offer_text": venue.offer_text,
            "offer_expires_at": venue.offer_expires_at.isoformat() if venue.offer_expires_at else None}


# ------------------------------------------------------------------ datos fiscales
@router.get("/fiscal")
def get_fiscal(company_id: UUID, a: Actor = Depends(actor("billing.view")), db: Session = Depends(get_db)):
    p = db.query(FiscalProfile).filter(FiscalProfile.company_id == company_id).first()
    if not p:
        return {"configured": False}
    return {"configured": True, "nif": p.nif, "legal_name": p.legal_name, "address": p.address,
            "postal_code": p.postal_code, "city": p.city, "province": p.province,
            "verifactu_enabled": p.verifactu_enabled, "environment": p.environment, "ticket_footer": p.ticket_footer}


@router.put("/fiscal")
def put_fiscal(company_id: UUID, data: FiscalProfileIn, a: Actor = Depends(actor("billing.manage", True)),
               db: Session = Depends(get_db)):
    nif = nif_check.normalize(data.nif)
    if not nif_check.is_valid_nif(nif):
        raise HTTPException(status_code=422, detail="El NIF no es válido (revisa la letra o el dígito de control).")
    other = db.query(FiscalProfile).filter(FiscalProfile.nif == nif, FiscalProfile.company_id != company_id).first()
    if other:
        # Con dos empresas y el mismo NIF saldrían dos «T1-2026-000001» para Hacienda.
        raise HTTPException(status_code=409, detail="Ese NIF ya factura en otra empresa de BUHOSS. "
                                                    "Usa una sola empresa con varias cajas (cada una con su serie).")
    p = db.query(FiscalProfile).filter(FiscalProfile.company_id == company_id).first()
    if p and p.nif != nif:
        from app.models.fiscal import FiscalRecord

        if db.query(FiscalRecord.id).filter(FiscalRecord.company_id == company_id).first():
            raise HTTPException(status_code=409, detail="Ya hay facturas emitidas con otro NIF: un cambio de titular es otra empresa.")
    if not p:
        p = FiscalProfile(company_id=company_id, nif=nif, legal_name=data.legal_name)
        db.add(p)
    values = data.model_dump()
    values["nif"] = nif
    for k, v in values.items():
        setattr(p, k, v)
    db.commit()
    return {"configured": True, "nif": p.nif, "legal_name": p.legal_name, "environment": p.environment,
            "verifactu_enabled": p.verifactu_enabled}


# ------------------------------------------------------------------ mesas
def table_dict(t: DiningTable, qr: QrCode | None, base: str) -> dict:
    return {"id": str(t.id), "name": t.name, "zone": t.zone, "seats": t.seats, "position": t.position,
            "is_active": t.is_active,
            "qr": qr_dict(qr, base) if qr else None}


def qr_dict(q: QrCode, base: str) -> dict:
    return {"id": str(q.id), "code": q.code, "kind": q.kind, "label": q.label,
            "table_id": str(q.table_id) if q.table_id else None, "target": q.target, "target_url": q.target_url,
            "campaign": q.campaign, "is_active": q.is_active, "scan_count": q.scan_count,
            "last_scan_at": q.last_scan_at.isoformat() if q.last_scan_at else None,
            "url": f"{base}/q/{q.code}", "svg_url": f"{base}/qr/{q.code}.svg"}


@router.get("/tables")
def list_tables(company_id: UUID, request: Request, a: Actor = Depends(actor()), db: Session = Depends(get_db)):
    base = public_base(request)
    tables = db.query(DiningTable).filter(DiningTable.company_id == company_id).order_by(DiningTable.position, DiningTable.name).all()
    qrs = {q.table_id: q for q in db.query(QrCode).filter(QrCode.company_id == company_id, QrCode.table_id.isnot(None)).all()}
    return [table_dict(t, qrs.get(t.id), base) for t in tables]


def _create_table(db: Session, company_id: UUID, data: TableIn) -> tuple[DiningTable, QrCode]:
    t = DiningTable(company_id=company_id, **data.model_dump())
    db.add(t)
    db.flush()
    q = QrCode(company_id=company_id, code=qr_service.new_code(db), kind="table", label=t.name, table_id=t.id)
    db.add(q)
    db.flush()
    return t, q


@router.post("/tables", status_code=201)
def create_table(company_id: UUID, data: TableIn, request: Request, a: Actor = Depends(actor("company.edit", True)),
                 db: Session = Depends(get_db)):
    t, q = _create_table(db, company_id, data)
    db.commit()
    return table_dict(t, q, public_base(request))


@router.post("/tables/bulk", status_code=201)
def create_tables_bulk(company_id: UUID, data: TablesBulkIn, request: Request,
                       a: Actor = Depends(actor("company.edit", True)), db: Session = Depends(get_db)):
    out = []
    for i in range(data.count):
        n = data.start_at + i
        t, q = _create_table(db, company_id, TableIn(name=f"{data.prefix} {n}", zone=data.zone, position=n))
        out.append((t, q))
    db.commit()
    base = public_base(request)
    return [table_dict(t, q, base) for t, q in out]


@router.patch("/tables/{table_id}")
def update_table(company_id: UUID, table_id: UUID, data: TableIn, request: Request,
                 a: Actor = Depends(actor("company.edit", True)), db: Session = Depends(get_db)):
    t = db.get(DiningTable, table_id)
    if not t or t.company_id != company_id:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    q = db.query(QrCode).filter(QrCode.table_id == t.id).first()
    if q:
        q.label = t.name
    db.commit()
    return table_dict(t, q, public_base(request))


@router.post("/tables/{table_id}/rotate-qr")
def rotate_table_qr(company_id: UUID, table_id: UUID, request: Request,
                    a: Actor = Depends(actor("company.edit", True)), db: Session = Depends(get_db)):
    """Nuevo código para la mesa (p. ej. alguien se llevó foto del QR y pide desde casa). El viejo deja de valer."""
    t = db.get(DiningTable, table_id)
    if not t or t.company_id != company_id:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    old = db.query(QrCode).filter(QrCode.table_id == t.id).first()
    if old:
        old.is_active = False
        old.table_id = None
        old.label = f"{t.name} (sustituido)"
    q = QrCode(company_id=company_id, code=qr_service.new_code(db), kind="table", label=t.name, table_id=t.id)
    db.add(q)
    db.commit()
    return table_dict(t, q, public_base(request))


# ------------------------------------------------------------------ QR
@router.get("/qr-codes")
def list_qr(company_id: UUID, request: Request, a: Actor = Depends(actor()), db: Session = Depends(get_db)):
    base = public_base(request)
    rows = db.query(QrCode).filter(QrCode.company_id == company_id).order_by(QrCode.kind, QrCode.label).all()
    return [qr_dict(q, base) for q in rows]


@router.post("/qr-codes", status_code=201)
def create_qr(company_id: UUID, data: QrIn, request: Request, a: Actor = Depends(actor("company.edit", True)),
              db: Session = Depends(get_db)):
    if data.target == "url" and not data.target_url:
        raise HTTPException(status_code=422, detail="Con destino «url» hace falta target_url (https://...).")
    if data.table_id:
        t = db.get(DiningTable, data.table_id)
        if not t or t.company_id != company_id:
            raise HTTPException(status_code=404, detail="Mesa no encontrada")
    q = QrCode(company_id=company_id, code=qr_service.new_code(db), **data.model_dump())
    db.add(q)
    db.commit()
    return qr_dict(q, public_base(request))


@router.patch("/qr-codes/{qr_id}")
def update_qr(company_id: UUID, qr_id: UUID, data: QrPatch, request: Request,
              a: Actor = Depends(actor("company.edit", True)), db: Session = Depends(get_db)):
    q = db.get(QrCode, qr_id)
    if not q or q.company_id != company_id:
        raise HTTPException(status_code=404, detail="QR no encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(q, k, v)
    if q.target == "url" and not q.target_url:
        raise HTTPException(status_code=422, detail="Con destino «url» hace falta target_url (https://...).")
    db.commit()
    return qr_dict(q, public_base(request))


@router.get("/qr-sheet", response_class=HTMLResponse)
def qr_sheet(company_id: UUID, request: Request, kind: str | None = Query(None),
             a: Actor = Depends(actor()), db: Session = Depends(get_db)):
    """Hoja A4 lista para imprimir: una pegatina por mesa/pieza con su QR y el nombre."""
    company = db.get(Company, company_id)
    venue = get_or_create_venue(db, company_id)
    q = db.query(QrCode).filter(QrCode.company_id == company_id, QrCode.is_active.is_(True))
    if kind:
        q = q.filter(QrCode.kind == kind)
    base = public_base(request)
    stickers = [{"label": c.label or c.kind, "code": c.code, "url": f"{base}/q/{c.code}",
                 "svg": qr_service.svg(f"{base}/q/{c.code}", dark=venue.brand_color or "#111111")}
                for c in q.order_by(QrCode.kind, QrCode.label).all()]
    db.commit()
    return templates.TemplateResponse(request, "qr_sheet.html", {
        "name": venue.display_name or company.name, "accent": venue.accent_color, "stickers": stickers})


# ------------------------------------------------------------------ opiniones y analítica
@router.get("/feedback")
def list_feedback(company_id: UUID, a: Actor = Depends(actor("clients.view")), db: Session = Depends(get_db)):
    rows = (db.query(VenueFeedback).filter(VenueFeedback.company_id == company_id)
            .order_by(VenueFeedback.created_at.desc()).limit(200).all())
    return [{"id": str(f.id), "message": f.message, "contact": f.contact, "status": f.status,
             "order_id": str(f.order_id) if f.order_id else None, "created_at": f.created_at.isoformat()} for f in rows]


@router.get("/analytics")
def analytics(company_id: UUID, days: int = Query(30, ge=1, le=365), a: Actor = Depends(actor("analytics.view")),
              db: Session = Depends(get_db)):
    """Qué pieza trae pedidos: escaneos y pedidos por QR, y pedidos por canal y entrega."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    scans = dict(db.query(QrScan.qr_id, func.count(QrScan.id))
                 .filter(QrScan.company_id == company_id, QrScan.scanned_at >= since).group_by(QrScan.qr_id).all())
    orders_by_qr = dict(db.query(Order.qr_id, func.count(Order.id))
                        .filter(Order.company_id == company_id, Order.created_at >= since, Order.qr_id.isnot(None),
                                Order.status.notin_(("rejected", "cancelled"))).group_by(Order.qr_id).all())
    revenue_by_qr = dict(db.query(Order.qr_id, func.coalesce(func.sum(Order.total), 0))
                         .filter(Order.company_id == company_id, Order.created_at >= since, Order.qr_id.isnot(None),
                                 Order.status.notin_(("rejected", "cancelled"))).group_by(Order.qr_id).all())
    pieces = []
    for q in db.query(QrCode).filter(QrCode.company_id == company_id).all():
        s, o = scans.get(q.id, 0), orders_by_qr.get(q.id, 0)
        pieces.append({"code": q.code, "label": q.label, "kind": q.kind, "scans": s, "orders": o,
                       "conversion": round(o / s, 3) if s else None, "revenue": f"{Decimal(revenue_by_qr.get(q.id, 0)):.2f}"})
    pieces.sort(key=lambda p: (p["orders"], p["scans"]), reverse=True)
    by_channel = [{"channel": c, "fulfillment": f, "orders": n, "total": f"{Decimal(t):.2f}"}
                  for c, f, n, t in db.query(Order.channel, Order.fulfillment, func.count(Order.id),
                                             func.coalesce(func.sum(Order.total), 0))
                  .filter(Order.company_id == company_id, Order.created_at >= since,
                          Order.status.notin_(("rejected", "cancelled")))
                  .group_by(Order.channel, Order.fulfillment).all()]
    return {"days": days, "pieces": pieces, "orders": by_channel}
