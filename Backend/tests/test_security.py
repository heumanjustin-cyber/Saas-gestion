"""Seguridad: sesión obligatoria, aislamiento entre empresas, contraseñas y tokens."""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt
from sqlalchemy import text

from app.core.config import ALGORITHM, SECRET_KEY
from app.db.database import engine
from tests.conftest import auth

ZERO = "00000000-0000-0000-0000-000000000000"

PROTECTED_GET = [
    "/companies", "/clients", "/employees", "/services", "/locations", "/appointments", "/appointments/today",
    "/resources", "/resource-bookings", "/blocked-times", "/employee-schedules", "/dashboard", "/dashboard/details",
    "/access/permissions", "/access/roles", "/access/memberships", "/me",
]


def new_user(client, name="Otro dueño"):
    email = f"user-{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/register", json={"email": email, "password": "clave-segura-1", "full_name": name})
    assert r.status_code == 200, r.text
    return {"email": email, "h": auth(r.json()["access_token"]), "id": r.json()["id"]}


def new_company(client, h, name="Empresa"):
    slug = f"empresa-{uuid.uuid4().hex[:8]}"
    r = client.post("/companies", headers=h, json={"name": name, "slug": slug})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_rutas_antiguas_piden_sesion(client):
    for path in PROTECTED_GET:
        assert client.get(path).status_code == 401, path
    for path in ("/clients", "/employees", "/services", "/appointments"):
        assert client.delete(f"{path}/{ZERO}").status_code == 401, path
    assert client.post("/locations", json={"company_id": ZERO, "name": "X"}).status_code == 401
    assert client.post("/blocked-times", json={"employee_id": ZERO, "starts_at": "2026-11-10T10:00:00Z",
                                               "ends_at": "2026-11-10T11:00:00Z"}).status_code == 401
    assert client.post("/employee-schedules", json={"employee_id": ZERO, "weekday": 1, "start_time": "09:00",
                                                    "end_time": "14:00"}).status_code == 401


def test_aislamiento_entre_empresas(client, owner):
    a = owner["h"]
    ca = new_company(client, a, "Peluquería A")
    cli = client.post("/clients", headers=a, json={"company_id": ca, "first_name": "Lucía", "last_name": "A",
                                                   "phone": "600000001"}).json()
    emp = client.post("/employees", headers=a, json={"company_id": ca, "first_name": "Ana", "last_name": "A"}).json()
    srv = client.post("/services", headers=a, json={"company_id": ca, "name": "Corte", "duration_minutes": 30,
                                                    "price": 15}).json()
    client.post("/locations", headers=a, json={"company_id": ca, "name": "Centro"})

    b = new_user(client)["h"]
    cb = new_company(client, b, "Barbería B")

    # B no ve nada de A
    assert [c["id"] for c in client.get("/companies", headers=b).json()] == [cb]
    for path in ("/clients", "/employees", "/services", "/locations", "/appointments", "/blocked-times",
                 "/employee-schedules", "/access/roles", "/access/memberships"):
        data = client.get(path, headers=b).json()
        assert all(str(x.get("company_id", cb)) == cb for x in data if isinstance(x, dict)), path
        assert not any(str(x.get("id")) in (cli["id"], emp["id"], srv["id"]) for x in data if isinstance(x, dict)), path
    dash = client.get("/dashboard", headers=b).json()
    assert dash["companies"] == 1 and dash["clients"] == 0 and dash["employees"] == 0

    # B no puede borrar, crear ni enlazar cosas de A
    r = client.delete(f"/clients/{cli['id']}", headers=b)
    assert r.status_code == 404 and r.json()["error"] == "Cliente no encontrado"
    assert any(c["id"] == cli["id"] for c in client.get("/clients", headers=a).json() if "id" in c) or \
        client.get("/clients", headers=a).json()
    assert client.delete(f"/employees/{emp['id']}", headers=b).status_code == 404
    assert client.delete(f"/services/{srv['id']}", headers=b).status_code == 404
    assert client.post("/locations", headers=b, json={"company_id": ca, "name": "Intruso"}).status_code == 403
    assert client.post("/blocked-times", headers=b, json={"employee_id": emp["id"], "starts_at": "2026-11-10T10:00:00Z",
                                                          "ends_at": "2026-11-10T11:00:00Z"}).status_code == 404
    assert client.post("/employee-schedules", headers=b, json={"employee_id": emp["id"], "weekday": 1,
                                                               "start_time": "09:00", "end_time": "14:00"}).status_code == 404
    assert client.get("/my/availability", headers=b, params={"employee_id": emp["id"], "target_date": "2026-11-10",
                                                              "duration_minutes": 30}).status_code == 404
    cita = client.post("/appointments", headers=b, json={"company_id": cb, "employee_id": emp["id"],
                                                         "starts_at": "2026-11-10T10:00:00Z", "ends_at": "2026-11-10T10:30:00Z"})
    assert cita.status_code == 422  # no se puede enlazar la empleada de otra empresa

    # A sigue viendo y gestionando lo suyo
    assert any(c.get("first_name") == "Lucía" for c in client.get("/clients", headers=a).json())
    assert client.delete(f"/services/{srv['id']}", headers=a).json() == {"message": "Servicio eliminado"}


