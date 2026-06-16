import requests
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = "http://127.0.0.1:8000"
EMP  = "4157d298-bc69-4009-bdb3-101741c472c6"

# Verificar que weekday es correcto
tz = ZoneInfo("Europe/Madrid")
dt = datetime(2026, 6, 17, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
local = dt.astimezone(tz)
print(f"2026-06-17T10:00:00Z en Madrid = {local}")
print(f"weekday() = {local.weekday()} (0=lunes, 1=martes)")
print(f"time() = {local.time()}")

# Ver horarios existentes en la BD
login = requests.post(f"{BASE}/login", json={"email": "elias@test.com", "password": "123456"})
token = login.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

schedules = requests.get(f"{BASE}/employee-schedules", headers=headers)
print(f"\nHorarios en BD:")
import json
for s in schedules.json():
    if s.get("employee_id") == EMP:
        print(f"  weekday={s.get('weekday')} start={s.get('start_time')} end={s.get('end_time')}")
