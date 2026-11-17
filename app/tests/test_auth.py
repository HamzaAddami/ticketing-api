from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from app.core.security import create_access_token

from .conftest import PASSWORD, headers, login, register


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_register_login_me(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "client"
    assert "password" not in body and "password_hash" not in body

    token = login(client, "alice@example.com")
    me = client.get("/auth/me", headers=headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_email_is_case_insensitive(client):
    register(client, "Alice@Example.com")
    assert register(client, "alice@example.com").status_code == 409
    assert login(client, "ALICE@example.com")


def test_cannot_register_as_admin(client):
    r = client.post(
        "/auth/register",
        json={"name": "Eve", "email": "eve@example.com", "password": PASSWORD, "role": "admin"},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "client"


def test_register_validation(client):
    assert register(client, password="short").status_code == 422
    assert register(client, email="not-an-email").status_code == 422
    assert register(client, password="é" * 40).status_code == 422  # > 72 bytes


def test_duplicate_email(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409


def test_login_failures_are_generic(client):
    register(client)
    wrong_pw = client.post("/auth/login", data={"username": "alice@example.com", "password": "nope-nope"})
    unknown = client.post("/auth/login", data={"username": "ghost@example.com", "password": PASSWORD})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


def test_protected_route_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=headers("garbage")).status_code == 401


def test_expired_token_rejected(client):
    register(client)
    token = create_access_token("1", expires_delta=timedelta(seconds=-5))
    assert client.get("/auth/me", headers=headers(token)).status_code == 401


def test_token_signed_with_other_key_rejected(client):
    register(client)
    now = datetime.now(timezone.utc)
    forged = jwt.encode(
        {"sub": "1", "iat": now, "exp": now + timedelta(minutes=5)},
        "another-key-another-key-another-key-123",
        algorithm="HS256",
    )
    assert client.get("/auth/me", headers=headers(forged)).status_code == 401


def test_alg_none_token_rejected(client):
    register(client)
    now = datetime.now(timezone.utc)
    unsigned = jwt.encode(
        {"sub": "1", "iat": now, "exp": now + timedelta(minutes=5)}, None, algorithm="none"
    )