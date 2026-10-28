import json
import os
import signal
import sys
from datetime import UTC, datetime

from sqlalchemy import update

from app.config import settings
from app.db.models import Artifact, BenchmarkMetric, BenchmarkRun, RunStatusEnum
from app.db.session import SessionLocal
from app.jobs.process_manager import process_start_token, same_process
from app.services.gpu_manager import GpuManager


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _sigterm_handler(signum, frame) -> None:
    sys.exit(0)


def _holder_dead(db) -> bool:
    """E1: True when the current GPU lock holder's worker is verifiably dead.

    Uses the same PID + /proc start-token identity as startup reconciliation.
    A holder with no identity row is treated as ALIVE (conservative: a legacy
    row should not cause lock takeover while its worker may still run).
    """
    holder = GpuManager.get_holder(db)
    if not holder:
        return False
    holder_run = db.get(BenchmarkRun, holder)
    if holder_run is None:
        return False
    return not same_process(holder_run.worker_pid, holder_run.worker_start_ts)



signal.signal(signal.SIGTERM, _sigterm_handler)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m app.jobs.runner <run_id>", file=sys.stderr)
        sys.exit(1)

    run_id = sys.argv[1]
    db = SessionLocal()

    try:
        run = db.get(BenchmarkRun, run_id)
        if not run:
            print(f"Error: Run {run_id} not found in database", file=sys.stderr)
            sys.exit(1)

        if run.cancel_requested:
            run.status = RunStatusEnum.CANCELLED
            run.completed_at = utcnow()
            db.commit()
            sys.exit(0)

        # A3: worker self-registration. The API records the PID right after
        # spawn, but an API restart in that gap would see worker_pid=None.
        # The worker re-asserts its identity here so reconciliation always has
        # a fresh, accurate liveness token.
        run.worker_pid = os.getpid()
        run.worker_start_ts = process_start_token(os.getpid())
        db.commit()

        # Acquire single GPU lock
        def cancel_check() -> bool:
            curr = db.get(BenchmarkRun, run_id, populate_existing=True)
            return bool(curr and curr.cancel_requested)

        # E1: queue semantics. A second job legitimately waits behind a
        # long-running benchmark — waiting is NOT failure. The worker waits
        # indefinitely (cancel-aware) instead of failing after 120 s. Two
        # bounded escape hatches keep the wait safe:
        #   - cancellation (checked every poll)
        #   - the lock holder's worker dying (checked every 30 s): then the
        #     lock is stale and this worker takes it over.
        import time as _time

        _last_holder_liveness = 0.0

        while True:
            try:
                if cancel_check():
                    break
                if GpuManager.try_acquire(db, run_id):
                    break
                # Periodic dead-holder takeover check (every 30 s).
                now = _time.monotonic()
                if now - _last_holder_liveness >= 30.0:
                    _last_holder_liveness = now
                    if _holder_dead(db):
                        # Stale lock from a crashed worker: recover it.
                        GpuManager.release(db)
                        continue
            except Exception as exc:
                # E2: a DB error inside the queue loop must not strand the run
                # in QUEUED forever — mark it FAILED with the underlying error
                # so the user sees actionable diagnostics.
                db.rollback()
                run = db.get(BenchmarkRun, run_id)
                if run is not None:
                    run.status = RunStatusEnum.FAILED
                    run.error_text = f"GPU queue loop error: {exc}"
                    run.completed_at = utcnow()
                    db.commit()
                sys.exit(1)
            _time.sleep(1.0)

        acquired = bool(GpuManager.is_locked(db) and GpuManager.get_holder(db) == run_id)

        if not acquired:
            db.refresh(run)
            if run.cancel_requested:
                run.status = RunStatusEnum.CANCELLED
                run.completed_at = utcnow()
                db.commit()
                sys.exit(0)
            else:
                run.status = RunStatusEnum.FAILED
                run.error_text = "Could not acquire GPU lock"
                run.completed_at = utcnow()
                db.commit()
                sys.exit(1)

        # Mark RUNNING — guarded: a run cancelled while queued must never be
        # flipped back to RUNNING by the worker that missed the cancel.
        running = db.execute(
            update(BenchmarkRun)
            .where(
                BenchmarkRun.id == run_id,
                BenchmarkRun.cancel_requested.is_(False),
                BenchmarkRun.status.in_([RunStatusEnum.QUEUED, RunStatusEnum.RUNNING]),
            )
            .values(status=RunStatusEnum.RUNNING, started_at=utcnow())
        )
        db.commit()
        if running.rowcount == 0:
            db.refresh(run)
            if run.status not in (RunStatusEnum.QUEUED, RunStatusEnum.RUNNING):
                sys.exit(0)  # terminal (e.g. cancelled while queued)
            # else: cancel_requested path handled by cancel_check loops.

        # Lazy import of benchmark.core.runner
        try:
            from benchmark.core.runner import run_benchmark
        except Exception as e:
            run.status = RunStatusEnum.FAILED
            run.error_text = f"ImportError: Failed to import benchmark runner: {e}"
            run.completed_at = utcnow()
            db.commit()
            GpuManager.release(db, run_id)
            print(f"Failed to import benchmark.core.runner: {e}", file=sys.stderr)
            sys.exit(1)

        # Device selection: prefer CUDA when a GPU is actually available,
        # otherwise fall back to CPU so the stack still runs benchmarks on
        # machines (and Docker containers) without a GPU. CUDA detection uses
        # torch.cuda.is_available via a subprocess probe — importing torch
        # in-process here previously segfaulted under the test suite's patched
        # sys.modules environment, and the model adapter re-checks
        # availability at load time anyway (raises RuntimeError if cuda was
        # requested without a device).
        import subprocess as _sp

        def _cuda_available() -> bool:
            try:
                probe = _sp.run(
                    [sys.executable, "-c", "import torch;print(int(torch.cuda.is_available()))"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                return probe.returncode == 0 and probe.stdout.strip() == "1"
            except Exception:
                return False

        device = "cuda" if _cuda_available() else "cpu"

        # Call benchmark execution
        artifacts_path = settings.artifacts_path / run_id
        artifacts_path.mkdir(parents=True, exist_ok=True)

        def progress_cb(done: int, total: int) -> None:
            r = db.get(BenchmarkRun, run_id)
            if r:
                r.progress_done = done
                r.progress_total = total
                db.commit()

        try:
            metrics = run_benchmark(
                run_id=run.id,
                model_id=run.model_id,
                dataset_id=run.dataset_id,
                split=run.split,
                sample_count=run.sample_count,
                seed=run.seed,
                protocol_id=run.protocol_id,
                artifacts_dir=str(settings.artifacts_path),
                device=device,
                progress_callback=progress_cb,
                cancel_check=cancel_check,
            )

            # Persist metrics
            if isinstance(metrics, dict):
                for metric_name, metric_val in metrics.items():
                    db.add(
                        BenchmarkMetric(
                            run_id=run.id,
                            metric_name=metric_name,
                            metric_value=float(metric_val),
                        )
                    )

            # Record artifacts
            if artifacts_path.is_dir():
                for file_entry in artifacts_path.rglob("*"):
                    if file_entry.is_file() and not file_entry.name.endswith(".tmp"):
                        rel = str(file_entry.relative_to(settings.artifacts_path))
                        db.add(
                            Artifact(
                                run_id=run.id,
                                artifact_type=file_entry.stem,
                                relative_path=rel,
                                file_size_bytes=file_entry.stat().st_size,
                                created_at=utcnow(),
                            )
                        )

            db.refresh(run)
            if run.cancel_requested:
                run.status = RunStatusEnum.CANCELLED
                run.completed_at = utcnow()
                db.commit()
                sys.exit(0)

            hw_candidates = [
                artifacts_path / "hardware.json",
                artifacts_path / run_id / "hardware.json",
            ]
            for hw_file in hw_candidates:
                if hw_file.is_file():
                    try:
                        with open(hw_file, encoding="utf-8") as f:
                            run.hardware_metadata = json.load(f)
                        break
                    except Exception as e:
                        print(f"Warning: could not read {hw_file}: {e}", file=sys.stderr)

            rc_candidates = [
                artifacts_path / "run_config.json",
                artifacts_path / run_id / "run_config.json",
            ]
            for rc_file in rc_candidates:
                if rc_file.is_file():
                    try:
                        with open(rc_file, encoding="utf-8") as f:
                            cfg_data = json.load(f)
                            sample_selection_data = {
                                "selected_sample_ids": cfg_data.get("selected_sample_ids", []),
                                "requested_samples": cfg_data.get("requested_samples"),
                                "actual_samples": cfg_data.get("actual_samples"),
                                "sample_shortfall": (
                                    cfg_data.get("shortfall_report", {}).get("shortfall", 0)
                                    if isinstance(cfg_data.get("shortfall_report"), dict)
                                    else max(
                                        0,
                                        (cfg_data.get("requested_samples") or 0)
                                        - (cfg_data.get("actual_samples") or 0),
                                    )
                                ),
                                "shortfall_report": cfg_data.get("shortfall_report"),
                            }
                            for k, v in cfg_data.items():
                                if k not in sample_selection_data:
                                    sample_selection_data[k] = v
                            run.sample_selection = sample_selection_data
                        break
                    except Exception as e:
                        print(f"Warning: could not read {rc_file}: {e}", file=sys.stderr)
            # A2: atomic terminal transition. Check-then-set would let a cancel
            # that lands between the read and the write be overwritten by
            # COMPLETED. Conditional UPDATE keeps cancelled runs CANCELLED,
            # and the status guard means an already-terminal run (FAILED by
            # reconciliation or the crash monitor) is never overwritten.
            completed = db.execute(
                update(BenchmarkRun)
                .where(
                    BenchmarkRun.id == run_id,
                    BenchmarkRun.cancel_requested.is_(False),
                    BenchmarkRun.status.in_([RunStatusEnum.QUEUED, RunStatusEnum.RUNNING]),
                )
                .values(status=RunStatusEnum.COMPLETED, completed_at=utcnow())
            )
            db.commit()
            if completed.rowcount == 0:
                db.execute(
                    update(BenchmarkRun)
                    .where(
                        BenchmarkRun.id == run_id,
                        BenchmarkRun.status.in_([RunStatusEnum.QUEUED, RunStatusEnum.RUNNING]),
                    )
                    .values(status=RunStatusEnum.CANCELLED, completed_at=utcnow())
                )
                db.commit()
                sys.exit(0)

        except Exception as e:
            db.refresh(run)
            if run.cancel_requested:
                run.status = RunStatusEnum.CANCELLED
                run.completed_at = utcnow()
                db.commit()
                sys.exit(0)
            else:
                run.status = RunStatusEnum.FAILED
                run.error_text = str(e)
                run.completed_at = utcnow()
                db.commit()
                sys.exit(1)
        finally:
            GpuManager.release(db, run_id)

    finally:
        db.close()


if __name__ == "__main__":
    main()
