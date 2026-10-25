from datetime import UTC, datetime, timedelta

from app.db.models import Session as DbSession
from app.db.models import User
from app.services.auth_service import hash_password, hash_session_token
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_register_success(client: TestClient):
    payload = {
        "username": "alice123",
        "email": "alice@example.com",
        "password": "strongpassword123",
    }
    res = client.post(
        "/api/v1/auth/register",
        json=payload,
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "alice123"
    assert data["email"] == "alice@example.com"
    assert "id" in data


def test_register_duplicate_username_and_email(client: TestClient):
    payload = {
        "username": "bob123",
        "email": "bob@example.com",
        "password": "strongpassword123",
    }
    res1 = client.post(
        "/api/v1/auth/register",
        json=payload,
        headers={"X-Rapier-Action": "1"},
    )
    assert res1.status_code == 201

    # Duplicate username
    res2 = client.post(
        "/api/v1/auth/register",
        json={
            "username": "bob123",
            "email": "another@example.com",
            "password": "strongpassword123",
        },
        headers={"X-Rapier-Action": "1"},
    )
    assert res2.status_code == 400
    assert "already taken" in res2.json()["detail"]

    # Duplicate email
    res3 = client.post(
        "/api/v1/auth/register",
        json={
            "username": "bob_new",
            "email": "bob@example.com",
            "password": "strongpassword123",
        },
        headers={"X-Rapier-Action": "1"},
    )
    assert res3.status_code == 400
    assert "already registered" in res3.json()["detail"]


def test_login_success_and_me(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "carol",
            "email": "carol@example.com",
            "password": "carolpassword",
        },
        headers={"X-Rapier-Action": "1"},
    )

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "carolpassword"},
        headers={"X-Rapier-Action": "1"},
    )
    assert login_res.status_code == 200
    assert "rapier_session" in login_res.cookies

    # GET /me with session cookie
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "carol@example.com"


def test_login_wrong_password(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "dave",
            "email": "dave@example.com",
            "password": "davepassword",
        },
        headers={"X-Rapier-Action": "1"},
    )

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "dave@example.com", "password": "wrongpassword"},
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]


def test_missing_csrf_header_rejected(client: TestClient):
    # Mutation without X-Rapier-Action: 1 must return 403
    res = client.post(
        "/api/v1/auth/register",
        json={
            "username": "evil_csrf",
            "email": "csrf@example.com",
            "password": "password123",
        },
    )
    assert res.status_code == 403
    assert "X-Rapier-Action" in res.json()["detail"]


def test_expired_session_rejected_and_purged(client: TestClient, db_session: Session):
    # Create user directly
    user = User(
        username="expired_user",
        email="expired@example.com",
        password_hash=hash_password("testpass123"),
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(user)
    db_session.commit()

    # Create expired session
    raw_token = "expired_raw_token_value_abc"
    hashed_token = hash_session_token(raw_token)
    past_date = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2)

    session_row = DbSession(
        id=hashed_token,
        user_id=user.id,
        created_at=past_date - timedelta(days=7),
        expires_at=past_date,
    )
    db_session.add(session_row)
    db_session.commit()

    # Attempt request with expired session cookie
    client.cookies.set("rapier_session", raw_token)
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401

    # Verify session row was deleted
    remaining = db_session.get(DbSession, hashed_token)
    assert remaining is None


def test_logout_invalidates_session(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "eve",
            "email": "eve@example.com",
            "password": "evepassword",
        },
        headers={"X-Rapier-Action": "1"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "eve@example.com", "password": "evepassword"},
        headers={"X-Rapier-Action": "1"},
    )
    assert login_res.status_code == 200
    cookie_val = login_res.cookies.get("rapier_session")

    # Logout
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"X-Rapier-Action": "1"},
    )
    assert logout_res.status_code == 200

    # Attempt to use the same cookie again
    client.cookies.set("rapier_session", cookie_val)
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 401
