"""Pedidos: precio en servidor, validación, número del día, estado y textos para el cliente."""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.company import Company
from app.models.dining import QrCode
from app.models.menu import MenuProduct, ModifierGroup
from app.models.order import FINAL_STATUSES, STAFF_TRANSITIONS, Order, OrderLine
from app.models.venue import VenueProfile
from app.services import hours as H
from app.services.counters import next_value
from app.services.verifactu import money

ACTIVE_STATUSES = ("pending", "accepted", "preparing", "ready")

STATUS_LABELS = {
    "es": {"pending": "Recibido", "accepted": "Aceptado", "preparing": "En la cocina", "ready": "¡Listo!",
           "completed": "Entregado", "rejected": "No aceptado", "cancelled": "Cancelado"},
    "en": {"pending": "Received", "accepted": "Accepted", "preparing": "In the kitchen", "ready": "Ready!",
           "completed": "Delivered", "rejected": "Not accepted", "cancelled": "Cancelled"},
    "fr": {"pending": "Reçue", "accepted": "Acceptée", "preparing": "En cuisine", "ready": "Prête !",
           "completed": "Remise", "rejected": "Refusée", "cancelled": "Annulée"},
}


class OrderRejected(HTTPException):
    """Error que se enseña tal cual al cliente: {code, message}."""

    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(status_code=status_code, detail={"code": code, "message": message})


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def business_date(moment: datetime, tz_name: str, day_change_hour: int) -> date:
    local = moment.astimezone(ZoneInfo(tz_name or "Europe/Madrid"))
    if local.hour < (day_change_hour or 0):
        return (local - timedelta(days=1)).date()
    return local.date()


