"""Caja: apertura con fondo, entradas/salidas, informe X (en curso) y cierre Z con arqueo."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.pos import AuditEvent, CashMovement, CashSession, Invoice, Payment, PosRegister
from app.services.counters import next_value
from app.services.verifactu import money

ZERO = Decimal("0.00")
DENOMINATIONS = ("500", "200", "100", "50", "20", "10", "5", "2", "1", "0.50", "0.20", "0.10", "0.05", "0.02", "0.01")


def open_session_for(db: Session, register_id) -> CashSession | None:
    return (db.query(CashSession)
            .filter(CashSession.register_id == register_id, CashSession.status == "open")
            .first())


def open_session(db: Session, register: PosRegister, actor_label: str, opening_float) -> CashSession:
    if open_session_for(db, register.id):
        raise HTTPException(status_code=409, detail="Esta caja ya está abierta.")
    amount = money(opening_float or 0)
    if amount < 0:
        raise HTTPException(status_code=422, detail="El fondo de caja no puede ser negativo.")
    session = CashSession(company_id=register.company_id, register_id=register.id, status="open",
                          opened_at=datetime.now(timezone.utc), opened_by=actor_label, opening_float=amount)
    db.add(session)
    db.add(AuditEvent(company_id=register.company_id, event_type="apertura_caja", actor=actor_label,
                      detail={"caja": register.name, "fondo": f"{amount}"}, created_at=datetime.now(timezone.utc)))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Esta caja ya está abierta.")
    return session


def add_movement(db: Session, session: CashSession, kind: str, amount, reason: str, actor_label: str) -> CashMovement:
    if session.status != "open":
        raise HTTPException(status_code=409, detail="La caja está cerrada.")
    if kind not in ("in", "out"):
        raise HTTPException(status_code=422, detail="Tipo de movimiento: in (entrada) u out (salida).")
    value = money(amount)
    if value <= 0:
        raise HTTPException(status_code=422, detail="El importe debe ser mayor que cero.")
    if not (reason or "").strip():
        raise HTTPException(status_code=422, detail="Indica el motivo (p. ej. «pago al proveedor de pan»).")
    mv = CashMovement(session_id=session.id, kind=kind, amount=value, reason=reason.strip()[:255],
                      created_by=actor_label)
    db.add(mv)
    db.flush()
    return mv


def summarize(db: Session, session: CashSession) -> dict:
    invoices = (db.query(Invoice).options(selectinload(Invoice.lines))
                .filter(Invoice.session_id == session.id).order_by(Invoice.issued_at).all())
    payments = db.query(Payment).filter(Payment.session_id == session.id).all()
    movements = db.query(CashMovement).filter(CashMovement.session_id == session.id).order_by(CashMovement.created_at).all()

    sales = [i for i in invoices if i.invoice_type in ("F1", "F2") and i.status == "issued"]
    refunds = [i for i in invoices if i.invoice_type == "R5" and i.status == "issued"]
    voided = [i for i in invoices if i.status == "voided"]
    gross = money(sum((i.total for i in sales), ZERO))
    refunded = money(sum((i.total for i in refunds), ZERO))

    by_method: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for p in payments:
        by_method[p.method] += Decimal(p.amount)

    taxes: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"base": ZERO, "tax": ZERO, "total": ZERO})
    for inv in sales + refunds:
        for row in inv.tax_breakdown or []:
            t = taxes[row["rate"]]
            t["base"] += Decimal(row["base"])
            t["tax"] += Decimal(row["tax"])
            t["total"] += Decimal(row["total"])

    channels: dict[str, dict] = defaultdict(lambda: {"tickets": 0, "total": ZERO})
    for inv in sales:
        c = channels[inv.channel or "pos"]
        c["tickets"] += 1
        c["total"] += Decimal(inv.total)

    products: dict[str, dict] = defaultdict(lambda: {"quantity": ZERO, "total": ZERO})
    for inv in sales + refunds:
        for line in inv.lines:
            pr = products[line.description]
            pr["quantity"] += Decimal(line.quantity)
            pr["total"] += Decimal(line.line_total)
    top = sorted(products.items(), key=lambda kv: kv[1]["total"], reverse=True)[:10]

    cash_in = money(sum((m.amount for m in movements if m.kind == "in"), ZERO))
    cash_out = money(sum((m.amount for m in movements if m.kind == "out"), ZERO))
    expected = money(Decimal(session.opening_float) + by_method.get("cash", ZERO) + cash_in - cash_out)

    numbers = [i.full_number for i in sales]
    return {
        "session_id": str(session.id),
        "status": session.status,
        "opened_at": session.opened_at.isoformat(),
        "opened_by": session.opened_by,
        "opening_float": f"{money(session.opening_float):.2f}",
        "tickets": len(sales),
        "first_ticket": numbers[0] if numbers else None,
        "last_ticket": numbers[-1] if numbers else None,
        "gross_sales": f"{gross:.2f}",
        "refunds": f"{refunded:.2f}",
        "refund_count": len(refunds),
        "net_sales": f"{money(gross + refunded):.2f}",
        "average_ticket": f"{money(gross / len(sales)) if sales else ZERO:.2f}",
        "voided_count": len(voided),
        "voided": [i.full_number for i in voided],
        "payments": {k: f"{money(v):.2f}" for k, v in sorted(by_method.items())},
        "taxes": [{"rate": r, "base": f"{money(v['base']):.2f}", "tax": f"{money(v['tax']):.2f}",
                   "total": f"{money(v['total']):.2f}"} for r, v in sorted(taxes.items())],
        "channels": {k: {"tickets": v["tickets"], "total": f"{money(v['total']):.2f}"} for k, v in channels.items()},
        "top_products": [{"name": n, "quantity": f"{v['quantity'].normalize():f}", "total": f"{money(v['total']):.2f}"}
                         for n, v in top],
        "cash_in": f"{cash_in:.2f}",
        "cash_out": f"{cash_out:.2f}",
        "movements": [{"kind": m.kind, "amount": f"{m.amount:.2f}", "reason": m.reason, "by": m.created_by,
                       "at": m.created_at.isoformat() if m.created_at else None} for m in movements],
        "expected_cash": f"{expected:.2f}",
    }


def counted_total(breakdown: dict | None) -> Decimal:
    total = ZERO
    for den, count in (breakdown or {}).items():
        if den not in DENOMINATIONS:
            raise HTTPException(status_code=422, detail=f"Billete o moneda no válida: {den}")
        n = int(count)
        if n < 0:
            raise HTTPException(status_code=422, detail="Las cantidades del arqueo no pueden ser negativas.")
        total += Decimal(den) * n
    return money(total)


def close_session(db: Session, session: CashSession, register: PosRegister, actor_label: str, *,
                  counted_cash=None, breakdown: dict | None = None, notes: str | None = None) -> CashSession:
    if session.status != "open":
        raise HTTPException(status_code=409, detail="La caja ya está cerrada.")
    if breakdown:
        counted = counted_total(breakdown)
    elif counted_cash is not None:
        counted = money(counted_cash)
    else:
        raise HTTPException(status_code=422, detail="Cuenta el efectivo del cajón para cerrar.")
    summary = summarize(db, session)
    expected = Decimal(summary["expected_cash"])
    now = datetime.now(timezone.utc)
    session.status = "closed"
    session.closed_at = now
    session.closed_by = actor_label
    session.counted_cash = counted
    session.counted_breakdown = {k: int(v) for k, v in (breakdown or {}).items()} or None
    session.expected_cash = expected
    session.difference = money(counted - expected)
    session.z_number = next_value(db, register.company_id, f"z:{register.id}")
    session.notes = (notes or "").strip()[:1000] or None
    summary.update({"status": "closed", "closed_at": now.isoformat(), "closed_by": actor_label,
                    "counted_cash": f"{counted:.2f}", "difference": f"{session.difference:.2f}",
                    "z_number": session.z_number, "register": register.name})
    session.z_report = summary
    db.add(AuditEvent(company_id=register.company_id, event_type="cierre_z", actor=actor_label,
                      detail={"caja": register.name, "z": session.z_number, "ventas": summary["net_sales"],
                              "descuadre": summary["difference"]}, created_at=now))
    db.flush()
    return session
