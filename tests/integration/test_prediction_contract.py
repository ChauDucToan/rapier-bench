"""Regression tests for the prediction failure-analysis contract (Audit C) and sampling modes (A4/G1)."""

import json

from app.config import settings
from app.db.models import BenchmarkRun, RunStatusEnum, User
from app.services.auth_service import hash_password
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _setup_run_with_predictions(client: TestClient, db_session: Session, run_id: str):
    user = User(username=f"u_{run_id}", email=f"{run_id}@test.com", password_hash=hash_password("pw"))
    db_session.add(user)
    db_session.commit()

    run = BenchmarkRun(
        id=run_id,
        user_id=user.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=4,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
        sample_selection={"selected_sample_ids": ["s1", "s2", "s3", "s4"]},
    )
    db_session.add(run)
    db_session.commit()

    art_dir = settings.artifacts_path / run_id
    art_dir.mkdir(parents=True, exist_ok=True)
    pred_file = art_dir / "predictions.jsonl"
    records = [
        {"sample_id": "s1", "parse_status": "success", "latency_ms": 12.5, "target": "A", "is_correct": True, "raw_output": "A"},
        {"sample_id": "s2", "parse_status": "success", "latency_ms": 13.5, "target": "B", "is_correct": False, "raw_output": "C"},
        {"sample_id": "s3", "parse_status": "failed", "latency_ms": 14.5, "target": "A", "is_correct": False, "raw_output": "garbage"},
        {"sample_id": "s4", "parse_status": "success", "latency_ms": 15.5, "target": "D", "is_correct": True, "raw_output": "D"},
    ]
    pred_file.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return pred_file, art_dir


def test_prediction_correctness_filters(client: TestClient, db_session: Session):
    """Correct/Incorrect/Parse Failure filters must operate on evaluated outcomes."""
    pred_file, art_dir = _setup_run_with_predictions(client, db_session, "run-pred-filters")
    try:
        base = "/api/v1/benchmarks/run-pred-filters/predictions"

        r_all = client.get(base)
        assert r_all.status_code == 200
        assert r_all.json()["total"] == 4

        r_correct = client.get(f"{base}?status=correct")
        assert r_correct.status_code == 200
        items = r_correct.json()["items"]
        assert r_correct.json()["total"] == 2
        assert {i["sample_id"] for i in items} == {"s1", "s4"}

        r_incorrect = client.get(f"{base}?status=incorrect")
        assert r_incorrect.json()["total"] == 2
        assert {i["sample_id"] for i in r_incorrect.json()["items"]} == {"s2", "s3"}

        r_parse_failure = client.get(f"{base}?status=parse_failure")
        assert r_parse_failure.json()["total"] == 1
        assert r_parse_failure.json()["items"][0]["sample_id"] == "s3"

        # raw parse_status values still work
        r_failed = client.get(f"{base}?status=failed")
        assert r_failed.json()["total"] == 1

        # invalid filter rejected
        r_bad = client.get(f"{base}?status=bogus")
        assert r_bad.status_code == 422

        # target and is_correct present on records (UI contract)
        rec = client.get(base).json()["items"][0]
        assert "target" in rec and "is_correct" in rec
    finally:
        pred_file.unlink(missing_ok=True)
        if art_dir.exists():
            art_dir.rmdir()


def test_old_prediction_artifacts_without_correctness_still_serve(client: TestClient, db_session: Session):
    """Legacy artifacts (no is_correct/target) must not crash; correctness filters
    simply return empty sets rather than failing."""
    user = User(username="u_legacy", email="legacy@test.com", password_hash=hash_password("pw"))
    db_session.add(user)
    db_session.commit()
    run = BenchmarkRun(
        id="run-legacy-preds",
        user_id=user.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=1,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    db_session.add(run)
    db_session.commit()

    art_dir = settings.artifacts_path / "run-legacy-preds"
    art_dir.mkdir(parents=True, exist_ok=True)
    pred_file = art_dir / "predictions.jsonl"
    pred_file.write_text('{"sample_id": "s1", "parse_status": "success", "latency_ms": 12.5}\n', encoding="utf-8")
    try:
        base = "/api/v1/benchmarks/run-legacy-preds/predictions"
        assert client.get(base).json()["total"] == 1
        assert client.get(f"{base}?status=correct").json()["total"] == 0
        assert client.get(f"{base}?status=incorrect").json()["total"] == 0
    finally:
        pred_file.unlink(missing_ok=True)
        if art_dir.exists():
            art_dir.rmdir()


def _auth(client, username, email):
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": "password123"},
        headers={"X-Rapier-Action": "1"},
    )
    assert reg.status_code == 201, reg.text
    # F1: register now establishes the session directly
    return reg.json()["id"]


