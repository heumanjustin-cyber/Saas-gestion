"""TPV: caja, cobros, devoluciones, factura completa, anulación, PIN, Verifactu y cierre Z."""
import random
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.db.database import engine
from app.services import verifactu as vf
from tests.conftest import auth, new_ref



def random_dni() -> str:
    """DNI de prueba con letra correcta, distinto en cada empresa (un NIF = una empresa)."""
    n = random.randint(10_000_000, 99_999_999)
    return f"{n}{'TRWAGMYFPDXBNJZSQVHLCKE'[n % 23]}"


@pytest.fixture()
def pos(client, venue):
    cid, h = venue["company_id"], venue["h"]
    bad = client.put(f"/my/venues/{cid}/fiscal", headers=h, json={"nif": "12345678A", "legal_name": "Ankara Kebab SL"})
    assert bad.status_code == 422
    nif = random_dni()
    r = client.put(f"/my/venues/{cid}/fiscal", headers=h, json={
        "nif": nif, "legal_name": "Ankara Kebab (datos de prueba)", "address": "Calle Carmen Medrano 1",
        "postal_code": "26005", "city": "Logroño", "environment": "test"})
    assert r.status_code == 200, r.text
    reg = client.post(f"/my/venues/{cid}/pos/registers", headers=h, json={"name": "Caja 1"}).json()
    tok = client.post(f"/my/venues/{cid}/pos/owner-session", headers=h, json={"register_id": reg["id"]}).json()
    return {**venue, "register": reg, "ph": auth(tok["access_token"]), "nif": nif}


def kebab_line(v, qty=1, extra=False):
    opts = [v["ternera"], v["blanca"]] + ([v["queso"]] if extra else [])
    return {"product_id": v["kebab"]["id"], "quantity": qty, "option_ids": opts, "removed": ["Sin cebolla"]}


def sale(client, p, lines, payments, **kw):
    return client.post("/pos/sales", headers=p["ph"], json={"lines": lines, "payments": payments, **kw})


def test_cobro_en_efectivo_con_cambio_y_registro_encadenado(client, pos):
    assert sale(client, pos, [kebab_line(pos)], [{"method": "cash", "amount": "5.00"}]).status_code == 409  # caja cerrada
    client.post("/pos/session/open", headers=pos["ph"], json={"opening_float": "100.00"})
    r = sale(client, pos, [kebab_line(pos, 2, extra=True), {"product_id": pos["coke"]["id"]}],
             [{"method": "cash", "amount": "12.30", "tendered": "20.00"}])
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["invoice_type"] == "F2" and t["full_number"].startswith("T1-") and t["full_number"].endswith("-000001")
    assert t["total"] == "12.30" and t["change"] == "7.70"
    assert t["lines"][0]["description"] == "Kebab (Ternera, Blanca, Queso, Sin cebolla)"
    assert t["tax_breakdown"] == [{"rate": "10.00", "base": "11.18", "tax": "1.12", "total": "12.30"}]
    assert t["order_numbers"] == ["001"]  # entra en cocina con número
    assert t["qr_url"].startswith(vf.QR_URL["test"]) and "numserie=T1-" in t["qr_url"]

    r2 = sale(client, pos, [kebab_line(pos)], [{"method": "card", "amount": "3.00"}, {"method": "cash", "amount": "2.00"}])
    assert r2.status_code == 201 and r2.json()["full_number"].endswith("-000002")
    chain = client.get(f"/my/venues/{pos['company_id']}/pos/fiscal-records", headers=pos["h"]).json()
    assert chain[1]["previous_hash"] is None and chain[0]["previous_hash"] == chain[1]["hash"]
    verify = client.get(f"/my/venues/{pos['company_id']}/pos/fiscal-records/verify", headers=pos["h"]).json()
    assert verify == {"records": 2, "ok": True, "errors": []}


def test_pagos_que_no_cuadran_y_ticket_vacio(client, pos):
    client.post("/pos/session/open", headers=pos["ph"], json={"opening_float": "0"})
    assert sale(client, pos, [kebab_line(pos)], [{"method": "cash", "amount": "4.00"}]).status_code == 422
    assert sale(client, pos, [kebab_line(pos)], [{"method": "card", "amount": "5.00", "tendered": "10"}]).status_code == 422
    assert sale(client, pos, [kebab_line(pos)], [{"method": "cash", "amount": "5.00", "tendered": "2"}]).status_code == 422
    assert sale(client, pos, [], [{"method": "cash", "amount": "1.00"}]).status_code == 422
    libre = sale(client, pos, [{"description": "Varios", "unit_price": "2.50", "quantity": 2}],
                 [{"method": "bizum", "amount": "5.00"}])
    assert libre.status_code == 201 and libre.json()["lines"][0]["description"] == "Varios"


