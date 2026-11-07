"""Horario del local: «abierto ahora», próximos tramos y textos para el cliente.

Formato guardado: {"mon": [["13:30", "24:00"]], "tue": [["19:00", "01:30"]], ...}
- Un tramo cuyo final es anterior o igual a su inicio cruza la medianoche
  (martes 19:00-01:30 sigue abierto el miércoles a la 1:00).
- "24:00" es la medianoche del final del día.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_OSM_DAYS = {"mo": 0, "tu": 1, "we": 2, "th": 3, "fr": 4, "sa": 5, "su": 6}
_SCHEMA_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

DAY_NAMES = {
    "es": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "fr": ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
}

_HHMM = re.compile(r"^([01]?\d|2[0-4]):([0-5]\d)$")


@dataclass
class Interval:
    start: datetime
    end: datetime


def _parse_hhmm(value: str) -> tuple[int, int]:
    m = _HHMM.match(str(value).strip())
    if not m:
        raise ValueError(f"Hora no válida: {value!r} (usa HH:MM)")
    h, mi = int(m.group(1)), int(m.group(2))
    if h == 24 and mi != 0:
        raise ValueError(f"Hora no válida: {value!r}")
    return h, mi


def validate_hours(hours: dict) -> dict:
    """Valida y normaliza el horario. Lanza ValueError con un mensaje claro."""
    clean: dict[str, list[list[str]]] = {}
    for day, ranges in (hours or {}).items():
        if day not in DAYS:
            raise ValueError(f"Día no válido: {day!r} (usa {', '.join(DAYS)})")
        out = []
        for r in ranges or []:
            if not isinstance(r, (list, tuple)) or len(r) != 2:
                raise ValueError(f"Tramo no válido en {day}: {r!r} (usa [\"13:30\", \"24:00\"])")
            a, b = _parse_hhmm(r[0]), _parse_hhmm(r[1])
            if a == (24, 0):
                raise ValueError(f"Un tramo no puede empezar a las 24:00 ({day})")
            out.append([f"{a[0]:02d}:{a[1]:02d}", f"{b[0]:02d}:{b[1]:02d}"])
        if out:
            clean[day] = out
    return clean


def _intervals_for_day(hours: dict, day: date, tz: ZoneInfo) -> list[Interval]:
    out = []
    for start_s, end_s in hours.get(DAYS[day.weekday()], []):
        sh, sm = _parse_hhmm(start_s)
        eh, em = _parse_hhmm(end_s)
        start = datetime.combine(day, time(sh, sm), tzinfo=tz)
        if (eh, em) == (24, 0):
            end = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=tz)
        else:
            end = datetime.combine(day, time(eh, em), tzinfo=tz)
            if end <= start:  # cruza la medianoche
                end = datetime.combine(day + timedelta(days=1), time(eh, em), tzinfo=tz)
        out.append(Interval(start, end))
    return out


def _closed_dates(closures: list) -> set[date]:
    days: set[date] = set()
    for c in closures or []:
        try:
            a = date.fromisoformat(str(c.get("from") or c.get("date")))
            b = date.fromisoformat(str(c.get("to") or c.get("from") or c.get("date")))
        except (TypeError, ValueError, AttributeError):
            continue
        while a <= b:
            days.add(a)
            a += timedelta(days=1)
    return days


def upcoming_intervals(hours: dict, closures: list, now: datetime, tz: ZoneInfo, days_ahead: int = 8) -> list[Interval]:
    local_today = now.astimezone(tz).date()
    closed = _closed_dates(closures)
    out: list[Interval] = []
    for offset in range(-1, days_ahead):
        day = local_today + timedelta(days=offset)
        if day in closed:
            continue
        out.extend(_intervals_for_day(hours, day, tz))
    out.sort(key=lambda i: i.start)
    return [i for i in out if i.end > now]


@dataclass
class OpenStatus:
    is_open: bool
    closes_at: datetime | None = None
    opens_at: datetime | None = None


def open_status(hours: dict, closures: list, now: datetime, tz_name: str = "Europe/Madrid") -> OpenStatus:
    tz = ZoneInfo(tz_name or "Europe/Madrid")
    intervals = upcoming_intervals(hours or {}, closures or [], now, tz)
    for i in intervals:
        if i.start <= now < i.end:
            # Tramos pegados (13:30-16:00 y 16:00-24:00) se leen como uno
            end = i.end
            for j in intervals:
                if j.start == end:
                    end = j.end
            return OpenStatus(True, closes_at=end)
    nxt = next((i for i in intervals if i.start > now), None)
    return OpenStatus(False, opens_at=nxt.start if nxt else None)


def _fmt_time(dt: datetime, lang: str) -> str:
    if dt.hour == 0 and dt.minute == 0:
        return {"es": "medianoche", "en": "midnight", "fr": "minuit"}.get(lang, "00:00")
    return dt.strftime("%H:%M")


def status_text(status: OpenStatus, now: datetime, tz_name: str = "Europe/Madrid", lang: str = "es") -> str:
    tz = ZoneInfo(tz_name or "Europe/Madrid")
    lang = lang if lang in DAY_NAMES else "es"
    t = {
        "es": {"open": "Abierto", "closed": "Cerrado", "closes": "cierra a las", "closes_mid": "cierra a",
               "soon": "cierra en {m} min", "opens_today": "abre hoy a las", "opens_tomorrow": "abre mañana a las",
               "opens_on": "abre el {d} a las", "unknown": "consulta el horario"},
        "en": {"open": "Open", "closed": "Closed", "closes": "closes at", "closes_mid": "closes at",
               "soon": "closes in {m} min", "opens_today": "opens today at", "opens_tomorrow": "opens tomorrow at",
               "opens_on": "opens {d} at", "unknown": "see opening hours"},
        "fr": {"open": "Ouvert", "closed": "Fermé", "closes": "ferme à", "closes_mid": "ferme à",
               "soon": "ferme dans {m} min", "opens_today": "ouvre aujourd'hui à", "opens_tomorrow": "ouvre demain à",
               "opens_on": "ouvre {d} à", "unknown": "voir les horaires"},
    }[lang]
    if status.is_open and status.closes_at:
        mins = int((status.closes_at - now).total_seconds() // 60)
        if mins <= 30:
            return f"{t['open']} · {t['soon'].format(m=max(mins, 1))}"
        ct = status.closes_at.astimezone(tz)
        word = t["closes_mid"] if (ct.hour, ct.minute) == (0, 0) else t["closes"]
        return f"{t['open']} · {word} {_fmt_time(ct, lang)}"
    if status.opens_at:
        ot = status.opens_at.astimezone(tz)
        today = now.astimezone(tz).date()
        if ot.date() == today:
            return f"{t['closed']} · {t['opens_today']} {ot:%H:%M}"
        if ot.date() == today + timedelta(days=1):
            return f"{t['closed']} · {t['opens_tomorrow']} {ot:%H:%M}"
        return f"{t['closed']} · {t['opens_on'].format(d=DAY_NAMES[lang][ot.weekday()])} {ot:%H:%M}"
    return f"{t['closed']} · {t['unknown']}"


def weekly_table(hours: dict, lang: str = "es") -> list[dict]:
    """Agrupa días seguidos con el mismo horario: [{"days": "miércoles a sábado", "hours": "13:30 – 24:00"}]."""
    names = DAY_NAMES.get(lang, DAY_NAMES["es"])
    closed_word = {"es": "Cerrado", "en": "Closed", "fr": "Fermé"}.get(lang, "Cerrado")
    joiner = {"es": " a ", "en": " – ", "fr": " au "}.get(lang, " a ")
    rows: list[dict] = []
    i = 0
    while i < 7:
        ranges = hours.get(DAYS[i], [])
        j = i
        while j + 1 < 7 and hours.get(DAYS[j + 1], []) == ranges:
            j += 1
        label = names[i] if i == j else f"{names[i]}{joiner}{names[j]}"
        text = " · ".join(f"{a} – {b}" for a, b in ranges) if ranges else closed_word
        rows.append({"days": label[:1].upper() + label[1:], "hours": text})
        i = j + 1
    return rows


def schema_org_hours(hours: dict) -> list[dict]:
    """openingHoursSpecification de schema.org (Google entiende «closes» < «opens» como madrugada)."""
    out = []
    for idx, day in enumerate(DAYS):
        for a, b in hours.get(day, []):
            out.append({
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": f"https://schema.org/{_SCHEMA_DAYS[idx]}",
                "opens": a,
                "closes": "23:59" if b == "24:00" else b,
            })
    return out


def parse_osm_hours(lines: list[str]) -> dict:
    """Convierte «Mo,We-Sa 13:30-23:59» / «Tu 19:00-01:30» (formato OSM) al formato de BUHOSS."""
    hours: dict[str, list[list[str]]] = {}
    for line in lines or []:
        line = str(line).strip()
        if not line:
            continue
        m = re.match(r"^([A-Za-z,\-\s]+)\s+(.+)$", line)
        if not m:
            raise ValueError(f"Horario no reconocido: {line!r}")
        day_part, time_part = m.group(1), m.group(2)
        days: list[int] = []
        for chunk in day_part.replace(" ", "").split(","):
            if "-" in chunk:
                a, b = chunk.lower().split("-", 1)
                ia, ib = _OSM_DAYS[a[:2]], _OSM_DAYS[b[:2]]
                k = ia
                while True:
                    days.append(k)
                    if k == ib:
                        break
                    k = (k + 1) % 7
            elif chunk:
                days.append(_OSM_DAYS[chunk.lower()[:2]])
        for rng in time_part.split(","):
            a, b = [x.strip() for x in rng.split("-", 1)]
            if b == "23:59":
                b = "24:00"
            for d in days:
                hours.setdefault(DAYS[d], []).append([a, b])
    return validate_hours(hours)


def order_slots(hours: dict, closures: list, now: datetime, tz_name: str = "Europe/Madrid",
                prep_minutes: int = 15, step: int = 15, limit: int = 48, lang: str = "es") -> list[dict]:
    """Horas a las que se puede programar un pedido (próximas 48 h, cada 15 min, dentro del horario)."""
    tz = ZoneInfo(tz_name or "Europe/Madrid")
    earliest = now + timedelta(minutes=prep_minutes)
    today = now.astimezone(tz).date()
    words = {"es": ("Hoy", "Mañana"), "en": ("Today", "Tomorrow"), "fr": ("Aujourd'hui", "Demain")}.get(lang, ("Hoy", "Mañana"))
    out: list[dict] = []
    for interval in upcoming_intervals(hours or {}, closures or [], now, tz, days_ahead=3):
        t = max(interval.start, earliest).astimezone(tz)
        # redondeo hacia arriba al siguiente múltiplo de `step`
        extra = (-t.minute) % step
        t = (t + timedelta(minutes=extra)).replace(second=0, microsecond=0)
        while t + timedelta(minutes=step) <= interval.end and len(out) < limit:
            if t >= earliest and t <= now + timedelta(hours=48):
                d = t.date()
                day = words[0] if d == today else words[1] if d == today + timedelta(days=1) else \
                    DAY_NAMES.get(lang, DAY_NAMES["es"])[t.weekday()].capitalize()
                out.append({"value": t.isoformat(), "label": f"{day} {t:%H:%M}"})
            t += timedelta(minutes=step)
        if len(out) >= limit:
            break
    return out


def is_dark(hex_color: str | None) -> bool:
    """¿Contrasta más el texto blanco que el negro sobre este color? (cruce WCAG en luminancia 0,179)."""
    try:
        h = (hex_color or "#000000").lstrip("#")[:6]
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return True

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b) < 0.179
