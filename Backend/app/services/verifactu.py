"""Verifactu: huella encadenada, QR tributario y XML de remisión a la AEAT.

Fuentes: RD 1007/2023, Orden HAC/1177/2024 y las especificaciones técnicas de
la AEAT (huella de registros y código QR). La huella está comprobada contra
los tres ejemplos oficiales de la AEAT (ver tests/test_verifactu.py).

Plazos (RDL 15/2025): sociedades desde el 1-1-2027; autónomos y resto desde el 1-7-2027.

Pendiente antes de producción: validar el XML contra el XSD oficial en el
entorno de pruebas de la AEAT y enviarlo con el certificado electrónico del
obligado (mTLS). Este módulo solo construye los datos; no envía nada.
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import quote

QR_URL = {
    "production": "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR",
    "test": "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR",
}

NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_LR = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroLR.xsd"
NS_INFO = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"

TWO = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


def fmt_amount(value) -> str:
    """Importe con punto y dos decimales: 12.35, 7.00, -3.50."""
    return f"{money(value):.2f}"


def fmt_fecha(d: date | datetime) -> str:
    """Fecha de expedición en formato AEAT: DD-MM-AAAA."""
    return d.strftime("%d-%m-%Y")


def fmt_timestamp(dt: datetime) -> str:
    """FechaHoraHusoGenRegistro: AAAA-MM-DDThh:mm:ss+hh:mm (con huso horario)."""
    if dt.tzinfo is None:
        raise ValueError("La fecha del registro debe llevar zona horaria")
    return dt.replace(microsecond=0).isoformat()


def _sha256_upper(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def hash_alta(*, nif: str, num_serie: str, fecha: str, tipo_factura: str, cuota_total: str,
              importe_total: str, huella_anterior: str | None, fecha_hora_huso: str) -> str:
    """Huella de un registro de alta. Los valores van tal cual se envían en el XML."""
    chain = (
        f"IDEmisorFactura={nif.strip()}"
        f"&NumSerieFactura={num_serie.strip()}"
        f"&FechaExpedicionFactura={fecha.strip()}"
        f"&TipoFactura={tipo_factura.strip()}"
        f"&CuotaTotal={cuota_total.strip()}"
        f"&ImporteTotal={importe_total.strip()}"
        f"&Huella={(huella_anterior or '').strip()}"
        f"&FechaHoraHusoGenRegistro={fecha_hora_huso.strip()}"
    )
    return _sha256_upper(chain)


def hash_anulacion(*, nif: str, num_serie: str, fecha: str, huella_anterior: str | None,
                   fecha_hora_huso: str) -> str:
    chain = (
        f"IDEmisorFacturaAnulada={nif.strip()}"
        f"&NumSerieFacturaAnulada={num_serie.strip()}"
        f"&FechaExpedicionFacturaAnulada={fecha.strip()}"
        f"&Huella={(huella_anterior or '').strip()}"
        f"&FechaHoraHusoGenRegistro={fecha_hora_huso.strip()}"
    )
    return _sha256_upper(chain)


def qr_url(*, nif: str, num_serie: str, fecha: str, importe_total: str, environment: str = "test") -> str:
    """URL de cotejo que va dentro del «QR tributario» del ticket (30x30 a 40x40 mm, nivel M)."""
    base = QR_URL["production" if environment == "production" else "test"]
    q = lambda v: quote(str(v), safe="")  # noqa: E731
    return f"{base}?nif={q(nif)}&numserie={q(num_serie)}&fecha={q(fecha)}&importe={q(importe_total)}"


def verify_chain(records: list[dict]) -> list[str]:
    """Recalcula la cadena y devuelve los errores encontrados (lista vacía = cadena íntegra).

    Cada registro: {"record_type", "issuer_nif", "num_serie", "fecha_expedicion", "tipo_factura",
    "cuota_total", "importe_total", "previous_hash", "hash", "generated_at", "sequence"}.
    """
    errors: list[str] = []
    prev: str | None = None
    for r in sorted(records, key=lambda x: x["sequence"]):
        if (r.get("previous_hash") or None) != prev:
            errors.append(f"Registro {r['sequence']} ({r['num_serie']}): no enlaza con el anterior")
        if r["record_type"] == "alta":
            expected = hash_alta(
                nif=r["issuer_nif"], num_serie=r["num_serie"], fecha=r["fecha_expedicion"],
                tipo_factura=r["tipo_factura"], cuota_total=r["cuota_total"], importe_total=r["importe_total"],
                huella_anterior=r.get("previous_hash"), fecha_hora_huso=r["generated_at"],
            )
        else:
            expected = hash_anulacion(
                nif=r["issuer_nif"], num_serie=r["num_serie"], fecha=r["fecha_expedicion"],
                huella_anterior=r.get("previous_hash"), fecha_hora_huso=r["generated_at"],
            )
        if expected != r["hash"]:
            errors.append(f"Registro {r['sequence']} ({r['num_serie']}): la huella no coincide (alterado)")
        prev = r["hash"]
    return errors


# ---------------------------------------------------------------------------
# XML de remisión (RegFactuSistemaFacturacion). PENDIENTE de validar con el XSD.
# ---------------------------------------------------------------------------
def _sub(parent, tag: str, text: str | None = None, ns: str = NS_INFO):
    el = ET.SubElement(parent, f"{{{ns}}}{tag}")
    if text is not None:
        el.text = str(text)
    return el


def _id_factura(parent, tag: str, nif: str, num_serie: str, fecha: str):
    idf = _sub(parent, tag)
    _sub(idf, "IDEmisorFactura", nif)
    _sub(idf, "NumSerieFactura", num_serie)
    _sub(idf, "FechaExpedicionFactura", fecha)
    return idf


def _encadenamiento(parent, previous: dict | None):
    enc = _sub(parent, "Encadenamiento")
    if not previous:
        _sub(enc, "PrimerRegistro", "S")
    else:
        ant = _sub(enc, "RegistroAnterior")
        _sub(ant, "IDEmisorFactura", previous["nif"])
        _sub(ant, "NumSerieFactura", previous["num_serie"])
        _sub(ant, "FechaExpedicionFactura", previous["fecha"])
        _sub(ant, "Huella", previous["hash"])


def _sistema(parent, sif: dict):
    s = _sub(parent, "SistemaInformatico")
    _sub(s, "NombreRazon", sif["producer_name"])
    _sub(s, "NIF", sif["producer_nif"])
    _sub(s, "NombreSistemaInformatico", sif["name"])
    _sub(s, "IdSistemaInformatico", sif["id"])
    _sub(s, "Version", sif["version"])
    _sub(s, "NumeroInstalacion", sif["installation"])
    _sub(s, "TipoUsoPosibleSoloVerifactu", "S")
    _sub(s, "TipoUsoPosibleMultiOT", "S")
    _sub(s, "IndicadorMultiplesOT", "S")


def build_envelope(records_xml: list[ET.Element], obligado_nif: str, obligado_nombre: str) -> str:
    ET.register_namespace("soapenv", NS_SOAP)
    ET.register_namespace("sum", NS_LR)
    ET.register_namespace("sum1", NS_INFO)
    env = ET.Element(f"{{{NS_SOAP}}}Envelope")
    ET.SubElement(env, f"{{{NS_SOAP}}}Header")
    body = ET.SubElement(env, f"{{{NS_SOAP}}}Body")
    reg = ET.SubElement(body, f"{{{NS_LR}}}RegFactuSistemaFacturacion")
    cab = ET.SubElement(reg, f"{{{NS_LR}}}Cabecera")
    obl = _sub(cab, "ObligadoEmision")
    _sub(obl, "NombreRazon", obligado_nombre)
    _sub(obl, "NIF", obligado_nif)
    for rec in records_xml:
        wrapper = ET.SubElement(reg, f"{{{NS_LR}}}RegistroFactura")
        wrapper.append(rec)
    return ET.tostring(env, encoding="unicode", xml_declaration=False)


def build_registro_alta(payload: dict, sif: dict) -> ET.Element:
    """payload: lo que se guarda en FiscalRecord.payload para un alta."""
    r = ET.Element(f"{{{NS_INFO}}}RegistroAlta")
    _sub(r, "IDVersion", "1.0")
    _id_factura(r, "IDFactura", payload["nif"], payload["num_serie"], payload["fecha"])
    _sub(r, "NombreRazonEmisor", payload["nombre_emisor"])
    _sub(r, "TipoFactura", payload["tipo_factura"])
    if payload["tipo_factura"] == "R5":
        _sub(r, "TipoRectificativa", "I")
        fr = _sub(r, "FacturasRectificadas")
        for f in payload.get("rectificadas", []):
            _id_factura(fr, "IDFacturaRectificada", f["nif"], f["num_serie"], f["fecha"])
    if payload["tipo_factura"] == "F3":
        fs = _sub(r, "FacturasSustituidas")
        for f in payload.get("sustituidas", []):
            _id_factura(fs, "IDFacturaSustituida", f["nif"], f["num_serie"], f["fecha"])
    _sub(r, "DescripcionOperacion", payload.get("descripcion") or "Servicio de restauración")
    if payload.get("destinatario"):
        ds = _sub(r, "Destinatarios")
        idd = _sub(ds, "IDDestinatario")
        _sub(idd, "NombreRazon", payload["destinatario"]["nombre"])
        _sub(idd, "NIF", payload["destinatario"]["nif"])
    des = _sub(r, "Desglose")
    for d in payload["desglose"]:
        det = _sub(des, "DetalleDesglose")
        _sub(det, "Impuesto", "01")
        _sub(det, "ClaveRegimen", "01")
        _sub(det, "CalificacionOperacion", "S1")
        _sub(det, "TipoImpositivo", d["tipo"])
        _sub(det, "BaseImponibleOimporteNoSujeto", d["base"])
        _sub(det, "CuotaRepercutida", d["cuota"])
    _sub(r, "CuotaTotal", payload["cuota_total"])
    _sub(r, "ImporteTotal", payload["importe_total"])
    _encadenamiento(r, payload.get("anterior"))
    _sistema(r, sif)
    _sub(r, "FechaHoraHusoGenRegistro", payload["fecha_hora_huso"])
    _sub(r, "TipoHuella", "01")
    _sub(r, "Huella", payload["huella"])
    return r


def build_registro_anulacion(payload: dict, sif: dict) -> ET.Element:
    r = ET.Element(f"{{{NS_INFO}}}RegistroAnulacion")
    _sub(r, "IDVersion", "1.0")
    idf = _sub(r, "IDFactura")
    _sub(idf, "IDEmisorFacturaAnulada", payload["nif"])
    _sub(idf, "NumSerieFacturaAnulada", payload["num_serie"])
    _sub(idf, "FechaExpedicionFacturaAnulada", payload["fecha"])
    _encadenamiento(r, payload.get("anterior"))
    _sistema(r, sif)
    _sub(r, "FechaHoraHusoGenRegistro", payload["fecha_hora_huso"])
    _sub(r, "TipoHuella", "01")
    _sub(r, "Huella", payload["huella"])
    return r
