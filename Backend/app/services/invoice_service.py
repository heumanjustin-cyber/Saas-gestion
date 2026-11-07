"""Emisión de tickets y facturas con su registro fiscal encadenado (Verifactu).

Reglas que aplica:
- Numeración correlativa por serie y año (T1-2026-000001), sin huecos.
- Tickets (F2) hasta 3.000 € en hostelería (RD 1619/2012, art. 4); por encima, factura completa.
- Devoluciones como rectificativa R5 en su propia serie, nunca editando el ticket.
- Factura completa a petición del cliente como F3 que sustituye a los tickets.
- Cada alta/anulación se encadena con la huella del registro anterior.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core import config
from app.models.company import Company
from app.models.fiscal import FiscalChainHead, FiscalProfile, FiscalRecord
from app.models.order import Order
from app.models.pos import PAYMENT_METHODS, AuditEvent, CashSession, Invoice, InvoiceLine, Payment, PosRegister
from app.services import nif as nif_check
from app.services import verifactu as vf
from app.services.counters import next_value
from app.services.verifactu import money

ZERO = Decimal("0.00")
SIMPLIFIED_LIMIT = Decimal("3000.00")


@dataclass
class SaleLine:
    description: str
    quantity: Decimal
    unit_price: Decimal  # IVA incluido
    tax_rate: Decimal
    product_id: UUID | None = None
    category_name: str | None = None
    source_line_id: UUID | None = None


@dataclass
class PaymentIn:
    method: str
    amount: Decimal
    tendered: Decimal | None = None
    reference: str | None = None


def tax_breakdown(lines: list[tuple[Decimal, Decimal]]) -> tuple[list[dict], Decimal, Decimal, Decimal]:
    """lines: [(tipo, total con IVA)]. Calcula base y cuota por tipo (no por línea: sin descuadres)."""
    by_rate: dict[Decimal, Decimal] = {}
    for rate, total in lines:
        by_rate[Decimal(rate)] = by_rate.get(Decimal(rate), ZERO) + money(total)
    rows, base_sum, tax_sum, total_sum = [], ZERO, ZERO, ZERO
    for rate, total in sorted(by_rate.items()):
        base = money(total / (Decimal("1") + rate / Decimal("100")))
        tax = money(total - base)
        rows.append({"rate": f"{rate:.2f}", "base": f"{base:.2f}", "tax": f"{tax:.2f}", "total": f"{total:.2f}"})
        base_sum, tax_sum, total_sum = base_sum + base, tax_sum + tax, total_sum + total
    return rows, money(base_sum), money(tax_sum), money(total_sum)


def _audit(db: Session, company_id: UUID, event_type: str, actor: str, detail: dict) -> None:
    db.add(AuditEvent(company_id=company_id, event_type=event_type, actor=actor, detail=detail,
                      created_at=datetime.now(timezone.utc)))


def get_fiscal_profile(db: Session, company_id: UUID) -> FiscalProfile:
    profile = db.query(FiscalProfile).filter(FiscalProfile.company_id == company_id).first()
    if not profile:
        raise HTTPException(status_code=409, detail="Configura los datos fiscales (NIF y razón social) antes de cobrar.")
    return profile


def _lock_chain(db: Session, company_id: UUID) -> FiscalChainHead:
    db.execute(insert(FiscalChainHead).values(company_id=company_id, sequence=0)
               .on_conflict_do_nothing(index_elements=[FiscalChainHead.company_id]))
    return db.query(FiscalChainHead).filter(FiscalChainHead.company_id == company_id).with_for_update().one()


def _sif(installation: str) -> dict:
    return {"producer_name": config.SIF_PRODUCER_NAME, "producer_nif": config.SIF_PRODUCER_NIF,
            "name": config.SIF_NAME, "id": config.SIF_ID, "version": config.SIF_VERSION,
            "installation": installation}


def _append_record(db: Session, head: FiscalChainHead, profile: FiscalProfile, invoice: Invoice,
                   record_type: str, local_now: datetime, extra: dict | None = None) -> FiscalRecord:
    tz = local_now.tzinfo
    fecha = vf.fmt_fecha(invoice.issued_at.astimezone(tz))
    ts = vf.fmt_timestamp(local_now)
    previous = None
    if head.sequence > 0 and head.last_hash:
        previous = {"nif": head.last_nif, "num_serie": head.last_num_serie, "fecha": head.last_fecha,
                    "hash": head.last_hash}
    payload = {"nif": profile.nif, "num_serie": invoice.full_number, "fecha": fecha, "fecha_hora_huso": ts,
               "anterior": previous, "sif": _sif(str(invoice.company_id))}  # una cadena = una instalación
    if record_type == "alta":
        cuota, importe = vf.fmt_amount(invoice.tax_total), vf.fmt_amount(invoice.total)
        h = vf.hash_alta(nif=profile.nif, num_serie=invoice.full_number, fecha=fecha,
                         tipo_factura=invoice.invoice_type, cuota_total=cuota, importe_total=importe,
                         huella_anterior=previous["hash"] if previous else None, fecha_hora_huso=ts)
        payload.update({
            "nombre_emisor": profile.legal_name, "tipo_factura": invoice.invoice_type,
            "descripcion": "Servicio de restauración", "cuota_total": cuota, "importe_total": importe,
            "desglose": [{"tipo": r["rate"], "base": r["base"], "cuota": r["tax"]} for r in invoice.tax_breakdown],
            "huella": h,
        })
        if invoice.customer_nif:
            payload["destinatario"] = {"nif": invoice.customer_nif, "nombre": invoice.customer_name}
        payload.update(extra or {})
        qr = vf.qr_url(nif=profile.nif, num_serie=invoice.full_number, fecha=fecha, importe_total=importe,
                       environment=profile.environment)
    else:
        cuota = importe = None
        h = vf.hash_anulacion(nif=profile.nif, num_serie=invoice.full_number, fecha=fecha,
                              huella_anterior=previous["hash"] if previous else None, fecha_hora_huso=ts)
        payload["huella"] = h
        qr = None
    record = FiscalRecord(
        company_id=invoice.company_id, sequence=head.sequence + 1, record_type=record_type, invoice_id=invoice.id,
        issuer_nif=profile.nif, num_serie=invoice.full_number, fecha_expedicion=fecha,
        tipo_factura=invoice.invoice_type if record_type == "alta" else None, cuota_total=cuota,
        importe_total=importe, previous_hash=previous["hash"] if previous else None, hash=h, generated_at=ts,
        payload=payload, qr_url=qr, environment=profile.environment,
        submission_status="pending" if profile.verifactu_enabled else "disabled",
    )
    head.sequence += 1
    head.last_hash, head.last_nif, head.last_num_serie, head.last_fecha = h, profile.nif, invoice.full_number, fecha
    db.add(record)
    return record


def _prefix(register: PosRegister, invoice_type: str) -> str:
    return {"F2": register.ticket_prefix, "F1": register.invoice_prefix, "F3": register.invoice_prefix,
            "R5": register.refund_prefix}[invoice_type]


def issue_invoice(db: Session, *, company: Company, register: PosRegister, session: CashSession | None,
                  actor_label: str, lines: list[SaleLine], payments: list[PaymentIn], invoice_type: str = "F2",
                  fulfillment: str | None = None, channel: str = "pos", table_label: str | None = None,
                  orders: list[Order] | None = None, customer: dict | None = None,
                  rectified: Invoice | None = None, substituted: list[Invoice] | None = None,
                  reason: str | None = None) -> Invoice:
    profile = get_fiscal_profile(db, company.id)
    if invoice_type != "F3" and (session is None or session.status != "open" or session.register_id != register.id):
        raise HTTPException(status_code=409, detail="Abre la caja antes de cobrar.")
    if not lines:
        raise HTTPException(status_code=422, detail="El ticket está vacío.")

    computed = []
    for line in lines:
        qty = Decimal(line.quantity)
        unit = money(line.unit_price)
        computed.append((line, qty, unit, money(unit * qty)))
    breakdown, base, tax, total = tax_breakdown([(line.tax_rate, lt) for line, _, _, lt in computed])

    if invoice_type in ("F1", "F2", "F3") and total <= ZERO:
        raise HTTPException(status_code=422, detail="El importe del ticket debe ser mayor que cero.")
    if invoice_type == "R5" and total >= ZERO:
        raise HTTPException(status_code=422, detail="Una devolución tiene importe negativo.")
    if invoice_type == "F2" and total > SIMPLIFIED_LIMIT:
        raise HTTPException(status_code=422, detail="Más de 3.000 €: emite factura completa con los datos del cliente.")
    if invoice_type in ("F1", "F3"):
        if not customer or not nif_check.is_valid_nif(customer.get("nif", "")) or not customer.get("name"):
            raise HTTPException(status_code=422, detail="Para la factura completa hacen falta un NIF válido y el nombre.")

    pays: list[Payment] = []
    if invoice_type == "F3":
        if payments:
            raise HTTPException(status_code=422, detail="La factura completa sustituye a tickets ya cobrados: sin pagos.")
    else:
        paid = money(sum((money(p.amount) for p in payments), ZERO))
        if paid != total:
            raise HTTPException(status_code=422, detail=f"Los pagos ({paid} €) no cuadran con el total ({total} €).")
        for p in payments:
            if p.method not in PAYMENT_METHODS:
                raise HTTPException(status_code=422, detail=f"Forma de pago no válida: {p.method}")
            amount = money(p.amount)
            change = None
            tendered = money(p.tendered) if p.tendered is not None else None
            if tendered is not None:
                if p.method != "cash":
                    raise HTTPException(status_code=422, detail="Solo el efectivo lleva «entregado» y cambio.")
                if tendered < amount:
                    raise HTTPException(status_code=422, detail="El cliente ha entregado menos de lo que cuesta.")
                change = money(tendered - amount)
            pays.append(Payment(session_id=session.id if session else None, method=p.method, amount=amount,
                                tendered=tendered, change_given=change, reference=(p.reference or None)))

    # Desde aquí, todo en orden bajo el bloqueo de la cadena: número, hora y huella van en el mismo orden
    head = _lock_chain(db, company.id)
    tz = ZoneInfo(company.timezone or "Europe/Madrid")
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(tz)
    series = f"{_prefix(register, invoice_type)}-{local_now.year}"
    number = next_value(db, company.id, f"invoice:{series}")
    invoice = Invoice(
        company_id=company.id, register_id=register.id, session_id=session.id if session else None,
        invoice_type=invoice_type, series=series, number=number, full_number=f"{series}-{number:06d}",
        issued_at=now, status="issued", fulfillment=fulfillment, channel=channel, table_label=table_label,
        customer_nif=nif_check.normalize(customer["nif"]) if customer else None,
        customer_name=(customer or {}).get("name"), customer_address=(customer or {}).get("address"),
        tax_base=base, tax_total=tax, total=total, tax_breakdown=breakdown,
        rectified_invoice_id=rectified.id if rectified else None,
        substituted_invoice_ids=[str(s.id) for s in (substituted or [])], reason=reason, created_by=actor_label,
    )
    for i, (line, qty, unit, lt) in enumerate(computed):
        invoice.lines.append(InvoiceLine(
            product_id=line.product_id, category_name=line.category_name, source_line_id=line.source_line_id,
            position=i, description=line.description[:255], quantity=qty, unit_price=unit,
            tax_rate=Decimal(line.tax_rate), line_total=lt,
        ))
    for p in pays:
        p.created_at = now
        invoice.payments.append(p)
    db.add(invoice)
    db.flush()

    extra = {}
    if rectified:
        rec_fecha = vf.fmt_fecha(rectified.issued_at.astimezone(tz))
        extra["rectificadas"] = [{"nif": profile.nif, "num_serie": rectified.full_number, "fecha": rec_fecha}]
    if substituted:
        extra["sustituidas"] = [{"nif": profile.nif, "num_serie": s.full_number,
                                 "fecha": vf.fmt_fecha(s.issued_at.astimezone(tz))} for s in substituted]
    _append_record(db, head, profile, invoice, "alta", local_now, extra)

    for order in orders or []:
        order.invoice_id = invoice.id
        order.payment_status = "paid"
    return invoice


def refunded_quantities(db: Session, original: Invoice) -> dict[UUID, Decimal]:
    rows = (
        db.query(InvoiceLine.source_line_id, InvoiceLine.quantity)
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .filter(Invoice.rectified_invoice_id == original.id, Invoice.status == "issued")
        .all()
    )
    out: dict[UUID, Decimal] = {}
    for line_id, qty in rows:
        if line_id:
            out[line_id] = out.get(line_id, ZERO) + (-Decimal(qty))
    return out


def refund_invoice(db: Session, *, company: Company, register: PosRegister, session: CashSession,
                   original: Invoice, actor_label: str, items: list[dict] | None, method: str,
                   reason: str) -> Invoice:
    """Devolución total o parcial de un ticket: rectificativa R5 por diferencias."""
    if original.company_id != company.id:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if original.invoice_type != "F2" or original.status != "issued":
        raise HTTPException(status_code=409, detail="Solo se devuelven tickets (facturas simplificadas) vigentes.")
    if not (reason or "").strip():
        raise HTTPException(status_code=422, detail="Indica el motivo de la devolución.")
    already = refunded_quantities(db, original)
    wanted = {UUID(str(i["line_id"])): Decimal(str(i["quantity"])) for i in items} if items else None
    lines: list[SaleLine] = []
    for line in original.lines:
        left = Decimal(line.quantity) - already.get(line.id, ZERO)
        qty = left if wanted is None else wanted.pop(line.id, ZERO)
        if qty <= 0:
            continue
        if qty > left:
            raise HTTPException(status_code=422, detail=f"De «{line.description}» solo quedan {left} por devolver.")
        lines.append(SaleLine(description=line.description, quantity=-qty, unit_price=line.unit_price,
                              tax_rate=line.tax_rate, product_id=line.product_id, category_name=line.category_name,
                              source_line_id=line.id))
    if wanted:
        raise HTTPException(status_code=422, detail="Alguna línea no pertenece a este ticket.")
    if not lines:
        raise HTTPException(status_code=409, detail="Este ticket ya está devuelto entero.")
    _, _, _, total = tax_breakdown([(line.tax_rate, money(line.unit_price * line.quantity)) for line in lines])
    invoice = issue_invoice(db, company=company, register=register, session=session, actor_label=actor_label,
                            lines=lines, payments=[PaymentIn(method=method, amount=total)], invoice_type="R5",
                            fulfillment=original.fulfillment, channel=original.channel,
                            table_label=original.table_label, rectified=original, reason=reason.strip()[:255])
    _audit(db, company.id, "devolucion", actor_label,
           {"original": original.full_number, "rectificativa": invoice.full_number, "importe": f"{invoice.total}"})
    return invoice


def full_invoice_for_tickets(db: Session, *, company: Company, register: PosRegister, actor_label: str,
                             tickets: list[Invoice], customer: dict) -> Invoice:
    """Factura completa F3 a nombre del cliente que sustituye a uno o varios tickets."""
    if not tickets:
        raise HTTPException(status_code=422, detail="Elige al menos un ticket.")
    taken = set()
    for f3 in db.query(Invoice).filter(Invoice.company_id == company.id, Invoice.invoice_type == "F3").all():
        taken.update(f3.substituted_invoice_ids or [])
    lines: list[SaleLine] = []
    for t in tickets:
        if t.company_id != company.id or t.invoice_type != "F2" or t.status != "issued":
            raise HTTPException(status_code=409, detail=f"{t.full_number} no se puede facturar.")
        if str(t.id) in taken:
            raise HTTPException(status_code=409, detail=f"{t.full_number} ya tiene factura completa.")
        if refunded_quantities(db, t):
            raise HTTPException(status_code=409, detail=f"{t.full_number} tiene devoluciones: factura el importe neto aparte.")
        for line in t.lines:
            lines.append(SaleLine(description=line.description, quantity=line.quantity, unit_price=line.unit_price,
                                  tax_rate=line.tax_rate, product_id=line.product_id,
                                  category_name=line.category_name))
    invoice = issue_invoice(db, company=company, register=register, session=None, actor_label=actor_label,
                            lines=lines, payments=[], invoice_type="F3", fulfillment=tickets[0].fulfillment,
                            channel=tickets[0].channel, customer=customer, substituted=tickets,
                            reason="Sustituye a " + ", ".join(t.full_number for t in tickets))
    _audit(db, company.id, "factura_completa", actor_label,
           {"factura": invoice.full_number, "sustituye": [t.full_number for t in tickets]})
    return invoice


def void_invoice(db: Session, *, company: Company, session: CashSession, invoice: Invoice, actor_label: str,
                 reason: str) -> Invoice:
    """Anulación de un ticket emitido por error (solo dentro de la caja abierta que lo cobró)."""
    if invoice.company_id != company.id:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    if invoice.status != "issued" or invoice.invoice_type != "F2":
        raise HTTPException(status_code=409, detail="Solo se anulan tickets vigentes.")
    if session is None or invoice.session_id != session.id or session.status != "open":
        raise HTTPException(status_code=409, detail="Solo se anula un ticket de la caja abierta. Si no, haz una devolución.")
    if refunded_quantities(db, invoice):
        raise HTTPException(status_code=409, detail="El ticket tiene devoluciones: no se puede anular.")
    if not (reason or "").strip():
        raise HTTPException(status_code=422, detail="Indica el motivo de la anulación.")
    profile = get_fiscal_profile(db, company.id)
    head = _lock_chain(db, company.id)
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(ZoneInfo(company.timezone or "Europe/Madrid"))
    _append_record(db, head, profile, invoice, "anulacion", local_now)
    invoice.status = "voided"
    invoice.reason = reason.strip()[:255]
    for p in list(invoice.payments):
        if p.amount > 0:
            invoice.payments.append(Payment(session_id=session.id, method=p.method, amount=-p.amount,
                                            reference="Anulación", created_at=now))
    for order in db.query(Order).filter(Order.invoice_id == invoice.id).all():
        order.invoice_id = None
        order.payment_status = "unpaid"
    _audit(db, company.id, "anulacion", actor_label, {"ticket": invoice.full_number, "motivo": invoice.reason})
    return invoice


def fiscal_records_for_verification(db: Session, company_id: UUID) -> list[dict]:
    rows = db.query(FiscalRecord).filter(FiscalRecord.company_id == company_id).order_by(FiscalRecord.sequence).all()
    return [{"sequence": r.sequence, "record_type": r.record_type, "issuer_nif": r.issuer_nif,
             "num_serie": r.num_serie, "fecha_expedicion": r.fecha_expedicion, "tipo_factura": r.tipo_factura,
             "cuota_total": r.cuota_total, "importe_total": r.importe_total, "previous_hash": r.previous_hash,
             "hash": r.hash, "generated_at": r.generated_at} for r in rows]
