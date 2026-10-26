from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    BenchmarkMetric,
    BenchmarkRun,
    DatasetDefinition,
    ModelDefinition,
    RunStatusEnum,
)
from app.schemas.recommendation import (
    RecommendationConstraints,
    RecommendationModelBreakdown,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationWeights,
)

PRIMARY_METRIC_MAP = {
    "multiple_choice": "accuracy",
    "attribute_value_extraction": "micro_f1",
    "binary_classification": "balanced_accuracy",
    "instruction_following": "prompt_level_strict_acc",
    "contextual_faithfulness": "balanced_score",
}

DATASET_PRIMARY_METRIC = {
    "sciq": "accuracy",
    "wdc_pave": "micro_f1",
    "legalbench_contract_nli": "balanced_accuracy",
    "ifeval": "prompt_level_strict_acc",
    "faitheval": "balanced_score",
}


def validate_and_normalize_weights(
    weights: RecommendationWeights | None,
) -> tuple[float, float, float]:
    if weights is None:
        return 0.5, 0.3, 0.2

    wq = float(weights.quality)
    wl = float(weights.latency)
    wv = float(weights.vram)

    if wq < 0.0 or wl < 0.0 or wv < 0.0:
        raise ValueError("Weights must be non-negative")

    total = wq + wl + wv
    if total <= 0.0:
        raise ValueError("Sum of weights must be greater than zero")

    return wq / total, wl / total, wv / total


