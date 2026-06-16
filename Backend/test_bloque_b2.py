import requests

BASE = "http://127.0.0.1:8000"
COMP = "70acd297-08e6-43fd-93f2-63f228ef217e"
EMP  = "4157d298-bc69-4009-bdb3-101741c472c6"
RESOURCE_ID = "61d12cbc-102a-412d-b46f-6b3d08f142c2"

login = requests.post(f"{BASE}/login", json={"email": "elias@test.com", "password": "123456"})
token = login.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

from datetime import datetime
from zoneinfo import ZoneInfo
dt = datetime(2026, 6, 18, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
weekday = dt.astimezone(ZoneInfo("Europe/Madrid")).weekday()
print(f"2026-06-18 es weekday={weekday}")

print("=== HORARIO JUEVES ===")
r = requests.post(f"{BASE}/employee-schedules", json={
    "employee_id": EMP, "weekday": weekday,
    "start_time": "09:00:00", "end_time": "18:00:00"
})
print(f"[{r.status_code}] {r.text}\n")

print("=== CREAR CITA ===")
r = requests.post(f"{BASE}/appointments", headers=headers, json={
    "company_id": COMP, "employee_id": EMP,
    "starts_at": "2026-06-18T10:00:00Z", "ends_at": "2026-06-18T11:00:00Z"
})
print(f"[{r.status_code}] {r.text}\n")
appt_id = r.json().get("id") if r.status_code == 200 else None

if appt_id:
    print("=== RESERVAR RECURSO ===")
    r = requests.post(f"{BASE}/resource-bookings", json={
        "resource_id": RESOURCE_ID, "appointment_id": appt_id,
        "starts_at": "2026-06-18T10:00:00Z", "ends_at": "2026-06-18T11:00:00Z",
    })
    print(f"[{r.status_code}] {r.text}\n")

    print("=== DOBLE RESERVA RECURSO (espera 409) ===")
    r = requests.post(f"{BASE}/resource-bookings", json={
        "resource_id": RESOURCE_ID, "appointment_id": appt_id,
        "starts_at": "2026-06-18T10:30:00Z", "ends_at": "2026-06-18T11:30:00Z",
    })
    print(f"[{r.status_code}] {r.text}\n")
