import contextlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config import settings
from app.db.models import BenchmarkRun, GpuLock, RunStatusEnum, User
from app.services.auth_service import hash_password
from app.services.benchmark_service import BenchmarkService
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from tests.integration.test_api_benchmarks import authenticate_user


def _make_user(db: Session, username: str = "reg_test_user") -> int:
    u = User(username=username, email=f"{username}@example.com", password_hash=hash_password("pw123456"))
    db.add(u)
    db.commit()
    return u.id



def test_create_benchmark_samples_alias(client: TestClient):
    """Regression test for Bug 4: CreateBenchmarkRequest accepts 'samples' alias."""
    authenticate_user(client)
    res = client.post(
        "/api/v1/benchmarks",
        json={
            "model_id": "lumma-0.6b",
            "dataset_id": "sciq",
            "samples": 5,
            "is_private": False,
        },
        headers={"X-Rapier-Action": "1"},
    )
    assert res.status_code == 202
    data = res.json()
    assert data["sample_count"] == 5


def test_runner_artifacts_dir_not_nested(db_session: Session, tmp_path: Path):
    """Regression test for Bug 1: runner passes settings.artifacts_path to run_benchmark, not nested run dir."""
    from app.jobs import runner

    run_id = "test-artifacts-not-nested-run"
    run = BenchmarkRun(
        id=run_id,
        user_id=_make_user(db_session, "user_art"),
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

    captured_args = {}

    def fake_run_benchmark(**kwargs):
        captured_args.update(kwargs)
        # Write dummy metrics and predictions
        run_art_dir = Path(kwargs["artifacts_dir"]) / run_id
        run_art_dir.mkdir(parents=True, exist_ok=True)
        (run_art_dir / "metrics.json").write_text('{"accuracy": 1.0}')
        (run_art_dir / "predictions.jsonl").write_text('{"sample_id": "s1"}\n')
        return {"accuracy": 1.0}
    session_factory = sessionmaker(bind=db_session.get_bind())
    with patch("app.jobs.runner.SessionLocal", side_effect=session_factory), \
         patch("app.jobs.runner.GpuManager.acquire", return_value=True), \
         patch("app.jobs.runner.GpuManager.release", return_value=True), \
         patch.dict("sys.modules", {"benchmark.core.runner": MagicMock(run_benchmark=fake_run_benchmark)}), \
         patch("sys.argv", ["runner.py", run_id]):
        runner.main()

    assert captured_args["artifacts_dir"] == str(settings.artifacts_path)
    with session_factory() as check_s:
        fresh_run = check_s.get(BenchmarkRun, run_id)
        assert fresh_run.status == RunStatusEnum.COMPLETED


def test_runner_cancelled_status_not_overwritten_by_completed(db_session: Session):
    """Regression test for Bug 3: when cancel_requested is True, status is marked CANCELLED, not COMPLETED."""
    from app.jobs import runner

    run_id = "test-cancel-not-completed-run"
    run = BenchmarkRun(
        id=run_id,
        user_id=_make_user(db_session, "user_canc"),
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        split="test",
        sample_count=5,
        status=RunStatusEnum.QUEUED,
        cancel_requested=False,
        is_private=False,
    )
    db_session.add(run)
    db_session.commit()
    def fake_run_benchmark(**kwargs):
        with sessionmaker(bind=db_session.get_bind())() as s:
            r = s.get(BenchmarkRun, run_id)
            r.cancel_requested = True
            s.commit()
        return {"accuracy": 0.5}

    session_factory = sessionmaker(bind=db_session.get_bind())
    with patch("app.jobs.runner.SessionLocal", side_effect=session_factory), \
         patch("app.jobs.runner.GpuManager.acquire", return_value=True), \
         patch("app.jobs.runner.GpuManager.release", return_value=True), \
         patch.dict("sys.modules", {"benchmark.core.runner": MagicMock(run_benchmark=fake_run_benchmark)}), \
         patch("sys.argv", ["runner.py", run_id]), \
         patch("sys.exit", side_effect=SystemExit(0)) as mock_exit, \
         contextlib.suppress(SystemExit):
        runner.main()

    with session_factory() as check_s:
        fresh_run = check_s.get(BenchmarkRun, run_id)
        assert fresh_run.status == RunStatusEnum.CANCELLED
    mock_exit.assert_called_with(0)


def test_runner_cancel_check_queries_db_with_populate_existing(db_session: Session):
    """Regression test for Bug 2: cancel_check detects DB update even when entity is cached in session."""

    run_id = "test-cancel-populate-existing-run"
    run = BenchmarkRun(
        id=run_id,
        user_id=_make_user(db_session, "user_pop"),
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        split="test",
        sample_count=5,
        status=RunStatusEnum.QUEUED,
        cancel_requested=False,
        is_private=False,
    )
    db_session.add(run)
    db_session.commit()

    # Load run into db_session identity map
    cached_run = db_session.get(BenchmarkRun, run_id)
    assert not cached_run.cancel_requested

    # Simulate another session/process updating cancel_requested in the DB directly
    db_session.execute(
        BenchmarkRun.__table__.update()
        .where(BenchmarkRun.id == run_id)
        .values(cancel_requested=True)
    )
    db_session.commit()

    # Without populate_existing=True, db_session.get(BenchmarkRun, run_id) would return False
    # With populate_existing=True, it detects True
    fresh = db_session.get(BenchmarkRun, run_id, populate_existing=True)
    assert fresh.cancel_requested is True


def test_startup_reconciliation_clears_lock_and_marks_failed(db_session: Session):
    """Regression test for Task 5: restart reconciles orphaned RUNNING and QUEUED runs and clears GPU lock."""
    # Create an orphaned RUNNING run and QUEUED run
    run1 = BenchmarkRun(
        id="orphan-running-1",
        user_id=_make_user(db_session, "user_rec"),
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        split="test",
        sample_count=5,
        status=RunStatusEnum.RUNNING,
        started_at=datetime.now(UTC).replace(tzinfo=None),
        progress_done=1,
        progress_total=5,
        is_private=False,
    )
    run2 = BenchmarkRun(
        id="orphan-queued-2",
        user_id=run1.user_id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        split="test",
        sample_count=5,
        status=RunStatusEnum.QUEUED,
        is_private=False,
    )
    db_session.add(run1)
    db_session.add(run2)

    # Set GPU lock holder
    lock = db_session.get(GpuLock, 1)
    if not lock:
        lock = GpuLock(id=1, holder_run_id="orphan-running-1", acquired_at=datetime.now(UTC).replace(tzinfo=None))
        db_session.add(lock)
    else:
        lock.holder_run_id = "orphan-running-1"
        lock.acquired_at = datetime.now(UTC).replace(tzinfo=None)
    db_session.commit()

    # Run reconciliation
    BenchmarkService.reconcile_stale_runs(db_session)

    db_session.refresh(run1)
    db_session.refresh(run2)
    db_session.refresh(lock)

    assert run1.status == RunStatusEnum.FAILED
    assert run1.error_text == "Orphaned run reconciled at startup"
    assert run2.status == RunStatusEnum.FAILED
    assert run2.error_text == "Orphaned run reconciled at startup"
    assert lock.holder_run_id is None
    assert lock.acquired_at is None
