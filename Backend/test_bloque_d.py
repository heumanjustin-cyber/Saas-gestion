import requests

BASE = "http://127.0.0.1:8000"
login = requests.post(f"{BASE}/login", json={"email": "elias@test.com", "password": "123456"})
token = login.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

for endpoint in ["/my-top-services", "/my-top-employees", "/my-recent-appointments",
                 "/my-employee-performance", "/my-service-revenue", "/my-business-health",
                 "/my-recommendations", "/my-growth-opportunities", "/my-plan-recommendation"]:
    r = requests.get(f"{BASE}{endpoint}", headers=headers)
    print(f"=== {endpoint} ===")
    print(f"[{r.status_code}] {r.text}\n")
