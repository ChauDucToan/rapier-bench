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

    # Find best run per (model_id, dataset_id)
    best_by_model: dict[str, LeaderboardItem] = {}

    for run, dataset, model in results:
        primary_key = DATASET_PRIMARY_METRIC.get(
            dataset.id,
            PRIMARY_METRIC_MAP.get(dataset.task_type, "accuracy"),
        )

        metric_stmt = select(BenchmarkMetric).where(
            BenchmarkMetric.run_id == run.id,
            BenchmarkMetric.metric_name == primary_key,
        )
        metric_obj = db.scalar(metric_stmt)

        if not metric_obj and dataset.id == "faitheval":
            metric_stmt = select(BenchmarkMetric).where(
                BenchmarkMetric.run_id == run.id,
                BenchmarkMetric.metric_name.in_(
                    ["unanswerable_context_accuracy", "unanswerable_acc_strict"]
                ),
            )
            metric_obj = db.scalar(metric_stmt)

        primary_value = float(metric_obj.metric_value) if metric_obj else 0.0

        # Latency (preferred: latency_ms_mean, fall back to median / legacy keys)
        lat_stmt = select(BenchmarkMetric).where(
            BenchmarkMetric.run_id == run.id,
            BenchmarkMetric.metric_name.in_([
                "latency_ms_mean",
                "latency_ms_median",
                "avg_latency_ms",
                "latency_ms",
                "latency_ms_p50",
            ]),
        )
        lat_metrics = {m.metric_name: m.metric_value for m in db.scalars(lat_stmt).all()}
        latency = (
            lat_metrics.get("latency_ms_mean")
            or lat_metrics.get("latency_ms_median")
            or lat_metrics.get("avg_latency_ms")
            or lat_metrics.get("latency_ms")
            or lat_metrics.get("latency_ms_p50")
        )

        item = LeaderboardItem(
            model_id=model.id,
            model_name=model.name,
            domain=dataset.domain,
            task_type=dataset.task_type,
            primary_metric_name=primary_key,
            primary_metric_value=round(primary_value, 4),
            avg_latency_ms=round(latency, 2) if latency is not None else None,
            vram_weight_gb=model.vram_weight_gb,
            run_id=run.id,
            sample_count=run.sample_count,
            completed_at=run.completed_at,
        )

        # Retain higher score per model
        existing = best_by_model.get(model.id)
        if not existing or item.primary_metric_value > existing.primary_metric_value:
            best_by_model[model.id] = item

    items = list(best_by_model.values())
    items.sort(key=lambda x: -x.primary_metric_value)

    return LeaderboardResponse(
        domain=domain,
        task_type=task_type,
        items=items,
        total=len(items),
    )
