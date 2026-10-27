import time
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import GpuLock


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class GpuManager:
    @staticmethod
    def ensure_gpu_lock_row(db: Session) -> None:
        lock = db.get(GpuLock, 1)
        if not lock:
            # Insert row 1 if missing
            db.execute(
                text(
                    "INSERT OR IGNORE INTO gpu_locks (id, holder_run_id, acquired_at) "
                    "VALUES (1, NULL, NULL)"
                )
            )
            db.commit()

    @staticmethod
    def is_locked(db: Session) -> bool:
        lock = db.get(GpuLock, 1)
        return lock is not None and lock.holder_run_id is not None

    @staticmethod
    def get_holder(db: Session) -> str | None:
        lock = db.get(GpuLock, 1)
        return lock.holder_run_id if lock else None

    @staticmethod
    def try_acquire(db: Session, run_id: str) -> bool:
        # ponytail: idempotent, so a caller that never seeded the row (worker
        # subprocess, direct test harness) acquires instead of waiting forever
        # on an UPDATE that matches zero rows.
        GpuManager.ensure_gpu_lock_row(db)
        now = utcnow()
        stmt = text(
            "UPDATE gpu_locks "
            "SET holder_run_id = :run_id, acquired_at = :now "
            "WHERE id = 1 AND holder_run_id IS NULL"
        )
        result = db.execute(stmt, {"run_id": run_id, "now": now})
        db.commit()
        return result.rowcount > 0

    @staticmethod
    def acquire(
        db: Session,
        run_id: str,
        timeout_sec: float = 30.0,
        interval_sec: float = 1.0,
        cancel_check=None,
    ) -> bool:
        GpuManager.ensure_gpu_lock_row(db)
        start_time = time.time()
        while True:
            if cancel_check and cancel_check():
                return False
            if GpuManager.try_acquire(db, run_id):
                return True
            if timeout_sec > 0 and (time.time() - start_time) >= timeout_sec:
                return False
            time.sleep(interval_sec)

    @staticmethod
    def release(db: Session, run_id: str | None = None) -> bool:
        if run_id:
            stmt = text(
                "UPDATE gpu_locks "
                "SET holder_run_id = NULL, acquired_at = NULL "
                "WHERE id = 1 AND holder_run_id = :run_id"
            )
            result = db.execute(stmt, {"run_id": run_id})
        else:
            stmt = text(
                "UPDATE gpu_locks SET holder_run_id = NULL, acquired_at = NULL WHERE id = 1"
            )
            result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0
