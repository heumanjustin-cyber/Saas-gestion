"""La huella se comprueba con los tres ejemplos oficiales de la AEAT
(«Detalle de las especificaciones técnicas para generación de la huella o hash»)."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.services import verifactu as vf

AEAT_1 = "3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60"
AEAT_2 = "F7B94CFD8924EDFF273501B01EE5153E4CE8F259766F88CF6ACB8935802A2B97"
AEAT_3 = "177547C0D57AC74748561D054A9CEC14B4C4EA23D1BEFD6F2E69E3A388F90C68"


def test_huella_primer_registro_ejemplo_aeat():
    h = vf.hash_alta(nif="89890001K", num_serie="12345678/G33", fecha="01-01-2024", tipo_factura="F1",
                     cuota_total="12.35", importe_total="123.45", huella_anterior=None,
                     fecha_hora_huso="2024-01-01T19:20:30+01:00")
    assert h == AEAT_1


def test_huella_encadenada_ejemplo_aeat():
    h = vf.hash_alta(nif="89890001K", num_serie="12345679/G34", fecha="01-01-2024", tipo_factura="F1",
                     cuota_total="12.35", importe_total="123.45", huella_anterior=AEAT_1,
                     fecha_hora_huso="2024-01-01T19:20:35+01:00")
    assert h == AEAT_2


def test_huella_anulacion_ejemplo_aeat():
    h = vf.hash_anulacion(nif="89890001K", num_serie="12345679/G34", fecha="01-01-2024",
                          huella_anterior=AEAT_2, fecha_hora_huso="2024-01-01T19:20:40+01:00")
    assert h == AEAT_3


def test_formatos():
    assert vf.fmt_amount(Decimal("7")) == "7.00"
    assert vf.fmt_amount("12.345") == "12.35"  # redondeo comercial
    assert vf.fmt_amount(Decimal("-3.5")) == "-3.50"
    assert vf.fmt_fecha(date(2026, 11, 7)) == "07-11-2026"
    madrid = timezone(timedelta(hours=1))
    assert vf.fmt_timestamp(datetime(2026, 11, 7, 21, 5, 9, 123456, tzinfo=madrid)) == "2026-11-07T21:05:09+01:00"


def test_qr_url_codifica_la_serie():
    url = vf.qr_url(nif="89890001K", num_serie="12345678&G33", fecha="01-01-2024", importe_total="241.40",
                    environment="test")
    assert url.startswith("https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR?")
    assert "numserie=12345678%26G33" in url and "importe=241.40" in url and "fecha=01-01-2024" in url
    assert vf.qr_url(nif="X", num_serie="T1-1", fecha="01-01-2027", importe_total="1.00",
                     environment="production").startswith("https://www2.agenciatributaria.gob.es/")


def test_verify_chain_detecta_alteraciones():
    recs = [
        {"sequence": 1, "record_type": "alta", "issuer_nif": "89890001K", "num_serie": "12345678/G33",
         "fecha_expedicion": "01-01-2024", "tipo_factura": "F1", "cuota_total": "12.35", "importe_total": "123.45",
         "previous_hash": None, "hash": AEAT_1, "generated_at": "2024-01-01T19:20:30+01:00"},
        {"sequence": 2, "record_type": "alta", "issuer_nif": "89890001K", "num_serie": "12345679/G34",
         "fecha_expedicion": "01-01-2024", "tipo_factura": "F1", "cuota_total": "12.35", "importe_total": "123.45",
         "previous_hash": AEAT_1, "hash": AEAT_2, "generated_at": "2024-01-01T19:20:35+01:00"},
        {"sequence": 3, "record_type": "anulacion", "issuer_nif": "89890001K", "num_serie": "12345679/G34",
         "fecha_expedicion": "01-01-2024", "tipo_factura": None, "cuota_total": None, "importe_total": None,
         "previous_hash": AEAT_2, "hash": AEAT_3, "generated_at": "2024-01-01T19:20:40+01:00"},
    ]
    assert vf.verify_chain(recs) == []
    recs[1]["importe_total"] = "1.45"  # alguien «retoca» un ticket
    errors = vf.verify_chain(recs)
    assert len(errors) == 1 and "alterado" in errors[0]


def test_xml_alta_tiene_encadenamiento_y_desglose():
    sif = {"producer_name": "BUHOS OS", "producer_nif": "B00000000", "name": "BUHOS TPV", "id": "BT",
           "version": "1.0.0", "installation": "1"}
    payload = {"nif": "B26000000", "num_serie": "T1-2026-000001", "fecha": "07-11-2026", "nombre_emisor": "Ankara",
               "tipo_factura": "F2", "desglose": [{"tipo": "10.00", "base": "6.36", "cuota": "0.64"}],
               "cuota_total": "0.64", "importe_total": "7.00", "anterior": None,
               "fecha_hora_huso": "2026-11-07T21:05:09+01:00", "huella": "A" * 64}
    xml = vf.build_envelope([vf.build_registro_alta(payload, sif)], "B26000000", "Ankara")
    assert "<sum1:PrimerRegistro>S</sum1:PrimerRegistro>" in xml
    assert "<sum1:TipoFactura>F2</sum1:TipoFactura>" in xml
    assert "<sum1:CuotaRepercutida>0.64</sum1:CuotaRepercutida>" in xml
