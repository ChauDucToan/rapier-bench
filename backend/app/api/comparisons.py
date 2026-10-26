from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional, get_db
from app.db.models import BenchmarkRun, User
from app.schemas.benchmark import BenchmarkRunResponse
from app.schemas.comparison import ComparisonResponse
from app.services.benchmark_service import BenchmarkService

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


@router.get("", response_model=ComparisonResponse)
def get_comparison(
    run_ids: str = Query(..., description="Comma-separated run IDs to compare"),
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    ids = [rid.strip() for rid in run_ids.split(",") if rid.strip()]
    if len(ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 run_ids are required for comparison",
        )

    runs: list[BenchmarkRun] = []
    for rid in ids:
        run = BenchmarkService.get_run(db, rid, current_user)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Benchmark run '{rid}' not found or access denied",
            )
        runs.append(run)

    # Comparability gate (docs/ARCHITECTURE.md §10): runs may only be scored
    # together when they share dataset, protocol, split AND the evaluated sample IDs.
    incompatibilities: list[str] = []
    if len({r.dataset_id for r in runs}) > 1:
        incompatibilities.append("different datasets")
    if len({r.protocol_id for r in runs}) > 1:
        incompatibilities.append("different protocols")
    if len({r.split for r in runs}) > 1:
        incompatibilities.append("different splits")

    sample_sets: dict[str, list[str]] = {
        r.id: list((r.sample_selection or {}).get("selected_sample_ids") or []) for r in runs
    }
    # D1: comparability evidence is REQUIRED. A run without persisted sample
    # selection cannot prove it evaluated the same samples, so a scored
    # side-by-side comparison would imply statistical comparability that the
    # evidence does not support. Reject instead of silently proceeding.
    missing_selection = [r.id for r in runs if not sample_sets[r.id]]
    if missing_selection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Runs are not comparable: missing sample-selection metadata "
                f"for run(s) {missing_selection}; evaluated sample sets cannot be verified"
            ),
        )
    all_have_selection = all(sample_sets.values())
    if all_have_selection and len({frozenset(v) for v in sample_sets.values()}) > 1:
        incompatibilities.append("different sample IDs")

    if incompatibilities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Runs are not comparable: " + "; ".join(incompatibilities),
        )

    # Metrics comparison: metric_name -> {run_id: float}
    metrics_map: dict[str, dict[str, float]] = {}
    for r in runs:
        for m in r.metrics:
            if m.metric_name not in metrics_map:
                metrics_map[m.metric_name] = {}
            metrics_map[m.metric_name][r.id] = m.metric_value

    diffs = {
        "models": list({r.model_id for r in runs}),
        "datasets": list({r.dataset_id for r in runs}),
        "protocols": list({r.protocol_id for r in runs}),
        "splits": list({r.split for r in runs}),
        "sample_counts": {r.id: r.sample_count for r in runs},
        "sample_id_sets": sample_sets,
        "sample_selection_available_for_all_runs": all_have_selection,
    }

    return ComparisonResponse(
        runs=[BenchmarkRunResponse.model_validate(r) for r in runs],
        metrics_comparison=metrics_map,
        diffs=diffs,
    )
