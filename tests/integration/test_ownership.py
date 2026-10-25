from app.db.models import BenchmarkRun, RunStatusEnum, User
from app.services.auth_service import hash_password
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def create_user(db: Session, username: str, email: str) -> User:
    u = User(username=username, email=email, password_hash=hash_password("password123"))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_cross_user_private_run_returns_404(client: TestClient, db_session: Session):
    owner = create_user(db_session, "owner_user", "owner@example.com")
    create_user(db_session, "stranger_user", "stranger@example.com")

    # Create private run owned by owner
    run = BenchmarkRun(
        id="private-run-123",
        user_id=owner.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.COMPLETED,
        is_private=True,
    )
    db_session.add(run)
    db_session.commit()

    # 1. Unauthenticated request -> 404 (not 403, avoids leaking existence)
    res_unauth = client.get(f"/api/v1/benchmarks/{run.id}")
    assert res_unauth.status_code == 404

    res_res_unauth = client.get(f"/api/v1/benchmarks/{run.id}/results")
    assert res_res_unauth.status_code == 404

    res_pred_unauth = client.get(f"/api/v1/benchmarks/{run.id}/predictions")
    assert res_pred_unauth.status_code == 404

    res_exp_unauth = client.get(f"/api/v1/benchmarks/{run.id}/export")
    assert res_exp_unauth.status_code == 404

    # 2. Authenticated as stranger -> 404
    client.post(
        "/api/v1/auth/login",
        json={"email": "stranger@example.com", "password": "password123"},
        headers={"X-Rapier-Action": "1"},
    )

    res_stranger = client.get(f"/api/v1/benchmarks/{run.id}")
    assert res_stranger.status_code == 404

    res_res_stranger = client.get(f"/api/v1/benchmarks/{run.id}/results")
    assert res_res_stranger.status_code == 404

    # 3. Authenticated as owner -> 200
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
        headers={"X-Rapier-Action": "1"},
    )
    res_owner = client.get(f"/api/v1/benchmarks/{run.id}")
    assert res_owner.status_code == 200
    assert res_owner.json()["id"] == "private-run-123"


def test_cross_user_cancel_returns_403(client: TestClient, db_session: Session):
    owner = create_user(db_session, "owner2", "owner2@example.com")
    create_user(db_session, "stranger2", "stranger2@example.com")

    run = BenchmarkRun(
        id="active-run-456",
        user_id=owner.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.RUNNING,
        is_private=False,
    )
    db_session.add(run)
    db_session.commit()

    # Stranger tries to cancel -> 403 Forbidden
    client.post(
        "/api/v1/auth/login",
        json={"email": "stranger2@example.com", "password": "password123"},
        headers={"X-Rapier-Action": "1"},
    )
    res = client.post(
        f"/api/v1/benchmarks/{run.id}/cancel",
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]


def test_cancel_terminal_run_returns_409(client: TestClient, db_session: Session):
    owner = create_user(db_session, "owner3", "owner3@example.com")

    run = BenchmarkRun(
        id="terminal-run-789",
        user_id=owner.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    db_session.add(run)
    db_session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": "owner3@example.com", "password": "password123"},
        headers={"X-Rapier-Action": "1"},
    )
    res = client.post(
        f"/api/v1/benchmarks/{run.id}/cancel",
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 409
    assert "already in a terminal state" in res.json()["detail"]
