from app.db.models import BenchmarkMetric, BenchmarkRun, RunStatusEnum, User
from app.services.auth_service import hash_password
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def setup_recommendation_models(db: Session) -> None:
    # Ensure a user exists
    user = User(
        username="rec_owner",
        email="rec@example.com",
        password_hash=hash_password("pw"),
    )
    db.add(user)
    db.commit()

    # 3 models in catalog: lumma-0.6b (vram 1.30), apertus-0.5b (vram 1.15), lfm2.5-350m (vram 0.71)
    # Model 1: lumma-0.6b -> High quality (0.90), Higher latency (120ms), Higher VRAM (1.30)
    # Model 2: apertus-0.5b -> Mid quality (0.75), Mid latency (60ms), Mid VRAM (1.15)
    # Model 3: lfm2.5-350m -> Lower quality (0.60), Low latency (20ms), Low VRAM (0.71)

    r1 = BenchmarkRun(
        id="rec-run-lumma",
        user_id=user.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=100,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    r2 = BenchmarkRun(
        id="rec-run-apertus",
        user_id=user.id,
        model_id="apertus-0.5b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=100,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    r3 = BenchmarkRun(
        id="rec-run-lfm",
        user_id=user.id,
        model_id="lfm2.5-350m",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=100,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    db.add_all([r1, r2, r3])
    db.commit()

    db.add_all([
        BenchmarkMetric(run_id="rec-run-lumma", metric_name="accuracy", metric_value=0.90),
        BenchmarkMetric(run_id="rec-run-lumma", metric_name="avg_latency_ms", metric_value=120.0),
        BenchmarkMetric(run_id="rec-run-apertus", metric_name="accuracy", metric_value=0.75),
        BenchmarkMetric(run_id="rec-run-apertus", metric_name="avg_latency_ms", metric_value=60.0),
        BenchmarkMetric(run_id="rec-run-lfm", metric_name="accuracy", metric_value=0.60),
        BenchmarkMetric(run_id="rec-run-lfm", metric_name="avg_latency_ms", metric_value=20.0),
    ])
    db.commit()


def test_weights_change_ranking(client: TestClient, db_session: Session):
    setup_recommendation_models(db_session)

    # 1. Quality-heavy: lumma-0.6b should win
    res_quality = client.post(
        "/api/v1/recommendations",
        json={
            "domain": "education",
            "weights": {"quality": 0.9, "latency": 0.05, "vram": 0.05},
        },
        headers={"X-Rapier-Action": "1"},
    )
    assert res_quality.status_code == 200
    q_data = res_quality.json()
    assert q_data["status"] == "success"
    assert q_data["recommendations"][0]["model_id"] == "lumma-0.6b"

    # 2. Latency/VRAM-heavy: lfm2.5-350m should win
    res_speed = client.post(
        "/api/v1/recommendations",
        json={
            "domain": "education",
            "weights": {"quality": 0.05, "latency": 0.65, "vram": 0.3},
        },
        headers={"X-Rapier-Action": "1"},
    )
    assert res_speed.status_code == 200
    s_data = res_speed.json()
    assert s_data["status"] == "success"
    assert s_data["recommendations"][0]["model_id"] == "lfm2.5-350m"


def test_hardware_and_quality_filtering(client: TestClient, db_session: Session):
    setup_recommendation_models(db_session)

    # VRAM cap: max 1.0 GB excludes lumma (1.30) and apertus (1.15), leaving 1 model (<3 -> insufficient_sample)
    res_vram = client.post(
        "/api/v1/recommendations",
        json={
            "domain": "education",
            "constraints": {"max_vram_gb": 1.0},
        },
        headers={"X-Rapier-Action": "1"},
    )
    assert res_vram.status_code == 200
    assert res_vram.json()["status"] == "insufficient_sample"
    assert res_vram.json()["eligible_count"] == 1


def test_zero_eligible_models_response(client: TestClient, db_session: Session):
    setup_recommendation_models(db_session)

    # Impossible constraint (min_quality 0.99)
    res = client.post(
        "/api/v1/recommendations",
        json={
            "domain": "education",
            "constraints": {"min_quality": 0.99},
        },
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "insufficient_sample"
    assert data["eligible_count"] == 0
    assert len(data["recommendations"]) == 0
    assert "Zero models eligible" in data["explanation"] or "No models" in data["explanation"]


def test_insufficient_sample_under_three_models(client: TestClient, db_session: Session):
    # Only 2 models in DB
    user = User(username="u_two", email="two@test.com", password_hash=hash_password("pw"))
    db_session.add(user)
    db_session.commit()

    r1 = BenchmarkRun(
        id="run-only-1",
        user_id=user.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    r2 = BenchmarkRun(
        id="run-only-2",
        user_id=user.id,
        model_id="apertus-0.5b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    db_session.add_all([
        BenchmarkMetric(run_id="run-only-1", metric_name="accuracy", metric_value=0.8),
        BenchmarkMetric(run_id="run-only-1", metric_name="avg_latency_ms", metric_value=50.0),
        BenchmarkMetric(run_id="run-only-2", metric_name="accuracy", metric_value=0.7),
        BenchmarkMetric(run_id="run-only-2", metric_name="avg_latency_ms", metric_value=40.0),
    ])
    db_session.commit()

    res = client.post(
        "/api/v1/recommendations",
        json={"domain": "education"},
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "insufficient_sample"
    assert data["eligible_count"] == 2
    assert "Fewer than 3 comparable models" in data["limitations"][0]


def test_missing_metrics_excluded_never_invented(client: TestClient, db_session: Session):
    setup_recommendation_models(db_session)

    # Add a 4th model without accuracy metric
    user = db_session.query(User).first()
    r4 = BenchmarkRun(
        id="run-missing-metric",
        user_id=user.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    db_session.add(r4)
    db_session.commit()

    res = client.post(
        "/api/v1/recommendations",
        json={"domain": "education"},
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    # Still exactly 3 models ranked, no invented score for incomplete runs
    assert len(data["recommendations"]) == 3


def test_incomparable_protocols_not_mixed(client: TestClient, db_session: Session):
    setup_recommendation_models(db_session)

    user = db_session.query(User).first()
    # Add a run under a different protocol "sciq_closed_book"
    r_alt = BenchmarkRun(
        id="run-alt-protocol",
        user_id=user.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_closed_book",
        sample_count=10,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    db_session.add(r_alt)
    db_session.commit()
    db_session.add(
        BenchmarkMetric(run_id="run-alt-protocol", metric_name="accuracy", metric_value=0.99)
    )
    db_session.commit()

    res = client.post(
        "/api/v1/recommendations",
        json={"domain": "education"},
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 200
    data = res.json()
    # The dominant protocol sciq_evidence_grounded is used, not mixed with sciq_closed_book
    assert "sciq_evidence_grounded" in data["limitations"][0]


def test_invalid_weights_handling(client: TestClient, db_session: Session):
    setup_recommendation_models(db_session)

    # 1. Negative weight -> 400
    res_neg = client.post(
        "/api/v1/recommendations",
        json={"domain": "education", "weights": {"quality": -0.5, "latency": 0.5, "vram": 0.5}},
        headers={"X-Rapier-Action": "1"},
    )
    assert res_neg.status_code == 400
    assert "non-negative" in res_neg.json()["detail"]

    # 2. All-zero weights -> 400
    res_zero = client.post(
        "/api/v1/recommendations",
        json={"domain": "education", "weights": {"quality": 0.0, "latency": 0.0, "vram": 0.0}},
        headers={"X-Rapier-Action": "1"},
    )
    assert res_zero.status_code == 400
    assert "greater than zero" in res_zero.json()["detail"]

    # 3. Weights not summing to 1 -> automatically normalized
    res_norm = client.post(
        "/api/v1/recommendations",
        json={"domain": "education", "weights": {"quality": 10.0, "latency": 20.0, "vram": 10.0}},
        headers={"X-Rapier-Action": "1"},
    )
    assert res_norm.status_code == 200
    assert "quality=0.25, latency=0.50, vram=0.25" in res_norm.json()["explanation"]


def test_deterministic_tie_breaking(client: TestClient, db_session: Session):
    user = User(username="tie_user", email="tie@test.com", password_hash=hash_password("pw"))
    db_session.add(user)
    db_session.commit()

    # Create 3 models with identical scores:
    # Model A: apertus-0.5b
    # Model B: lumma-0.6b
    # Model C: lfm2.5-350m
    # All same quality 0.80, same latency 50ms, but different model_id
    r1 = BenchmarkRun(
        id="tie-1",
        user_id=user.id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    r2 = BenchmarkRun(
        id="tie-2",
        user_id=user.id,
        model_id="apertus-0.5b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    r3 = BenchmarkRun(
        id="tie-3",
        user_id=user.id,
        model_id="lfm2.5-350m",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        sample_count=10,
        status=RunStatusEnum.COMPLETED,
        is_private=False,
    )
    db_session.add_all([r1, r2, r3])
    db_session.commit()

    for rid in ["tie-1", "tie-2", "tie-3"]:
        db_session.add_all([
            BenchmarkMetric(run_id=rid, metric_name="accuracy", metric_value=0.80),
            BenchmarkMetric(run_id=rid, metric_name="avg_latency_ms", metric_value=50.0),
        ])
    db_session.commit()

    # VRAM weights set to 0.0 so composite scores tie exactly
    res = client.post(
        "/api/v1/recommendations",
        json={"domain": "education", "weights": {"quality": 0.5, "latency": 0.5, "vram": 0.0}},
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 200
    recs = res.json()["recommendations"]
    assert len(recs) == 3
    # Composite scores and metrics tie -> alphabetical by model_id: apertus-0.5b, lfm2.5-350m, lumma-0.6b
    assert [r["model_id"] for r in recs] == ["apertus-0.5b", "lfm2.5-350m", "lumma-0.6b"]


def test_recommendation_recognizes_latency_ms_mean(client: TestClient, db_session: Session):
    """Verify that runs with latency_ms_mean (from benchmark engine) are recognized."""
    user = User(username="u_mean", email="mean@test.com", password_hash=hash_password("pw"))
    db_session.add(user)
    db_session.commit()

    for i, m_id in enumerate(["lumma-0.6b", "apertus-0.5b", "lfm2.5-350m"]):
        rid = f"mean-run-{i}"
        db_session.add(
            BenchmarkRun(
                id=rid,
                user_id=user.id,
                model_id=m_id,
                dataset_id="sciq",
                protocol_id="sciq_evidence_grounded",
                sample_count=10,
                status=RunStatusEnum.COMPLETED,
                is_private=False,
            )
        )
        db_session.add_all([
            BenchmarkMetric(run_id=rid, metric_name="accuracy", metric_value=0.85),
            BenchmarkMetric(run_id=rid, metric_name="latency_ms_mean", metric_value=45.0 + i * 10),
        ])
    db_session.commit()

    res = client.post(
        "/api/v1/recommendations",
        json={"domain": "education", "weights": {"quality": 0.5, "latency": 0.5, "vram": 0.0}},
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert len(res.json()["recommendations"]) == 3
