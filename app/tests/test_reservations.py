from concurrent.futures import ThreadPoolExecutor

from .conftest import make_event


def reserve(client, headers, event_id, seats=1):
    return client.post("/reservations", json={"event_id": event_id, "seats": seats}, headers=headers)


def remaining(client, event_id) -> int:
    return client.get(f"/events/{event_id}").json()["places_remaining"]


def test_reservation_requires_auth(client, admin):
    event = make_event(client, admin)
    r = client.post("/reservations", json={"event_id": event["id"], "seats": 1})
    assert r.status_code == 401


def test_full_flow_payment_accepted(client, admin, alice):
    event = make_event(client, admin, seats=5, price_cents=2500)

    r = reserve(client, alice, event["id"], seats=2)
    assert r.status_code == 201
    res = r.json()
    assert res["status"] == "pending"
    assert res["total_cents"] == 5000
    assert res["tickets"] == [] and res["payment"] is None
    assert remaining(client, event["id"]) == 3  # seats are held

    r = client.post(f"/reservations/{res['id']}/pay", json={}, headers=alice)
    assert r.status_code == 200
    paid = r.json()
    assert paid["status"] == "confirmed"
    assert paid["payment"]["status"] == "accepted"
    assert len(paid["tickets"]) == 2
    codes = {t["code"] for t in paid["tickets"]}
    assert len(codes) == 2 and all(len(c) == 16 for c in codes)
    assert remaining(client, event["id"]) == 3

    mine = client.get("/reservations/me", headers=alice).json()
    assert [m["id"] for m in mine] == [res["id"]]


def test_payment_refused_releases_seats(client, admin, alice):
    event = make_event(client, admin, seats=5)
    res = reserve(client, alice, event["id"], seats=3).json()
    assert remaining(client, event["id"]) == 2

    r = client.post(f"/reservations/{res['id']}/pay", json={"simulate_refusal": True}, headers=alice)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "cancelled"
    assert body["payment"]["status"] == "refused"
    assert body["tickets"] == []
    assert remaining(client, event["id"]) == 5


def test_cannot_pay_twice(client, admin, alice):
    event = make_event(client, admin)
    res = reserve(client, alice, event["id"]).json()
    assert client.post(f"/reservations/{res['id']}/pay", json={}, headers=alice).status_code == 200
    assert client.post(f"/reservations/{res['id']}/pay", json={}, headers=alice).status_code == 409


def test_overbooking_rejected(client, admin, alice, bob):
    event = make_event(client, admin, seats=3)
    assert reserve(client, alice, event["id"], seats=2).status_code == 201
    assert reserve(client, bob, event["id"], seats=2).status_code == 409
    assert remaining(client, event["id"]) == 1
    assert reserve(client, bob, event["id"], seats=1).status_code == 201
    assert remaining(client, event["id"]) == 0


def test_seat_count_validation(client, admin, alice):
    event = make_event(client, admin)
    assert reserve(client, alice, event["id"], seats=0).status_code == 422
    assert reserve(client, alice, event["id"], seats=-1).status_code == 422
    assert reserve(client, alice, event["id"], seats=11).status_code == 422  # max is 10

