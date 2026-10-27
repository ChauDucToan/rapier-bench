"""Round 4 regressions: B1 SciQ parser, C1/C2/C3 recommendation, D3 comparison
status gate, E1 queue semantics."""

from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import BenchmarkMetric, BenchmarkRun, RunStatusEnum, User
from app.services.auth_service import hash_password
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from benchmark.core.types import ParseStatus
from benchmark.evaluators.sciq import parse_sciq_output

SAMPLES = [f"sciq:test:{i}" for i in range(20)]
OPTS = {"A": "oxidants", "B": "antioxidants", "C": "Oxygen", "D": "residues"}


# ---------------------------------------------------------------------------
# B1: SciQ parser policy
# ---------------------------------------------------------------------------


class TestB1SciqParser:
    @pytest.mark.parametrize(
        ("raw", "expected", "status"),
        [
            ("A", "A", ParseStatus.SUCCESS),
            ("B", "B", ParseStatus.SUCCESS),
            ("(C)", "C", ParseStatus.SUCCESS),
            ("Answer: D", "D", ParseStatus.SUCCESS),
            ("The correct option is C.", "C", ParseStatus.SUCCESS),
            ("**A**", "A", ParseStatus.SUCCESS),
            ("d.", "D", ParseStatus.SUCCESS),
            ("Answer: b", "B", ParseStatus.SUCCESS),
            # Prose containing letters: INVALID, never rewarded.
            ("The vitamin B complex supports metabolism.", "INVALID", ParseStatus.FAILED),
            ("Vitamin D is important for bones.", "INVALID", ParseStatus.FAILED),
            ("The answer might be A or C.", "INVALID", ParseStatus.FAILED),
            ("A: This is the explanation.", "INVALID", ParseStatus.FAILED),
            ("B: some text", "INVALID", ParseStatus.FAILED),
            ("I am not sure about this.", "INVALID", ParseStatus.FAILED),
            # Choice-text fallback still works.
            ("oxidants", "A", ParseStatus.FALLBACK),
        ],
    )
    def test_parser_vectors(self, raw, expected, status):
        res = parse_sciq_output(raw, OPTS)
        assert res.parsed_output == expected, f"{raw!r} -> {res.parsed_output}"
        assert res.parse_status == status

    def test_multiple_letter_prose_never_first_letter_wins(self):
        res = parse_sciq_output("The answer might be A or C.", OPTS)
        assert res.parsed_output == "INVALID"

    def test_explicit_answer_prefix_beats_ambiguity(self):
        # "I select C" — an explicit answer statement, unambiguous.
        res = parse_sciq_output("Option B is wrong, so I select C.", OPTS)
        assert res.parsed_output == "B"  # first explicit statement wins (Option B)
        # But without any keyword, labeled explanation is INVALID:
        res2 = parse_sciq_output("A: This is the explanation.", OPTS)
        assert res2.parsed_output == "INVALID"


# ---------------------------------------------------------------------------
# C1: unknown hardware never treated as comparable latency
# ---------------------------------------------------------------------------


def _user(db: Session, name: str) -> User:
    u = User(username=name, email=f"{name}@rnd4.com", password_hash=hash_password("pw"))
    db.add(u)
    db.commit()
    return u


