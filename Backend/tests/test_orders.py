"""Pedido desde el QR: precio en servidor, reglas de negocio, seguimiento y cocina."""
from datetime import datetime, timedelta, timezone

from tests.conftest import new_ref


def order_body(v, **kw):
    body = {
        "client_ref": new_ref(), "fulfillment": "takeaway", "customer_name": "Lucía", "customer_phone": "612345678",
        "payment_method": "card", "language": "es",
        "lines": [
            {"product_id": v["kebab"]["id"], "quantity": 2, "option_ids": [v["ternera"], v["blanca"], v["queso"]],
             "removed": ["Sin cebolla"]},
            {"product_id": v["coke"]["id"], "quantity": 1},
        ],
    }
    body.update(kw)
    return body


def place(client, v, **kw):
    return client.post(f"/api/public/venues/{v['slug']}/orders", json=order_body(v, **kw))


def test_carta_publica_con_alergenos_y_menu(client, venue):
    r = client.get(f"/api/public/venues/{venue['slug']}")
    assert r.status_code == 200
    data = r.json()
    assert data["venue"]["is_open"] is True
    assert data["venue"]["review_url"].startswith("https://search.google.com/local/writereview?placeid=")
    kebab = next(p for c in data["menu"] for p in c["products"] if p["name"] == "Kebab")
    assert kebab["allergens"] == ["gluten"]
    assert kebab["upsell"]["extra"] == "2.00"  # «¿Lo hacemos menú? +2,00 €»
    assert [g["name"] for g in kebab["groups"]] == ["Carne", "Salsa", "Extras"]


def test_pedido_precio_calculado_en_servidor_e_idempotente(client, venue):
    body = order_body(venue)
    r = client.post(f"/api/public/venues/{venue['slug']}/orders", json=body)
    assert r.status_code == 201, r.text
    o = r.json()
    # 2 x (5,00 + 0,50 queso) + 1,30 = 12,30. El cliente no manda precios.
    assert o["total"] == "12.30" and o["created"] is True
    assert o["lines"][0]["modifiers"][2]["name"] == "Queso" and o["lines"][0]["removed"] == ["Sin cebolla"]
    assert o["number"] == "001"
    again = client.post(f"/api/public/venues/{venue['slug']}/orders", json=body)
    assert again.json()["token"] == o["token"] and again.json()["created"] is False
    second = place(client, venue)
    assert second.json()["number"] == "002"  # correlativo, nunca repetido


def test_reglas_de_la_carta(client, venue):
    missing = place(client, venue, lines=[{"product_id": venue["kebab"]["id"], "option_ids": [venue["pollo"]]}])
    assert missing.status_code == 422 and missing.json()["detail"]["code"] == "missing_choice"
    two_meats = place(client, venue, lines=[{"product_id": venue["kebab"]["id"],
                                             "option_ids": [venue["pollo"], venue["ternera"], venue["blanca"]]}])
    assert two_meats.json()["detail"]["code"] == "too_many_choices"
    bad_removal = place(client, venue, lines=[{"product_id": venue["kebab"]["id"],
                                               "option_ids": [venue["pollo"], venue["blanca"]], "removed": ["Sin carne"]}])
    assert bad_removal.json()["detail"]["code"] == "invalid_removal"
    foreign = place(client, venue, lines=[{"product_id": venue["coke"]["id"], "option_ids": [venue["queso"]]}])
    assert foreign.json()["detail"]["code"] == "invalid_option"


def test_agotado_se_refleja_al_momento(client, venue):
    r = client.patch(f"/my/venues/{venue['company_id']}/menu/products/{venue['coke']['id']}/availability",
                     headers=venue["h"], json={"is_available": False})
    assert r.status_code == 200
    res = place(client, venue)
    assert res.status_code == 422 and res.json()["detail"]["code"] == "sold_out"
    menu = client.get(f"/api/public/venues/{venue['slug']}").json()["menu"]
    coke = next(p for c in menu for p in c["products"] if p["name"] == "Coca-Cola lata")
    assert coke["available"] is False


def test_domicilio_minimo_y_envio(client, venue):
    small = place(client, venue, fulfillment="delivery", delivery_address="Calle Laurel 5, 2ºB",
                  lines=[{"product_id": venue["coke"]["id"], "quantity": 2}])
    assert small.status_code == 422 and small.json()["detail"]["code"] == "min_order"
    no_phone = place(client, venue, fulfillment="delivery", customer_phone=None, delivery_address="Calle Laurel 5")
    assert no_phone.json()["detail"]["code"] == "phone_required"
    ok = place(client, venue, fulfillment="delivery", delivery_address="Calle Laurel 5, 2ºB")
    assert ok.status_code == 201
    assert ok.json()["delivery_fee"] == "1.00" and ok.json()["total"] == "13.30"


