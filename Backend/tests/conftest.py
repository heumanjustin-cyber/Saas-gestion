"""Pruebas contra un Postgres real (los triggers y los contadores atómicos son de Postgres).

Base de datos: TEST_DATABASE_URL o postgresql://postgres:postgres@localhost:5432/buhos_test.
El esquema se borra y se recrea al empezar.
"""
from __future__ import annotations

import os
import uuid

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/buhos_test"
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-solo-para-pruebas")
os.environ.setdefault("ALGORITHM", "HS256")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.database import engine  # noqa: E402
from app.db.init_db import create_tables  # noqa: E402
from app.main import app  # noqa: E402
from app.services import ratelimit  # noqa: E402

ALL_DAY = {d: [["00:00", "24:00"]] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


@pytest.fixture(scope="session", autouse=True)
def _schema():
    # Las pruebas borran el esquema entero: nunca contra una base que no sea de pruebas
    if "test" not in (engine.url.database or ""):
        pytest.exit(f"La base de pruebas debe llamarse *test* (es {engine.url.database!r}). No toco nada.", returncode=2)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    create_tables()
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    ratelimit.reset()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def owner(client):
    email = f"dueno-{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/register", json={"email": email, "password": "secreto-123", "full_name": "Dueño Ankara"})
    assert r.status_code == 200, r.text
    token = client.post("/login", json={"email": email, "password": "secreto-123"}).json()["access_token"]
    return {"token": token, "h": auth(token), "email": email}


@pytest.fixture()
def venue(client, owner):
    """Empresa con perfil de hostelería abierto 24 h y una carta mínima tipo kebab."""
    slug = f"ankara-{uuid.uuid4().hex[:6]}"
    r = client.post("/companies", json={"name": "Ankara Kebab", "slug": slug}, headers=owner["h"])
    cid = r.json()["id"]
    h = owner["h"]
    r = client.patch(f"/my/venues/{cid}/profile", headers=h, json={
        "display_name": "Ankara Kebab", "opening_hours": ALL_DAY, "delivery_enabled": True,
        "delivery_fee": "1.00", "delivery_min_order": "10.00", "payment_methods": ["cash", "card", "bizum"],
        "languages": ["es", "en", "fr"], "tags": ["halal"], "phone": "+34 941 89 71 50",
        "whatsapp": "34602552973", "address": "Calle Carmen Medrano 1", "city": "Logroño",
        "google_place_id": "ChIJUQUjoe1VRQ0RoEKpuucdgF0"})
    assert r.status_code == 200, r.text

    def post(path, body):
        res = client.post(f"/my/venues/{cid}/menu{path}", headers=h, json=body)
        assert res.status_code == 201, res.text
        return res.json()

    cat = post("/categories", {"name": "Kebab, Dürüm y Lahmacun"})
    drinks = post("/categories", {"name": "Bebidas", "position": 9})
    meat = post("/groups", {"name": "Carne", "min_select": 1, "max_select": 1, "options": [
        {"name": "Pollo"}, {"name": "Ternera"}, {"name": "Mixto"}, {"name": "Falafel", "allergens": ["gluten"]}]})
    sauce = post("/groups", {"name": "Salsa", "min_select": 1, "max_select": 1, "options": [
        {"name": "Blanca", "allergens": ["milk"]}, {"name": "Picante"}, {"name": "Sin salsa"}]})
    extras = post("/groups", {"name": "Extras", "min_select": 0, "max_select": 0, "options": [
        {"name": "Queso", "price_delta": "0.50", "allergens": ["milk"]}, {"name": "Extra de carne", "price_delta": "1.00"}]})
    menu_kebab = post("/products", {"category_id": cat["id"], "name": "Menú Kebab", "price": "7.00",
                                    "allergens": ["gluten"], "group_ids": [meat["id"], sauce["id"]]})
    kebab = post("/products", {"category_id": cat["id"], "name": "Kebab", "price": "5.00", "allergens": ["gluten"],
                               "removable_ingredients": ["Sin cebolla", "Sin tomate"],
                               "upsell_product_id": menu_kebab["id"],
                               "group_ids": [meat["id"], sauce["id"], extras["id"]]})
    coke = post("/products", {"category_id": drinks["id"], "name": "Coca-Cola lata", "price": "1.30",
                              "takeaway_tax_rate": "21"})
    opt = lambda group, name: next(o["id"] for o in group["options"] if o["name"] == name)  # noqa: E731
    return {
        "company_id": cid, "slug": slug, "h": h, "kebab": kebab, "menu_kebab": menu_kebab, "coke": coke,
        "pollo": opt(meat, "Pollo"), "ternera": opt(meat, "Ternera"), "blanca": opt(sauce, "Blanca"),
        "picante": opt(sauce, "Picante"), "queso": opt(extras, "Queso"), "extra_carne": opt(extras, "Extra de carne"),
        "groups": {"meat": meat, "sauce": sauce, "extras": extras},
    }


def new_ref() -> str:
    return uuid.uuid4().hex
