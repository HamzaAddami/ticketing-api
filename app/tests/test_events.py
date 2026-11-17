from datetime import datetime, timedelta, timezone

from .conftest import make_event


def test_events_are_public(client, admin):
    make_event(client, admin)
    r = client.get("/events")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_event_404(client):
    assert client.get("/events/12345").status_code == 404


def test_pagination_limits(client):
    assert client.get("/events?limit=0").status_code == 422
    assert client.get("/events?limit=1000").status_code == 422


def test_client_cannot_manage_events(client, alice):
    when = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    body = {"title": "X", "date": when, "location": "Y", "price_cents": 100, "places_total": 10}
    assert client.post("/events", json=body).status_code == 401
    assert client.post("/events", json=body, headers=alice).status_code == 403


def test_admin_event_crud(client, admin):
    event = make_event(client, admin, seats=10)
    assert event["places_remaining"] == 10

    r = client.patch(f"/events/{event['id']}", json={"title": "Renamed", "places_total": 20}, headers=admin)
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed"
    assert r.json()["places_remaining"] == 20

    assert client.delete(f"/events/{event['id']}", headers=admin).status_code == 204
    assert client.get(f"/events/{event['id']}").status_code == 404


def test_event_in_the_past_rejected(client, admin):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = client.post(
        "/events",
        headers=admin,
        json={"title": "Old", "date": past, "location": "Y", "price_cents": 100, "places_total": 10},
    )
    assert r.status_code == 422


def test_naive_date_rejected(client, admin):
    naive = (datetime.now() + timedelta(days=2)).replace(tzinfo=None).isoformat()
    r = client.post(
        "/events",
        headers=admin,
        json={"title": "N", "date": naive, "location": "Y", "price_cents": 100, "places_total": 10},
    )
    assert r.status_code == 422


def test_negative_price_rejected(client, admin):
    when = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    r = client.post(
        "/events",
        headers=admin,
        json={"title": "X", "date": when, "location": "Y", "price_cents": -1, "places_total": 10},
    )
    assert r.status_code == 422


def test_cannot_shrink_below_reserved_seats(client, admin, alice):
    event = make_event(client, admin, seats=5)
    client.post("/reservations", json={"event_id": event["id"], "seats": 4}, headers=alice)
    r = client.patch(f"/events/{event['id']}", json={"places_total": 2}, headers=admin)
    assert r.status_code == 409


def test_cannot_delete_event_with_reservations(client, admin, alice):
    event = make_event(client, admin)
    client.post("/reservations", json={"event_id": event["id"], "seats": 1}, headers=alice)
    assert client.delete(f"/events/{event['id']}", headers=admin).status_code == 409