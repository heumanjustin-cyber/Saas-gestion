"""Lo que ve el cliente: página del local, QR dinámicos, pedido, seguimiento en vivo y opinión.

La página se pinta en el servidor (rápida, con el nombre del local y legible por
Google aunque el móvil no ejecute JavaScript); el JavaScript solo añade el carrito.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy.orm import Session, selectinload
from starlette.concurrency import run_in_threadpool

from app.db.dependencies import get_db
from app.db.session import SessionLocal
from app.models.company import Company
from app.models.dining import QrCode, QrScan
from app.models.order import FINAL_STATUSES, Order
from app.models.venue import VenueFeedback, VenueProfile
from app.schemas.hospitality import FeedbackIn, PublicOrderIn
from app.services import hours as H
from app.services import order_service as osvc
from app.services import qr_service, ratelimit
from app.services.allergens import catalog as allergen_catalog
from app.services.i18n import STRINGS, pick_language
from app.services.menu_service import load_menu, menu_dict
from app.web.render import public_base, templates

router = APIRouter(tags=["Hostelería · público"])


def _venue_by_slug(db: Session, slug: str) -> tuple[Company, VenueProfile]:
    company = db.query(Company).filter(Company.slug == slug, Company.is_active.is_(True)).first()
    venue = db.query(VenueProfile).filter(VenueProfile.company_id == company.id).first() if company else None
    if not company or not venue or not venue.is_published:
        raise HTTPException(status_code=404, detail="Local no encontrado")
    return company, venue


def review_url(venue: VenueProfile) -> str | None:
    if venue.google_place_id:
        return f"https://search.google.com/local/writereview?placeid={quote(venue.google_place_id)}"
    return None


def maps_url(venue: VenueProfile, name: str) -> str | None:
    if venue.google_maps_url:
        return venue.google_maps_url
    if venue.latitude is not None and venue.longitude is not None:
        return f"https://www.google.com/maps/dir/?api=1&destination={venue.latitude},{venue.longitude}"
    if venue.address:
        return "https://www.google.com/maps/search/?api=1&query=" + quote(f"{name} {venue.address} {venue.city or ''}")
    return None


def wa_link(number: str | None, text: str | None = None) -> str | None:
    digits = re.sub(r"\D", "", number or "")
    if not digits:
        return None
    if len(digits) == 9:
        digits = "34" + digits
    return f"https://wa.me/{digits}" + (f"?text={quote(text)}" if text else "")


def venue_public_dict(company: Company, venue: VenueProfile, lang: str, now: datetime) -> dict:
    tz = company.timezone or "Europe/Madrid"
    st = H.open_status(venue.opening_hours, venue.closures, now, tz)
    name = venue.display_name or company.name
    paused = bool(venue.ordering_paused_until and venue.ordering_paused_until > now)
    offer = venue.offer_text if venue.offer_text and (not venue.offer_expires_at or venue.offer_expires_at > now) else None
    return {
        "slug": company.slug, "name": name, "tagline": venue.tagline, "description": venue.description,
        "logo_url": venue.logo_url, "cover_url": venue.cover_url, "brand_color": venue.brand_color,
        "accent_color": venue.accent_color, "tags": venue.tags, "cuisine": venue.cuisine,
        "price_range": venue.price_range, "phone": venue.phone, "whatsapp": venue.whatsapp,
        "address": venue.address, "postal_code": venue.postal_code, "city": venue.city, "province": venue.province,
        "latitude": f"{venue.latitude}" if venue.latitude is not None else None,
        "longitude": f"{venue.longitude}" if venue.longitude is not None else None,
        "is_open": st.is_open, "status_text": H.status_text(st, now, tz, lang),
        "status_short": H.status_text(st, now, tz, lang).split(" · ")[0],
        "closes_at": st.closes_at.isoformat() if st.closes_at else None,
        "opens_at": st.opens_at.isoformat() if st.opens_at else None,
        "hours": H.weekly_table(venue.opening_hours, lang), "offer": offer,
        "ordering": {
            "enabled": venue.ordering_enabled and not paused, "paused": paused,
            "dine_in": venue.dine_in_enabled, "takeaway": venue.takeaway_enabled, "delivery": venue.delivery_enabled,
            "delivery_fee": f"{venue.delivery_fee:.2f}", "delivery_min_order": f"{venue.delivery_min_order:.2f}",
            "delivery_note": venue.delivery_note, "prep_time_minutes": venue.prep_time_minutes,
            "payment_methods": venue.payment_methods, "scheduled": venue.accepts_scheduled_orders,
        },
        "slots": H.order_slots(venue.opening_hours, venue.closures, now, tz, venue.prep_time_minutes or 15,
                               lang=lang) if venue.accepts_scheduled_orders else [],
        "theme": "dark" if H.is_dark(venue.brand_color) else "light",
        "accent_text": "#ffffff" if H.is_dark(venue.accent_color) else "#111111",
        "languages": venue.languages or ["es"], "review_url": review_url(venue),
        "maps_url": maps_url(venue, name), "whatsapp_url": wa_link(venue.whatsapp),
        "free_tap_water": venue.free_tap_water, "allergen_notice": venue.allergen_notice,
    }


def _qr_context(db: Session, company: Company, code: str | None) -> dict | None:
    if not code:
        return None
    q = db.query(QrCode).options(selectinload(QrCode.table)).filter(QrCode.code == code).first()
    if not q or q.company_id != company.id or not q.is_active:
        return None
    table = q.table if (q.table and q.table.is_active) else None
    return {"code": q.code, "kind": q.kind, "label": q.label, "table": table.name if table else None}


def _json_ld(company: Company, venue: VenueProfile, menu: list[dict], page_url: str) -> str:
    name = venue.display_name or company.name
    data = {
        "@context": "https://schema.org", "@type": "Restaurant", "name": name, "url": page_url,
        "servesCuisine": venue.cuisine or None, "priceRange": venue.price_range,
        "telephone": venue.phone, "image": venue.cover_url or venue.logo_url, "logo": venue.logo_url,
        "address": {"@type": "PostalAddress", "streetAddress": venue.address, "postalCode": venue.postal_code,
                    "addressLocality": venue.city, "addressRegion": venue.province, "addressCountry": venue.country},
        "openingHoursSpecification": H.schema_org_hours(venue.opening_hours) or None,
        "acceptsReservations": False,
        "hasMenu": {
            "@type": "Menu", "name": f"Carta de {name}", "inLanguage": "es",
            "hasMenuSection": [{
                "@type": "MenuSection", "name": c["name"],
                "hasMenuItem": [{"@type": "MenuItem", "name": p["name"], "description": p["description"] or None,
                                 "offers": {"@type": "Offer", "price": p["price"], "priceCurrency": company.currency or "EUR"}}
                                for p in c["products"]],
            } for c in menu],
        },
    }
    if venue.latitude is not None and venue.longitude is not None:
        data["geo"] = {"@type": "GeoCoordinates", "latitude": float(venue.latitude), "longitude": float(venue.longitude)}

    def prune(x):
        if isinstance(x, dict):
            return {k: prune(v) for k, v in x.items() if v not in (None, [], {}, "")}
        if isinstance(x, list):
            return [prune(v) for v in x]
        return x

    # </script> dentro de un nombre no puede cerrar la etiqueta
    return json.dumps(prune(data), ensure_ascii=False).replace("</", "<\\/")


# ------------------------------------------------------------------ páginas
@router.get("/r/{slug}", response_class=HTMLResponse)
def venue_page(slug: str, request: Request, q: str | None = Query(None, max_length=16),
               lang: str | None = Query(None, max_length=5), db: Session = Depends(get_db)):
    company, venue = _venue_by_slug(db, slug)
    lang = pick_language(lang, request.headers.get("accept-language"), venue.languages or ["es"])
    now = datetime.now(timezone.utc)
    info = venue_public_dict(company, venue, lang, now)
    menu = menu_dict(load_menu(db, company.id), lang)
    ctx = _qr_context(db, company, q)
    base = public_base(request)
    page_url = f"{base}/r/{company.slug}"
    config = {
        "slug": company.slug, "lang": lang, "api": f"{base}/api/public", "qr": ctx, "venue": info,
        "menu": menu, "allergens": allergen_catalog(lang), "strings": STRINGS[lang], "currency": company.currency,
    }
    unverified = any("allergens_unverified" in p["tags"] for c in menu for p in c["products"])
    return templates.TemplateResponse(request, "venue.html", {
        "unverified": unverified,
        "v": info, "menu": menu, "qr": ctx, "lang": lang, "t": STRINGS[lang], "page_url": page_url,
        "json_ld": _json_ld(company, venue, menu, page_url), "allergens": allergen_catalog(lang),
        "allergen_map": {a["code"]: a for a in allergen_catalog(lang)},
        "config_json": json.dumps(config, ensure_ascii=False).replace("</", "<\\/"),
        "alternates": [(code, f"{page_url}?lang={code}") for code in (venue.languages or ["es"])],
    })


@router.get("/q/{code}")
def qr_redirect(code: str, request: Request, db: Session = Depends(get_db)):
    """Destino de cada QR impreso. Cuenta el escaneo (sin IP ni datos personales) y redirige."""
    q = db.query(QrCode).filter(QrCode.code == code).first()
    if not q:
        raise HTTPException(status_code=404, detail="Este código no existe")
    company = db.get(Company, q.company_id)
    venue = db.query(VenueProfile).filter(VenueProfile.company_id == q.company_id).first()
    ua = (request.headers.get("user-agent") or "").lower()
    device = "bot" if re.search(r"bot|crawl|spider|preview|whatsapp|facebookexternalhit", ua) else (
        "mobile" if re.search(r"mobile|android|iphone|ipad", ua) else "desktop")
    if device != "bot":
        db.add(QrScan(qr_id=q.id, company_id=q.company_id, device=device,
                      lang=(request.headers.get("accept-language") or "")[:2] or None))
        q.scan_count = (q.scan_count or 0) + 1
        q.last_scan_at = datetime.now(timezone.utc)
        db.commit()
    if q.is_active and q.target == "url" and q.target_url:
        return RedirectResponse(q.target_url, status_code=302)
    if q.is_active and q.target == "review" and venue and review_url(venue):
        return RedirectResponse(review_url(venue), status_code=302)
    suffix = f"?q={q.code}" if q.is_active else ""
    return RedirectResponse(f"/r/{company.slug}{suffix}", status_code=302)


@router.get("/qr/{code}.svg")
def qr_svg(code: str, request: Request, db: Session = Depends(get_db)):
    q = db.query(QrCode).filter(QrCode.code == code).first()
    if not q:
        raise HTTPException(status_code=404, detail="Este código no existe")
    venue = db.query(VenueProfile).filter(VenueProfile.company_id == q.company_id).first()
    svg = qr_service.svg(f"{public_base(request)}/q/{q.code}", dark=(venue.brand_color if venue else None) or "#111111")
    svg = svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1) if "xmlns=" not in svg else svg
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


# ------------------------------------------------------------------ API pública
@router.get("/api/public/venues/{slug}")
def public_venue(slug: str, request: Request, lang: str | None = Query(None, max_length=5),
                 db: Session = Depends(get_db)):
    company, venue = _venue_by_slug(db, slug)
    lang = pick_language(lang, request.headers.get("accept-language"), venue.languages or ["es"])
    now = datetime.now(timezone.utc)
    return {"venue": venue_public_dict(company, venue, lang, now), "menu": menu_dict(load_menu(db, company.id), lang)}


@router.post("/api/public/venues/{slug}/orders", status_code=201)
def place_order(slug: str, data: PublicOrderIn, request: Request, db: Session = Depends(get_db)):
    company, venue = _venue_by_slug(db, slug)
    if data.website:  # un humano no rellena el campo oculto
        raise HTTPException(status_code=422, detail={"code": "spam", "message": "No se pudo enviar el pedido."})
    ratelimit.check(f"order:{company.id}", ratelimit.client_key(request), limit=6, window_seconds=600)
    qr = None
    if data.qr_code:
        qr = db.query(QrCode).options(selectinload(QrCode.table)).filter(QrCode.code == data.qr_code).first()
        if not qr or qr.company_id != company.id or not qr.is_active:
            qr = None
    order, created = osvc.create_public_order(db, company, venue, data, qr)
    body = osvc.order_public_dict(order, data.language)
    body["tracking_url"] = f"{public_base(request)}/r/{company.slug}?pedido={order.public_token}"
    body["created"] = created
    return body


def _load_order(db: Session, token: str) -> Order:
    o = db.query(Order).options(selectinload(Order.lines)).filter(Order.public_token == token).first()
    if not o:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return o


@router.get("/api/public/orders/{token}")
def track_order(token: str, lang: str = Query("es", max_length=5), db: Session = Depends(get_db)):
    return osvc.order_public_dict(_load_order(db, token), lang)


@router.post("/api/public/orders/{token}/cancel")
def cancel_order(token: str, db: Session = Depends(get_db)):
    o = _load_order(db, token)
    osvc.customer_cancel(o)
    db.commit()
    return osvc.order_public_dict(o, o.language)


@router.get("/api/public/orders/{token}/stream")
async def track_order_stream(token: str, request: Request, lang: str = Query("es", max_length=5)):
    """El cliente ve «Recibido → En la cocina → ¡Listo!» sin recargar (SSE)."""

    def _get():
        with SessionLocal() as db:
            o = db.query(Order).options(selectinload(Order.lines)).filter(Order.public_token == token).first()
            return osvc.order_public_dict(o, lang) if o else None

    first = await run_in_threadpool(_get)
    if not first:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    async def gen():
        last = None
        ticks = 0
        data = first
        while not await request.is_disconnected():
            if data != last:
                yield f"event: order\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                last = data
            if data["status"] in FINAL_STATUSES:
                break
            await asyncio.sleep(3)
            ticks += 1
            if ticks % 10 == 0:
                yield ": latido\n\n"
            if ticks > 1200:  # una hora como mucho
                break
            data = await run_in_threadpool(_get) or last

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/api/public/venues/{slug}/feedback", status_code=201)
def send_feedback(slug: str, data: FeedbackIn, request: Request, db: Session = Depends(get_db)):
    """Comentario privado al dueño (el otro botón, igual de visible, lleva a Google)."""
    company, _ = _venue_by_slug(db, slug)
    if data.website:
        raise HTTPException(status_code=422, detail="No se pudo enviar.")
    ratelimit.check(f"feedback:{company.id}", ratelimit.client_key(request), limit=3, window_seconds=600)
    order_id = None
    if data.order_token:
        o = db.query(Order).filter(Order.public_token == data.order_token, Order.company_id == company.id).first()
        order_id = o.id if o else None
    db.add(VenueFeedback(company_id=company.id, order_id=order_id, message=data.message.strip(),
                         contact=(data.contact or "").strip() or None))
    db.commit()
    return {"ok": True}


@router.get("/api/public/venues/{slug}/vcard")
def vcard(slug: str, db: Session = Depends(get_db)):
    company, venue = _venue_by_slug(db, slug)
    name = venue.display_name or company.name

    def esc(v: str | None) -> str:
        return (v or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")

    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{esc(name)}", f"ORG:{esc(name)}"]
    if venue.phone:
        lines.append(f"TEL;TYPE=WORK,VOICE:{esc(venue.phone)}")
    if venue.whatsapp and venue.whatsapp != venue.phone:
        lines.append(f"TEL;TYPE=CELL:{esc(venue.whatsapp)}")
    if venue.address:
        lines.append(f"ADR;TYPE=WORK:;;{esc(venue.address)};{esc(venue.city)};{esc(venue.province)};"
                     f"{esc(venue.postal_code)};{esc(venue.country)}")
    if venue.website:
        lines.append(f"URL:{esc(venue.website)}")
    lines.append("END:VCARD")
    filename = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower() or "contacto"
    return Response("\r\n".join(lines) + "\r\n", media_type="text/vcard; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}.vcf"'})

