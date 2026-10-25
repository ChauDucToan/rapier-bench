import asyncio
import signal
import sys
from typing import ClassVar


class ProcessManager:
    # Track child processes by run_id
    _processes: ClassVar[dict[str, asyncio.subprocess.Process]] = {}

    @classmethod
    async def spawn_runner(cls, run_id: str) -> int:
        cmd = [sys.executable, "-m", "app.jobs.runner", run_id]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        cls._processes[run_id] = proc

        # Register cleanup when process finishes
        asyncio.create_task(cls._monitor_process(run_id, proc))
        return proc.pid

    @classmethod
    async def _monitor_process(cls, run_id: str, proc: asyncio.subprocess.Process) -> None:
        try:
            await proc.wait()
        finally:
            cls._processes.pop(run_id, None)

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
