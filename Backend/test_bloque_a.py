import requests

BASE = "http://127.0.0.1:8000"
EMP  = "4157d298-bc69-4009-bdb3-101741c472c6"

login = requests.post(f"{BASE}/login", json={"email": "elias@test.com", "password": "123456"})
token = login.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

print("=== REGISTER ===")
r = requests.post(f"{BASE}/register", json={"email": "nuevo@test.com", "password": "123456", "full_name": "Nuevo Usuario"})
print(f"[{r.status_code}] {r.text}\n")

print("=== REGISTER DUPLICADO (espera 400) ===")
r = requests.post(f"{BASE}/register", json={"email": "nuevo@test.com", "password": "123456", "full_name": "Nuevo Usuario"})
print(f"[{r.status_code}] {r.text}\n")

print("=== DISPONIBILIDAD ===")
r = requests.get(f"{BASE}/my/availability", headers=headers, params={
    "employee_id": EMP,
    "target_date": "2026-06-17",
    "duration_minutes": 60,
    "slot_interval_minutes": 30,
})
print(f"[{r.status_code}] {r.text}\n")
