"""Tablero de pedidos para cocina y barra: en vivo (SSE), cambios de estado y comanda impresa."""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session, selectinload
from starlette.concurrency import run_in_threadpool

from app.api.venue_admin import actor, get_or_create_venue
from app.core.company_access import Actor, resolve_actor
from app.db.dependencies import get_db
from app.db.session import SessionLocal
from app.models.company import Company
from app.models.order import Order
from app.schemas.hospitality import StatusChangeIn
from app.services import order_service as osvc
from app.web.render import templates

router = APIRouter(prefix="/my/venues/{company_id}/orders", tags=["Hostelería · pedidos"])


def _board_query(db: Session, company_id: UUID, since: datetime | None, include_final_hours: int = 6):
    q = db.query(Order).options(selectinload(Order.lines)).filter(Order.company_id == company_id)
    if since:
        q = q.filter(Order.updated_at > since)
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=include_final_hours)
        q = q.filter((Order.status.in_(osvc.ACTIVE_STATUSES)) | (Order.updated_at >= cutoff))
    return q.order_by(Order.created_at)


@router.get("")
def list_orders(company_id: UUID, status: str | None = Query(None), business_date: date | None = Query(None),
                updated_since: datetime | None = Query(None), a: Actor = Depends(actor("orders.view")),
                db: Session = Depends(get_db)):
    """Sin filtros: lo activo + lo cerrado en las últimas 6 h (lo que pinta el tablero)."""
    if status or business_date:
        q = db.query(Order).options(selectinload(Order.lines)).filter(Order.company_id == company_id)
        if status:
            q = q.filter(Order.status == status)
        if business_date:
            q = q.filter(Order.business_date == business_date)
        rows = q.order_by(Order.created_at).limit(500).all()
    else:
        rows = _board_query(db, company_id, updated_since).limit(500).all()
    return {"server_time": datetime.now(timezone.utc).isoformat(), "orders": [osvc.order_staff_dict(o) for o in rows]}


@router.get("/stream")
async def stream_orders(company_id: UUID, request: Request, authorization: str | None = Header(None)):
    """Eventos SSE «order» con cada pedido nuevo o cambiado. Usar con fetch (lleva cabecera Authorization)."""

    def _check():
        with SessionLocal() as db:
            resolve_actor(db, authorization, company_id, "orders.view")

    await run_in_threadpool(_check)

    def _changes(since: datetime | None):
        with SessionLocal() as db:
            rows = _board_query(db, company_id, since).limit(300).all()
            return [osvc.order_staff_dict(o) for o in rows]

    # updated_at es la hora de inicio de la transacción: una que empezó antes del último sondeo
    # puede aparecer después con una hora anterior. Por eso se pregunta con 15 s de solape y se
    # deduplica por (id, updated_at).
    overlap = timedelta(seconds=15)

    async def gen():
        sent: dict[str, str] = {}
        cursor = datetime.now(timezone.utc)
        snapshot = await run_in_threadpool(_changes, None)
        for item in snapshot:
            sent[item["id"]] = item["updated_at"]
        yield f"event: snapshot\ndata: {json.dumps(snapshot)}\n\n"
        idle = 0
        while not await request.is_disconnected():
            await asyncio.sleep(2)
            started = datetime.now(timezone.utc)
            changed = [i for i in await run_in_threadpool(_changes, cursor - overlap)
                       if sent.get(i["id"]) != i["updated_at"]]
            for item in changed:
                sent[item["id"]] = item["updated_at"]
                yield f"event: order\ndata: {json.dumps(item)}\n\n"
            cursor = started
            idle = 0 if changed else idle + 1
            if idle and idle % 8 == 0:
                yield ": latido\n\n"  # mantiene viva la conexión tras proxies
            if len(sent) > 3000:
                sent = dict(list(sent.items())[-1000:])

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{order_id}")
def get_order(company_id: UUID, order_id: UUID, a: Actor = Depends(actor("orders.view")),
              db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o or o.company_id != company_id:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return osvc.order_staff_dict(o)


@router.post("/{order_id}/status")
def change_status(company_id: UUID, order_id: UUID, data: StatusChangeIn,
                  a: Actor = Depends(actor("orders.manage")), db: Session = Depends(get_db)):
    o = db.query(Order).filter(Order.id == order_id, Order.company_id == company_id).with_for_update().first()
    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if data.status == "rejected" and not (data.reason or "").strip():
        raise HTTPException(status_code=422, detail="Di al cliente por qué no se acepta (p. ej. «nos quedamos sin pan»).")
    venue = get_or_create_venue(db, company_id)
    osvc.staff_transition(o, data.status, reason=data.reason, eta_minutes=data.eta_minutes,
                          prep_minutes=venue.prep_time_minutes or 15)
    db.commit()
    db.refresh(o)
    return osvc.order_staff_dict(o)


@router.get("/{order_id}/kitchen-ticket", response_class=HTMLResponse)
def kitchen_ticket(company_id: UUID, order_id: UUID, request: Request, a: Actor = Depends(actor("orders.view")),
                   db: Session = Depends(get_db)):
    """Comanda de cocina para impresora térmica de 80 mm."""
    o = db.get(Order, order_id)
    if not o or o.company_id != company_id:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    company = db.get(Company, company_id)
    venue = get_or_create_venue(db, company_id)
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(company.timezone or "Europe/Madrid")
    return templates.TemplateResponse(request, "kitchen_ticket.html", {
        "o": o, "venue_name": venue.display_name or company.name,
        "created": o.created_at.astimezone(tz).strftime("%d/%m %H:%M"),
        "scheduled": o.scheduled_for.astimezone(tz).strftime("%H:%M") if o.scheduled_for else None,
    })