def test_contrasenas_scrypt_y_migracion_de_las_antiguas(client):
    u = new_user(client)
    with engine.begin() as conn:
        h = conn.execute(text("SELECT hashed_password FROM users WHERE email = :e"), {"e": u["email"]}).scalar_one()
    assert h.startswith("scrypt$") and u["email"] not in h

    # Usuario con el hash antiguo (SHA-256 sin sal): entra y se le convierte a scrypt
    legacy = f"antiguo-{uuid.uuid4().hex[:6]}@test.com"
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id, email, hashed_password, full_name, is_active, is_verified) "
                          "VALUES (:id, :e, :h, 'Antiguo', true, true)"),
                     {"id": str(uuid.uuid4()), "e": legacy, "h": hashlib.sha256(b"123456").hexdigest()})
    assert client.post("/login", json={"email": legacy, "password": "123456"}).status_code == 200
    with engine.begin() as conn:
        assert conn.execute(text("SELECT hashed_password FROM users WHERE email = :e"),
                            {"e": legacy}).scalar_one().startswith("scrypt$")
    assert client.post("/login", json={"email": legacy.upper(), "password": "123456"}).status_code == 200

    bad = client.post("/login", json={"email": legacy, "password": "mala"})
    assert bad.status_code == 401 and bad.json()["error"] == "Email o contraseña incorrectos"
    nobody = client.post("/login", json={"email": "nadie@test.com", "password": "x"})
    assert nobody.status_code == 401 and nobody.json() == bad.json()  # no revela si el email existe


def test_limite_de_intentos_de_login(client):
    u = new_user(client)
    codes = [client.post("/login", json={"email": u["email"], "password": "mala"}).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_tokens_caducados_o_ajenos_dan_401(client):
    u = new_user(client)
    expired = jwt.encode({"sub": u["id"], "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, SECRET_KEY,
                         algorithm=ALGORITHM)
    assert client.get("/me", headers=auth(expired)).status_code == 401
    assert client.get("/me", headers=auth("no.es.un.jwt")).status_code == 401
    pos = jwt.encode({"typ": "pos", "cid": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                     SECRET_KEY, algorithm=ALGORITHM)
    assert client.get("/me", headers=auth(pos)).status_code == 401
    forged = jwt.encode({"sub": u["id"], "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "otra-clave",
                        algorithm="HS256")
    assert client.get("/me", headers=auth(forged)).status_code == 401
    assert client.get("/me", headers=u["h"]).status_code == 200


def test_registro_y_slug_validados(client):
    assert client.post("/register", json={"email": "corto@test.com", "password": "1234567",
                                          "full_name": "Corto"}).status_code == 422
    assert client.post("/register", json={"email": "sin-arroba", "password": "clave-larga-1",
                                          "full_name": "Mal"}).status_code == 422
    u = new_user(client)
    dup = client.post("/register", json={"email": u["email"].upper(), "password": "clave-larga-1", "full_name": "Dup"})
    assert dup.status_code == 400
    assert client.post("/companies", headers=u["h"], json={"name": "Mi Bar", "slug": "Mi Bar/../admin"}).status_code == 422
    ok = client.post("/companies", headers=u["h"], json={"name": "Mi Bar", "slug": f"mi-bar-{uuid.uuid4().hex[:5]}"})
    assert ok.status_code == 200
    again = client.post("/companies", headers=u["h"], json={"name": "Otro", "slug": ok.json()["slug"]})
    assert again.status_code == 409 and again.json()["error"] == "Slug already exists"
