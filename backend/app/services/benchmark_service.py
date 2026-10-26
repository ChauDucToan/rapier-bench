import json
from datetime import UTC, datetime
from pathlib import Path

import yaml
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    BenchmarkProtocol,
    BenchmarkRun,
    DatasetDefinition,
    GpuLock,
    ModelDefinition,
    RunStatusEnum,
    User,
)
from app.jobs.process_manager import ProcessManager, process_start_token, same_process


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ConflictError(Exception):
    pass


class SafePathError(Exception):
    pass


SAMPLE_MODE_COUNTS = {
    "smoke": 10,
    "pilot": 25,
    "standard": 100,
}


def safe_artifact_path(artifacts_dir: Path, run_id: str, filename: str) -> Path:
    # ARCHITECTURE §7.3 Path-Traversal-Safe Serving
    base = artifacts_dir.resolve()
    run_dir = (base / run_id).resolve()
    if not run_dir.is_relative_to(base) or run_dir == base:
        raise SafePathError("Artifact not found")
    raw_target = run_dir / filename
    if raw_target.is_symlink():
        raise SafePathError("Artifact not found")
    target = raw_target.resolve()
    if not target.is_relative_to(run_dir) or not target.is_file():
        raise SafePathError("Artifact not found")
    return target


class BenchmarkService:
    @staticmethod
    def seed_catalogs(db: Session, configs_dir: Path | None = None) -> None:
        if configs_dir is None:
            configs_dir = Path("configs")

        # 1. Models
        models_file = configs_dir / "models.yaml"
        if models_file.is_file():
            with open(models_file, encoding="utf-8") as f:
                models_data = yaml.safe_load(f) or []
            for m in models_data:
                model_id = m["id"]
                existing = db.get(ModelDefinition, model_id)
                if not existing:
                    existing = ModelDefinition(id=model_id)
                    db.add(existing)
                existing.name = m["name"]
                existing.hf_id = m["hf_id"]
                existing.revision = m["revision"]
                existing.parameters = int(m["parameters"])
                existing.context_length = int(m["context_length"])
                existing.torch_dtype = m.get("torch_dtype", "bfloat16")
                existing.vram_weight_gb = float(m["vram_weight_gb"])
                existing.trust_remote_code = bool(m.get("trust_remote_code", False))
                existing.license = m.get("license", "unknown")
            db.flush()
        # 2. Datasets
        datasets_file = configs_dir / "datasets.yaml"
        if datasets_file.is_file():
            with open(datasets_file, encoding="utf-8") as f:
                datasets_data = yaml.safe_load(f) or []
            for d in datasets_data:
                dataset_id = d["id"]
                existing_d = db.get(DatasetDefinition, dataset_id)
                if not existing_d:
                    existing_d = DatasetDefinition(id=dataset_id)
                    db.add(existing_d)
                existing_d.name = d["name"]
                hf_id = d.get("hf_id")
                if not hf_id and isinstance(d.get("fallback_source"), dict):
                    hf_id = d["fallback_source"].get("hf_id")
                if not hf_id:
                    hf_id = d.get("raw_url", "")
                existing_d.hf_id = hf_id or "unknown"
                existing_d.domain = d["domain"]
                existing_d.task_type = d["task_type"]
                existing_d.default_split = d.get("default_split", "test")
                existing_d.evaluator_key = d["evaluator_key"]
            db.flush()
        # 3. Protocols
        protocols_dir = configs_dir / "protocols"
        if protocols_dir.is_dir():
            for p_file in protocols_dir.glob("*.yaml"):
                with open(p_file, encoding="utf-8") as f:
                    protocols_data = yaml.safe_load(f) or []
                for p in protocols_data:
                    proto_id = p["id"]
                    existing_p = db.get(BenchmarkProtocol, proto_id)
                    if not existing_p:
                        existing_p = BenchmarkProtocol(id=proto_id)
                        db.add(existing_p)
                    existing_p.dataset_id = p["dataset_id"]
                    existing_p.name = p["name"]
                    existing_p.version = str(p.get("version", "1.0.0"))
                    existing_p.prompt_template = p["prompt_template"]
                    existing_p.expected_answer_format = p["expected_answer_format"]

        db.commit()

    @staticmethod
    def reconcile_stale_runs(db: Session) -> None:
        # ARCHITECTURE §6.4 Stale Run Reconciliation at Startup
        # A3: a QUEUED/RUNNING run is only stale when its worker process is
        # NOT alive. If the API restarted but the worker survived (separate
        # process), failing the run and freeing the GPU lock would let a new
        # worker start inference concurrently on the same GPU. Identity uses
        # PID + /proc start token to avoid PID-recycling false positives.
        def _worker_alive(run: BenchmarkRun) -> bool:
            return same_process(run.worker_pid, run.worker_start_ts)

        stmt = (
            select(BenchmarkRun)
            .where(BenchmarkRun.status.in_([RunStatusEnum.QUEUED, RunStatusEnum.RUNNING]))
        )
        stale_runs = db.scalars(stmt).all()
        for run in stale_runs:
            if _worker_alive(run):
                # Worker survived the API restart: leave status and GPU lock
                # alone; the worker owns the rest of the lifecycle.
                continue
            run.status = RunStatusEnum.FAILED
            run.error_text = "Orphaned run reconciled at startup (worker process not running)"
            run.completed_at = utcnow()

        # Clear GPU lock only when it is not held by a surviving worker.
        lock = db.get(GpuLock, 1)
        holder = lock.holder_run_id if lock else None
        holder_alive = False
        if holder:
            holder_run = db.get(BenchmarkRun, holder)
            holder_alive = _worker_alive(holder_run) if holder_run else False
        if not holder_alive:
            if not lock:
                db.add(GpuLock(id=1, holder_run_id=None, acquired_at=None))
            else:
                lock.holder_run_id = None
                lock.acquired_at = None

        db.commit()

    @staticmethod
    def list_models(
        db: Session,
        domain: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ModelDefinition]:
        stmt = select(ModelDefinition)
        # ModelDefinition doesn't have domain directly; filter if datasets with domain exist
        if domain:
            # Models that have completed runs in this domain
            stmt = (
                stmt.join(BenchmarkRun, BenchmarkRun.model_id == ModelDefinition.id)
                .join(DatasetDefinition, BenchmarkRun.dataset_id == DatasetDefinition.id)
                .where(
                    DatasetDefinition.domain == domain,
                    BenchmarkRun.status == RunStatusEnum.COMPLETED,
                    BenchmarkRun.is_private.is_(False),
                )
                .distinct()
            )
        stmt = stmt.order_by(ModelDefinition.name).offset(offset).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_model(db: Session, model_id: str) -> ModelDefinition | None:
        return db.get(ModelDefinition, model_id)

    @staticmethod
    def list_datasets(
        db: Session,
        domain: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DatasetDefinition]:
        stmt = select(DatasetDefinition)
        if domain:
            stmt = stmt.where(DatasetDefinition.domain == domain)
        stmt = stmt.order_by(DatasetDefinition.name).offset(offset).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_dataset(db: Session, dataset_id: str) -> DatasetDefinition | None:
        return db.get(DatasetDefinition, dataset_id)

    @staticmethod
    async def create_benchmark(
        db: Session,
        user: User,
        model_id: str,
        dataset_id: str,
        protocol_id: str | None = None,
        split: str | None = None,
        sample_size_mode: str = "smoke",
        sample_count: int | None = None,
        seed: int = 42,
        is_private: bool = True,
    ) -> BenchmarkRun:
        # Validate model
        model = db.get(ModelDefinition, model_id)
        if not model:
            raise ValueError(f"Unknown model_id: '{model_id}'")

        # Validate dataset
        dataset = db.get(DatasetDefinition, dataset_id)
        if not dataset:
            raise ValueError(f"Unknown dataset_id: '{dataset_id}'")

        # Validate or default protocol
        if protocol_id:
            proto = db.get(BenchmarkProtocol, protocol_id)
            if not proto or proto.dataset_id != dataset_id:
                raise ValueError(
                    f"Unknown or incompatible protocol_id: '{protocol_id}' for dataset '{dataset_id}'"
                )
        else:
            stmt = select(BenchmarkProtocol).where(BenchmarkProtocol.dataset_id == dataset_id)
            proto = db.scalars(stmt).first()
            if not proto:
                raise ValueError(f"No protocol found for dataset '{dataset_id}'")
            protocol_id = proto.id

        split = split or dataset.default_split
        # A4: 'full' means the ENTIRE eligible split (count=None -> runner selects
        # all eligible samples), not a hardcoded 1000. 'custom' uses the explicit
        # sample_count as the exact requested count (G1).
        if sample_size_mode == "full":
            count = None
        elif sample_size_mode == "custom":
            count = sample_count
            if count is None:
                raise ValueError("sample_count is required when sample_size_mode is 'custom'")
        else:
            count = sample_count or SAMPLE_MODE_COUNTS.get(sample_size_mode, 10)

        import uuid

        run_id = str(uuid.uuid4())
        run = BenchmarkRun(
            id=run_id,
            user_id=user.id,
            model_id=model_id,
            dataset_id=dataset_id,
            protocol_id=protocol_id,
            split=split,
            sample_size_mode=sample_size_mode,
            sample_count=count,
            seed=seed,
            status=RunStatusEnum.QUEUED,
            is_private=is_private,
            cancel_requested=False,
            progress_done=0,
            progress_total=count or 0,
            created_at=utcnow(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Spawn runner process
        pid = await ProcessManager.spawn_runner(run.id)
        # A3: persist PID + process start token so startup reconciliation can
        # verify worker identity (PID alone can be recycled by the OS).
        run.worker_pid = pid
        run.worker_start_ts = process_start_token(pid)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def get_run(
        db: Session,
        run_id: str,
        current_user: User | None = None,
    ) -> BenchmarkRun | None:
        run = db.get(BenchmarkRun, run_id)
        if not run:
            return None
        # Privacy guard: if private and user is not owner, return None (404)
        if run.is_private and (not current_user or current_user.id != run.user_id):
            return None
        return run

    @staticmethod
    def list_runs(
        db: Session,
        current_user: User | None = None,
        model_id: str | None = None,
        domain: str | None = None,
        status: RunStatusEnum | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BenchmarkRun], int]:
        stmt = select(BenchmarkRun)
        count_stmt = select(func.count(BenchmarkRun.id))

        # Visibility filter
        if current_user:
            vis_filter = or_(
                BenchmarkRun.is_private.is_(False),
                BenchmarkRun.user_id == current_user.id,
            )
        else:
            vis_filter = BenchmarkRun.is_private.is_(False)

        stmt = stmt.where(vis_filter)
        count_stmt = count_stmt.where(vis_filter)

        if model_id:
            stmt = stmt.where(BenchmarkRun.model_id == model_id)
            count_stmt = count_stmt.where(BenchmarkRun.model_id == model_id)

        if domain:
            stmt = stmt.join(DatasetDefinition).where(DatasetDefinition.domain == domain)
            count_stmt = count_stmt.join(DatasetDefinition).where(
                DatasetDefinition.domain == domain
            )

        if status:
            stmt = stmt.where(BenchmarkRun.status == status)
            count_stmt = count_stmt.where(BenchmarkRun.status == status)

        total = db.scalar(count_stmt) or 0
        runs = list(
            db.scalars(
                stmt.order_by(BenchmarkRun.created_at.desc()).offset(offset).limit(limit)
            ).all()
        )
        return runs, total

    @staticmethod
    def cancel_run(db: Session, run_id: str, current_user: User) -> BenchmarkRun:
        run = db.get(BenchmarkRun, run_id)
        if not run:
            raise KeyError("Run not found")
        if run.user_id != current_user.id:
            raise PermissionError("Forbidden: only run owner may cancel")

        if run.status in [
            RunStatusEnum.COMPLETED,
            RunStatusEnum.FAILED,
            RunStatusEnum.CANCELLED,
        ]:
            raise ConflictError("Run is already in a terminal state")

        run.cancel_requested = True
        if run.status == RunStatusEnum.QUEUED:
            run.status = RunStatusEnum.CANCELLED
            run.completed_at = utcnow()
            ProcessManager.terminate_process(run.id)

        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    async def rerun(db: Session, run_id: str, current_user: User) -> BenchmarkRun:
        old_run = db.get(BenchmarkRun, run_id)
        if not old_run:
            raise KeyError("Run not found")
        if old_run.user_id != current_user.id:
            raise PermissionError("Forbidden: only run owner may rerun")

        return await BenchmarkService.create_benchmark(
            db=db,
            user=current_user,
            model_id=old_run.model_id,
            dataset_id=old_run.dataset_id,
            protocol_id=old_run.protocol_id,
            split=old_run.split,
            sample_size_mode=old_run.sample_size_mode,
            sample_count=old_run.sample_count,
            seed=old_run.seed,
            is_private=old_run.is_private,
        )

    @staticmethod
    def get_run_results(
        db: Session,
        run_id: str,
        current_user: User | None = None,
    ) -> dict | None:
        run = BenchmarkService.get_run(db, run_id, current_user)
        if not run:
            return None

        # Collect metrics
        metrics = {m.metric_name: m.metric_value for m in run.metrics}

        # Collect artifacts metadata
        artifacts_list = [
            {
                "artifact_type": a.artifact_type,
                "relative_path": a.relative_path,
                "file_size_bytes": a.file_size_bytes,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in run.artifacts
        ]

        return {
            "run_id": run.id,
            "status": run.status,
            "metrics": metrics,
            "hardware_metadata": run.hardware_metadata,
            "sample_selection": run.sample_selection,
            "artifacts": artifacts_list,
        }

    @staticmethod
    def get_run_predictions(
        db: Session,
        run_id: str,
        current_user: User | None = None,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int] | None:
        run = BenchmarkService.get_run(db, run_id, current_user)
        if not run:
            return None

        # Look for predictions.jsonl artifact
        try:
            pred_file = safe_artifact_path(
                settings.artifacts_path, run_id, "predictions.jsonl"
            )
        except SafePathError:
            return [], 0

        # C (Failure Analysis): filter contract shared with the UI.
        # - correctness filters operate on the evaluated outcome (is_correct)
        # - 'parse_failure' maps to the artifact parse_status value 'failed'
        # - raw parse_status values ('success'/'fallback'/'failed') still pass through
        # for direct API use.
        parse_status_values = {"success", "fallback", "failed"}

        predictions: list[dict] = []
        with open(pred_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if status_filter == "correct":
                    if record.get("is_correct") is not True:
                        continue
                elif status_filter == "incorrect":
                    if record.get("is_correct") is not False:
                        continue
                elif status_filter == "parse_failure":
                    if record.get("parse_status") != "failed":
                        continue
                elif status_filter in parse_status_values:
                    if record.get("parse_status") != status_filter:
                        continue
                elif status_filter is not None:
                    # Unknown filter value: 422-style rejection happens at the API layer.
                    raise ValueError(
                        f"Invalid status filter '{status_filter}'. Use 'correct', 'incorrect', "
                        "'parse_failure', 'success', 'fallback', or 'failed'."
                    )
                predictions.append(record)

        total = len(predictions)
        sliced = predictions[offset : offset + limit]
        return sliced, total