def test_mesa_solo_con_qr_de_la_mesa(client, venue):
    no_table = place(client, venue, fulfillment="dine_in")
    assert no_table.json()["detail"]["code"] == "table_required"
    tables = client.post(f"/my/venues/{venue['company_id']}/tables/bulk", headers=venue["h"],
                         json={"count": 4, "prefix": "Mesa"}).json()
    code = tables[2]["qr"]["code"]
    ok = place(client, venue, fulfillment="dine_in", qr_code=code, customer_name=None)
    assert ok.status_code == 201 and ok.json()["table"] == "Mesa 3"


def test_cerrado_pausado_y_programado(client, venue):
    cid, h = venue["company_id"], venue["h"]
    today = datetime.now(timezone.utc).astimezone().strftime("%a").lower()[:3]
    closed_all = {d: [] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    client.patch(f"/my/venues/{cid}/profile", headers=h, json={"opening_hours": closed_all})
    r = place(client, venue)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "closed"

    # Abierto 24 h otra vez y pausa de 20 minutos porque la cocina va a tope
    client.patch(f"/my/venues/{cid}/profile", headers=h,
                 json={"opening_hours": {d: [["00:00", "24:00"]] for d in closed_all}})
    client.post(f"/my/venues/{cid}/pause", headers=h, json={"minutes": 20})
    paused = place(client, venue)
    assert paused.status_code == 409 and paused.json()["detail"]["code"] == "paused"
    client.post(f"/my/venues/{cid}/pause", headers=h, json={"minutes": 0})

    later = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    scheduled = place(client, venue, scheduled_for=later)
    assert scheduled.status_code == 201 and scheduled.json()["scheduled_for"]
    too_soon = place(client, venue, scheduled_for=(datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat())
    assert too_soon.json()["detail"]["code"] == "too_soon"
    assert today  # el día no importa: el horario cubre la semana entera


def test_trampa_para_bots(client, venue):
    r = place(client, venue, website="http://spam.example")
    assert r.status_code == 422


def test_seguimiento_y_cocina(client, venue):
    o = place(client, venue).json()
    token = o["token"]
    track = client.get(f"/api/public/orders/{token}").json()
    assert track["status"] == "pending" and track["can_cancel"] is True

    board = client.get(f"/my/venues/{venue['company_id']}/orders", headers=venue["h"]).json()["orders"]
    staff = next(x for x in board if x["token"] == token)
    assert staff["customer_phone"] == "+34612345678"  # normalizado
    oid = staff["id"]
    base = f"/my/venues/{venue['company_id']}/orders/{oid}/status"
    assert client.post(base, headers=venue["h"], json={"status": "accepted", "eta_minutes": 12}).status_code == 200
    assert client.post(f"/api/public/orders/{token}/cancel").status_code == 409  # ya está en cocina
    assert client.post(base, headers=venue["h"], json={"status": "preparing"}).json()["status"] == "preparing"
    assert client.post(base, headers=venue["h"], json={"status": "ready"}).json()["status_label"] == "¡Listo!"
    assert client.post(base, headers=venue["h"], json={"status": "accepted"}).status_code == 409
    done = client.post(base, headers=venue["h"], json={"status": "completed"}).json()
    assert done["status"] == "completed" and done["completed_at"]
    en = client.get(f"/api/public/orders/{token}?lang=en").json()
    assert en["status_label"] == "Delivered"


def test_rechazo_necesita_motivo_y_cancelacion_del_cliente(client, venue):
    o = place(client, venue).json()
    oid = next(x["id"] for x in client.get(f"/my/venues/{venue['company_id']}/orders", headers=venue["h"]).json()["orders"]
               if x["token"] == o["token"])
    r = client.post(f"/my/venues/{venue['company_id']}/orders/{oid}/status", headers=venue["h"], json={"status": "rejected"})
    assert r.status_code == 422
    o2 = place(client, venue).json()
    assert client.post(f"/api/public/orders/{o2['token']}/cancel").json()["status"] == "cancelled"


def test_otro_dueno_no_ve_mis_pedidos(client, venue):
    other = client.post("/register", json={"email": f"otro-{new_ref()[:6]}@test.com", "password": "x12345678",
                                           "full_name": "Otro"})
    h = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get(f"/my/venues/{venue['company_id']}/orders", headers=h).status_code == 403
    assert client.patch(f"/my/venues/{venue['company_id']}/menu/products/{venue['kebab']['id']}/availability",
                        headers=h, json={"is_available": False}).status_code == 403


def test_limite_de_pedidos_por_ip(client, venue):
    codes = [place(client, venue).status_code for _ in range(7)]
    assert codes[:6] == [201] * 6 and codes[6] == 429