class RecommendationEngine:
    @staticmethod
    def recommend(
        db: Session,
        req: RecommendationRequest,
    ) -> RecommendationResponse:
        w_quality, w_latency, w_vram = validate_and_normalize_weights(req.weights)
        constraints = req.constraints or RecommendationConstraints()

        # Find completed runs in requested domain
        stmt = (
            select(BenchmarkRun, DatasetDefinition, ModelDefinition)
            .join(DatasetDefinition, BenchmarkRun.dataset_id == DatasetDefinition.id)
            .join(ModelDefinition, BenchmarkRun.model_id == ModelDefinition.id)
            .where(
                BenchmarkRun.status == RunStatusEnum.COMPLETED,
                BenchmarkRun.is_private.is_(False),
                DatasetDefinition.domain == req.domain,
            )
        )
        if req.task_type:
            stmt = stmt.where(DatasetDefinition.task_type == req.task_type)

        results = db.execute(stmt).all()

        if not results:
            return RecommendationResponse(
                status="insufficient_sample",
                domain=req.domain,
                task_type=req.task_type,
                recommendations=[],
                eligible_count=0,
                limitations=["No completed runs found for the requested domain"],
                explanation="Zero models eligible: no historical benchmark runs exist for this domain.",
            )

        # E2: dominant protocol is selected PER DATASET (a domain may contain
        # several datasets, and protocol ids are dataset-scoped). Deterministic
        # tie-break by protocol id. One model/user cannot swing the selection
        # across unrelated datasets.
        protocol_counts: dict[str, dict[str, int]] = {}
        for run, dataset, _model in results:
            per_ds = protocol_counts.setdefault(dataset.id, {})
            per_ds[run.protocol_id] = per_ds.get(run.protocol_id, 0) + 1

        dominant_protocol_by_ds = {
            ds_id: max(sorted(per_ds.keys()), key=lambda p: per_ds[p])
            for ds_id, per_ds in protocol_counts.items()
        }

        # Filter to runs with comparable protocol
        comparable_runs = [
            (run, dataset, model)
            for (run, dataset, model) in results
            if run.protocol_id == dominant_protocol_by_ds.get(dataset.id)
        ]
        dominant_protocol = (
            ", ".join(sorted({p for p in dominant_protocol_by_ds.values()}))
            if dominant_protocol_by_ds
            else "n/a"
        )

        # Group by model, select best run per model based on primary metric.
        # E1: best-run selection is cohort-scoped — only runs evaluating the
        # SAME selected sample IDs compete for a model's best score. A 10-sample
        # 100% run and a 200-sample 85% run are different cohorts and cannot
        # crown each other. The largest verified cohort wins the model slot.
        # Missing metrics are excluded, never invented.
        model_candidates: dict[str, dict] = {}
        cohort_sizes: dict[str, int] = {}

        for run, dataset, model in comparable_runs:
            # Determine primary metric key
            primary_key = DATASET_PRIMARY_METRIC.get(
                dataset.id,
                PRIMARY_METRIC_MAP.get(dataset.task_type, "accuracy"),
            )

            # Look up primary metric
            metric_stmt = select(BenchmarkMetric).where(
                BenchmarkMetric.run_id == run.id,
                BenchmarkMetric.metric_name == primary_key,
            )
            metric_obj = db.scalar(metric_stmt)

            # E5: FaithEval balanced_score is only reported when controls were
            # actually evaluated. Falling back to the unanswerable strict metric
            # would silently rank models on a different quantity. Instead, skip
            # the run unless a genuine balanced_score exists.
            if not metric_obj and dataset.id == "faitheval":
                continue

            if not metric_obj:
                # Exclude run if primary metric missing
                continue

            quality = float(metric_obj.metric_value)

            # Determine latency
            lat_stmt = select(BenchmarkMetric).where(
                BenchmarkMetric.run_id == run.id,
                BenchmarkMetric.metric_name.in_([
                    "latency_ms_mean",
                    "avg_latency_ms",
                    "latency_ms",
                    "latency_ms_median",
                ]),
            )
            lat_obj = db.scalar(lat_stmt)
            if lat_obj:
                latency = float(lat_obj.metric_value)
            elif run.hardware_metadata and ("latency_ms_mean" in run.hardware_metadata or "avg_latency_ms" in run.hardware_metadata):
                latency = float(run.hardware_metadata.get("latency_ms_mean") or run.hardware_metadata.get("avg_latency_ms"))
            else:
                # Exclude if latency cannot be measured
                continue

            vram = float(model.vram_weight_gb)

            # Hard constraints filtering
            if constraints.max_vram_gb is not None and vram > constraints.max_vram_gb:
                continue
            if (
                constraints.max_latency_ms is not None
                and latency > constraints.max_latency_ms
            ):
                continue
            if constraints.min_quality is not None and quality < constraints.min_quality:
                continue

            # If model already seen, keep run from the largest verified sample
            # cohort; within the same cohort keep higher quality.
            # Runs without persisted sample-selection metadata are excluded —
            # their cohort cannot be verified (E1/D1).
            cohort_raw = (run.sample_selection or {}).get("selected_sample_ids")
            if not cohort_raw:
                continue
            cohort_key = tuple(sorted(cohort_raw))
            cohort_size = len(cohort_key)
            existing = model_candidates.get(model.id)
            if existing is None or cohort_size > cohort_sizes[model.id] or cohort_size == cohort_sizes[model.id] and quality > existing["quality"]:
                better = True
            else:
                better = False
            if better:
                cohort_sizes[model.id] = cohort_size
                model_candidates[model.id] = {
                    "model_id": model.id,
                    "model_name": model.name,
                    "quality": quality,
                    "latency": latency,
                    "vram": vram,
                    "run_id": run.id,
                    "sample_count": len(cohort_key),
                }

        eligible_models = list(model_candidates.values())

        if len(eligible_models) == 0:
            return RecommendationResponse(
                status="insufficient_sample",
                domain=req.domain,
                task_type=req.task_type,
                recommendations=[],
                eligible_count=0,
                limitations=["No models satisfied the hard constraints"],
                explanation="Zero models eligible: all candidate models were filtered out by latency, VRAM, or minimum quality constraints.",
            )

        # E6: the 3-model minimum is an architectural guard (ARCHITECTURE §10.2),
        # not a hard product requirement. With 1-2 eligible models we still
        # rank them, clearly labeling the small comparison set.
        if len(eligible_models) < 3:
            small_set_note = (
                f"Only {len(eligible_models)} comparable model(s) available; "
                "ranking is informational with a small comparison set"
            )
            if len(eligible_models) == 0:
                return RecommendationResponse(
                    status="insufficient_sample",
                    domain=req.domain,
                    task_type=req.task_type,
                    recommendations=[],
                    eligible_count=0,
                    limitations=["No models satisfied the hard constraints"],
                    explanation="Zero models eligible: all candidate models were filtered out by latency, VRAM, or minimum quality constraints.",
                )

        # Min-Max Normalization per ARCHITECTURE §10.2
        q_vals = [m["quality"] for m in eligible_models]
        l_vals = [m["latency"] for m in eligible_models]
        v_vals = [m["vram"] for m in eligible_models]

        min_q, max_q = min(q_vals), max(q_vals)
        min_l, max_l = min(l_vals), max(l_vals)
        min_v, max_v = min(v_vals), max(v_vals)

        ranked: list[RecommendationModelBreakdown] = []
        for m in eligible_models:
            q_norm = 1.0 if max_q == min_q else (m["quality"] - min_q) / (max_q - min_q)
            # Lower latency is better
            l_norm = 1.0 if max_l == min_l else (max_l - m["latency"]) / (max_l - min_l)
            # Lower VRAM is better
            v_norm = 1.0 if max_v == min_v else (max_v - m["vram"]) / (max_v - min_v)

            composite = (w_quality * q_norm) + (w_latency * l_norm) + (w_vram * v_norm)

            ranked.append(
                RecommendationModelBreakdown(
                    model_id=m["model_id"],
                    model_name=m["model_name"],
                    composite_score=round(composite, 4),
                    quality_score=round(m["quality"], 4),
                    latency_ms=round(m["latency"], 2),
                    vram_gb=round(m["vram"], 2),
                    normalized_quality=round(q_norm, 4),
                    normalized_latency=round(l_norm, 4),
                    normalized_vram=round(v_norm, 4),
                    run_id=m["run_id"],
                )
            )

        # Deterministic Tie-Breaking per ARCHITECTURE §10.2:
        # CompositeScore DESC, PrimaryMetric DESC, Latency ASC, ModelID ASC
        ranked.sort(
            key=lambda x: (
                -x.composite_score,
                -x.quality_score,
                x.latency_ms,
                x.model_id,
            )
        )

        # E3: VRAM values are model-weight estimates from the catalog
        # (configs/models.yaml), NOT measured peak inference VRAM.
        limitations = [
            f"Evaluated on dominant protocol(s) '{dominant_protocol}' per dataset",
            "Scores normalized min-max across eligible candidates",
            "VRAM figures are estimated model-weight footprints from the model catalog, not measured peak inference memory",
        ]
        if len(eligible_models) < 3:
            limitations.append(small_set_note)

        return RecommendationResponse(
            status="success",
            domain=req.domain,
            task_type=req.task_type,
            recommendations=ranked,
            eligible_count=len(eligible_models),
            limitations=limitations,
            explanation=(
                f"Ranked {len(ranked)} models for domain '{req.domain}' using normalized weights: "
                f"quality={w_quality:.2f}, latency={w_latency:.2f}, vram={w_vram:.2f}."
            ),
        )
