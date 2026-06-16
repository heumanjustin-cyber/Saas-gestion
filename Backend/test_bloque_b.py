import requests

BASE = "http://127.0.0.1:8000"
COMP = "70acd297-08e6-43fd-93f2-63f228ef217e"
EMP  = "4157d298-bc69-4009-bdb3-101741c472c6"

login = requests.post(f"{BASE}/login", json={"email": "elias@test.com", "password": "123456"})
token = login.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

print("=== CREAR RECURSO (sala) ===")
r = requests.post(f"{BASE}/resources", headers=headers, json={
    "company_id": COMP,
    "name": "Sala 1",
    "resource_type": "room",
    "description": "Sala principal",
})
print(f"[{r.status_code}] {r.text}\n")
resource_id = r.json().get("id") if r.status_code == 200 else None

print("=== CREAR CITA ===")
r = requests.post(f"{BASE}/appointments", headers=headers, json={
    "company_id": COMP, "employee_id": EMP,
    "starts_at": "2026-06-18T10:00:00Z", "ends_at": "2026-06-18T11:00:00Z"
})
print(f"[{r.status_code}] {r.text}\n")
appt_id = r.json().get("id") if r.status_code == 200 else None

if resource_id and appt_id:
    print("=== RESERVAR RECURSO ===")
    r = requests.post(f"{BASE}/resource-bookings", json={
        "resource_id": resource_id,
        "appointment_id": appt_id,
        "starts_at": "2026-06-18T10:00:00Z",
        "ends_at": "2026-06-18T11:00:00Z",
    })
    print(f"[{r.status_code}] {r.text}\n")

    print("=== DOBLE RESERVA RECURSO (espera 409) ===")
    r = requests.post(f"{BASE}/resource-bookings", json={
        "resource_id": resource_id,
        "appointment_id": appt_id,
        "starts_at": "2026-06-18T10:30:00Z",
        "ends_at": "2026-06-18T11:30:00Z",
    })
    print(f"[{r.status_code}] {r.text}\n")

print("=== LISTAR RECURSOS ===")
r = requests.get(f"{BASE}/resources")
print(f"[{r.status_code}] {r.text}\n")
