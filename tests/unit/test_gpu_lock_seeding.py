"""Regression test: try_acquire must self-seed row 1 of gpu_locks.

Symptom before the fix: runner.main() queued on a lock table with no row 1.
`UPDATE gpu_locks ... WHERE id = 1` matched zero rows forever, so the (deliberately
unbounded) queue loop spun until the test timed out instead of acquiring the lock.
"""

from app.db.models import GpuLock
from app.services.gpu_manager import GpuManager
from sqlalchemy.orm import Session


def test_try_acquire_seeds_missing_lock_row(db_session: Session) -> None:
    assert db_session.get(GpuLock, 1) is None

    assert GpuManager.try_acquire(db_session, "run-a") is True
    assert GpuManager.get_holder(db_session) == "run-a"
    assert GpuManager.try_acquire(db_session, "run-b") is False

def test_try_acquire_is_idempotent_when_row_exists(db_session: Session) -> None:
    GpuManager.ensure_gpu_lock_row(db_session)
    assert GpuManager.try_acquire(db_session, "run-a") is True
    GpuManager.release(db_session, "run-a")
    assert GpuManager.try_acquire(db_session, "run-b") is True
    assert GpuManager.get_holder(db_session) == "run-b"
