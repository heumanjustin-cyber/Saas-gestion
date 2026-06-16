import requests
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = "http://127.0.0.1:8000"
EMP  = "4157d298-bc69-4009-bdb3-101741c472c6"
COMP = "70acd297-08e6-43fd-93f2-63f228ef217e"

tz = ZoneInfo("Europe/Madrid")
dt = datetime(2026, 6, 17, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
local = dt.astimezone(tz)
weekday_needed = local.weekday()
print(f"weekday necesario: {weekday_needed}")

login = requests.post(f"{BASE}/login", json={"email": "elias@test.com", "password": "123456"})
token = login.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

print(f"Creando horario para weekday={weekday_needed}...")
r = requests.post(f"{BASE}/employee-schedules", json={
    "employee_id": EMP, "weekday": weekday_needed,
    "start_time": "09:00:00", "end_time": "18:00:00"
})
print(f"[{r.status_code}] {r.text}")

print("\nCita valida:")
r = requests.post(f"{BASE}/appointments", headers=headers, json={
    "company_id": COMP, "employee_id": EMP,
    "starts_at": "2026-06-17T10:00:00Z", "ends_at": "2026-06-17T11:00:00Z"
})
print(f"[{r.status_code}] {r.text}")
appt_id = r.json().get("id") if r.status_code == 200 else None

print("\nDoble reserva (espera 409):")
r = requests.post(f"{BASE}/appointments", headers=headers, json={
    "company_id": COMP, "employee_id": EMP,
    "starts_at": "2026-06-17T10:30:00Z", "ends_at": "2026-06-17T11:30:00Z"
})
print(f"[{r.status_code}] {r.text}")

print("\nCita en bloqueo (espera 409):")
r = requests.post(f"{BASE}/appointments", headers=headers, json={
    "company_id": COMP, "employee_id": EMP,
    "starts_at": "2026-06-17T13:15:00Z", "ends_at": "2026-06-17T13:45:00Z"
})
print(f"[{r.status_code}] {r.text}")

print("\nAgenda:")
r = requests.get(f"{BASE}/my/agenda?company_id={COMP}&target_date=2026-06-17", headers=headers)
print(f"[{r.status_code}] {r.text}")

if appt_id:
    print("\nCancelar:")
    r = requests.post(f"{BASE}/my/appointments/{appt_id}/cancel", headers=headers, json={"reason": "Cliente no puede asistir"})
    print(f"[{r.status_code}] {r.text}")
    print("\nHistorial:")
    r = requests.get(f"{BASE}/my/appointments/{appt_id}/history", headers=headers)
    print(f"[{r.status_code}] {r.text}")