def normalize_phone(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    raw = value.strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        result = "+" + digits
    elif raw.startswith("00"):
        result = "+" + digits[2:]
    elif len(digits) == 9 and digits[0] in "6789":
        result = "+34" + digits
    else:
        result = "+" + digits
    if not 9 <= len(result) - 1 <= 15:
        raise OrderRejected("phone_invalid", "El teléfono no parece correcto. Escríbelo con todas sus cifras.")
    return result


def _clean(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    v = re.sub(r"\s+", " ", str(value)).strip()
    return v[:limit] or None


@dataclass
class LineIn:
    product_id: UUID
    quantity: int = 1
    option_ids: list[UUID] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    note: str | None = None


@dataclass
class PricedLine:
    product: MenuProduct
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    tax_rate: Decimal
    modifiers: list[dict]
    removed: list[str]
    note: str | None


def price_lines(db: Session, company_id: UUID, lines: list, fulfillment: str,
                allow_unavailable: bool = False) -> list[PricedLine]:
    """Calcula cada línea con los precios de la carta. Nunca usa precios del cliente."""
    if not lines:
        raise OrderRejected("empty", "El pedido está vacío.")
    ids = {UUID(str(line.product_id)) for line in lines}
    products = {
        p.id: p
        for p in db.query(MenuProduct)
        .options(selectinload(MenuProduct.modifier_groups).selectinload(ModifierGroup.options),
                 selectinload(MenuProduct.category))
        .filter(MenuProduct.company_id == company_id, MenuProduct.id.in_(ids))
        .all()
    }
    out: list[PricedLine] = []
    for line in lines:
        p = products.get(UUID(str(line.product_id)))
        if not p or not p.is_active or not p.category.is_active:
            raise OrderRejected("product_not_found", "Uno de los platos ya no está en la carta. Recarga la página.")
        if not p.is_available and not allow_unavailable:
            raise OrderRejected("sold_out", f"«{p.name}» se ha agotado por hoy.")
        qty = int(line.quantity or 1)
        if not 1 <= qty <= 50:
            raise OrderRejected("quantity", "La cantidad de cada plato va de 1 a 50.")
        remaining = list(dict.fromkeys(UUID(str(o)) for o in (line.option_ids or [])))
        chosen: list[dict] = []
        for g in p.modifier_groups:
            selected = [o for o in g.options if o.id in remaining]
            for o in selected:
                remaining.remove(o.id)
            if len(selected) < g.min_select:
                raise OrderRejected("missing_choice", f"Elige {g.name.lower()} para «{p.name}».")
            if g.max_select > 0 and len(selected) > g.max_select:
                raise OrderRejected("too_many_choices",
                                    f"En «{p.name}» puedes elegir como máximo {g.max_select} de {g.name.lower()}.")
            for o in selected:
                if not o.is_available and not allow_unavailable:
                    raise OrderRejected("option_sold_out", f"«{o.name}» se ha agotado por hoy.")
                chosen.append({"group": g.name, "name": o.name, "price_delta": f"{money(o.price_delta):.2f}",
                               "option_id": str(o.id)})
        if remaining:
            raise OrderRejected("invalid_option", f"Una de las opciones elegidas no vale para «{p.name}».")
        allowed = list(p.removable_ingredients or [])
        removed = list(dict.fromkeys(line.removed or []))
        for r in removed:
            if r not in allowed:
                raise OrderRejected("invalid_removal", f"No se puede quitar «{r}» de «{p.name}».")
        unit = money(Decimal(p.price) + sum((Decimal(m["price_delta"]) for m in chosen), Decimal("0")))
        rate = p.tax_rate
        if fulfillment in ("takeaway", "delivery") and p.takeaway_tax_rate is not None:
            rate = p.takeaway_tax_rate
        out.append(PricedLine(p, qty, unit, money(unit * qty), Decimal(rate), chosen, removed,
                              _clean(getattr(line, "note", None), 140)))
    return out


def _attach_lines(order: Order, priced: list[PricedLine]) -> None:
    for i, pl in enumerate(priced):
        order.lines.append(OrderLine(
            product_id=pl.product.id, position=i, name=pl.product.name, quantity=pl.quantity,
            unit_price=pl.unit_price, line_total=pl.line_total, tax_rate=pl.tax_rate,
            modifiers=pl.modifiers, removed=pl.removed, note=pl.note, kitchen_station=pl.product.kitchen_station,
        ))


def estimate_ready(db: Session, company_id: UUID, venue: VenueProfile, now: datetime) -> datetime:
    """Tiempo de preparación + 2 min por pedido que ya hay en cocina (hasta 10)."""
    in_kitchen = (
        db.query(Order.id)
        .filter(Order.company_id == company_id, Order.status.in_(("pending", "accepted", "preparing")))
        .count()
    )
    return now + timedelta(minutes=(venue.prep_time_minutes or 15) + 2 * min(in_kitchen, 10))


def create_public_order(db: Session, company: Company, venue: VenueProfile, data, qr: QrCode | None,
                        now: datetime | None = None) -> tuple[Order, bool]:
    """Crea el pedido que llega desde el móvil. Devuelve (pedido, creado). Reintentos → mismo pedido."""
    now = now or now_utc()
    existing = db.query(Order).filter(Order.company_id == company.id, Order.client_ref == data.client_ref).first()
    if existing:
        return existing, False

    tz = company.timezone or "Europe/Madrid"
    lang = data.language if data.language in STATUS_LABELS else "es"
    if not venue.is_published or not venue.ordering_enabled:
        raise OrderRejected("ordering_disabled", "Este local no acepta pedidos online ahora mismo.", 409)
    if venue.ordering_paused_until and venue.ordering_paused_until > now:
        mins = int((venue.ordering_paused_until - now).total_seconds() // 60) + 1
        raise OrderRejected("paused", f"La cocina va a tope. Vuelve a intentarlo en {mins} min o pide en la barra.", 409)

    f = data.fulfillment
    enabled = {"dine_in": venue.dine_in_enabled, "takeaway": venue.takeaway_enabled,
               "delivery": venue.delivery_enabled}
    if not enabled.get(f):
        raise OrderRejected("fulfillment_disabled", "Esa forma de entrega no está disponible.")

    table_id = table_label = None
    if f == "dine_in":
        if not qr or not qr.table_id or not qr.table or not qr.table.is_active:
            raise OrderRejected("table_required", "Para pedir a la mesa, escanea el QR que hay en tu mesa.")
        table_id, table_label = qr.table_id, qr.table.name

    name = _clean(data.customer_name, 120)
    phone = normalize_phone(data.customer_phone)
    address = _clean(data.delivery_address, 255)
    if f == "delivery":
        if not phone:
            raise OrderRejected("phone_required", "Para llevártelo a casa necesitamos tu teléfono.")
        if not address:
            raise OrderRejected("address_required", "Escribe la dirección completa: calle, número, piso y puerta.")
    if f == "takeaway" and not name:
        raise OrderRejected("name_required", "Dinos tu nombre para avisarte cuando esté listo.")

    scheduled = data.scheduled_for
    if scheduled:
        if not venue.accepts_scheduled_orders:
            raise OrderRejected("no_scheduling", "Este local no acepta pedidos programados.")
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=ZoneInfo(tz))
        if scheduled < now + timedelta(minutes=(venue.prep_time_minutes or 15) - 1):
            raise OrderRejected("too_soon", f"Programa el pedido con al menos {venue.prep_time_minutes} min de margen.")
        if scheduled > now + timedelta(days=2):
            raise OrderRejected("too_far", "Solo se puede programar con hasta 2 días de antelación.")
        if not H.open_status(venue.opening_hours, venue.closures, scheduled, tz).is_open:
            raise OrderRejected("closed_at_time", "A esa hora el local está cerrado. Elige otra hora.")
    else:
        st = H.open_status(venue.opening_hours, venue.closures, now, tz)
        if not st.is_open:
            raise OrderRejected("closed", f"Ahora mismo estamos cerrados ({H.status_text(st, now, tz, lang)}). "
                                          "Puedes programar tu pedido para cuando abramos.", 409)

    priced = price_lines(db, company.id, data.lines, f)
    subtotal = money(sum((pl.line_total for pl in priced), Decimal("0")))
    fee = Decimal("0.00")
    if f == "delivery":
        if subtotal < money(venue.delivery_min_order):
            raise OrderRejected("min_order", f"El pedido mínimo a domicilio es de {money(venue.delivery_min_order):.2f} €.".replace(".", ","))
        fee = money(venue.delivery_fee)

    methods = list(venue.payment_methods or [])
    if data.payment_method and methods and data.payment_method not in methods:
        raise OrderRejected("payment_method", "Esa forma de pago no está disponible en este local.")

    bdate = business_date(scheduled or now, tz, venue.day_change_hour)
    order = Order(
        company_id=company.id, business_date=bdate, number=next_value(db, company.id, f"order:{bdate.isoformat()}"),
        public_token=secrets.token_urlsafe(16), client_ref=data.client_ref,
        channel="qr" if qr else "web", fulfillment=f, table_id=table_id, table_label=table_label,
        qr_id=qr.id if qr else None, customer_name=name, customer_phone=phone, delivery_address=address,
        customer_note=_clean(data.customer_note, 280), language=lang, scheduled_for=scheduled,
        status="pending", subtotal=subtotal, delivery_fee=fee, total=money(subtotal + fee),
        payment_method=data.payment_method, payment_status="unpaid",
        estimated_ready_at=scheduled or estimate_ready(db, company.id, venue, now),
    )
    _attach_lines(order, priced)
    db.add(order)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        again = db.query(Order).filter(Order.company_id == company.id, Order.client_ref == data.client_ref).first()
        if again:
            return again, False
        raise
    db.refresh(order)
    return order, True


def create_pos_order(db: Session, company: Company, venue: VenueProfile | None, lines: list, *,
                     fulfillment: str, actor_label: str, table_label: str | None = None,
                     customer_name: str | None = None, note: str | None = None,
                     now: datetime | None = None) -> Order:
    """Pedido tomado en barra: entra directo en cocina (ya aceptado)."""
    now = now or now_utc()
    tz = company.timezone or "Europe/Madrid"
    priced = price_lines(db, company.id, lines, fulfillment, allow_unavailable=True)
    bdate = business_date(now, tz, venue.day_change_hour if venue else 6)
    subtotal = money(sum((pl.line_total for pl in priced), Decimal("0")))
    order = Order(
        company_id=company.id, business_date=bdate, number=next_value(db, company.id, f"order:{bdate.isoformat()}"),
        public_token=secrets.token_urlsafe(16), channel="pos", fulfillment=fulfillment,
        table_label=_clean(table_label, 60), customer_name=_clean(customer_name, 120), customer_note=_clean(note, 280),
        status="accepted", accepted_at=now, subtotal=subtotal, delivery_fee=Decimal("0.00"), total=subtotal,
        payment_status="unpaid", status_reason=f"Tomado por {actor_label}",
        estimated_ready_at=now + timedelta(minutes=(venue.prep_time_minutes if venue else 15)),
    )
    _attach_lines(order, priced)
    db.add(order)
    db.flush()
    return order


def staff_transition(order: Order, new_status: str, *, reason: str | None = None, eta_minutes: int | None = None,
                     prep_minutes: int = 15, now: datetime | None = None) -> None:
    now = now or now_utc()
    if new_status not in STAFF_TRANSITIONS.get(order.status, set()):
        raise HTTPException(status_code=409, detail=f"No se puede pasar de «{order.status}» a «{new_status}»")
    if new_status in ("accepted", "preparing", "ready") and order.accepted_at is None:
        order.accepted_at = now
        if order.scheduled_for is None:
            order.estimated_ready_at = now + timedelta(minutes=eta_minutes or prep_minutes)
    if new_status == "accepted" and eta_minutes:
        order.estimated_ready_at = now + timedelta(minutes=eta_minutes)
    if new_status == "ready":
        order.ready_at = now
    if new_status == "completed":
        order.completed_at = now
    if new_status in ("rejected", "cancelled"):
        order.status_reason = _clean(reason, 255) or order.status_reason
    order.status = new_status


def customer_cancel(order: Order) -> None:
    if order.status != "pending":
        raise HTTPException(status_code=409, detail="El pedido ya está en cocina: llama al local para cambiarlo.")
    order.status = "cancelled"
    order.status_reason = "Cancelado por el cliente"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def order_public_dict(order: Order, lang: str = "es") -> dict:
    labels = STATUS_LABELS.get(lang, STATUS_LABELS["es"])
    return {
        "token": order.public_token,
        "number": order.display_number,
        "status": order.status,
        "status_label": labels.get(order.status, order.status),
        "status_reason": order.status_reason if order.status in ("rejected", "cancelled") else None,
        "fulfillment": order.fulfillment,
        "table": order.table_label,
        "customer_name": order.customer_name,
        "scheduled_for": _iso(order.scheduled_for),
        "estimated_ready_at": _iso(order.estimated_ready_at),
        "created_at": _iso(order.created_at),
        "updated_at": _iso(order.updated_at),
        "subtotal": f"{order.subtotal:.2f}",
        "delivery_fee": f"{order.delivery_fee:.2f}",
        "total": f"{order.total:.2f}",
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "can_cancel": order.status == "pending",
        "lines": [
            {"name": line.name, "quantity": line.quantity, "unit_price": f"{line.unit_price:.2f}",
             "line_total": f"{line.line_total:.2f}", "modifiers": line.modifiers, "removed": line.removed,
             "note": line.note}
            for line in order.lines
        ],
    }


def order_staff_dict(order: Order) -> dict:
    d = order_public_dict(order, "es")
    d.update({
        "id": str(order.id),
        "channel": order.channel,
        "customer_phone": order.customer_phone,
        "delivery_address": order.delivery_address,
        "customer_note": order.customer_note,
        "status_reason": order.status_reason,
        "language": order.language,
        "invoice_id": str(order.invoice_id) if order.invoice_id else None,
        "accepted_at": _iso(order.accepted_at),
        "ready_at": _iso(order.ready_at),
        "completed_at": _iso(order.completed_at),
        "business_date": order.business_date.isoformat(),
        "is_final": order.status in FINAL_STATUSES,
        "lines": [
            {"product_id": str(line.product_id) if line.product_id else None, "name": line.name,
             "quantity": line.quantity, "unit_price": f"{line.unit_price:.2f}", "line_total": f"{line.line_total:.2f}",
             "tax_rate": f"{line.tax_rate:.2f}", "modifiers": line.modifiers, "removed": line.removed,
             "note": line.note, "kitchen_station": line.kitchen_station}
            for line in order.lines
        ],
    })
    return d
