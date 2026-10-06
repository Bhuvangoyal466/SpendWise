"""
End-to-end smoke test: runs the full central user journey from the plan
(section 26) against a live server — signup, seed data, dashboard,
behavioral, anomalies, forecast, subscriptions, goals, simulate (forward +
time machine), insights, assistant. Exits non-zero on any failure.

Usage: ./venv/bin/python tests/smoke_test.py
(requires the server running on localhost:8000)
"""
import sys
import requests

BASE = "http://127.0.0.1:8000"


def check(name, resp, expect=200):
    ok = resp.status_code == expect
    print(f"{'OK  ' if ok else 'FAIL'} [{resp.status_code}] {name}")
    if not ok:
        print("   ", resp.text[:300])
        sys.exit(1)
    return resp


def main():
    email = "smoketest@spendwise.ai"
    check("health", requests.get(f"{BASE}/api/health"))

    r = requests.post(f"{BASE}/api/auth/signup", json={"email": email, "password": "testpass123", "name": "Smoke Test"})
    if r.status_code not in (200, 400):  # 400 = already exists, fine for reruns
        check("signup", r)

    r = check("login", requests.post(f"{BASE}/api/auth/login",
              data={"username": email, "password": "testpass123"}))
    token = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    check("seed synthetic", requests.post(f"{BASE}/api/transactions/seed-synthetic", headers=auth))
    check("list transactions", requests.get(f"{BASE}/api/transactions?limit=10", headers=auth))
    check("dashboard summary", requests.get(f"{BASE}/api/dashboard/summary", headers=auth))
    check("dashboard heatmap", requests.get(f"{BASE}/api/dashboard/heatmap", headers=auth))
    check("behavioral profile", requests.get(f"{BASE}/api/behavioral/profile", headers=auth))
    check("anomalies", requests.get(f"{BASE}/api/anomalies", headers=auth))
    check("forecast", requests.get(f"{BASE}/api/forecast?horizon_months=3", headers=auth))
    check("subscriptions", requests.get(f"{BASE}/api/subscriptions", headers=auth))

    r = check("create goal", requests.post(f"{BASE}/api/goals", headers=auth, json={
        "name": "Emergency Fund", "target_amount": 10000, "current_saved": 1500, "target_date": "2027-06-01"
    }))
    check("list goals", requests.get(f"{BASE}/api/goals", headers=auth))

    check("simulate forward", requests.post(f"{BASE}/api/simulate", headers=auth, json={
        "mode": "forward",
        "assumptions": {"category_pct_changes": {"Shopping": -0.3}, "income_pct_change": 0.0},
        "horizon_months": 6,
    }))
    check("simulate time_machine", requests.post(f"{BASE}/api/simulate", headers=auth, json={
        "mode": "time_machine",
        "assumptions": {"category_pct_changes": {"Shopping": -0.4}},
        "period_start": "2026-05-27", "period_end": "2026-08-25",
    }))

    check("generate insights", requests.post(f"{BASE}/api/insights/generate", headers=auth))
    check("list insights", requests.get(f"{BASE}/api/insights", headers=auth))

    check("assistant category", requests.post(f"{BASE}/api/assistant/ask", headers=auth,
          json={"question": "How much did I spend on Dining?"}))
    check("assistant simulate", requests.post(f"{BASE}/api/assistant/ask", headers=auth,
          json={"question": "What if I reduce shopping by 20%?"}))
    check("assistant goal", requests.post(f"{BASE}/api/assistant/ask", headers=auth,
          json={"question": "Can I afford my goal?"}))

    print("\nAll smoke tests passed.")


if __name__ == "__main__":
    main()