def test_cobrar_pedidos_del_qr(client, pos):
    client.post("/pos/session/open", headers=pos["ph"], json={"opening_float": "0"})
    o = client.post(f"/api/public/venues/{pos['slug']}/orders", json={
        "client_ref": new_ref(), "fulfillment": "delivery", "customer_name": "Ana", "customer_phone": "612345678",
        "delivery_address": "Calle Laurel 5", "lines": [kebab_line(pos, 2)]}).json()
    unpaid = client.get("/pos/orders/unpaid", headers=pos["ph"]).json()
    order = next(x for x in unpaid if x["token"] == o["token"])
    r = sale(client, pos, [], [{"method": "card", "amount": "11.00"}], order_ids=[order["id"]])
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["total"] == "11.00" and t["channel"] == "web" and t["fulfillment"] == "delivery"  # pedido web, sin QR
    assert any(line["description"] == "Envío a domicilio" for line in t["lines"])
    assert client.get(f"/api/public/orders/{o['token']}").json()["payment_status"] == "paid"
    again = sale(client, pos, [], [{"method": "card", "amount": "11.00"}], order_ids=[order["id"]])
    assert again.status_code == 409


def test_refresco_para_llevar_al_21(client, pos):
    client.post("/pos/session/open", headers=pos["ph"], json={"opening_float": "0"})
    r = sale(client, pos, [{"product_id": pos["coke"]["id"]}, kebab_line(pos)],
             [{"method": "cash", "amount": "6.30"}], fulfillment="takeaway")
    rates = {row["rate"] for row in r.json()["tax_breakdown"]}
    assert rates == {"10.00", "21.00"}


def test_devolucion_parcial_r5_y_limites(client, pos):
    client.post("/pos/session/open", headers=pos["ph"], json={"opening_float": "50"})
    t = sale(client, pos, [kebab_line(pos, 3)], [{"method": "cash", "amount": "15.00"}]).json()
    line_id = t["lines"][0]["id"]
    url = f"/pos/invoices/{t['id']}/refund"
    r = client.post(url, headers=pos["ph"], json={"items": [{"line_id": line_id, "quantity": 1}], "method": "cash",
                                                   "reason": "Un kebab salió frío"})
    assert r.status_code == 201, r.text
    refund = r.json()
    assert refund["invoice_type"] == "R5" and refund["total"] == "-5.00" and refund["rectified"] == t["full_number"]
    assert refund["full_number"].startswith("R1-")
    assert client.get(f"/pos/invoices/{t['id']}", headers=pos["ph"]).json()["lines"][0]["refundable"] == "2"
    too_many = client.post(url, headers=pos["ph"], json={"items": [{"line_id": line_id, "quantity": 3}],
                                                         "method": "cash", "reason": "x" * 5})
    assert too_many.status_code == 422
    rest = client.post(url, headers=pos["ph"], json={"method": "cash", "reason": "Cliente se va"})
    assert rest.json()["total"] == "-10.00"
    assert client.post(url, headers=pos["ph"], json={"method": "cash", "reason": "otra vez"}).status_code == 409


def test_anulacion_y_factura_completa(client, pos):
    client.post("/pos/session/open", headers=pos["ph"], json={"opening_float": "0"})
    wrong = sale(client, pos, [kebab_line(pos)], [{"method": "cash", "amount": "5.00"}]).json()
    v = client.post(f"/pos/invoices/{wrong['id']}/void", headers=pos["ph"], json={"reason": "Cobrado dos veces"})
    assert v.status_code == 200 and v.json()["status"] == "voided"
    assert client.post(f"/pos/invoices/{wrong['id']}/void", headers=pos["ph"], json={"reason": "otra"}).status_code == 409

    t1 = sale(client, pos, [kebab_line(pos)], [{"method": "card", "amount": "5.00"}]).json()
    t2 = sale(client, pos, [{"product_id": pos["coke"]["id"]}], [{"method": "card", "amount": "1.30"}]).json()
    bad = client.post("/pos/invoices/full-invoice", headers=pos["ph"],
                      json={"invoice_ids": [t1["id"]], "nif": "B0000000X", "name": "Empresa SL"})
    assert bad.status_code == 422
    f3 = client.post("/pos/invoices/full-invoice", headers=pos["ph"], json={
        "invoice_ids": [t1["id"], t2["id"]], "nif": "12345678z", "name": "Cliente con factura",
        "address": "Gran Vía 1, Logroño"})
    assert f3.status_code == 201, f3.text
    f = f3.json()
    assert f["invoice_type"] == "F3" and f["full_number"].startswith("F1-") and f["total"] == "6.30"
    assert f["customer"]["nif"] == "12345678Z" and f["payments"] == []
    dup = client.post("/pos/invoices/full-invoice", headers=pos["ph"],
                      json={"invoice_ids": [t1["id"]], "nif": "12345678Z", "name": "Cliente"})
    assert dup.status_code == 409

    records = client.get(f"/my/venues/{pos['company_id']}/pos/fiscal-records", headers=pos["h"]).json()
    types = [(r["type"], r["tipo_factura"]) for r in reversed(records)]
    assert types == [("alta", "F2"), ("anulacion", None), ("alta", "F2"), ("alta", "F2"), ("alta", "F3")]
    assert client.get(f"/my/venues/{pos['company_id']}/pos/fiscal-records/verify", headers=pos["h"]).json()["ok"]
    xml = client.get(f"/my/venues/{pos['company_id']}/pos/fiscal-records/5/xml", headers=pos["h"]).text
    assert "<sum1:FacturasSustituidas>" in xml and "<sum1:IDDestinatario>" in xml


