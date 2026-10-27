"""FIX 1/2/3/4/8 regression tests: FaithEval metric integrity, common-cohort
recommendation, private-run visibility, hardware latency gating, numeric
robustness, and leaderboard cohort grouping."""

import pytest
from app.db.models import (
    BenchmarkMetric,
    BenchmarkRun,
    RunStatusEnum,
    User,
)
from app.services.auth_service import hash_password
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

SAMPLES_A = [f"sciq:test:{i}" for i in range(200)]
SAMPLES_B = [f"sciq:test:{i}" for i in range(200, 400)]
SAMPLES_SMALL = [f"sciq:test:{i}" for i in range(10)]


def _user(db: Session, name: str) -> User:
    u = User(username=name, email=f"{name}@test.com", password_hash=hash_password("pw"))
    db.add(u)
    db.commit()
    return u


def _run(
    db: Session,
    run_id: str,
    user_id: int,
    model_id: str,
    *,
    dataset_id="sciq",
    protocol_id="sciq_evidence_grounded",
    split="test",
    seed=42,
    is_private=False,
    selected_ids=SAMPLES_A,
    metrics: dict[str, float] | None = None,
    hardware: dict | None = None,
):
    run = BenchmarkRun(
        id=run_id,
        user_id=user_id,
        model_id=model_id,
        dataset_id=dataset_id,
        protocol_id=protocol_id,
        split=split,
        sample_size_mode="standard",
        sample_count=len(selected_ids),
        seed=seed,
        status=RunStatusEnum.COMPLETED,
        is_private=is_private,
        sample_selection={"selected_sample_ids": selected_ids},
        hardware_metadata=hardware,
    )
    db.add(run)
    db.commit()
    if metrics:
        db.add_all(
            [
                BenchmarkMetric(run_id=run_id, metric_name=k, metric_value=v)
                for k, v in metrics.items()
            ]
        )
        db.commit()
    return run



def _register(client: TestClient, name: str) -> int:
    """Register via API (establishes session cookie) and return user id."""
    res = client.post(
        "/api/v1/auth/register",
        json={"username": name, "email": f"{name}@test.com", "password": "password123"},
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]

def _recommend(client: TestClient, body: dict | None = None):
    return client.post(
        "/api/v1/recommendations",
        json=body or {"domain": "education"},
        headers={"X-Rapier-Action": "1"},
    )


# ---------------------------------------------------------------------------
# FIX 1: FaithEval metric names never substituted
# ---------------------------------------------------------------------------


