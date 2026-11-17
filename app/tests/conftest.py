import os
import tempfile
from datetime import datetime, timedelta, timezone

# Settings must be in place BEFORE the app is imported.
_tmp_dir = tempfile.mkdtemp()
os.environ.update(
    {
        "SECRET_KEY": "test-secret-key-test-secret-key-0123456789",
        "DATABASE_URL": f"sqlite:///{_tmp_dir}/test.db",
        "ADMIN_EMAIL": "admin@example.com",
        "ADMIN_PASSWORD": "AdminPass123!",
        "SEED_DEMO_DATA": "false",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402

PASSWORD = "Password123!"


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)  # fresh database for every test
    with TestClient(app) as c:  # runs the lifespan: create tables + admin
        yield c


def register(client, email="alice@example.com", name="Alice", password=PASSWORD):
    return client.post(
        "/auth/register", json={"name": name, "email": email, "password": password}
    )


def login(client, email, password=PASSWORD) -> str:
    r = client.post("/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin(client) -> dict[str, str]:
    return headers(login(client, "admin@example.com", "AdminPass123!"))


@pytest.fixture()
def alice(client) -> dict[str, str]:
    register(client, "alice@example.com", "Alice")
    return headers(login(client, "alice@example.com"))


@pytest.fixture()
def bob(client) -> dict[str, str]:
    register(client, "bob@example.com", "Bob")
    return headers(login(client, "bob@example.com"))


def make_event(client, admin_headers, seats=5, price_cents=2500, days=7) -> dict:
    when = datetime.now(timezone.utc) + timedelta(days=days)
    r = client.post(
        "/events",
        headers=admin_headers,
        json={
            "title": "Test Event",
            "date": when.isoformat(),
            "location": "Casablanca",
            "price_cents": price_cents,
            "places_total": seats,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()