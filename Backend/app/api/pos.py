"""TPV de BUHOS: dispositivos, PIN del personal, caja, cobros, tickets y registros Verifactu."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, selectinload

from app.api.venue_admin import actor, get_or_create_venue
from app.core.company_access import Actor, create_pos_token, hash_secret, new_secret, pos_actor, resolve_actor
from app.db.dependencies import get_db
from app.models.company import Company
from app.models.employee import Employee
from app.models.fiscal import FiscalProfile, FiscalRecord
from app.models.order import Order
from app.models.pos import CashSession, Invoice, PosDevice, PosPairingCode, PosRegister, StaffPin
from app.schemas.hospitality import (
    CloseSessionIn,
    FullInvoiceIn,
    MovementIn,
    OpenSessionIn,
    OwnerSessionIn,
    PairIn,
    PairingCodeIn,
    PinLoginIn,
    RefundIn,
    RegisterIn,
    SaleIn,
    StaffPinIn,
    VoidIn,
)
from app.services import cash_service as cash
from app.services import invoice_service as inv
from app.services import order_service as osvc
from app.services import qr_service, ratelimit
from app.services import verifactu as vf
from app.services.menu_service import load_menu, menu_dict
from app.web.render import templates

admin = APIRouter(prefix="/my/venues/{company_id}/pos", tags=["TPV · gestión"])
router = APIRouter(prefix="/pos", tags=["TPV"])

PIN_ITERATIONS = 120_000
TYPE_LABELS = {"F2": "Factura simplificada", "F1": "Factura", "F3": "Factura (sustituye tickets)",
               "R5": "Factura rectificativa (devolución)"}


def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), PIN_ITERATIONS).hex()


def _register(db: Session, company_id: UUID, register_id: UUID) -> PosRegister:
    r = db.get(PosRegister, register_id)
    if not r or r.company_id != company_id or not r.is_active:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    return r


def register_dict(r: PosRegister) -> dict:
    return {"id": str(r.id), "name": r.name, "ticket_prefix": r.ticket_prefix, "invoice_prefix": r.invoice_prefix,
            "refund_prefix": r.refund_prefix, "is_active": r.is_active}


# ======================================================================= gestión (dueño/encargado)
@admin.get("/registers")
def list_registers(company_id: UUID, a: Actor = Depends(actor()), db: Session = Depends(get_db)):
    return [register_dict(r) for r in db.query(PosRegister).filter(PosRegister.company_id == company_id).all()]


@admin.post("/registers", status_code=201)
def create_register(company_id: UUID, data: RegisterIn, a: Actor = Depends(actor("billing.manage", True)),
                    db: Session = Depends(get_db)):
    prefixes = {data.ticket_prefix, data.invoice_prefix, data.refund_prefix}
    if len(prefixes) < 3:
        raise HTTPException(status_code=422, detail="Tickets, facturas y devoluciones necesitan series distintas.")
    used = {p for r in db.query(PosRegister).filter(PosRegister.company_id == company_id).all()
            for p in (r.ticket_prefix, r.invoice_prefix, r.refund_prefix)}
    if prefixes & used:
        raise HTTPException(status_code=409, detail="Esa serie ya la usa otra caja.")
    r = PosRegister(company_id=company_id, **data.model_dump())
    db.add(r)
    db.commit()
    return register_dict(r)


@admin.post("/pairing-codes", status_code=201)
def create_pairing_code(company_id: UUID, data: PairingCodeIn, a: Actor = Depends(actor("billing.manage", True)),
                        db: Session = Depends(get_db)):
    """Código de 8 caracteres para emparejar la tablet/TPV del local. Caduca en 15 minutos."""
    _register(db, company_id, data.register_id)
    code = "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(8))
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    db.add(PosPairingCode(company_id=company_id, register_id=data.register_id, code_hash=hash_secret(code),
                          device_name=data.device_name, expires_at=expires))
    db.commit()
    return {"code": code, "expires_at": expires.isoformat()}


@admin.get("/devices")
def list_devices(company_id: UUID, a: Actor = Depends(actor()), db: Session = Depends(get_db)):
    rows = db.query(PosDevice).filter(PosDevice.company_id == company_id).order_by(PosDevice.created_at).all()
    return [{"id": str(d.id), "name": d.name, "register_id": str(d.register_id), "is_active": d.is_active,
             "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None} for d in rows]


@admin.delete("/devices/{device_id}", status_code=204)
def revoke_device(company_id: UUID, device_id: UUID, a: Actor = Depends(actor("billing.manage", True)),
                  db: Session = Depends(get_db)):
    """Tablet perdida o cambiada: deja de funcionar al momento (sus sesiones también)."""
    d = db.get(PosDevice, device_id)
    if not d or d.company_id != company_id:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    d.is_active = False
    db.commit()


@admin.get("/staff")
def list_staff(company_id: UUID, a: Actor = Depends(actor()), db: Session = Depends(get_db)):
    pins = {p.employee_id: p for p in db.query(StaffPin).filter(StaffPin.company_id == company_id).all()}
    out = []
    for e in db.query(Employee).filter(Employee.company_id == company_id).order_by(Employee.first_name).all():
        p = pins.get(e.id)
        out.append({"employee_id": str(e.id), "name": e.public_name or e.first_name, "has_pin": bool(p and p.is_active),
                    "role": p.role if p else None})
    return out


@admin.put("/staff-pins")
def set_staff_pin(company_id: UUID, data: StaffPinIn, a: Actor = Depends(actor("employees.edit", True)),
                  db: Session = Depends(get_db)):
    e = db.get(Employee, data.employee_id)
    if not e or e.company_id != company_id:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    if len(set(data.pin)) == 1 or data.pin in ("1234", "12345", "123456", "4321"):
        raise HTTPException(status_code=422, detail="Ese PIN es demasiado fácil. Elige otro.")
    salt = secrets.token_hex(16)
    p = db.query(StaffPin).filter(StaffPin.employee_id == e.id).first()
    if not p:
        p = StaffPin(company_id=company_id, employee_id=e.id, pin_hash="", pin_salt=salt)
        db.add(p)
    p.pin_salt, p.pin_hash = salt, _hash_pin(data.pin, salt)
    p.role, p.is_active, p.failed_attempts, p.locked_until = data.role, True, 0, None
    db.commit()
    return {"employee_id": str(e.id), "role": p.role}


@admin.post("/owner-session")
def owner_session(company_id: UUID, data: OwnerSessionIn, authorization: str | None = Header(None),
                  db: Session = Depends(get_db)):
    """El dueño abre el TPV con su cuenta (sin PIN), p. ej. el día de la instalación."""
    a = resolve_actor(db, authorization, company_id, "billing.view")
    if a.user_id is None:
        raise HTTPException(status_code=403, detail="Inicia sesión con tu cuenta de BUHOS")
    r = _register(db, company_id, data.register_id)
    token = create_pos_token(company_id=company_id, register_id=r.id, label=a.label, role="owner", user_id=a.user_id)
    return {"access_token": token, "token_type": "bearer", "register": register_dict(r), "name": a.label, "role": "owner"}


@admin.get("/fiscal-records")
def fiscal_records(company_id: UUID, limit: int = Query(100, ge=1, le=1000), a: Actor = Depends(actor("billing.view")),
                   db: Session = Depends(get_db)):
    rows = (db.query(FiscalRecord).filter(FiscalRecord.company_id == company_id)
            .order_by(FiscalRecord.sequence.desc()).limit(limit).all())
    return [{"sequence": r.sequence, "type": r.record_type, "num_serie": r.num_serie, "fecha": r.fecha_expedicion,
             "tipo_factura": r.tipo_factura, "importe_total": r.importe_total, "hash": r.hash,
             "previous_hash": r.previous_hash, "generated_at": r.generated_at, "qr_url": r.qr_url,
             "submission_status": r.submission_status} for r in rows]


@admin.get("/fiscal-records/verify")
def verify_fiscal_chain(company_id: UUID, a: Actor = Depends(actor("billing.view")), db: Session = Depends(get_db)):
    """Recalcula toda la cadena de huellas: demuestra que ningún ticket se ha tocado."""
    records = inv.fiscal_records_for_verification(db, company_id)
    errors = vf.verify_chain(records)
    return {"records": len(records), "ok": not errors, "errors": errors[:50]}


@admin.get("/fiscal-records/{sequence}/xml")
def fiscal_record_xml(company_id: UUID, sequence: int, a: Actor = Depends(actor("billing.view")),
                      db: Session = Depends(get_db)):
    """XML de remisión del registro (pendiente de validar con el XSD de la AEAT antes de enviarlo)."""
    r = db.query(FiscalRecord).filter(FiscalRecord.company_id == company_id, FiscalRecord.sequence == sequence).first()
    if not r:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    profile = db.query(FiscalProfile).filter(FiscalProfile.company_id == company_id).first()
    sif = r.payload.get("sif")
    el = vf.build_registro_alta(r.payload, sif) if r.record_type == "alta" else vf.build_registro_anulacion(r.payload, sif)
    xml = vf.build_envelope([el], profile.nif, profile.legal_name)
    return Response(xml, media_type="application/xml")


# ======================================================================= dispositivo
def _device(db: Session, token: str | None) -> PosDevice:
    if not token:
        raise HTTPException(status_code=401, detail="Este dispositivo no está emparejado")
    d = db.query(PosDevice).filter(PosDevice.token_hash == hash_secret(token)).first()
    if not d or not d.is_active:
        raise HTTPException(status_code=401, detail="Este dispositivo no está emparejado")
    d.last_seen_at = datetime.now(timezone.utc)
    return d


@router.post("/pair")
def pair_device(data: PairIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.check("pos-pair", ratelimit.client_key(request), limit=10, window_seconds=600)
    now = datetime.now(timezone.utc)
    pc = db.query(PosPairingCode).filter(PosPairingCode.code_hash == hash_secret(data.code.strip().upper())).with_for_update().first()
    if not pc or pc.used_at or pc.expires_at < now:
        raise HTTPException(status_code=401, detail="Código no válido o caducado. Genera otro desde el panel.")
    pc.used_at = now
    token = new_secret(32)
    d = PosDevice(company_id=pc.company_id, register_id=pc.register_id, name=data.device_name or pc.device_name or "TPV",
                  token_hash=hash_secret(token), last_seen_at=now)
    db.add(d)
    db.commit()
    company = db.get(Company, pc.company_id)
    return {"device_token": token, "device_id": str(d.id), "company": {"id": str(company.id), "name": company.name,
            "slug": company.slug}, "register": register_dict(db.get(PosRegister, pc.register_id))}


@router.get("/staff")
def device_staff(x_device_token: str | None = Header(None), db: Session = Depends(get_db)):
    d = _device(db, x_device_token)
    rows = (db.query(StaffPin, Employee).join(Employee, Employee.id == StaffPin.employee_id)
            .filter(StaffPin.company_id == d.company_id, StaffPin.is_active.is_(True))
            .order_by(Employee.first_name).all())
    db.commit()
    return [{"employee_id": str(e.id), "name": e.public_name or e.first_name, "role": p.role} for p, e in rows]


@router.post("/login")
def pin_login(data: PinLoginIn, request: Request, x_device_token: str | None = Header(None),
              db: Session = Depends(get_db)):
    d = _device(db, x_device_token)
    ratelimit.check("pos-pin", f"{d.id}", limit=20, window_seconds=300)
    now = datetime.now(timezone.utc)
    p = (db.query(StaffPin).filter(StaffPin.employee_id == data.employee_id, StaffPin.company_id == d.company_id,
                                   StaffPin.is_active.is_(True)).with_for_update().first())
    if not p:
        raise HTTPException(status_code=401, detail="PIN incorrecto")
    if p.locked_until and p.locked_until > now:
        mins = int((p.locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(status_code=423, detail=f"Demasiados intentos. Espera {mins} min o avisa al encargado.")
    if not hmac.compare_digest(_hash_pin(data.pin, p.pin_salt), p.pin_hash):
        p.failed_attempts += 1
        if p.failed_attempts >= 5:
            p.locked_until, p.failed_attempts = now + timedelta(minutes=5), 0
        db.commit()
        raise HTTPException(status_code=401, detail="PIN incorrecto")
    p.failed_attempts, p.locked_until = 0, None
    e = db.get(Employee, p.employee_id)
    name = e.public_name or e.first_name
    token = create_pos_token(company_id=d.company_id, register_id=d.register_id, label=name, role=p.role,
                             device_id=d.id, employee_id=e.id)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "name": name, "role": p.role,
            "register": register_dict(db.get(PosRegister, d.register_id))}


# ======================================================================= operativa (token TPV)
def _ctx(db: Session, a: Actor) -> tuple[Company, PosRegister]:
    company = db.get(Company, a.company_id)
    return company, _register(db, a.company_id, a.register_id)


@router.get("/me")
def pos_me(a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    company, register = _ctx(db, a)
    venue = get_or_create_venue(db, company.id)
    fiscal = db.query(FiscalProfile).filter(FiscalProfile.company_id == company.id).first()
    session = cash.open_session_for(db, register.id)
    db.commit()
    return {"name": a.label, "role": a.role, "is_manager": a.is_manager,
            "company": {"id": str(company.id), "name": venue.display_name or company.name, "slug": company.slug},
            "register": register_dict(register), "session_open": bool(session),
            "fiscal": {"configured": bool(fiscal), "environment": fiscal.environment if fiscal else None,
                       "verifactu_enabled": fiscal.verifactu_enabled if fiscal else False},
            "payment_methods": ["cash", "card", "bizum"], "accent_color": venue.accent_color}


@router.get("/catalog")
def pos_catalog(a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    return menu_dict(load_menu(db, a.company_id), "es")


@router.get("/session")
def current_session(a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    _, register = _ctx(db, a)
    s = cash.open_session_for(db, register.id)
    return {"session": cash.summarize(db, s) if s else None}


@router.post("/session/open", status_code=201)
def open_cash(data: OpenSessionIn, a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    _, register = _ctx(db, a)
    s = cash.open_session(db, register, a.label, data.opening_float)
    db.commit()
    return {"session": cash.summarize(db, s)}


@router.post("/session/movements", status_code=201)
def cash_movement(data: MovementIn, a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    _, register = _ctx(db, a)
    s = cash.open_session_for(db, register.id)
    if not s:
        raise HTTPException(status_code=409, detail="La caja está cerrada.")
    cash.add_movement(db, s, data.kind, data.amount, data.reason, a.label)
    db.commit()
    return {"session": cash.summarize(db, s)}


@router.post("/session/close")
def close_cash(data: CloseSessionIn, a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    _, register = _ctx(db, a)
    s = cash.open_session_for(db, register.id)
    if not s:
        raise HTTPException(status_code=409, detail="La caja ya está cerrada.")
    cash.close_session(db, s, register, a.label, counted_cash=data.counted_cash, breakdown=data.breakdown,
                       notes=data.notes)
    db.commit()
    return {"session_id": str(s.id), "z_report": s.z_report}


@router.get("/sessions/{session_id}/z-report", response_class=HTMLResponse)
def z_report_html(session_id: UUID, request: Request, a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    s = db.get(CashSession, session_id)
    if not s or s.company_id != a.company_id:
        raise HTTPException(status_code=404, detail="Cierre no encontrado")
    company = db.get(Company, a.company_id)
    report = s.z_report or cash.summarize(db, s)
    fiscal = db.query(FiscalProfile).filter(FiscalProfile.company_id == company.id).first()
    tz = ZoneInfo(company.timezone or "Europe/Madrid")
    fmt = "%d/%m/%Y %H:%M"
    return templates.TemplateResponse(request, "z_report.html", {
        "r": report, "fiscal": fiscal, "name": company.name, "is_z": s.status == "closed",
        "opened": s.opened_at.astimezone(tz).strftime(fmt),
        "closed": s.closed_at.astimezone(tz).strftime(fmt) if s.closed_at else "",
        "printed": datetime.now(timezone.utc).astimezone(tz).strftime(fmt)})


@router.get("/orders/unpaid")
def unpaid_orders(a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    """Pedidos del QR (y de barra) pendientes de cobro: «Mesa 3 · 18,50 €»."""
    since = datetime.now(timezone.utc) - timedelta(hours=18)
    rows = (db.query(Order).options(selectinload(Order.lines))
            .filter(Order.company_id == a.company_id, Order.payment_status == "unpaid", Order.invoice_id.is_(None),
                    Order.status.notin_(("rejected", "cancelled")), Order.created_at >= since)
            .order_by(Order.created_at).all())
    return [osvc.order_staff_dict(o) for o in rows]


def describe(name: str, modifiers: list, removed: list) -> str:
    extras = [m["name"] for m in (modifiers or [])] + list(removed or [])
    return f"{name} ({', '.join(extras)})" if extras else name


def invoice_dict(db: Session, i: Invoice) -> dict:
    record = (db.query(FiscalRecord).filter(FiscalRecord.invoice_id == i.id, FiscalRecord.record_type == "alta")
              .first())
    rectified = db.get(Invoice, i.rectified_invoice_id) if i.rectified_invoice_id else None
    refunded = inv.refunded_quantities(db, i) if i.invoice_type == "F2" else {}
    orders = db.query(Order).filter(Order.invoice_id == i.id).all()
    return {
        "id": str(i.id), "full_number": i.full_number, "invoice_type": i.invoice_type,
        "type_label": TYPE_LABELS.get(i.invoice_type, i.invoice_type), "status": i.status,
        "issued_at": i.issued_at.isoformat(), "total": f"{i.total:.2f}", "tax_base": f"{i.tax_base:.2f}",
        "tax_total": f"{i.tax_total:.2f}", "tax_breakdown": i.tax_breakdown, "table_label": i.table_label,
        "channel": i.channel, "fulfillment": i.fulfillment, "created_by": i.created_by, "reason": i.reason,
        "customer": {"nif": i.customer_nif, "name": i.customer_name, "address": i.customer_address} if i.customer_nif else None,
        "rectified": rectified.full_number if rectified else None,
        "order_numbers": [o.display_number for o in orders],
        "lines": [{"id": str(line.id), "description": line.description, "quantity": f"{line.quantity.normalize():f}",
                   "unit_price": f"{line.unit_price:.2f}", "tax_rate": f"{line.tax_rate:.2f}",
                   "line_total": f"{line.line_total:.2f}",
                   "refundable": f"{(line.quantity - refunded.get(line.id, Decimal('0'))).normalize():f}"}
                  for line in i.lines],
        "payments": [{"method": p.method, "amount": f"{p.amount:.2f}",
                      "tendered": f"{p.tendered:.2f}" if p.tendered is not None else None,
                      "change": f"{p.change_given:.2f}" if p.change_given is not None else None,
                      "reference": p.reference} for p in i.payments],
        "change": f"{sum((p.change_given or 0) for p in i.payments):.2f}",
        "hash": record.hash if record else None, "qr_url": record.qr_url if record else None,
    }


@router.post("/sales", status_code=201)
def create_sale(data: SaleIn, a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    """Cobra pedidos del QR y/o lo que se marca en el TPV. Lo nuevo entra en cocina si send_to_kitchen."""
    company, register = _ctx(db, a)
    session = cash.open_session_for(db, register.id)
    if not session:
        raise HTTPException(status_code=409, detail="Abre la caja antes de cobrar.")
    venue = get_or_create_venue(db, company.id)
    sale_lines: list[inv.SaleLine] = []
    orders: list[Order] = []

    if data.order_ids:
        ids = list(dict.fromkeys(data.order_ids))
        orders = (db.query(Order).options(selectinload(Order.lines))
                  .filter(Order.id.in_(ids), Order.company_id == company.id).with_for_update().all())
        if len(orders) != len(ids):
            raise HTTPException(status_code=404, detail="Algún pedido no existe.")
        for o in orders:
            if o.invoice_id or o.payment_status == "paid":
                raise HTTPException(status_code=409, detail=f"El pedido {o.display_number} ya está cobrado.")
            if o.status in ("rejected", "cancelled"):
                raise HTTPException(status_code=409, detail=f"El pedido {o.display_number} está cancelado.")
            for line in o.lines:
                sale_lines.append(inv.SaleLine(description=describe(line.name, line.modifiers, line.removed),
                                               quantity=Decimal(line.quantity), unit_price=line.unit_price,
                                               tax_rate=line.tax_rate, product_id=line.product_id))
            if o.delivery_fee and o.delivery_fee > 0:
                sale_lines.append(inv.SaleLine(description="Envío a domicilio", quantity=Decimal(1),
                                               unit_price=o.delivery_fee, tax_rate=Decimal("10")))

    product_lines = [line for line in data.lines if line.product_id]
    if product_lines:
        priced = osvc.price_lines(db, company.id, product_lines, data.fulfillment, allow_unavailable=True)
        for pl in priced:
            sale_lines.append(inv.SaleLine(description=describe(pl.product.name, pl.modifiers, pl.removed),
                                           quantity=Decimal(pl.quantity), unit_price=pl.unit_price, tax_rate=pl.tax_rate,
                                           product_id=pl.product.id, category_name=pl.product.category.name))
        if data.send_to_kitchen:
            orders.append(osvc.create_pos_order(db, company, venue, product_lines, fulfillment=data.fulfillment,
                                                actor_label=a.label, table_label=data.table_label,
                                                customer_name=data.customer_name, note=data.note))
    for line in data.lines:
        if line.product_id:
            continue
        if not (line.description or "").strip() or line.unit_price is None:
            raise HTTPException(status_code=422, detail="Artículo libre: escribe qué es y su precio.")
        sale_lines.append(inv.SaleLine(description=line.description.strip(), quantity=Decimal(line.quantity),
                                       unit_price=line.unit_price, tax_rate=line.tax_rate))
    if not sale_lines:
        raise HTTPException(status_code=422, detail="El ticket está vacío.")

    online = [o for o in orders if o.channel != "pos"]
    invoice = inv.issue_invoice(
        db, company=company, register=register, session=session, actor_label=a.label, lines=sale_lines,
        payments=[inv.PaymentIn(method=p.method, amount=p.amount, tendered=p.tendered, reference=p.reference)
                  for p in data.payments],
        fulfillment=online[0].fulfillment if online else data.fulfillment,
        channel=online[0].channel if online else "pos",
        table_label=data.table_label or next((o.table_label for o in orders if o.table_label), None),
        orders=orders,
    )
    db.commit()
    return invoice_dict(db, invoice)


@router.get("/invoices")
def list_invoices(scope: str = Query("session", pattern="^(session|today|all)$"), q: str | None = Query(None, max_length=40),
                  a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    company, register = _ctx(db, a)
    query = db.query(Invoice).filter(Invoice.company_id == company.id)
    if scope == "session":
        s = cash.open_session_for(db, register.id)
        query = query.filter(Invoice.session_id == (s.id if s else None))
    elif scope == "today":
        tz = ZoneInfo(company.timezone or "Europe/Madrid")
        start = datetime.now(timezone.utc).astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(Invoice.issued_at >= start)
    if q:
        query = query.filter(Invoice.full_number.ilike(f"%{q.strip()}%"))
    rows = query.order_by(Invoice.issued_at.desc()).limit(200).all()
    return [{"id": str(i.id), "full_number": i.full_number, "invoice_type": i.invoice_type, "status": i.status,
             "issued_at": i.issued_at.isoformat(), "total": f"{i.total:.2f}", "table_label": i.table_label,
             "methods": sorted({p.method for p in i.payments})} for i in rows]


def _invoice(db: Session, a: Actor, invoice_id: UUID) -> Invoice:
    i = db.get(Invoice, invoice_id)
    if not i or i.company_id != a.company_id:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return i


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: UUID, a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    return invoice_dict(db, _invoice(db, a, invoice_id))


@router.get("/invoices/{invoice_id}/ticket", response_class=HTMLResponse)
def ticket_html(invoice_id: UUID, request: Request, copy: bool = Query(False), a: Actor = Depends(pos_actor),
                db: Session = Depends(get_db)):
    """Ticket de 80 mm con el «QR tributario». Se imprime desde el navegador del TPV."""
    i = _invoice(db, a, invoice_id)
    company = db.get(Company, a.company_id)
    venue = get_or_create_venue(db, company.id)
    fiscal = db.query(FiscalProfile).filter(FiscalProfile.company_id == company.id).first()
    data = invoice_dict(db, i)
    show_qr = bool(fiscal and data["qr_url"] and (fiscal.verifactu_enabled or fiscal.environment == "test"))
    tz = ZoneInfo(company.timezone or "Europe/Madrid")
    issued = i.issued_at.astimezone(tz)
    if copy:
        db.add(inv.AuditEvent(company_id=company.id, event_type="reimpresion", actor=a.label,
                              detail={"ticket": i.full_number}, created_at=datetime.now(timezone.utc)))
        db.commit()
    return templates.TemplateResponse(request, "ticket.html", {
        "i": data, "fiscal": fiscal, "venue": venue, "name": venue.display_name or company.name,
        "issued": issued.strftime("%d/%m/%Y %H:%M"), "copy": copy,
        "qr_svg": qr_service.svg(data["qr_url"], border=1) if show_qr else None,
        "verifactu": bool(fiscal and fiscal.verifactu_enabled),
        "test_mode": bool(fiscal and fiscal.environment == "test"),
    })


@router.post("/invoices/{invoice_id}/refund", status_code=201)
def refund(invoice_id: UUID, data: RefundIn, a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    if not a.is_manager:
        raise HTTPException(status_code=403, detail="Las devoluciones las hace un encargado.")
    company, register = _ctx(db, a)
    session = cash.open_session_for(db, register.id)
    if not session:
        raise HTTPException(status_code=409, detail="Abre la caja para hacer la devolución.")
    original = _invoice(db, a, invoice_id)
    items = [i.model_dump() for i in data.items] if data.items else None
    r = inv.refund_invoice(db, company=company, register=register, session=session, original=original,
                           actor_label=a.label, items=items, method=data.method, reason=data.reason)
    db.commit()
    return invoice_dict(db, r)


@router.post("/invoices/{invoice_id}/void")
def void(invoice_id: UUID, data: VoidIn, a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    if not a.is_manager:
        raise HTTPException(status_code=403, detail="Las anulaciones las hace un encargado.")
    company, register = _ctx(db, a)
    session = cash.open_session_for(db, register.id)
    i = inv.void_invoice(db, company=company, session=session, invoice=_invoice(db, a, invoice_id),
                         actor_label=a.label, reason=data.reason)
    db.commit()
    return invoice_dict(db, i)


@router.post("/invoices/full-invoice", status_code=201)
def full_invoice(data: FullInvoiceIn, a: Actor = Depends(pos_actor), db: Session = Depends(get_db)):
    """El cliente pide factura con su NIF: F3 que sustituye a sus tickets."""
    company, register = _ctx(db, a)
    tickets = [_invoice(db, a, i) for i in dict.fromkeys(data.invoice_ids)]
    f3 = inv.full_invoice_for_tickets(db, company=company, register=register, actor_label=a.label, tickets=tickets,
                                      customer={"nif": data.nif, "name": data.name.strip(), "address": data.address})
    db.commit()
    return invoice_dict(db, f3)
