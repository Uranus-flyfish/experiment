import time
import uuid
import requests

BASE = "http://localhost:8081"


def test_healthz():
    """Smoke: health check returns ok"""
    r = requests.get(f"{BASE}/healthz", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["service"] == "reservation"


def test_list_tables():
    """Smoke: list tables"""
    r = requests.get(f"{BASE}/api/tables", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    assert len(data["data"]["list"]) > 0


def test_create_reservation():
    """Smoke: create reservation (unique per call to avoid 409 conflict)"""
    unique_id = uuid.uuid4().hex[:8]
    payload = {
        "storeId": "store-001",
        "date": f"2026-07-{int(unique_id[:2], 16) % 28 + 1:02d}",
        "timeSlot": f"{int(unique_id[2:4], 16) % 14 + 10:02d}:{int(unique_id[4:6], 16) % 2 * 30:02d}",
        "guestCount": 2,
        "tableId": "table-001",
        "note": f"smoke test {unique_id}",
    }
    r = requests.post(f"{BASE}/api/reservations", json=payload, timeout=5)
    assert r.status_code == 201, f"Create failed (status={r.status_code}): {r.text}"
    data = r.json()
    assert data["data"]["status"] == "PENDING"
    return data["data"]["id"]


def test_accept_reservation():
    """Smoke: accept → confirm lifecycle"""
    res_id = test_create_reservation()
    # Accept
    r = requests.post(f"{BASE}/api/reservations/{res_id}/accept", timeout=5)
    assert r.status_code == 200, f"Accept failed: {r.text}"
    assert r.json()["data"]["status"] == "CONFIRMED"


def test_list_timeslots():
    """Smoke: time slots query"""
    r = requests.get(f"{BASE}/api/timeslots?date=2026-07-01&storeId=store-001", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert data["data"]["date"] == "2026-07-01"
