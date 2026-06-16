import requests

BASE = "http://127.0.0.1:8000"
COMP = "70acd297-08e6-43fd-93f2-63f228ef217e"

login = requests.post(f"{BASE}/login", json={"email": "elias@test.com", "password": "123456"})
token = login.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

print("=== ONBOARDING ===")
r = requests.post(f"{BASE}/onboarding", headers=headers, json={
    "company_id": COMP, "business_type": "hair_salon",
    "whatsapp_number": "+34600000000", "instagram_username": "peluqueria_elias",
    "website": "https://peluqueriaelias.com", "enable_ai": False, "enable_reminders": True,
})
print(f"[{r.status_code}] {r.text}\n")

print("=== COMPANY SETTINGS ===")
r = requests.get(f"{BASE}/my-company-settings", headers=headers)
print(f"[{r.status_code}] {r.text}\n")

print("=== SETUP STATUS ===")
r = requests.get(f"{BASE}/my-setup-status", headers=headers)
print(f"[{r.status_code}] {r.text}\n")

print("=== DASHBOARD ===")
r = requests.get(f"{BASE}/my-dashboard", headers=headers)
print(f"[{r.status_code}] {r.text}\n")

print("=== REVENUE ===")
r = requests.get(f"{BASE}/my-revenue", headers=headers)
print(f"[{r.status_code}] {r.text}\n")

print("=== KPIS ===")
r = requests.get(f"{BASE}/my-kpis", headers=headers)
print(f"[{r.status_code}] {r.text}\n")
