"""Section 14 API integration flow: register/login → private benchmark →
recommendation privacy → cohort selection → metric names → leaderboard."""

def test_full_api_flow(client, db_session, tmp_path):
    # 1. Register + session
    r = client.post("/api/v1/auth/register", json={"username": "flow_a", "email": "flow_a@t.com", "password": "password123"}, headers={"X-Rapier-Action": "1"})
    assert r.status_code == 201, r.text
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    uid_a = me.json()["id"]

    # 2. Create a private benchmark (full mode) — worker mocked
    from unittest.mock import AsyncMock, patch
    with patch("app.services.benchmark_service.ProcessManager.spawn_runner", new=AsyncMock(return_value=999)):
        r = client.post("/api/v1/benchmarks", json={"model_id": "lumma-0.6b", "dataset_id": "sciq", "sample_size_mode": "full", "is_private": True}, headers={"X-Rapier-Action": "1"})
    assert r.status_code == 202, r.text
    run_a = r.json()
    assert run_a["sample_count"] is None  # full mode
    assert run_a["is_private"] is True

    # 3. Read its results (owner)
    r = client.get(f"/api/v1/benchmarks/{run_a['id']}")
    assert r.status_code == 200

    # 4. Stranger cannot see it
    client.cookies.clear()
    r2 = client.post("/api/v1/auth/register", json={"username": "flow_b", "email": "flow_b@t.com", "password": "password123"}, headers={"X-Rapier-Action": "1"})
    assert r2.status_code == 201
    r = client.get(f"/api/v1/benchmarks/{run_a['id']}")
    assert r.status_code == 404

    # 5. Recommendation with only stranger's public view: no leak
    rec = client.post("/api/v1/recommendations", json={"domain": "education"}, headers={"X-Rapier-Action": "1"})
    assert rec.status_code == 200
    assert run_a["id"] not in rec.text

    # 6-9. Cohort + metric-name integrity via seeded runs (direct DB)
    from app.db.models import BenchmarkMetric, BenchmarkRun, RunStatusEnum
    ids = [f"s{i}" for i in range(20)]
    for j, (m, acc) in enumerate([("lumma-0.6b", 0.9), ("apertus-0.5b", 0.8), ("lfm2.5-350m", 0.7)]):
        rid = f"flow-co-{j}"
        db_session.add(BenchmarkRun(id=rid, user_id=uid_a, model_id=m, dataset_id="sciq",
            protocol_id="sciq_evidence_grounded", split="test", sample_size_mode="standard",
            sample_count=20, seed=42, status=RunStatusEnum.COMPLETED, is_private=False,
            sample_selection={"selected_sample_ids": ids}))
        db_session.commit()
        db_session.add(BenchmarkMetric(run_id=rid, metric_name="accuracy", metric_value=acc))
        db_session.add(BenchmarkMetric(run_id=rid, metric_name="latency_ms_mean", metric_value=50.0 + j))
        db_session.commit()

    # FaithEval strict-only run: must never appear as balanced_score
    fe_ids = [f"f{i}" for i in range(10)]
    db_session.add(BenchmarkRun(id="flow-fe", user_id=uid_a, model_id="lumma-0.6b", dataset_id="faitheval",
        protocol_id="faitheval_unanswerable_v1", split="test", sample_size_mode="standard",
        sample_count=10, seed=42, status=RunStatusEnum.COMPLETED, is_private=False,
        sample_selection={"selected_sample_ids": fe_ids}))
    db_session.commit()
    db_session.add(BenchmarkMetric(run_id="flow-fe", metric_name="unanswerable_context_accuracy_strict", metric_value=0.9))
    db_session.commit()

    lb = client.get("/api/v1/leaderboard")
    groups = lb.json()["groups"]
    all_items = [i for g in groups for i in g["items"]]
    assert all(i["run_id"] != "flow-fe" for i in all_items), "FaithEval strict-only leaked into leaderboard"
    for g in groups:
        for i in g["items"]:
            assert i["primary_metric_name"] in ("accuracy", "micro_f1", "balanced_accuracy", "balanced_score", "prompt_level_strict_acc")
    # grouped rendering: sciq group exists with 3 models
    sciq_groups = [g for g in groups if g["dataset_id"] == "sciq"]
    assert len(sciq_groups) == 1 and len(sciq_groups[0]["items"]) == 3

    # 10. Full-mode rerun compatibility (rerun of full run)
    client.cookies.clear()
    client.post("/api/v1/auth/login", json={"email": "flow_a@t.com", "password": "password123"}, headers={"X-Rapier-Action": "1"})
    with patch("app.services.benchmark_service.ProcessManager.spawn_runner", new=AsyncMock(return_value=998)):
        rr = client.post(f"/api/v1/benchmarks/{run_a['id']}/rerun", headers={"X-Rapier-Action": "1"})
    assert rr.status_code == 202
    assert rr.json()["sample_count"] is None