def test_la_base_de_datos_impide_retocar_tickets(client, pos):
    client.post("/pos/session/open", headers=pos["ph"], json={"opening_float": "0"})
    t = sale(client, pos, [kebab_line(pos)], [{"method": "cash", "amount": "5.00"}]).json()
    for stmt in (f"UPDATE invoices SET total = 1 WHERE id = '{t['id']}'",
                 f"DELETE FROM invoices WHERE id = '{t['id']}'",
                 f"UPDATE invoice_lines SET line_total = 1 WHERE invoice_id = '{t['id']}'",
                 f"DELETE FROM payments WHERE invoice_id = '{t['id']}'",
                 f"UPDATE fiscal_records SET importe_total = '1.00' WHERE invoice_id = '{t['id']}'",
                 f"DELETE FROM fiscal_records WHERE invoice_id = '{t['id']}'"):
        with pytest.raises(Exception) as exc:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        assert "BUHOS" in str(exc.value)
    # El estado de remisión a la AEAT sí puede cambiar
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE fiscal_records SET submission_status = 'sent' WHERE invoice_id = '{t['id']}'"))


def test_cierre_z_con_arqueo(client, pos):
    ph = pos["ph"]
    client.post("/pos/session/open", headers=ph, json={"opening_float": "100.00"})
    assert client.post("/pos/session/open", headers=ph, json={"opening_float": "1"}).status_code == 409
    sale(client, pos, [kebab_line(pos, 2)], [{"method": "cash", "amount": "10.00", "tendered": "20"}])
    t = sale(client, pos, [kebab_line(pos)], [{"method": "card", "amount": "5.00"}]).json()
    client.post(f"/pos/invoices/{t['id']}/refund", headers=ph, json={"method": "card", "reason": "Error de pedido"})
    client.post("/pos/session/movements", headers=ph, json={"kind": "out", "amount": "20.00", "reason": "Pan"})
    x = client.get("/pos/session", headers=ph).json()["session"]
    assert x["expected_cash"] == "90.00" and x["net_sales"] == "10.00" and x["payments"] == {"card": "0.00", "cash": "10.00"}
    assert "Informe X" in client.get(f"/pos/sessions/{x['session_id']}/z-report", headers=ph).text
    # Contamos 1 billete de 50, 2 de 20 y una moneda de 0,50: sobran 50 céntimos
    z = client.post("/pos/session/close", headers=ph, json={"breakdown": {"50": 1, "20": 2, "0.50": 1}}).json()["z_report"]
    assert z["z_number"] == 1 and z["counted_cash"] == "90.50" and z["difference"] == "0.50"
    assert z["tickets"] == 2 and z["refund_count"] == 1 and z["channels"]["pos"]["tickets"] == 2
    html = client.get(f"/pos/sessions/{z['session_id']}/z-report", headers=ph).text
    assert "CIERRE Z Nº 1" in html and "90,50 €" in html
    assert client.get("/pos/session", headers=ph).json()["session"] is None


def test_ticket_imprimible_con_qr_tributario(client, pos):
    client.post("/pos/session/open", headers=pos["ph"], json={"opening_float": "0"})
    t = sale(client, pos, [kebab_line(pos)], [{"method": "cash", "amount": "5.00", "tendered": "10"}]).json()
    html = client.get(f"/pos/invoices/{t['id']}/ticket", headers=pos["ph"]).text
    assert t["full_number"] in html and "QR tributario" in html and "MODO PRUEBAS" in html
    assert f"NIF {pos['nif']}" in html and "Cambio" in html and "5,00 €" in html
    assert "<svg" in html


