import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_current_user_optional,
    get_db,
    verify_csrf_header,
)
from app.config import settings
from app.db.models import RunStatusEnum, User
from app.schemas.benchmark import (
    BenchmarkRunResponse,
    CreateBenchmarkRequest,
    PaginatedPredictionsResponse,
    PaginatedRunsResponse,
    RunResultsResponse,
    RunStatusResponse,
)
from app.services.benchmark_service import (
    BenchmarkService,
    ConflictError,
    SafePathError,
    safe_artifact_path,
)

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.post(
    "",
    response_model=BenchmarkRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_csrf_header)],
)
async def create_benchmark(
    req: CreateBenchmarkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        run = await BenchmarkService.create_benchmark(
            db=db,
            user=current_user,
            model_id=req.model_id,
            dataset_id=req.dataset_id,
            protocol_id=req.protocol_id,
            split=req.split,
            sample_size_mode=req.sample_size_mode,
            sample_count=req.sample_count,
            seed=req.seed,
            is_private=req.is_private,
        )
        return run
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("", response_model=PaginatedRunsResponse)
def list_benchmarks(
    model_id: str | None = Query(None),
    domain: str | None = Query(None),
    run_status: RunStatusEnum | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    runs, total = BenchmarkService.list_runs(
        db=db,
        current_user=current_user,
        model_id=model_id,
        domain=domain,
        status=run_status,
        limit=limit,
        offset=offset,
    )
    return PaginatedRunsResponse(items=runs, total=total, limit=limit, offset=offset)


@router.get("/{id}", response_model=BenchmarkRunResponse)
def get_benchmark(
    id: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    run = BenchmarkService.get_run(db, id, current_user)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark run '{id}' not found",
        )
    return run


@router.get("/{id}/status", response_model=RunStatusResponse)
def get_benchmark_status(
    id: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    run = BenchmarkService.get_run(db, id, current_user)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark run '{id}' not found",
        )
    return RunStatusResponse(
        id=run.id,
        status=run.status,
        progress_done=run.progress_done,
        progress_total=run.progress_total,
        cancel_requested=run.cancel_requested,
        error_text=run.error_text,
    )


@router.get("/{id}/results", response_model=RunResultsResponse)
def get_benchmark_results(
    id: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    results = BenchmarkService.get_run_results(db, id, current_user)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark run '{id}' not found",
        )
    return results


@router.get("/{id}/predictions", response_model=PaginatedPredictionsResponse)
def get_benchmark_predictions(
    id: str,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    preds = BenchmarkService.get_run_predictions(
        db=db,
        run_id=id,
        current_user=current_user,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    if preds is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark run '{id}' not found",
        )
    items, total = preds
    return PaginatedPredictionsResponse(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/{id}/cancel",
    response_model=RunStatusResponse,
    dependencies=[Depends(verify_csrf_header)],
)
def cancel_benchmark(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        run = BenchmarkService.cancel_run(db, id, current_user)
        return RunStatusResponse(
            id=run.id,
            status=run.status,
            progress_done=run.progress_done,
            progress_total=run.progress_total,
            cancel_requested=run.cancel_requested,
            error_text=run.error_text,
        )
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark run '{id}' not found",
        ) from e
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.post(
    "/{id}/rerun",
    response_model=BenchmarkRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_csrf_header)],
)
async def rerun_benchmark(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return await BenchmarkService.rerun(db, id, current_user)
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark run '{id}' not found",
        ) from e
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


@router.get("/{id}/export")
def export_benchmark(
    id: str,
    export_format: str = Query("jsonl", alias="format", pattern="^(jsonl|csv)$"),
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    # Verify access
    run = BenchmarkService.get_run(db, id, current_user)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark run '{id}' not found",
        )

    try:
        pred_path = safe_artifact_path(settings.artifacts_path, id, "predictions.jsonl")
    except SafePathError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Predictions artifact not found",
        ) from e

    if export_format == "jsonl":
        return FileResponse(
            path=pred_path,
            media_type="application/x-ndjson",
            filename=f"run_{id}_predictions.jsonl",
        )

    # Convert jsonl to CSV stream
    def generate_csv():
        buf = io.StringIO()
        writer = None
        with open(pred_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if writer is None:
                        # Establish CSV columns from first record
                        fieldnames = list(record.keys())
                        writer = csv.DictWriter(buf, fieldnames=fieldnames)
                        writer.writeheader()
                    # Flatten any complex fields
                    row = {
                        k: json.dumps(v) if isinstance(v, (dict, list)) else v
                        for k, v in record.items()
                    }
                    writer.writerow(row)
                    yield buf.getvalue()
                    buf.seek(0)
                    buf.truncate(0)
                except json.JSONDecodeError:
                    continue

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=run_{id}_predictions.csv"},
    )
