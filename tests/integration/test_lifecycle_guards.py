"""Section 11 lifecycle regression: terminal statuses cannot be overwritten.

The worker's COMPLETED transition is a conditional UPDATE requiring the run
to still be QUEUED/RUNNING and not cancel-requested. A run already FAILED by
reconciliation or the crash monitor must stay FAILED even if the (stale)
worker finishes normally afterwards.
"""

from contextlib import suppress
from datetime import UTC, datetime
from unittest.mock import patch

from app.db.models import BenchmarkRun, RunStatusEnum
from app.jobs import runner as job_runner
from sqlalchemy.orm import sessionmaker


def _make_run(db_session, run_id, status, user_id):
    run = BenchmarkRun(
        id=run_id,
        user_id=user_id,
        model_id="lumma-0.6b",
        dataset_id="sciq",
        protocol_id="sciq_evidence_grounded",
        split="test",
        sample_count=5,
        status=status,
        is_private=False,
    )
    db_session.add(run)
    db_session.commit()
    return run


def test_completed_transition_never_overwrites_failed(db_session):
    """Run already FAILED (e.g. crash monitor) must not become COMPLETED."""
    from tests.integration.test_integration_regressions import _make_user

    run_id = "test-terminal-failed-guard"
    _make_run(db_session, run_id, RunStatusEnum.FAILED, _make_user(db_session, "user_tfg"))

    # Simulate the worker's guarded transition directly (same SQL shape).
    from sqlalchemy import update

    res = db_session.execute(
        update(BenchmarkRun)
        .where(
            BenchmarkRun.id == run_id,
            BenchmarkRun.cancel_requested.is_(False),
            BenchmarkRun.status.in_([RunStatusEnum.QUEUED, RunStatusEnum.RUNNING]),
        )
        .values(status=RunStatusEnum.COMPLETED, completed_at=datetime.now(UTC).replace(tzinfo=None))
    )
    db_session.commit()
    assert res.rowcount == 0
    fresh = db_session.get(BenchmarkRun, run_id)
    assert fresh.status == RunStatusEnum.FAILED


def test_completed_transition_never_overwrites_cancelled(db_session):
    from tests.integration.test_integration_regressions import _make_user

    run_id = "test-terminal-cancelled-guard"
    _make_run(db_session, run_id, RunStatusEnum.CANCELLED, _make_user(db_session, "user_tcg"))

    from sqlalchemy import update

    res = db_session.execute(
        update(BenchmarkRun)
        .where(
            BenchmarkRun.id == run_id,
            BenchmarkRun.cancel_requested.is_(False),
            BenchmarkRun.status.in_([RunStatusEnum.QUEUED, RunStatusEnum.RUNNING]),
        )
        .values(status=RunStatusEnum.COMPLETED, completed_at=datetime.now(UTC).replace(tzinfo=None))
    )
    db_session.commit()
    assert res.rowcount == 0
    assert db_session.get(BenchmarkRun, run_id).status == RunStatusEnum.CANCELLED


def test_worker_exits_when_run_terminal_before_running(db_session):
    """Worker spawn races a queued-cancel: RUNNING transition fails, worker exits."""
    from tests.integration.test_integration_regressions import _make_user

    run_id = "test-queued-cancel-race"
    run = _make_run(db_session, run_id, RunStatusEnum.CANCELLED, _make_user(db_session, "user_qcr"))
    run.cancel_requested = True
    db_session.commit()

    session_factory = sessionmaker(bind=db_session.get_bind())
    with (
        patch("app.jobs.runner.SessionLocal", side_effect=session_factory),
        patch("sys.argv", ["runner.py", run_id]),
        patch("sys.exit", side_effect=SystemExit(0)),
        suppress(SystemExit),
    ):
        job_runner.main()

    assert db_session.get(BenchmarkRun, run_id).status == RunStatusEnum.CANCELLED