def test_full_mode_creates_null_count_run(client: TestClient, db_session: Session):
    """A4: 'full' must select the entire eligible split (count=None), not 1000."""
    from unittest.mock import AsyncMock, patch

    _auth(client, "u_full", "full@test.com")

    with patch("app.services.benchmark_service.ProcessManager.spawn_runner", new=AsyncMock(return_value=12345)):
        res = client.post(
            "/api/v1/benchmarks",
            json={
                "model_id": "lumma-0.6b",
                "dataset_id": "sciq",
                "sample_size_mode": "full",
                "is_private": False,
            },
            headers={"X-Rapier-Action": "1"},
        )
    assert res.status_code == 202
    data = res.json()
    assert data["sample_count"] is None
    assert data["sample_size_mode"] == "full"
    db_session.query(BenchmarkRun).filter(BenchmarkRun.id == data["id"]).delete()
    db_session.commit()


def test_custom_mode_uses_explicit_count(client: TestClient, db_session: Session):
    """G1: 'custom' mode with explicit sample_count must be accepted."""
    from unittest.mock import AsyncMock, patch

    _auth(client, "u_custom", "custom@test.com")

    with patch("app.services.benchmark_service.ProcessManager.spawn_runner", new=AsyncMock(return_value=12346)):
        res = client.post(
            "/api/v1/benchmarks",
            json={
                "model_id": "lumma-0.6b",
                "dataset_id": "sciq",
                "sample_size_mode": "custom",
                "sample_count": 33,
                "is_private": False,
            },
            headers={"X-Rapier-Action": "1"},
        )
    assert res.status_code == 202
    data = res.json()
    assert data["sample_count"] == 33
    db_session.query(BenchmarkRun).filter(BenchmarkRun.id == data["id"]).delete()
    db_session.commit()


def test_custom_mode_without_count_rejected(client: TestClient, db_session: Session):
    _auth(client, "u_custom2", "custom2@test.com")
    res = client.post(
        "/api/v1/benchmarks",
        json={
            "model_id": "lumma-0.6b",
            "dataset_id": "sciq",
            "sample_size_mode": "custom",
            "is_private": False,
        },
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 400
    assert "sample_count is required" in res.json()["detail"]


def test_registration_creates_session_cookie(client: TestClient):
    """F1: successful registration must establish a server-side session."""
    res = client.post(
        "/api/v1/auth/register",
        json={
            "username": "reg_session_user",
            "email": "reg_session@test.com",
            "password": "password123",
        },
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 201
    assert "rapier_session" in res.cookies

    # Session cookie must authenticate protected endpoints immediately
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "reg_session_user"


def test_comparison_rejects_missing_sample_selection(client: TestClient, db_session: Session):
    """D1: runs lacking sample-selection metadata must not be silently compared."""
    user = User(username="u_d1", email="d1@test.com", password_hash=hash_password("pw"))
    db_session.add(user)
    db_session.commit()
    common = dict(
        user_id=user.id,
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        split="test",
        sample_count=2,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    db_session.add_all([
        BenchmarkRun(id="run-d1-a", model_id="lumma-0.6b", sample_selection={"selected_sample_ids": ["s1", "s2"]}, **common),
        BenchmarkRun(id="run-d1-b", model_id="apertus-0.5b", **common),  # no selection metadata
    ])
    db_session.commit()

    res = client.get("/api/v1/comparisons?run_ids=run-d1-a,run-d1-b")
    assert res.status_code == 400
    assert "sample-selection metadata" in res.json()["detail"]
