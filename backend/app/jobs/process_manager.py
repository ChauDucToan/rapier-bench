import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import ClassVar


def process_start_token(pid: int) -> str | None:
    """Best-effort Linux process identity: /proc start time (field 22).

    Combined with the PID it defeats PID-recycling false positives during
    startup reconciliation. Returns None where unavailable (non-Linux);
    callers then rely on PID liveness alone.
    """
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
            fields = f.read().rsplit(")", 1)[-1].split()
        return fields[19]  # starttime (22nd field, 0-indexed after comm)
    except (OSError, IndexError):
        return None


def same_process(pid: int | None, start_token: str | None) -> bool:
    """True when `pid` is alive AND matches the recorded start token."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but is owned by another user: treat as alive.
        return True
    if start_token is None:
        return True  # no recorded token: fall back to bare PID liveness
    return process_start_token(pid) == start_token


class ProcessManager:
    # Track child processes by run_id
    _processes: ClassVar[dict[str, asyncio.subprocess.Process]] = {}

    @classmethod
    async def spawn_runner(cls, run_id: str) -> int:
        cmd = [sys.executable, "-m", "app.jobs.runner", run_id]
        # F4: capture worker output to per-run log files instead of DEVNULL so
        # worker crashes leave actionable diagnostics.
        log_dir = Path("logs/workers")
        log_dir.mkdir(parents=True, exist_ok=True)
        # ponytail: file handle lifetime is managed by _monitor_process (closed
        # after wait()); restructure to context manager only if nested-process
        # log routing grows.
        log_file = open(log_dir / f"{run_id}.log", "ab")  # noqa: SIM115
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=log_file,
                stderr=asyncio.subprocess.STDOUT,
            )
        except Exception:
            log_file.close()
            raise
        cls._processes[run_id] = proc

        # Register cleanup when process finishes
        asyncio.create_task(cls._monitor_process(run_id, proc, log_file))
        return proc.pid

    @classmethod
    async def _monitor_process(
        cls, run_id: str, proc: asyncio.subprocess.Process, log_file=None
    ) -> None:
        """A2: if the worker dies abnormally while the run is still non-terminal,
        mark it FAILED in the DB instead of leaving it RUNNING/QUEUED forever.
        """
        try:
            returncode = await proc.wait()
            if returncode not in (0,):
                from app.db.models import BenchmarkRun, RunStatusEnum
                from app.db.session import SessionLocal

                with SessionLocal() as db:
                    run = db.get(BenchmarkRun, run_id)
                    if run and run.status in (RunStatusEnum.QUEUED, RunStatusEnum.RUNNING):
                        run.status = RunStatusEnum.FAILED
                        run.error_text = f"Worker process exited with code {returncode}; see logs/workers/{run_id}.log"
                        from datetime import UTC, datetime

                        run.completed_at = datetime.now(UTC).replace(tzinfo=None)
                        db.commit()
        finally:
            cls._processes.pop(run_id, None)
            if log_file:
                log_file.close()

    @classmethod
    def terminate_process(cls, run_id: str) -> bool:
        proc = cls._processes.get(run_id)
        if proc and proc.returncode is None:
            try:
                proc.send_signal(signal.SIGTERM)
                return True
            except ProcessLookupError:
                pass
        return False

    @classmethod
    def get_pid(cls, run_id: str) -> int | None:
        proc = cls._processes.get(run_id)
        return proc.pid if proc else None
