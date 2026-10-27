import json
import os
import signal
import sys
from datetime import UTC, datetime

from sqlalchemy import update

from app.config import settings
from app.db.models import Artifact, BenchmarkMetric, BenchmarkRun, RunStatusEnum
from app.db.session import SessionLocal
from app.jobs.process_manager import process_start_token
from app.services.gpu_manager import GpuManager


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _sigterm_handler(signum, frame) -> None:
    sys.exit(0)


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

        acquired = GpuManager.acquire(
            db,
            run_id,
            timeout_sec=120.0,
            interval_sec=1.0,
            cancel_check=cancel_check,
        )

        if not acquired:
            db.refresh(run)
            if run.cancel_requested:
                run.status = RunStatusEnum.CANCELLED
                run.completed_at = utcnow()
                db.commit()
                sys.exit(0)
            else:
                run.status = RunStatusEnum.FAILED
                run.error_text = "Timed out waiting to acquire GPU lock"
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
                device="cuda",
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