class TestFaithEvalMetricIntegrity:
    def test_leaderboard_excludes_faitheval_without_balanced_score(self, client: TestClient, db_session: Session):
        """Unanswerable-only runs (strict present, balanced_score absent) must not
        appear on the leaderboard at all — never labeled balanced_score."""
        user = _user(db_session, "fe_user")
        _run(
            db_session,
            "fe-run-1",
            user.id,
            "lumma-0.6b",
            dataset_id="faitheval",
            protocol_id="faitheval_unanswerable_v1",
            selected_ids=[f"faitheval:test:{i}" for i in range(10)],
            metrics={
                "unanswerable_context_accuracy_strict": 0.9,
                "unanswerable_context_accuracy_loose": 0.95,
            },
        )
        res = client.get("/api/v1/leaderboard?domain=contextual_faithfulness")
        assert res.status_code == 200
        items = [i for g in res.json()["groups"] for i in g["items"]]
        assert all(i["run_id"] != "fe-run-1" for i in items)

    def test_leaderboard_includes_faitheval_with_balanced_score(self, client: TestClient, db_session: Session):
        user = _user(db_session, "fe_user2")
        _run(
            db_session,
            "fe-run-2",
            user.id,
            "lumma-0.6b",
            dataset_id="faitheval",
            protocol_id="faitheval_unanswerable_v1",
            selected_ids=[f"faitheval:test:{i}" for i in range(10)],
            metrics={"balanced_score": 0.72},
        )
        res = client.get("/api/v1/leaderboard?domain=contextual_faithfulness")
        assert res.status_code == 200
        items = [i for g in res.json()["groups"] for i in g["items"]]
        match = [i for i in items if i["run_id"] == "fe-run-2"]
        assert len(match) == 1
        assert match[0]["primary_metric_name"] == "balanced_score"
        assert match[0]["primary_metric_value"] == 0.72

    def test_recommendation_excludes_faitheval_without_balanced_score(self, client: TestClient, db_session: Session):
        user = _user(db_session, "fe_user3")
        _run(
            db_session,
            "fe-run-3",
            user.id,
            "lumma-0.6b",
            dataset_id="faitheval",
            protocol_id="faitheval_unanswerable_v1",
            selected_ids=[f"faitheval:test:{i}" for i in range(10)],
            metrics={
                "unanswerable_context_accuracy_strict": 0.9,
                "latency_ms_mean": 30.0,
            },
        )
        res = _recommend(client, {"domain": "contextual_faithfulness"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "insufficient_sample"
        assert all(r["run_id"] != "fe-run-3" for r in data["recommendations"])


# ---------------------------------------------------------------------------
# FIX 2: common-cohort selection
# ---------------------------------------------------------------------------


class TestCommonCohort:
    def test_same_cohort_ranks_together(self, client: TestClient, db_session: Session):
        user = _user(db_session, "cohort_user")
        for i, model in enumerate(["lumma-0.6b", "apertus-0.5b", "lfm2.5-350m"]):
            _run(
                db_session,
                f"co-r{i}",
                user.id,
                model,
                metrics={"accuracy": 0.8 - i * 0.1, "latency_ms_mean": 50.0 + i},
            )
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "success"
        assert len(data["recommendations"]) == 3
        assert "shared evaluation cohort" in data["explanation"]

    def test_disjoint_sample_sets_not_ranked_together(self, client: TestClient, db_session: Session):
        """Case B: three models, 200 samples each, all DIFFERENT IDs."""
        user = _user(db_session, "cohort_user_b")
        for i, (model, ids) in enumerate(
            zip(
                ["lumma-0.6b", "apertus-0.5b", "lfm2.5-350m"],
                [SAMPLES_A, SAMPLES_B, [f"sciq:test:{i}" for i in range(400, 600)]],
                strict=True,
            )
        ):
            _run(
                db_session,
                f"co-b{i}",
                user.id,
                model,
                selected_ids=ids,
                metrics={"accuracy": 0.8 - i * 0.1, "latency_ms_mean": 50.0 + i},
            )
        res = _recommend(client)
        data = res.json()
        # No cohort has 2+ models: cannot produce a comparable ranking.
        assert data["status"] == "insufficient_sample"
        assert data["recommendations"] == []

    def test_partial_cohort_only_comparable_models_ranked(self, client: TestClient, db_session: Session):
        """Case C: two models share cohort, third uses another."""
        user = _user(db_session, "cohort_user_c")
        _run(db_session, "co-c0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "co-c1", user.id, "apertus-0.5b", metrics={"accuracy": 0.8, "latency_ms_mean": 50.0})
        _run(
            db_session,
            "co-c2",
            user.id,
            "lfm2.5-350m",
            selected_ids=SAMPLES_B,
            metrics={"accuracy": 0.95, "latency_ms_mean": 10.0},
        )
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "success"
        ranked_models = {r["model_id"] for r in data["recommendations"]}
        # The shared cohort (A) has 2 models; model on cohort B must not join.
        assert ranked_models == {"lumma-0.6b", "apertus-0.5b"}

    def test_no_cherry_picking_between_small_and_large_cohort(self, client: TestClient, db_session: Session):
        """Case D: model with 10-sample 100% run and 200-sample 80% run."""
        user = _user(db_session, "cohort_user_d")
        _run(
            db_session,
            "co-d-small",
            user.id,
            "lumma-0.6b",
            selected_ids=SAMPLES_A,
            metrics={"accuracy": 0.80, "latency_ms_mean": 60.0},
        )
        _run(
            db_session,
            "co-d-big",
            user.id,
            "apertus-0.5b",
            selected_ids=SAMPLES_A,
            metrics={"accuracy": 0.85, "latency_ms_mean": 55.0},
        )
        _run(
            db_session,
            "co-d-small2",
            user.id,
            "lfm2.5-350m",
            selected_ids=SAMPLES_SMALL,
            metrics={"accuracy": 1.0, "latency_ms_mean": 5.0},
        )
        res = _recommend(client)
        data = res.json()
        ranked = {r["model_id"]: r for r in data["recommendations"]}
        # The 10-sample perfect run must not enter the 200-sample cohort.
        assert "lfm2.5-350m" not in ranked
        assert ranked["lumma-0.6b"]["quality_score"] == 0.80

    def test_different_protocol_not_mixed(self, client: TestClient, db_session: Session):
        """Case E: same samples, different protocol."""
        user = _user(db_session, "cohort_user_e")
        _run(db_session, "co-e0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(
            db_session,
            "co-e1",
            user.id,
            "apertus-0.5b",
            protocol_id="sciq_closed_book",
            metrics={"accuracy": 0.7, "latency_ms_mean": 50.0},
        )
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "insufficient_sample"

    def test_missing_selection_not_assumed_comparable(self, client: TestClient, db_session: Session):
        """Case F: missing sample selection -> excluded."""
        user = _user(db_session, "cohort_user_f")
        run = _run(db_session, "co-f0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        run.sample_selection = None
        db_session.commit()
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "insufficient_sample"

    def test_same_samples_different_order_same_cohort(self, client: TestClient, db_session: Session):
        """Case G: order is not material; sorted IDs define the cohort."""
        user = _user(db_session, "cohort_user_g")
        _run(db_session, "co-g0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(
            db_session,
            "co-g1",
            user.id,
            "apertus-0.5b",
            selected_ids=list(reversed(SAMPLES_A)),
            metrics={"accuracy": 0.8, "latency_ms_mean": 50.0},
        )
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "success"
        assert len(data["recommendations"]) == 2

    def test_repeated_runs_per_model_deterministic(self, client: TestClient, db_session: Session):
        """Case H: multiple runs per model in one cohort — deterministic pick."""
        user = _user(db_session, "cohort_user_h")
        _run(db_session, "co-h0", user.id, "lumma-0.6b", metrics={"accuracy": 0.7, "latency_ms_mean": 60.0})
        _run(db_session, "co-h1", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 65.0})
        _run(db_session, "co-h2", user.id, "apertus-0.5b", metrics={"accuracy": 0.8, "latency_ms_mean": 50.0})
        res = _recommend(client)
        data = res.json()
        lumma = [r for r in data["recommendations"] if r["model_id"] == "lumma-0.6b"]
        assert len(lumma) == 1
        assert lumma[0]["run_id"] in ("co-h0", "co-h1")
        # Same request again: same deterministic choice.
        res2 = _recommend(client)
        lumma2 = [r for r in res2.json()["recommendations"] if r["model_id"] == "lumma-0.6b"]
        assert lumma2[0]["run_id"] == lumma[0]["run_id"]


# ---------------------------------------------------------------------------
# FIX 3: private-run visibility
# ---------------------------------------------------------------------------


class TestPrivateRunVisibility:
    def test_owner_private_runs_used_for_recommendation(self, client: TestClient, db_session: Session):
        user_b_id = _user(db_session, "priv_b").id
        client.cookies.clear()
        user_a_id = _register(client, "priv_a")
        # Two of user A's PRIVATE models + one of user B's PRIVATE model.
        _run(db_session, "pv-a0", user_a_id, "lumma-0.6b", is_private=True, metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "pv-a1", user_a_id, "apertus-0.5b", is_private=True, metrics={"accuracy": 0.8, "latency_ms_mean": 50.0})
        _run(db_session, "pv-a2", user_a_id, "lfm2.5-350m", is_private=True, metrics={"accuracy": 0.7, "latency_ms_mean": 40.0})
        _run(db_session, "pv-b0", user_b_id, "lumma-0.6b", is_private=True, selected_ids=SAMPLES_B, metrics={"accuracy": 0.95, "latency_ms_mean": 5.0})

        res = _recommend(client)
        data = res.json()
        assert data["status"] == "success"
        models = {r["model_id"] for r in data["recommendations"]}
        assert models == {"lumma-0.6b", "apertus-0.5b", "lfm2.5-350m"}
        # User A's lumma run is from cohort A, not user B's 0.95 cohort-B run.
        lumma = next(r for r in data["recommendations"] if r["model_id"] == "lumma-0.6b")
        assert lumma["run_id"] == "pv-a0"

    def test_other_users_private_runs_invisible(self, client: TestClient, db_session: Session):
        user_b = _user(db_session, "priv_b2")
        _run(db_session, "pv-b1", user_b.id, "lumma-0.6b", is_private=True, metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "pv-b2", user_b.id, "apertus-0.5b", is_private=True, metrics={"accuracy": 0.8, "latency_ms_mean": 50.0})

        # Anonymous: nothing visible.
        res = _recommend(client)
        assert res.json()["status"] == "insufficient_sample"

        # Registered unrelated user: still nothing.
        client.cookies.clear()
        _register(client, "priv_c")
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "insufficient_sample"
        # No private run IDs leaked.
        assert "pv-b1" not in res.text and "pv-b2" not in res.text

    def test_public_and_own_private_mixed(self, client: TestClient, db_session: Session):
        user_a = _user(db_session, "mix_a_owner")
        _run(db_session, "mix-pub", user_a.id, "lumma-0.6b", is_private=False, metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        # Another owner's private run in the SAME cohort would be a leak if used.
        other = _user(db_session, "mix_other")
        _run(db_session, "mix-priv-other", other.id, "apertus-0.5b", is_private=True, metrics={"accuracy": 0.99, "latency_ms_mean": 1.0})
        client.cookies.clear()
        _register(client, "mix_a")
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "insufficient_sample"  # only 1 visible model
        assert "mix-priv-other" not in res.text


# ---------------------------------------------------------------------------
# FIX 4: cross-hardware latency gating
# ---------------------------------------------------------------------------


class TestHardwareLatencyGating:
    def test_mixed_hardware_latency_compared_within_one_group_only(self, client: TestClient, db_session: Session):
        user = _user(db_session, "hw_user")
        hw_gpu1 = {"gpu_available": True, "gpu_name": "RTX 4090", "cuda_version": "12.1", "torch_version": "2.3"}
        hw_gpu2 = {"gpu_available": True, "gpu_name": "RTX 3060", "cuda_version": "12.1", "torch_version": "2.3"}
        # Cohort with 2 models on GPU1, 1 model on GPU2.
        _run(db_session, "hw-0", user.id, "lumma-0.6b", hardware=hw_gpu1, metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "hw-1", user.id, "apertus-0.5b", hardware=hw_gpu1, metrics={"accuracy": 0.85, "latency_ms_mean": 50.0})
        _run(db_session, "hw-2", user.id, "lfm2.5-350m", hardware=hw_gpu2, metrics={"accuracy": 0.95, "latency_ms_mean": 5.0})
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "success"
        models = {r["model_id"] for r in data["recommendations"]}
        # GPU2 model excluded from latency comparison cohort.
        assert models == {"lumma-0.6b", "apertus-0.5b"}
        assert any("same recorded hardware" in lim for lim in data["limitations"])

    def test_missing_hardware_metadata_not_assumed_equivalent(self, client: TestClient, db_session: Session):
        user = _user(db_session, "hw_user2")
        hw_gpu = {"gpu_available": True, "gpu_name": "RTX 4090", "cuda_version": "12.1", "torch_version": "2.3"}
        _run(db_session, "hw-3", user.id, "lumma-0.6b", hardware=hw_gpu, metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "hw-4", user.id, "apertus-0.5b", hardware=None, metrics={"accuracy": 0.85, "latency_ms_mean": 50.0})
        res = _recommend(client)
        data = res.json()
        # 'unknown' hardware is its own group: no 3-model comparable latency set.
        assert data["status"] in ("insufficient_sample", "success")
        if data["status"] == "success":
            # Whichever group won, latency was not compared across unknown/known.
            assert any(
                ("hardware" in lim) or ("Latency weight could not be applied" in lim)
                for lim in data["limitations"]
            )

    def test_quality_only_ignores_hardware(self, client: TestClient, db_session: Session):
        """Latency weight = 0: mixed hardware is acceptable."""
        user = _user(db_session, "hw_user3")
        hw_gpu1 = {"gpu_available": True, "gpu_name": "RTX 4090", "cuda_version": "12.1", "torch_version": "2.3"}
        hw_cpu = {"gpu_available": False, "gpu_name": None}
        _run(db_session, "hq-0", user.id, "lumma-0.6b", hardware=hw_gpu1, metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "hq-1", user.id, "apertus-0.5b", hardware=hw_cpu, metrics={"accuracy": 0.85, "latency_ms_mean": 500.0})
        _run(db_session, "hq-2", user.id, "lfm2.5-350m", hardware=hw_cpu, metrics={"accuracy": 0.7, "latency_ms_mean": 300.0})
        res = _recommend(
            client,
            {"domain": "education", "weights": {"quality": 1.0, "latency": 0.0, "vram": 0.0}},
        )
        data = res.json()
        assert data["status"] == "success"
        assert len(data["recommendations"]) == 3

    def test_missing_latency_disclosed_not_fabricated(self, client: TestClient, db_session: Session):
        user = _user(db_session, "hw_user4")
        _run(db_session, "hl-0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "hl-1", user.id, "apertus-0.5b", metrics={"accuracy": 0.85})  # no latency
        _run(db_session, "hl-2", user.id, "lfm2.5-350m", metrics={"accuracy": 0.7, "latency_ms_mean": 40.0})
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "success"
        no_lat = [r for r in data["recommendations"] if r["latency_ms"] is None]
        assert len(no_lat) == 1
        assert any("could not be applied" in lim for lim in data["limitations"])


# ---------------------------------------------------------------------------
# FIX 8: numeric robustness
# ---------------------------------------------------------------------------


class TestNumericRobustness:
    def test_nan_weight_rejected(self, client: TestClient, db_session: Session):
        _user(db_session, "num_user")
        # NaN is not valid JSON; the equivalent hostile input is a huge value
        # that normalizes to non-finite, or literal nan accepted by some
        # parsers. Send raw body to exercise engine-side validation directly.
        from app.schemas.recommendation import RecommendationWeights
        from app.services.recommendation_engine import (
            validate_and_normalize_weights,
        )

        with pytest.raises(ValueError, match="finite"):
            validate_and_normalize_weights(
                RecommendationWeights(quality=float("nan"), latency=0.3, vram=0.2)
            )

    def test_infinity_weight_rejected(self, client: TestClient, db_session: Session):
        _user(db_session, "num_user2")
        from app.schemas.recommendation import RecommendationWeights
        from app.services.recommendation_engine import validate_and_normalize_weights

        with pytest.raises(ValueError, match="finite"):
            validate_and_normalize_weights(
                RecommendationWeights(quality=float("inf"), latency=0.3, vram=0.2)
            )

    def test_negative_latency_run_excluded(self, client: TestClient, db_session: Session):
        user = _user(db_session, "num_user3")
        _run(db_session, "nl-0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "nl-1", user.id, "apertus-0.5b", metrics={"accuracy": 0.85, "latency_ms_mean": -5.0})
        _run(db_session, "nl-2", user.id, "lfm2.5-350m", metrics={"accuracy": 0.7, "latency_ms_mean": 40.0})
        res = _recommend(client)
        data = res.json()
        models = {r["model_id"] for r in data["recommendations"]}
        assert "apertus-0.5b" not in models

    def test_zero_latency_accepted(self, client: TestClient, db_session: Session):
        user = _user(db_session, "num_user4")
        _run(db_session, "zl-0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 0.0})
        _run(db_session, "zl-1", user.id, "apertus-0.5b", metrics={"accuracy": 0.85, "latency_ms_mean": 0.0})
        _run(db_session, "zl-2", user.id, "lfm2.5-350m", metrics={"accuracy": 0.7, "latency_ms_mean": 0.0})
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "success"
        assert all(r["latency_ms"] == 0.0 for r in data["recommendations"])


# ---------------------------------------------------------------------------
# FIX 7: leaderboard cohort grouping
# ---------------------------------------------------------------------------


class TestLeaderboardCohortGroups:
    def test_groups_by_cohort_and_ranks_reset(self, client: TestClient, db_session: Session):
        user = _user(db_session, "lb_user")
        # Cohort A: 2 models.
        _run(db_session, "lb-a0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9})
        _run(db_session, "lb-a1", user.id, "apertus-0.5b", metrics={"accuracy": 0.8})
        # Cohort B (different samples): 1 model.
        _run(db_session, "lb-b0", user.id, "lfm2.5-350m", selected_ids=SAMPLES_SMALL, metrics={"accuracy": 0.99})
        # Different dataset: separate group.
        _run(
            db_session,
            "lb-c0",
            user.id,
            "lumma-0.6b",
            dataset_id="wdc_pave",
            protocol_id="wdc_pave_extraction",
            selected_ids=[f"wdc_pave:test:{i}" for i in range(20)],
            metrics={"micro_f1": 0.5},
        )

        res = client.get("/api/v1/leaderboard")
        assert res.status_code == 200
        data = res.json()
        groups = data["groups"]
        assert len(groups) == 3

        a = next(g for g in groups if g["protocol_id"] == "sciq_evidence_grounded" and (g["sample_count"] or 0) == 200)
        assert len(a["items"]) == 2
        # Rank positions are group-local list indices (client renders #idx+1);
        # values sorted descending within group.
        assert [i["primary_metric_value"] for i in a["items"]] == [0.9, 0.8]

        b = next(g for g in groups if (g["sample_count"] or 0) == 10)
        assert len(b["items"]) == 1
        assert b["items"][0]["primary_metric_value"] == 0.99

        c = next(g for g in groups if g["dataset_id"] == "wdc_pave")
        assert c["primary_metric_name"] == "micro_f1"

    def test_different_protocol_same_samples_separate_groups(self, client: TestClient, db_session: Session):
        user = _user(db_session, "lb_user2")
        _run(db_session, "lb-p0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9})
        _run(db_session, "lb-p1", user.id, "apertus-0.5b", protocol_id="sciq_closed_book", metrics={"accuracy": 0.8})
        res = client.get("/api/v1/leaderboard?domain=education")
        groups = res.json()["groups"]
        assert len(groups) == 2
        assert {g["protocol_id"] for g in groups} == {"sciq_evidence_grounded", "sciq_closed_book"}

    def test_missing_selection_excluded_from_leaderboard(self, client: TestClient, db_session: Session):
        user = _user(db_session, "lb_user3")
        run = _run(db_session, "lb-m0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9})
        run.sample_selection = None
        db_session.commit()
        res = client.get("/api/v1/leaderboard?domain=education")
        items = [i for g in res.json()["groups"] for i in g["items"]]
        assert all(i["run_id"] != "lb-m0" for i in items)

    def test_private_runs_never_on_leaderboard(self, client: TestClient, db_session: Session):
        user = _user(db_session, "lb_user4")
        _run(db_session, "lb-priv", user.id, "lumma-0.6b", is_private=True, metrics={"accuracy": 0.99})
        res = client.get("/api/v1/leaderboard")
        items = [i for g in res.json()["groups"] for i in g["items"]]
        assert all(i["run_id"] != "lb-priv" for i in items)


class TestSingleModelAfterConstraints:
    def test_one_model_result_disclosed_not_recommended(self, client: TestClient, db_session: Session):
        """Constraints leaving a single model: still returned (completeness)
        but explicitly labeled as not-a-recommendation."""
        user = _user(db_session, "single_user")
        _run(db_session, "sg-0", user.id, "lfm2.5-350m", is_private=False, metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "sg-1", user.id, "apertus-0.5b", is_private=False, metrics={"accuracy": 0.8, "latency_ms_mean": 50.0})
        # Filter out apertus (1.15 GB) via VRAM cap, keeping lfm (0.71 GB).
        res = _recommend(client, {"domain": "education", "constraints": {"max_vram_gb": 1.0}})
        data = res.json()
        assert data["status"] == "success"
        assert len(data["recommendations"]) == 1
        assert any("at least 2 comparable models" in lim for lim in data["limitations"])


class TestEffectiveWeightExplanation:
    def test_missing_latency_explanation_mentions_omission(self, client: TestClient, db_session: Session):
        user = _user(db_session, "exp_user")
        _run(db_session, "ex-0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "ex-1", user.id, "apertus-0.5b", metrics={"accuracy": 0.85, "latency_ms_mean": 50.0})
        _run(db_session, "ex-2", user.id, "lfm2.5-350m", metrics={"accuracy": 0.7})  # no latency
        res = _recommend(client)
        data = res.json()
        assert "Latency weight was omitted" in data["explanation"]
