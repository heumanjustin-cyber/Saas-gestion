"""Pantallas del local servidas por el backend: TPV (/app/tpv) y cocina (/app/cocina).

Son HTML + JS sin compilación: se abren en el navegador de la tablet o del TPV
y se pueden «instalar» en la pantalla de inicio. Sin app que mantener.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.render import templates

router = APIRouter(tags=["Hostelería · apps"])


@router.get("/app/tpv", response_class=HTMLResponse, include_in_schema=False)
def tpv_app(request: Request):
    return templates.TemplateResponse(request, "tpv.html", {})


@router.get("/app/cocina", response_class=HTMLResponse, include_in_schema=False)
def kitchen_app(request: Request):
    return templates.TemplateResponse(request, "cocina.html", {})