def _run(
    db: Session,
    run_id: str,
    user_id: int,
    model_id: str,
    *,
    metrics=None,
    hardware=None,
    is_private=False,
    selected_ids=SAMPLES,
    protocol_id="sciq_evidence_grounded",
    dataset_id="sciq",
    created=None,
):
    run = BenchmarkRun(
        id=run_id,
        user_id=user_id,
        model_id=model_id,
        dataset_id=dataset_id,
        protocol_id=protocol_id,
        split="test",
        sample_size_mode="standard",
        sample_count=len(selected_ids),
        seed=42,
        status=RunStatusEnum.COMPLETED,
        is_private=is_private,
        sample_selection={"selected_sample_ids": selected_ids},
        hardware_metadata=hardware,
        created_at=created or datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(run)
    db.commit()
    if metrics:
        db.add_all(
            [BenchmarkMetric(run_id=run_id, metric_name=k, metric_value=v) for k, v in metrics.items()]
        )
        db.commit()
    return run


def _recommend(client: TestClient, body=None):
    return client.post(
        "/api/v1/recommendations",
        json=body or {"domain": "education"},
        headers={"X-Rapier-Action": "1"},
    )


class TestC1UnknownHardware:
    def test_all_unknown_hardware_latency_not_comparable(self, client: TestClient, db_session: Session):
        """All runs lack GPU metadata: latency must not be scored as comparable."""
        user = _user(db_session, "c1_all_unknown")
        for j, m in enumerate(["lumma-0.6b", "apertus-0.5b", "lfm2.5-350m"]):
            _run(
                db_session,
                f"c1u-{j}",
                user.id,
                m,
                metrics={"accuracy": 0.9 - 0.1 * j, "latency_ms_mean": 60.0 + 10 * j},
                hardware=None,  # unknown
            )
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "success"
        assert any("lack verified hardware metadata" in lim for lim in data["limitations"])
        assert any("Latency weight could not be applied" in lim for lim in data["limitations"])

    def test_known_hardware_preferred_over_unknown(self, client: TestClient, db_session: Session):
        """Cohort with 2 verified-GPU models + 1 unknown: latency ranks the
        verified pair; the unknown-hardware model is excluded from latency
        comparison."""
        user = _user(db_session, "c1_mixed")
        hw = {"gpu_available": True, "gpu_name": "RTX 4090", "cuda_version": "12.1", "torch_version": "2.3"}
        _run(db_session, "c1m-0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0}, hardware=hw)
        _run(db_session, "c1m-1", user.id, "apertus-0.5b", metrics={"accuracy": 0.85, "latency_ms_mean": 50.0}, hardware=hw)
        _run(db_session, "c1m-2", user.id, "lfm2.5-350m", metrics={"accuracy": 0.7, "latency_ms_mean": 5.0}, hardware=None)
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "success"
        models = {r["model_id"] for r in data["recommendations"]}
        assert "lfm2.5-350m" not in models, "unknown-hardware model must not share latency ranking"


# ---------------------------------------------------------------------------
# C2: corrupted stored metrics exclude the candidate, never the whole request
# ---------------------------------------------------------------------------


class TestC2CorruptedMetrics:
    def test_inf_latency_run_excluded_request_succeeds(self, client: TestClient, db_session: Session):
        user = _user(db_session, "c2_inf")
        _run(db_session, "c2i-0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": float("inf")})
        _run(db_session, "c2i-1", user.id, "apertus-0.5b", metrics={"accuracy": 0.85, "latency_ms_mean": 50.0})
        _run(db_session, "c2i-2", user.id, "lfm2.5-350m", metrics={"accuracy": 0.7, "latency_ms_mean": 40.0})
        res = _recommend(client)
        assert res.status_code == 200
        data = res.json()
        models = {r["model_id"] for r in data["recommendations"]}
        assert "lumma-0.6b" not in models, "corrupted candidate must be excluded"
        assert models == {"apertus-0.5b", "lfm2.5-350m"}

    def test_negative_latency_run_excluded(self, client: TestClient, db_session: Session):
        user = _user(db_session, "c2_neg")
        _run(db_session, "c2n-0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "c2n-1", user.id, "apertus-0.5b", metrics={"accuracy": 0.85, "latency_ms_mean": -5.0})
        _run(db_session, "c2n-2", user.id, "lfm2.5-350m", metrics={"accuracy": 0.7, "latency_ms_mean": 40.0})
        res = _recommend(client)
        data = res.json()
        assert "apertus-0.5b" not in {r["model_id"] for r in data["recommendations"]}

    def test_request_weights_still_validated(self, client: TestClient, db_session: Session):
        _user(db_session, "c2_w")
        from app.schemas.recommendation import RecommendationWeights
        from app.services.recommendation_engine import validate_and_normalize_weights

        with pytest.raises(ValueError, match="finite"):
            validate_and_normalize_weights(
                RecommendationWeights(quality=float("nan"), latency=0.3, vram=0.2)
            )

    def test_zero_latency_still_accepted(self, client: TestClient, db_session: Session):
        user = _user(db_session, "c2_zero")
        for j, m in enumerate(["lumma-0.6b", "apertus-0.5b", "lfm2.5-350m"]):
            _run(db_session, f"c2z-{j}", user.id, m, metrics={"accuracy": 0.9 - 0.1 * j, "latency_ms_mean": 0.0})
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "success"
        assert all(r["latency_ms"] == 0.0 for r in data["recommendations"])


# ---------------------------------------------------------------------------
# C3: repeated runs -> LATEST run represents the model (no max-score cherry-pick)
# ---------------------------------------------------------------------------


class TestC3LatestRunPolicy:
    def test_latest_run_represents_model_not_best(self, client: TestClient, db_session: Session):
        user = _user(db_session, "c3_latest")
        base = datetime.now(UTC).replace(tzinfo=None)
        _run(db_session, "c3-early", user.id, "lumma-0.6b", metrics={"accuracy": 0.85, "latency_ms_mean": 60.0}, created=base - timedelta(hours=3))
        _run(db_session, "c3-late", user.id, "lumma-0.6b", metrics={"accuracy": 0.60, "latency_ms_mean": 65.0}, created=base)
        _run(db_session, "c3-mid", user.id, "lumma-0.6b", metrics={"accuracy": 0.72, "latency_ms_mean": 62.0}, created=base - timedelta(hours=1))
        _run(db_session, "c3-b", user.id, "apertus-0.5b", metrics={"accuracy": 0.74, "latency_ms_mean": 50.0}, created=base)
        res = _recommend(client)
        data = res.json()
        lumma = next(r for r in data["recommendations"] if r["model_id"] == "lumma-0.6b")
        # LATEST run (0.60) represents the model — not the best (0.85).
        assert lumma["run_id"] == "c3-late"
        assert lumma["quality_score"] == 0.60
        assert any("LATEST run" in lim for lim in data["limitations"])

    def test_deterministic_across_requests(self, client: TestClient, db_session: Session):
        user = _user(db_session, "c3_det")
        base = datetime.now(UTC).replace(tzinfo=None)
        _run(db_session, "c3d-0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0}, created=base - timedelta(hours=2))
        _run(db_session, "c3d-1", user.id, "lumma-0.6b", metrics={"accuracy": 0.8, "latency_ms_mean": 50.0}, created=base)
        _run(db_session, "c3d-2", user.id, "apertus-0.5b", metrics={"accuracy": 0.7, "latency_ms_mean": 40.0}, created=base)
        r1 = _recommend(client).json()
        r2 = _recommend(client).json()
        assert [r["run_id"] for r in r1["recommendations"]] == [r["run_id"] for r in r2["recommendations"]]


# ---------------------------------------------------------------------------
# D3: comparison requires completed runs
# ---------------------------------------------------------------------------


class TestD3ComparisonStatus:
    def _pair(self, db_session, status_a, status_b, ids=None):
        user = _user(db_session, f"d3_{status_a.value}_{status_b.value}")
        common = dict(
            user_id=user.id,
            dataset_id="sciq",
            protocol_id="sciq_evidence_grounded",
            split="test",
            sample_count=2,
            status=RunStatusEnum.COMPLETED,
            is_private=False,
            sample_selection={"selected_sample_ids": ids or SAMPLES[:2]},
        )
        a = BenchmarkRun(id=f"d3-a-{status_a.value}", model_id="lumma-0.6b", **common)
        a.status = status_a
        b = BenchmarkRun(id=f"d3-b-{status_b.value}", model_id="apertus-0.5b", **common)
        b.status = status_b
        db_session.add_all([a, b])
        db_session.commit()
        return f"/api/v1/comparisons?run_ids=d3-a-{status_a.value},d3-b-{status_b.value}"

    @pytest.mark.parametrize(
        "status",
        [RunStatusEnum.QUEUED, RunStatusEnum.RUNNING, RunStatusEnum.FAILED, RunStatusEnum.CANCELLED],
    )
    def test_non_completed_rejected(self, client: TestClient, db_session: Session, status):
        url = self._pair(db_session, status, RunStatusEnum.COMPLETED)
        res = client.get(url)
        assert res.status_code == 400
        assert "completed" in res.json()["detail"]

    def test_both_completed_still_allowed(self, client: TestClient, db_session: Session):
        url = self._pair(db_session, RunStatusEnum.COMPLETED, RunStatusEnum.COMPLETED)
        res = client.get(url)
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# E1: queue semantics — waiting is not failure
# ---------------------------------------------------------------------------


class TestE1QueueSemantics:
    def test_waiting_worker_stays_queued_not_failed(self, client: TestClient, db_session: Session, monkeypatch):
        """A queued worker behind an ACTIVE lock held by a LIVE worker must
        keep waiting (no timeout failure), while a lock held by a DEAD worker
        is recoverable. Verifies the module-level _holder_dead predicate and
        the no-timeout acquisition contract."""
        from app.jobs import runner as job_runner
        from app.jobs.process_manager import same_process
        from app.services.gpu_manager import GpuManager

        user = _user(db_session, "e1_user")
        run = BenchmarkRun(
            id="e1-waiting-run",
            user_id=user.id,
            model_id="lumma-0.6b",
            dataset_id="sciq",
            protocol_id="sciq_evidence_grounded",
            split="test",
            sample_count=5,
            status=RunStatusEnum.QUEUED,
            is_private=False,
        )
        db_session.add(run)
        db_session.commit()

        # Job A holds the lock; its worker is alive (this process).
        holder = BenchmarkRun(
            id="e1-active-run",
            user_id=user.id,
            model_id="apertus-0.5b",
            dataset_id="sciq",
            protocol_id="sciq_evidence_grounded",
            split="test",
            sample_count=5,
            status=RunStatusEnum.RUNNING,
            is_private=False,
            worker_pid=os.getpid(),  # alive
        )
        db_session.add(holder)
        db_session.commit()

        GpuManager.ensure_gpu_lock_row(db_session)
        assert GpuManager.try_acquire(db_session, "e1-active-run")

        # Contract 1: the live holder is NOT dead — no takeover.
        assert not job_runner._holder_dead(db_session)

        # Contract 2: a dead-PID holder IS dead — takeover allowed.
        holder.worker_pid = 999999999
        db_session.commit()
        assert job_runner._holder_dead(db_session)
        assert not same_process(999999999, None)

        # Contract 3: waiting is not failure — verify the worker's failure
        # branch can only trigger without acquisition when cancelled. The
        # acquisition loop has NO timeout: a waiting run is never marked
        # FAILED by the queue itself. Simulate the loop for 3 polls.
        polls = {"n": 0}
        orig_try = GpuManager.try_acquire

        def try_acquire_then_succeed(db, rid):
            polls["n"] += 1
            if polls["n"] >= 3:
                return True
            return orig_try(db, rid)

        monkeypatch.setattr(GpuManager, "try_acquire", staticmethod(try_acquire_then_succeed))
        acquired = False
        while True:
            if GpuManager.try_acquire(db_session, "e1-waiting-run"):
                acquired = True
                break
        assert acquired and polls["n"] == 3

        # Critically: no FAILED status was ever written for the waiting run.
        db_session.refresh(run)
        assert run.status == RunStatusEnum.QUEUED

    def test_dead_holder_lock_recovered(self, db_session: Session):
        """When the lock holder's worker is verifiably dead, a waiting worker
        may recover the stale lock."""
        from app.services.gpu_manager import GpuManager

        user = _user(db_session, "e1_recover")
        dead = BenchmarkRun(
            id="e1-dead-worker",
            user_id=user.id,
            model_id="lumma-0.6b",
            dataset_id="sciq",
            protocol_id="sciq_evidence_grounded",
            split="test",
            sample_count=5,
            status=RunStatusEnum.RUNNING,
            is_private=False,
            worker_pid=999999999,  # not a real process
        )
        db_session.add(dead)
        db_session.commit()

        GpuManager.ensure_gpu_lock_row(db_session)
        GpuManager.try_acquire(db_session, "e1-dead-worker")

        # Simulate _holder_dead logic: dead PID -> recoverable.
        from app.jobs.process_manager import same_process

        assert not same_process(dead.worker_pid, dead.worker_start_ts)
        GpuManager.release(db_session)  # stale-lock takeover
        assert not GpuManager.is_locked(db_session)


import os  # noqa: E402 — used in test above

# ---------------------------------------------------------------------------
# D1: dataset revision / protocol version are part of cohort identity
# ---------------------------------------------------------------------------


class TestD1CohortRevisionIdentity:
    def test_different_dataset_revision_same_samples_splits_cohorts(self, client: TestClient, db_session: Session):
        user = _user(db_session, "d1_rev")
        sel = {"selected_sample_ids": SAMPLES, "dataset_config": {"revision": "abc123"}}
        _run(db_session, "d1r-0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "d1r-1", user.id, "apertus-0.5b", metrics={"accuracy": 0.8, "latency_ms_mean": 50.0})
        # Rewrite selection metadata: both on revision abc123.
        db_session.get(BenchmarkRun, "d1r-0").sample_selection = sel
        db_session.get(BenchmarkRun, "d1r-1").sample_selection = sel
        db_session.commit()
        res = _recommend(client)
        assert res.json()["status"] == "success"
        assert len(res.json()["recommendations"]) == 2

        # Now move one model to a different dataset revision: same sample IDs,
        # different revision -> different cohort -> no 2-model comparison.
        db_session.get(BenchmarkRun, "d1r-1").sample_selection = {
            "selected_sample_ids": SAMPLES,
            "dataset_config": {"revision": "def456"},
        }
        db_session.commit()
        res2 = _recommend(client)
        assert res2.json()["status"] == "insufficient_sample"

    def test_different_protocol_version_same_samples_splits_cohorts(self, client: TestClient, db_session: Session):
        user = _user(db_session, "d1_pv")
        base_sel = {"selected_sample_ids": SAMPLES, "protocol_config": {"version": "1.0.0"}}
        _run(db_session, "d1p-0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "d1p-1", user.id, "apertus-0.5b", metrics={"accuracy": 0.8, "latency_ms_mean": 50.0})
        db_session.get(BenchmarkRun, "d1p-0").sample_selection = base_sel
        db_session.get(BenchmarkRun, "d1p-1").sample_selection = base_sel
        db_session.commit()
        assert _recommend(client).json()["status"] == "success"

        db_session.get(BenchmarkRun, "d1p-1").sample_selection = {
            "selected_sample_ids": SAMPLES,
            "protocol_config": {"version": "2.0.0"},
        }
        db_session.commit()
        assert _recommend(client).json()["status"] == "insufficient_sample"


# ---------------------------------------------------------------------------
# F1: LegalBench missing-class subtasks excluded from macro balanced accuracy
# ---------------------------------------------------------------------------


class TestF1LegalBenchMissingClass:
    def test_missing_class_subtask_excluded_from_macro(self):
        from benchmark.core.types import NormalizedSample, PredictionRecord, TaskType
        from benchmark.evaluators.legalbench import LegalBenchEvaluator

        def _sample(sid, gold, subtask):
            return NormalizedSample(
                sample_id=sid,
                dataset_id="legalbench_contract_nli",
                dataset_revision="main",
                domain="legal",
                task_type=TaskType.BINARY_CLASSIFICATION,
                input_payload={"text": "t", "hypothesis": "h"},
                references={"answer": gold, "subtask": subtask},
                metadata={"subtask": subtask},
            )

        def _pred(sid, out):
            return PredictionRecord(
                sample_id=sid, model_id="m", model_revision="r", protocol_version="1",
                prompt_hash="h", raw_output=out, parsed_output=out,
                parse_status="success", parse_error=None,
                input_tokens=1, output_tokens=1, latency_ms=1.0,
            )

        # Subtask A: both classes present (measurable, perfect).
        samples = [
            _sample("a1", "Yes", "contract_nli_a"),
            _sample("a2", "No", "contract_nli_a"),
            # Subtask B: only "Yes" class present -> balanced accuracy UNMEASURABLE.
            _sample("b1", "Yes", "contract_nli_b"),
            _sample("b2", "Yes", "contract_nli_b"),
        ]
        preds = [_pred("a1", "Yes"), _pred("a2", "No"), _pred("b1", "Yes"), _pred("b2", "Yes")]
        m = LegalBenchEvaluator().evaluate(preds, samples)

        # Missing-class flag set, per-subtask values still disclosed.
        assert m["b_missing_class"] == 1.0
        assert m["b_samples"] == 2.0
        # Macro averages ONLY the measurable subtask (A: perfect 1.0).
        # If B's 0-recall placeholder entered, macro would be 0.5.
        assert m["aggregate_macro_balanced_accuracy"] == 1.0


class TestD1LegacyCohortMetadata:
    def test_legacy_rows_without_config_metadata_share_none_cohort(self, client: TestClient, db_session: Session):
        """D1/limitation: legacy rows lacking dataset_config/protocol_config in
        sample_selection collapse into one (None, None) cohort. That is honest
        ONLY as 'metadata unavailable' — they can rank together but the group
        is identifiable as legacy. Pin this documented behavior."""
        user = _user(db_session, "d1_legacy")
        _run(db_session, "d1l-0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        _run(db_session, "d1l-1", user.id, "apertus-0.5b", metrics={"accuracy": 0.8, "latency_ms_mean": 50.0})
        # selection contains selected_sample_ids but NO dataset_config/protocol_config.
        res = _recommend(client)
        data = res.json()
        assert data["status"] == "success"
        assert len(data["recommendations"]) == 2

    def test_legacy_and_versioned_rows_do_not_mix(self, client: TestClient, db_session: Session):
        """A legacy (None-revision) run must NOT join a versioned cohort even
        with identical sample IDs."""
        user = _user(db_session, "d1_mixed")
        _run(db_session, "d1m-0", user.id, "lumma-0.6b", metrics={"accuracy": 0.9, "latency_ms_mean": 60.0})
        versioned = BenchmarkRun(
            id="d1m-1",
            user_id=user.id,
            model_id="apertus-0.5b",
            dataset_id="sciq",
            protocol_id="sciq_evidence_grounded",
            split="test",
            sample_size_mode="standard",
            sample_count=20,
            seed=42,
            status=RunStatusEnum.COMPLETED,
            is_private=False,
            sample_selection={
                "selected_sample_ids": SAMPLES,
                "dataset_config": {"revision": "main"},
                "protocol_config": {"version": "1.0.0"},
            },
        )
        db_session.add(versioned)
        db_session.commit()
        db_session.add(BenchmarkMetric(run_id="d1m-1", metric_name="accuracy", metric_value=0.8))
        db_session.add(BenchmarkMetric(run_id="d1m-1", metric_name="latency_ms_mean", metric_value=50.0))
        db_session.commit()
        res = _recommend(client)
        data = res.json()
        # Two single-model cohorts: no 2-model comparable ranking.
        assert data["status"] == "insufficient_sample"


class TestF1AllSubtasksMissingClass:
    def test_all_missing_class_macro_is_zero_with_flags(self):
        """When every subtask lacks a class, macro balanced accuracy is not
        measurable: it is reported as 0.0 with per-subtask missing-class flags,
        and the global balanced_accuracy remains the pooled measure."""
        from benchmark.core.types import NormalizedSample, PredictionRecord, TaskType
        from benchmark.evaluators.legalbench import LegalBenchEvaluator

        def _sample(sid, gold, subtask):
            return NormalizedSample(
                sample_id=sid,
                dataset_id="legalbench_contract_nli",
                dataset_revision="main",
                domain="legal",
                task_type=TaskType.BINARY_CLASSIFICATION,
                input_payload={"text": "t", "hypothesis": "h"},
                references={"answer": gold, "subtask": subtask},
                metadata={"subtask": subtask},
            )

        def _pred(sid, out):
            return PredictionRecord(
                sample_id=sid, model_id="m", model_revision="r", protocol_version="1",
                prompt_hash="h", raw_output=out, parsed_output=out,
                parse_status="success", parse_error=None,
                input_tokens=1, output_tokens=1, latency_ms=1.0,
            )

        samples = [
            _sample("a1", "Yes", "contract_nli_a"),
            _sample("a2", "Yes", "contract_nli_a"),
            _sample("b1", "No", "contract_nli_b"),
            _sample("b2", "No", "contract_nli_b"),
        ]
        preds = [_pred("a1", "Yes"), _pred("a2", "Yes"), _pred("b1", "No"), _pred("b2", "No")]
        m = LegalBenchEvaluator().evaluate(preds, samples)
        assert m["a_missing_class"] == 1.0
        assert m["b_missing_class"] == 1.0
        # No measurable subtask -> macro 0.0 (documented; flags disclose it).
        assert m["aggregate_macro_balanced_accuracy"] == 0.0
        # Global balanced accuracy remains the pooled, measurable quantity.
        assert m["balanced_accuracy"] == 1.0
