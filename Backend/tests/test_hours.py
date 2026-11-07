from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services import hours as H

TZ = ZoneInfo("Europe/Madrid")
# Horario de Ankara confirmado por el dueño (30/10/2026)
ANKARA = {
    "mon": [["13:30", "24:00"]], "tue": [["19:00", "01:30"]], "wed": [["13:30", "24:00"]],
    "thu": [["13:30", "24:00"]], "fri": [["13:30", "24:00"]], "sat": [["13:30", "24:00"]],
    "sun": [["13:30", "24:00"]],
}


def at(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=TZ)


def test_abierto_y_cierra_a_medianoche():
    st = H.open_status(ANKARA, [], at(2026, 11, 9, 20, 0))  # lunes
    assert st.is_open and st.closes_at == at(2026, 11, 10, 0, 0)
    assert H.status_text(st, at(2026, 11, 9, 20, 0)) == "Abierto · cierra a medianoche"


def test_martes_de_madrugada_sigue_abierto_el_miercoles():
    st = H.open_status(ANKARA, [], at(2026, 11, 11, 1, 0))  # miércoles 1:00, tramo del martes
    assert st.is_open and st.closes_at == at(2026, 11, 11, 1, 30)
    assert "cierra en 30 min" in H.status_text(st, at(2026, 11, 11, 1, 0))


def test_martes_por_la_tarde_cerrado_hasta_las_19():
    now = at(2026, 11, 10, 15, 0)
    st = H.open_status(ANKARA, [], now)
    assert not st.is_open and st.opens_at == at(2026, 11, 10, 19, 0)
    assert H.status_text(st, now) == "Cerrado · abre hoy a las 19:00"
    assert H.status_text(st, now, lang="en") == "Closed · opens today at 19:00"


def test_cierre_puntual():
    now = at(2026, 12, 24, 14, 0)
    st = H.open_status(ANKARA, [{"from": "2026-12-24", "to": "2026-12-25", "reason": "Navidad"}], now)
    assert not st.is_open and st.opens_at == at(2026, 12, 26, 13, 30)


def test_cambio_de_hora_de_octubre():
    # 25-10-2026 (domingo): a las 3:00 el reloj vuelve a las 2:00. 13:30 sigue siendo 13:30.
    st = H.open_status(ANKARA, [], at(2026, 10, 25, 12, 0))
    assert st.opens_at == at(2026, 10, 25, 13, 30)


def test_tabla_semanal_agrupa_dias():
    rows = H.weekly_table(ANKARA)
    assert rows[0] == {"days": "Lunes", "hours": "13:30 – 24:00"}
    assert rows[1] == {"days": "Martes", "hours": "19:00 – 01:30"}
    assert rows[2] == {"days": "Miércoles a domingo", "hours": "13:30 – 24:00"}


def test_parse_osm_de_studio42():
    h = H.parse_osm_hours(["Mo,We-Sa 13:30-23:59", "Tu 19:00-01:30", "Su 09:00-23:59"])
    assert h["mon"] == [["13:30", "24:00"]] and h["tue"] == [["19:00", "01:30"]]
    assert h["sat"] == [["13:30", "24:00"]] and h["sun"] == [["09:00", "24:00"]]


def test_schema_org():
    spec = H.schema_org_hours(ANKARA)
    assert {"@type": "OpeningHoursSpecification", "dayOfWeek": "https://schema.org/Tuesday",
            "opens": "19:00", "closes": "01:30"} in spec
    assert all(s["closes"] != "24:00" for s in spec)


def test_validacion():
    with pytest.raises(ValueError):
        H.validate_hours({"lunes": [["13:00", "16:00"]]})
    with pytest.raises(ValueError):
        H.validate_hours({"mon": [["25:00", "16:00"]]})
