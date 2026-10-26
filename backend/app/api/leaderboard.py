from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import (
    BenchmarkMetric,
    BenchmarkRun,
    DatasetDefinition,
    ModelDefinition,
    RunStatusEnum,
)
from app.schemas.leaderboard import LeaderboardItem, LeaderboardResponse
from app.services.recommendation_engine import DATASET_PRIMARY_METRIC, PRIMARY_METRIC_MAP

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

def _run_metric(db: Session, run_id: str, names: list[str]) -> float | None:
    stmt = select(BenchmarkMetric).where(
        BenchmarkMetric.run_id == run_id,
        BenchmarkMetric.metric_name.in_(names),
    )
    metrics = {m.metric_name: m.metric_value for m in db.scalars(stmt).all()}
    for n in names:
        v = metrics.get(n)
        if v is not None:
            return float(v)
    return None

@router.get("", response_model=LeaderboardResponse)
def get_leaderboard(
    domain: str | None = Query(None),
    task_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    stmt = (
        select(BenchmarkRun, DatasetDefinition, ModelDefinition)
        .join(DatasetDefinition, BenchmarkRun.dataset_id == DatasetDefinition.id)
        .join(ModelDefinition, BenchmarkRun.model_id == ModelDefinition.id)
        .where(
            BenchmarkRun.status == RunStatusEnum.COMPLETED,
            BenchmarkRun.is_private.is_(False),
        )
    )

    if domain:
        stmt = stmt.where(DatasetDefinition.domain == domain)
    if task_type:
        stmt = stmt.where(DatasetDefinition.task_type == task_type)

    results = db.execute(stmt).all()

    # D2/D3: best-run selection is cohort-scoped. A "cohort" is
    # (model, dataset, protocol, split, evaluated sample IDs). Only runs inside
    # the same cohort compete for the best score, so a 10-sample 100% run can
    # no longer beat a 200-sample 85% run: they are different cohorts and each
    # is listed separately.
    best_by_cohort: dict[tuple, LeaderboardItem] = {}

    for run, dataset, model in results:
        primary_key = DATASET_PRIMARY_METRIC.get(
            dataset.id,
            PRIMARY_METRIC_MAP.get(dataset.task_type, "accuracy"),
        )

        if dataset.id == "faitheval":
            metric_names = [primary_key, "unanswerable_context_accuracy_strict"]
        else:
            metric_names = [primary_key]
        primary_value = _run_metric(db, run.id, metric_names)
        if primary_value is None:
            # D2: missing primary metric — never invent a 0.0 score.
            continue

        latency = _run_metric(
            db,
            run.id,
            ["latency_ms_mean", "latency_ms_median", "avg_latency_ms", "latency_ms", "latency_ms_p50"],
        )

        selection = run.sample_selection or {}
        selected_ids_raw = selection.get("selected_sample_ids")
        if not selected_ids_raw:
            # D2: runs without persisted sample-selection metadata cannot prove
            # cohort membership. Exclude from ranking rather than collapsing all
            # unknown cohorts into one shared empty cohort.
            continue
        selected_ids = tuple(sorted(selected_ids_raw))

        item = LeaderboardItem(
            model_id=model.id,
            model_name=model.name,
            domain=dataset.domain,
            task_type=dataset.task_type,
            dataset_id=dataset.id,
            primary_metric_name=primary_key,
            primary_metric_value=round(primary_value, 4),
            avg_latency_ms=round(latency, 2) if latency is not None else None,
            vram_weight_gb=model.vram_weight_gb,
            run_id=run.id,
            sample_count=run.sample_count,
            completed_at=run.completed_at,
        )

        # Cohort key: same model+dataset+protocol+split+same evaluated samples.
        # D3: dataset is part of the key, so All-Domains never merges
        # SciQ accuracy with WDC micro-F1 into one raw-value ranking; sections
        # are emitted per dataset instead.
        cohort = (model.id, dataset.id, run.protocol_id, run.split, selected_ids)
        existing = best_by_cohort.get(cohort)
        if not existing or item.primary_metric_value > existing.primary_metric_value:
            best_by_cohort[cohort] = item

    items = list(best_by_cohort.values())
    # D3: sort within comparable groups (same dataset+metric), datasets in a
    # stable order; a single global raw-value ranking across different metrics
    # would be misleading.
    items.sort(
        key=lambda x: (
            x.primary_metric_name != "accuracy" and x.primary_metric_name,
            -x.primary_metric_value,
        )
    )
    # Stable secondary: group by dataset first for readable sectioning.
    dataset_of = {}
    for run, dataset, _model in results:
        dataset_of[run.id] = dataset.id
    items.sort(key=lambda x: (dataset_of.get(x.run_id, ""), x.primary_metric_name, -x.primary_metric_value))

    return LeaderboardResponse(
        domain=domain,
        task_type=task_type,
        items=items,
        total=len(items),
    )
