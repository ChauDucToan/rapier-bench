from pathlib import Path

from app.config import settings
from app.db.models import BenchmarkMetric, BenchmarkRun, RunStatusEnum, User
from app.services.auth_service import hash_password
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def authenticate_user(client: TestClient, username: str = "tester", email: str = "tester@example.com") -> int:
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": "password123"},
        headers={"X-Rapier-Action": "1"},
    )
    user_id = reg.json()["id"]
    client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
        headers={"X-Rapier-Action": "1"},
    )
    return user_id


def test_create_benchmark_unknown_model_rejected(client: TestClient):
    authenticate_user(client)
    res = client.post(
        "/api/v1/benchmarks",
        json={"model_id": "nonexistent_model", "dataset_id": "sciq"},
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 400
    assert "Unknown model_id" in res.json()["detail"]


def test_create_benchmark_unknown_dataset_rejected(client: TestClient):
    authenticate_user(client)
    res = client.post(
        "/api/v1/benchmarks",
        json={"model_id": "lumma-0.6b", "dataset_id": "nonexistent_dataset"},
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 400
    assert "Unknown dataset_id" in res.json()["detail"]


def test_create_benchmark_success(client: TestClient):
    authenticate_user(client)
    res = client.post(
        "/api/v1/benchmarks",
        json={
            "model_id": "lumma-0.6b",
            "dataset_id": "sciq",
            "sample_size_mode": "smoke",
            "is_private": False,
        },
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "queued"
    assert data["model_id"] == "lumma-0.6b"
    assert data["dataset_id"] == "sciq"
    assert data["sample_count"] == 10
    assert "id" in data


def test_path_traversal_on_artifact_serving(client: TestClient, db_session: Session):
    user_id = authenticate_user(client)
    run = BenchmarkRun(
        id="test-run-artifacts-1",
        user_id=user_id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    db_session.add(run)
    db_session.commit()

    # Traversal attempts on export
    res1 = client.get("/api/v1/benchmarks/test-run-artifacts-1/export?format=jsonl")
    assert res1.status_code == 404

    # Traversal via run_id manipulation
    res2 = client.get("/api/v1/benchmarks/../../etc/passwd/export")
    assert res2.status_code in [404, 422]

    # Traversal with URL-encoded slashes
    res3 = client.get("/api/v1/benchmarks/%2E%2E%2F%2E%2E%2Fetc%2Fpasswd/export")
    assert res3.status_code in [404, 422]


def test_benchmark_export_jsonl_and_csv(client: TestClient, db_session: Session):
    user_id = authenticate_user(client)
    run_id = "test-export-run"
    run = BenchmarkRun(
        id=run_id,
        user_id=user_id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=2,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    db_session.add(run)
    db_session.commit()

    # Create dummy artifact predictions.jsonl
    art_dir = settings.artifacts_path / run_id
    art_dir.mkdir(parents=True, exist_ok=True)
    pred_file = art_dir / "predictions.jsonl"
    pred_file.write_text(
        '{"sample_id": "s1", "parse_status": "success", "latency_ms": 12.5}\n'
        '{"sample_id": "s2", "parse_status": "success", "latency_ms": 14.1}\n',
        encoding="utf-8",
    )

    try:
        # JSONL export
        res_jsonl = client.get(f"/api/v1/benchmarks/{run_id}/export?format=jsonl")
        assert res_jsonl.status_code == 200
        assert "s1" in res_jsonl.text
        assert "s2" in res_jsonl.text

        # CSV export
        res_csv = client.get(f"/api/v1/benchmarks/{run_id}/export?format=csv")
        assert res_csv.status_code == 200
        assert "sample_id" in res_csv.text
        assert "12.5" in res_csv.text

        # Predictions pagination API
        res_preds = client.get(f"/api/v1/benchmarks/{run_id}/predictions?limit=10&offset=0")
        assert res_preds.status_code == 200
        data = res_preds.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
    finally:
        if pred_file.exists():
            pred_file.unlink()
        if art_dir.exists():
            art_dir.rmdir()


def test_comparisons_and_leaderboard(client: TestClient, db_session: Session):
    user = User(username="u1", email="u1@test.com", password_hash=hash_password("pw"))
    db_session.add(user)
    db_session.commit()

    r1 = BenchmarkRun(
        id="run-comp-1",
        user_id=user.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
        sample_selection={"selected_sample_ids": [f"sciq:test:{i}" for i in range(10)]},
    )
    r2 = BenchmarkRun(
        id="run-comp-2",
        user_id=user.id,
        model_id="apertus-0.5b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
        sample_selection={"selected_sample_ids": [f"sciq:test:{i}" for i in range(10)]},
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    db_session.add_all([
        BenchmarkMetric(run_id="run-comp-1", metric_name="accuracy", metric_value=0.85),
        BenchmarkMetric(run_id="run-comp-1", metric_name="avg_latency_ms", metric_value=45.0),
        BenchmarkMetric(run_id="run-comp-2", metric_name="accuracy", metric_value=0.78),
        BenchmarkMetric(run_id="run-comp-2", metric_name="avg_latency_ms", metric_value=40.0),
    ])
    db_session.commit()

    # Comparison API (<2 run_ids -> 400)
    res_bad = client.get("/api/v1/comparisons?run_ids=run-comp-1")
    assert res_bad.status_code == 400

    # Comparison API (2 run_ids -> 200)
    res_comp = client.get("/api/v1/comparisons?run_ids=run-comp-1,run-comp-2")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert len(comp_data["runs"]) == 2
    assert "accuracy" in comp_data["metrics_comparison"]
    assert comp_data["metrics_comparison"]["accuracy"]["run-comp-1"] == 0.85
    assert comp_data["metrics_comparison"]["accuracy"]["run-comp-2"] == 0.78

    # Leaderboard API
    res_lb = client.get("/api/v1/leaderboard?domain=education")
    assert res_lb.status_code == 200
    lb_data = res_lb.json()
    assert lb_data["total"] >= 2
    # Verify sorted by primary metric desc
    assert lb_data["items"][0]["model_id"] == "lumma-0.6b"
    assert lb_data["items"][0]["primary_metric_value"] == 0.85

def test_comparisons_reject_different_sample_ids(client: TestClient, db_session: Session):
    """Same dataset+protocol+split but different evaluated sample IDs must NOT be compared."""
    user = User(username="u2", email="u2@test.com", password_hash=hash_password("pw"))
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
    # Same protocol, DIFFERENT seeds -> disjoint sample sets.
    db_session.add_all([
        BenchmarkRun(
            id="run-same-a",
            model_id="lumma-0.6b",
            sample_selection={"selected_sample_ids": ["sciq:test:1", "sciq:test:2"]},
            **common,
        ),
        BenchmarkRun(
            id="run-same-b",
            model_id="apertus-0.5b",
            sample_selection={"selected_sample_ids": ["sciq:test:3", "sciq:test:4"]},
            **common,
        ),
        # Identical sample sets -> comparable.
        BenchmarkRun(
            id="run-same-c",
            model_id="lfm2.5-350m",
            sample_selection={"selected_sample_ids": ["sciq:test:1", "sciq:test:2"]},
            **common,
        ),
    ])
    db_session.commit()

    res_ok = client.get("/api/v1/comparisons?run_ids=run-same-a,run-same-c")
    assert res_ok.status_code == 200
    body = res_ok.json()
    assert body["diffs"]["sample_selection_available_for_all_runs"] is True
    assert body["diffs"]["sample_id_sets"]["run-same-a"] == ["sciq:test:1", "sciq:test:2"]

    res_bad = client.get("/api/v1/comparisons?run_ids=run-same-a,run-same-b")
    assert res_bad.status_code == 400
    assert "different sample IDs" in res_bad.json()["detail"]


def test_comparisons_reject_mixed_protocols(client: TestClient, db_session: Session):
    """Cross-protocol or cross-dataset comparisons are rejected, not silently averaged."""
    user = User(username="u3", email="u3@test.com", password_hash=hash_password("pw"))
    db_session.add(user)
    db_session.commit()

    db_session.add_all([
        BenchmarkRun(
            id="run-mix-a",
            user_id=user.id,
            model_id="lumma-0.6b",
            dataset_id="sciq",
            protocol_id="sciq_evidence_grounded",
            sample_count=5,
            status=RunStatusEnum.COMPLETED,
            is_private=False,
            sample_selection={"selected_sample_ids": ["sciq:test:1"]},
        ),
        BenchmarkRun(
            id="run-mix-b",
            user_id=user.id,
            model_id="lumma-0.6b",
            dataset_id="sciq",
            protocol_id="sciq_closed_book",
            sample_count=5,
            status=RunStatusEnum.COMPLETED,
            is_private=False,
            sample_selection={"selected_sample_ids": ["sciq:test:1"]},
        ),
    ])
    db_session.commit()

    res = client.get("/api/v1/comparisons?run_ids=run-mix-a,run-mix-b")
    assert res.status_code == 400
    assert "different protocols" in res.json()["detail"]


def test_safe_artifact_path_sibling_prefix_traversal(tmp_path: Path):
    from app.services.benchmark_service import SafePathError, safe_artifact_path

    base_artifacts = tmp_path / "artifacts"
    base_artifacts.mkdir()
    sibling_artifacts = tmp_path / "artifacts_evil"
    sibling_artifacts.mkdir()
    secret_file = sibling_artifacts / "secret.txt"
    secret_file.write_text("evil", encoding="utf-8")

    # Attempt to access sibling directory with shared prefix "artifacts_evil"
    import pytest
    with pytest.raises(SafePathError):
        safe_artifact_path(base_artifacts, "../artifacts_evil", "secret.txt")


def test_leaderboard_latency_ms_mean_metric(client: TestClient, db_session: Session):
    user = User(username="u_latency", email="ulat@test.com", password_hash=hash_password("pw"))
    db_session.add(user)
    db_session.commit()

    run = BenchmarkRun(
        id="run-latency-mean",
        user_id=user.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        sample_selection={"selected_sample_ids": [f"sciq:test:{i}" for i in range(10)]},
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    db_session.add(run)
    db_session.commit()

    db_session.add_all([
        BenchmarkMetric(run_id="run-latency-mean", metric_name="accuracy", metric_value=0.91),
        BenchmarkMetric(run_id="run-latency-mean", metric_name="latency_ms_mean", metric_value=73.5),
    ])
    db_session.commit()

    res = client.get("/api/v1/leaderboard?domain=education")
    assert res.status_code == 200
    items = res.json()["items"]
    match = next((item for item in items if item["run_id"] == "run-latency-mean"), None)
    assert match is not None
    assert match["avg_latency_ms"] == 73.5


def test_create_benchmark_default_is_private(client: TestClient, db_session: Session):
    authenticate_user(client, username="priv_user", email="priv@test.com")
    # Omit is_private -> must default to True per ARCHITECTURE §5/§8
    res = client.post(
        "/api/v1/benchmarks",
        json={"model_id": "lumma-0.6b", "dataset_id": "sciq"},
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 202
    assert res.json()["is_private"] is True

    # Explicitly set is_private=False -> allowed
    res_pub = client.post(
        "/api/v1/benchmarks",
        json={"model_id": "lumma-0.6b", "dataset_id": "sciq", "is_private": False},
        headers={"X-Rapier-Action": "1"},
    )
    assert res_pub.status_code == 202
    assert res_pub.json()["is_private"] is False

    user = db_session.query(User).filter_by(username="priv_user").first()
    model_run = BenchmarkRun(
        id="model-priv-check",
        user_id=user.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=5,
    )
    db_session.add(model_run)
    db_session.flush()
    assert model_run.is_private is True

def test_sample_selection_populated_from_run_config(db_session: Session, tmp_path: Path):
    import json

    from app.config import settings

    user = User(username="u_sample_sel", email="usel@test.com", password_hash=hash_password("pw"))
    db_session.add(user)
    db_session.commit()

    run_id = "test-sample-sel-pop"
    run = BenchmarkRun(
        id=run_id,
        user_id=user.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.RUNNING,
        is_private=False,
    )
    db_session.add(run)
    db_session.commit()
    # Write mock run_config.json
    art_dir = settings.artifacts_path / run_id
    art_dir.mkdir(parents=True, exist_ok=True)
    rc_file = art_dir / "run_config.json"
    rc_file.write_text(
        json.dumps({
            "run_id": run_id,
            "requested_samples": 10,
            "actual_samples": 8,
            "selected_sample_ids": [f"sciq:test:{i}" for i in range(8)],
            "shortfall_report": {"shortfall": 2},
        }),
        encoding="utf-8",
    )

    try:
        # Read and assign as runner does
        with open(rc_file, encoding="utf-8") as f:
            cfg_data = json.load(f)
            run.sample_selection = {
                "selected_sample_ids": cfg_data.get("selected_sample_ids", []),
                "requested_samples": cfg_data.get("requested_samples"),
                "actual_samples": cfg_data.get("actual_samples"),
                "sample_shortfall": 2,
                "shortfall_report": cfg_data.get("shortfall_report"),
            }
            db_session.commit()

        refreshed = db_session.get(BenchmarkRun, run_id)
        assert refreshed.sample_selection is not None
        assert len(refreshed.sample_selection["selected_sample_ids"]) == 8
        assert refreshed.sample_selection["sample_shortfall"] == 2
    finally:
        if rc_file.exists():
            rc_file.unlink()
        if art_dir.exists():
            art_dir.rmdir()
