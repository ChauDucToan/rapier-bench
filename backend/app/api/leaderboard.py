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
from app.schemas.leaderboard import LeaderboardGroup, LeaderboardItem, LeaderboardResponse
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

    # D2/D3/FIX 7: results are grouped into comparable evaluation cohorts
    # (dataset, protocol, split, exact evaluated sample IDs). Each group is
    # ranked independently; a global rank across cohorts is never implied.
    # Runs without persisted sample-selection metadata cannot join a cohort.
    best_by_cohort_model: dict[tuple, LeaderboardItem] = {}
    cohort_order: list[tuple] = []
    dataset_of: dict[str, str] = {}
    sample_count_of: dict[tuple, int | None] = {}
    protocol_of: dict[str, str] = {}
    split_of: dict[str, str] = {}
    metric_of: dict[str, str] = {}

    for run, dataset, model in results:
        primary_key = DATASET_PRIMARY_METRIC.get(
            dataset.id,
            PRIMARY_METRIC_MAP.get(dataset.task_type, "accuracy"),
        )

        # FIX 1: a metric is only displayed under its actual name. No
        # substitution: a run lacking the dataset's primary metric is excluded
        # (e.g. FaithEval unanswerable-only runs without balanced_score).
        primary_value = _run_metric(db, run.id, [primary_key])
        if primary_value is None:
            continue

        selection = run.sample_selection or {}
        selected_ids_raw = selection.get("selected_sample_ids")
        if not selected_ids_raw:
            # Unverifiable cohort: cannot be ranked.
            continue
        selected_ids = tuple(sorted(str(x) for x in selected_ids_raw))

        latency = _run_metric(
            db,
            run.id,
            ["latency_ms_mean", "latency_ms_median", "avg_latency_ms", "latency_ms", "latency_ms_p50"],
        )

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

        # Cohort key excludes model: models compete WITHIN a cohort. D1:
        # dataset revision and protocol version (persisted at execution time
        # in sample_selection via run_config.json) are part of the identity.
        ds_revision = (selection.get("dataset_config") or {}).get("revision")
        proto_version = (selection.get("protocol_config") or {}).get("version")
        cohort = (dataset.id, run.protocol_id, run.split, selected_ids, ds_revision, proto_version)
        model_key = (cohort, model.id)
        existing = best_by_cohort_model.get(model_key)
        if not existing or item.primary_metric_value > existing.primary_metric_value:
            best_by_cohort_model[model_key] = item
        if cohort not in cohort_order:
            cohort_order.append(cohort)
            dataset_of[cohort] = dataset.id
            protocol_of[cohort] = run.protocol_id
            split_of[cohort] = run.split
            metric_of[cohort] = primary_key
            sample_count_of[cohort] = len(selected_ids)

    groups: list[LeaderboardGroup] = []
    flat_items: list[LeaderboardItem] = []
    cohort_ids: dict[tuple, str] = {}
    for cohort in cohort_order:
        import hashlib

        cohort_hash = hashlib.sha256("\n".join(cohort[3]).encode("utf-8")).hexdigest()[:12]
        cohort_ids[cohort] = cohort_hash
        items = sorted(
            (
                item
                for (c, _m), item in best_by_cohort_model.items()
                if c == cohort
            ),
            key=lambda x: -x.primary_metric_value,
        )
        groups.append(
            LeaderboardGroup(
                dataset_id=cohort[0],
                protocol_id=cohort[1],
                split=cohort[2],
                sample_count=sample_count_of[cohort],
                primary_metric_name=metric_of[cohort],
                cohort_id=cohort_ids[cohort],
                items=items,
            )
        )
        flat_items.extend(items)

    # Stable group ordering: dataset, protocol, split, then cohort size.
    groups.sort(
        key=lambda g: (
            g.dataset_id,
            g.protocol_id,
            g.split,
            -(g.sample_count or 0),
            len(g.items),
        )
    )

    return LeaderboardResponse(
        domain=domain,
        task_type=task_type,
        groups=groups,
        items=flat_items,
        total=len(flat_items),
    )