def test_tablet_emparejada_y_pin_del_personal(client, pos):
    cid, h = pos["company_id"], pos["h"]
    emp = client.post("/employees", headers=h, json={"company_id": cid, "first_name": "Omar", "last_name": "K"}).json()
    assert client.put(f"/my/venues/{cid}/pos/staff-pins", headers=h,
                      json={"employee_id": emp["id"], "pin": "1111"}).status_code == 422  # demasiado fácil
    assert client.put(f"/my/venues/{cid}/pos/staff-pins", headers=h,
                      json={"employee_id": emp["id"], "pin": "4826", "role": "cashier"}).status_code == 200
    code = client.post(f"/my/venues/{cid}/pos/pairing-codes", headers=h,
                       json={"register_id": pos["register"]["id"], "device_name": "Tablet barra"}).json()["code"]
    paired = client.post("/pos/pair", json={"code": code}).json()
    assert client.post("/pos/pair", json={"code": code}).status_code == 401  # un solo uso
    dev = {"X-Device-Token": paired["device_token"]}
    staff = client.get("/pos/staff", headers=dev).json()
    assert staff == [{"employee_id": emp["id"], "name": "Omar", "role": "cashier"}]
    for _ in range(4):
        assert client.post("/pos/login", headers=dev, json={"employee_id": emp["id"], "pin": "0000"}).status_code == 401
    assert client.post("/pos/login", headers=dev, json={"employee_id": emp["id"], "pin": "0001"}).status_code == 401
    assert client.post("/pos/login", headers=dev, json={"employee_id": emp["id"], "pin": "4826"}).status_code == 423

    with engine.begin() as conn:  # el encargado lo desbloquea
        conn.execute(text(f"UPDATE pos_staff_pins SET locked_until = NULL WHERE employee_id = '{emp['id']}'"))
    login = client.post("/pos/login", headers=dev, json={"employee_id": emp["id"], "pin": "4826"}).json()
    ch = auth(login["access_token"])
    assert client.get("/pos/me", headers=ch).json()["role"] == "cashier"
    client.post("/pos/session/open", headers=ch, json={"opening_float": "0"})
    t = sale(client, {**pos, "ph": ch}, [kebab_line(pos)], [{"method": "cash", "amount": "5.00"}])
    assert t.json()["created_by"] == "Omar"
    no = client.post(f"/pos/invoices/{t.json()['id']}/refund", headers=ch, json={"method": "cash", "reason": "Prueba"})
    assert no.status_code == 403  # el camarero no devuelve dinero
    # La cocina con ese token ve los pedidos
    assert client.get(f"/my/venues/{cid}/orders", headers=ch).status_code == 200

    devices = client.get(f"/my/venues/{cid}/pos/devices", headers=h).json()
    client.delete(f"/my/venues/{cid}/pos/devices/{devices[0]['id']}", headers=h)
    assert client.get("/pos/me", headers=ch).status_code == 401  # tablet desvinculada
    assert client.get("/pos/staff", headers=dev).status_code == 401


def test_limite_factura_simplificada(client, pos):
    client.post("/pos/session/open", headers=pos["ph"], json={"opening_float": "0"})
    r = sale(client, pos, [{"description": "Catering evento", "unit_price": "3500.00"}],
             [{"method": "card", "amount": "3500.00"}])
    assert r.status_code == 422 and "3.000" in r.json()["detail"]


def test_concurrencia_numeracion_sin_huecos(client, pos):
    """Varios cobros seguidos: numeración y cadena siguen el mismo orden."""
    client.post("/pos/session/open", headers=pos["ph"], json={"opening_float": "0"})
    numbers = [sale(client, pos, [kebab_line(pos)], [{"method": "card", "amount": "5.00"}]).json()["full_number"]
               for _ in range(5)]
    assert [int(n.rsplit("-", 1)[1]) for n in numbers] == [1, 2, 3, 4, 5]
    recs = client.get(f"/my/venues/{pos['company_id']}/pos/fiscal-records", headers=pos["h"]).json()
    assert [r["num_serie"] for r in reversed(recs)] == numbers
    assert Decimal(recs[0]["importe_total"]) == Decimal("5.00")


def test_tokens_raros_no_rompen_nada(client, pos):
    from jose import jwt as _jwt

    from app.core.config import ALGORITHM, SECRET_KEY

    assert client.get("/pos/me", headers=pos["h"]).status_code == 401  # token de usuario en el TPV
    assert client.get("/pos/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401
    nosub = _jwt.encode({"x": 1}, SECRET_KEY, algorithm=ALGORITHM)
    r = client.get(f"/my/venues/{pos['company_id']}/orders", headers={"Authorization": f"Bearer {nosub}"})
    assert r.status_code == 401
    assert client.get("/pos/me").status_code == 401
