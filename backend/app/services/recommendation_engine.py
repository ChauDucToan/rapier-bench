from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    BenchmarkMetric,
    BenchmarkRun,
    DatasetDefinition,
    ModelDefinition,
    RunStatusEnum,
    User,
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
    # F2: the default FaithEval protocol evaluates unanswerable contexts
    # only; its legitimately measured primary metric is strict abstention
    # accuracy. balanced_score requires the answerable-control protocol
    # addition and is reported as a metric when present, never substituted.
    "contextual_faithfulness": "unanswerable_context_accuracy_strict",
}

DATASET_PRIMARY_METRIC = {
    "sciq": "accuracy",
    "wdc_pave": "micro_f1",
    "legalbench_contract_nli": "balanced_accuracy",
    "ifeval": "prompt_level_strict_acc",
    "faitheval": "unanswerable_context_accuracy_strict",
}

@dataclass
class _RunCandidate:
    run_id: str
    model_id: str
    model_name: str
    quality: float
    latency_ms: float | None
    vram_gb: float
    dataset_id: str
    protocol_id: str
    split: str
    seed: int
    selected_ids: tuple[str, ...]
    gpu_name: str | None
    hardware_key: str
    created_at: object | None = None
    dataset_revision: str | None = None
    protocol_version: str | None = None


def _finite(value: float, name: str) -> float:
    """FIX 8: reject non-finite / invalid measured values instead of letting
    them produce meaningless normalized scores."""
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(f"{name} must be a finite number, got {value}")
    return v


def validate_and_normalize_weights(
    weights: RecommendationWeights | None,
) -> tuple[float, float, float]:
    if weights is None:
        return 0.5, 0.3, 0.2

    wq = _finite(weights.quality, "quality weight")
    wl = _finite(weights.latency, "latency weight")
    wv = _finite(weights.vram, "vram weight")

    if wq < 0.0 or wl < 0.0 or wv < 0.0:
        raise ValueError("Weights must be non-negative")

    total = wq + wl + wv
    if total <= 0.0:
        raise ValueError("Sum of weights must be greater than zero")

    return wq / total, wl / total, wv / total


def _hardware_key(run: BenchmarkRun) -> str:
    """FIX 4: hardware comparability key. Latency is only comparable between
    runs whose recorded hardware environment matches on the dimensions that
    materially affect generation speed."""
    hw = run.hardware_metadata or {}
    gpu = hw.get("gpu_name")
    if not hw.get("gpu_available") or not gpu:
        return "unknown"
    # GPU identity + CUDA/torch stack define the comparison class.
    return f"{gpu}|{hw.get('cuda_version') or '?'}|{hw.get('torch_version') or '?'}"


class RecommendationEngine:
    @staticmethod
    def recommend(
        db: Session,
        req: RecommendationRequest,
        current_user: User | None = None,
    ) -> RecommendationResponse:
        w_quality, w_latency, w_vram = validate_and_normalize_weights(req.weights)
        constraints = req.constraints or RecommendationConstraints()

        # FIX 3: visibility. Authenticated users contribute their OWN private
        # completed runs in addition to all public runs; unauthenticated
        # requests see public runs only. Another user's private runs are never
        # visible, and absence is reported generically (no private run IDs).
        stmt = (
            select(BenchmarkRun, DatasetDefinition, ModelDefinition)
            .join(DatasetDefinition, BenchmarkRun.dataset_id == DatasetDefinition.id)
            .join(ModelDefinition, BenchmarkRun.model_id == ModelDefinition.id)
            .where(
                BenchmarkRun.status == RunStatusEnum.COMPLETED,
                DatasetDefinition.domain == req.domain,
            )
        )
        if current_user is not None:
            from sqlalchemy import or_

            stmt = stmt.where(
                or_(
                    BenchmarkRun.is_private.is_(False),
                    BenchmarkRun.user_id == current_user.id,
                )
            )
        else:
            stmt = stmt.where(BenchmarkRun.is_private.is_(False))

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

        # ------------------------------------------------------------------
        # FIX 2: choose ONE common cohort first, then select model results
        # within that cohort. Cohort identity = (dataset, protocol, split,
        # selected sample IDs). Model checkpoints are candidates within the
        # cohort, not part of its identity. Runs without cohort metadata
        # (missing sample selection) cannot join any cohort.
        # ------------------------------------------------------------------
        candidates: list[_RunCandidate] = []
        latency_weight_active = w_latency > 0.0

        for run, dataset, model in results:
            primary_key = DATASET_PRIMARY_METRIC.get(
                dataset.id,
                PRIMARY_METRIC_MAP.get(dataset.task_type, "accuracy"),
            )

            metric_obj = db.scalar(
                select(BenchmarkMetric).where(
                    BenchmarkMetric.run_id == run.id,
                    BenchmarkMetric.metric_name == primary_key,
                )
            )
            # FIX 1 alignment: no metric substitution. A run lacking the
            # dataset's primary metric (e.g. FaithEval balanced_score without
            # answerable controls) is excluded, never scored under a different
            # metric name.
            if not metric_obj:
                continue

            # C2: corrupted stored measurements exclude THAT CANDIDATE; the
            # request must still succeed for the remaining valid models.
            q_raw = metric_obj.metric_value
            if not isinstance(q_raw, (int, float)) or not math.isfinite(float(q_raw)) or float(q_raw) < 0.0:
                continue
            quality = float(q_raw)

            lat_obj = db.scalar(
                select(BenchmarkMetric).where(
                    BenchmarkMetric.run_id == run.id,
                    BenchmarkMetric.metric_name.in_([
                        "latency_ms_mean",
                        "latency_ms_median",
                        "avg_latency_ms",
                        "latency_ms",
                    ]),
                )
            )
            latency_ms: float | None = None
            if lat_obj is not None:
                lat_raw = lat_obj.metric_value
                if not isinstance(lat_raw, (int, float)) or not math.isfinite(float(lat_raw)) or float(lat_raw) < 0.0:
                    continue  # corrupted latency evidence: exclude candidate
                latency_ms = float(lat_raw)

            vram_raw = model.vram_weight_gb
            if not isinstance(vram_raw, (int, float)) or not math.isfinite(float(vram_raw)):
                continue
            vram = float(vram_raw)

            selection = run.sample_selection or {}
            selected_ids_raw = selection.get("selected_sample_ids")
            if not selected_ids_raw:
                continue
            selected_ids = tuple(sorted(str(x) for x in selected_ids_raw))
            # D1: capture the evaluation-identity metadata persisted at
            # execution time (from run_config.json via the worker). Read from
            # the run row — NOT from the mutable live registry — so cohort
            # identity reflects what actually ran.
            ds_revision = (selection.get("dataset_config") or {}).get("revision")
            proto_version = (selection.get("protocol_config") or {}).get("version")

            candidates.append(
                _RunCandidate(
                    run_id=run.id,
                    model_id=model.id,
                    model_name=model.name,
                    quality=quality,
                    latency_ms=latency_ms,
                    vram_gb=vram,
                    dataset_id=dataset.id,
                    protocol_id=run.protocol_id,
                    split=run.split,
                    seed=run.seed,
                    selected_ids=selected_ids,
                    gpu_name=(run.hardware_metadata or {}).get("gpu_name"),
                    hardware_key=_hardware_key(run),
                    created_at=run.created_at,
                    dataset_revision=ds_revision,
                    protocol_version=proto_version,
                )
            )

        # Partition into cohorts (D1): dataset revision and protocol version
        # are part of the identity — the same sample IDs under a different
        # dataset revision or protocol version are NOT the same evaluation.
        cohorts: dict[tuple, list[_RunCandidate]] = {}
        for c in candidates:
            cohorts.setdefault(
                (
                    c.dataset_id,
                    c.protocol_id,
                    c.split,
                    c.selected_ids,
                    c.dataset_revision,
                    c.protocol_version,
                ),
                [],
            ).append(c)

        # Deterministic cohort choice: most distinct models, then largest
        # sample set, then lexicographic cohort key. Never select a cohort by
        # the quality of its best run (no cherry-picking).
        def _cohort_sort_key(key: tuple) -> tuple:
            # None-safe ordering for cohort keys (legacy rows carry None
            # revision/version fields in the key).
            return tuple(str(k) for k in key)

        def _cohort_score(key: tuple) -> tuple:
            runs = cohorts[key]
            models = {r.model_id for r in runs}
            return (len(models), len(key[3]), tuple(str(k) for k in reversed(key)))

        if not cohorts:
            return RecommendationResponse(
                status="insufficient_sample",
                domain=req.domain,
                task_type=req.task_type,
                recommendations=[],
                eligible_count=0,
                limitations=[
                    "No completed runs carry the primary metric and sample-selection "
                    "metadata required for comparable ranking"
                ],
                explanation="Zero models eligible: runs lack comparable evaluation evidence.",
            )

        best_cohort_key = max(sorted(cohorts.keys(), key=_cohort_sort_key), key=_cohort_score)
        cohort_runs = cohorts[best_cohort_key]
        dataset_id, protocol_id, split, selected_ids, _ds_rev, _proto_ver = best_cohort_key

        # A cohort with a single model has nothing to compare against; a
        # ranking needs at least two distinct models on the shared cohort.
        if len({c.model_id for c in cohort_runs}) < 2:
            return RecommendationResponse(
                status="insufficient_sample",
                domain=req.domain,
                task_type=req.task_type,
                recommendations=[],
                eligible_count=0,
                limitations=[
                    "No evaluation cohort contains two or more distinct models with "
                    "matching dataset, protocol, split, and evaluated sample IDs"
                ],
                explanation=(
                    "No common evaluation cohort with multiple models exists for "
                    "this domain; models were evaluated on different sample sets, "
                    "protocols, or splits and cannot be ranked together."
                ),
            )

        # Hardware comparability (FIX 4 + C1): latency is only comparable
        # within one VERIFIED hardware key. 'unknown' (missing GPU metadata)
        # is not evidence of a shared environment: latency from unverified
        # runs is never treated as comparable speed evidence. When latency
        # weight is zero the whole cohort is usable regardless of hardware.
        hw_groups: dict[str, list[_RunCandidate]] = {}
        for c in cohort_runs:
            hw_groups.setdefault(c.hardware_key, []).append(c)

        unknown_hw = [c for c in cohort_runs if c.hardware_key == "unknown"]
        known_hw_keys = [k for k in hw_groups if k != "unknown"]

        if latency_weight_active and known_hw_keys:
            # Rank latency only inside verified hardware groups.
            ranked_hw = sorted(
                ((k, hw_groups[k]) for k in known_hw_keys),
                key=lambda kv: (-len({r.model_id for r in kv[1]}), kv[0]),
            )
            chosen_hw_key, cohort_runs = ranked_hw[0]
        else:
            chosen_hw_key = cohort_runs[0].hardware_key if cohort_runs else "unknown"

        # One run per model within the cohort (C3): deterministic LATEST run
        # policy. Selecting the highest-scoring repeated run would create
        # optimistic bias (max-of-N trials); selecting the latest is
        # reproducible, explainable, and independent of the outcomes. Ties on
        # created_at fall back to run_id for a total order.
        by_model: dict[str, _RunCandidate] = {}
        for c in cohort_runs:
            constraints_ok = True
            if constraints.max_vram_gb is not None and c.vram_gb > constraints.max_vram_gb:
                constraints_ok = False
            if constraints.max_latency_ms is not None and (
                c.latency_ms is None or c.latency_ms > constraints.max_latency_ms
            ):
                constraints_ok = False
            if constraints.min_quality is not None and c.quality < constraints.min_quality:
                constraints_ok = False
            if not constraints_ok:
                continue
            existing = by_model.get(c.model_id)
            # Latest created_at wins; run_id breaks exact ties deterministically.
            # None-safe ordering: rows without created_at sort before any
            # timestamp (defensive for corrupted/legacy rows).
            def _order(cand: _RunCandidate) -> tuple:
                return (cand.created_at is not None, cand.created_at or "", cand.run_id)

            if existing is None or _order(c) > _order(existing):
                by_model[c.model_id] = c

        eligible = list(by_model.values())

        if not eligible:
            return RecommendationResponse(
                status="insufficient_sample",
                domain=req.domain,
                task_type=req.task_type,
                recommendations=[],
                eligible_count=0,
                limitations=["No models satisfied the hard constraints"],
                explanation="Zero models eligible: all candidate models were filtered out by latency, VRAM, or minimum quality constraints.",
            )

        missing_latency = [c for c in eligible if c.latency_ms is None]

        # FIX 4 disclosure: if latency cannot be compared (missing measurements
        # or mixed hardware), do not silently redistribute the latency weight.
        # C1: latency is comparable only when every eligible candidate has a
        # measurement AND the ranking cohort is a VERIFIED hardware group.
        # 'unknown' hardware (missing GPU metadata) is not evidence of a shared
        # environment — latency from unverified runs is never speed evidence.
        latency_comparable = (
            latency_weight_active
            and all(c.latency_ms is not None for c in eligible)
            and chosen_hw_key != "unknown"
        )

        limitations: list[str] = [
            (
                f"Ranked on a single verified evaluation cohort: dataset={dataset_id}, "
                f"protocol={protocol_id}, split={split}, {len(selected_ids)} shared samples"
            ),
            "Scores normalized min-max across eligible candidates",
            "VRAM figures are estimated model-weight footprints from the model catalog, not measured peak inference memory",
        ]

        if latency_weight_active:
            if known_hw_keys and len(known_hw_keys) > 1:
                limitations.append(
                    "Latency compared only across runs sharing the same recorded hardware "
                    f"environment (GPU/CUDA/torch: {chosen_hw_key}); other hardware groups excluded"
                )
            if unknown_hw:
                limitations.append(
                    f"{len(unknown_hw)} run(s) lack verified hardware metadata; their latency "
                    "is not treated as comparable speed evidence"
                )
            if missing_latency:
                limitations.append(
                    f"{len(missing_latency)} model(s) lack latency measurements"
                )
        # C3: disclose the repeated-run selection policy.
        limitations.append(
            "When a model has multiple runs in the shared cohort, the LATEST run "
            "represents it (no best-of-N cherry-picking)"
        )
        if len(eligible) < 3:
            if len(eligible) <= 1:
                limitations.append(
                    f"Only {len(eligible)} model(s) satisfied the constraints within the "
                    "shared cohort; a ranking needs at least 2 comparable models — this "
                    "result is shown for completeness, not as a recommendation"
                )
            else:
                limitations.append(
                    f"Only {len(eligible)} comparable model(s) available in the shared cohort; "
                    "ranking is informational with a small comparison set"
                )

        # ------------------------------------------------------------------
        # Scoring. Quality always ranks. Latency participates only when every
        # candidate in the cohort has a measured latency (FIX 4: never silently
        # treat missing latency as a value). VRAM is a static estimate.
        # ------------------------------------------------------------------
        if latency_weight_active and not latency_comparable:
            # Latency weight cannot be honored: report it instead of silently
            # renormalizing or fabricating values.
            limitations.append(
                "Latency weight could not be applied: comparable latency measurements "
                "are unavailable for all candidates; ranking used quality and VRAM only"
            )
            effective_w_latency = 0.0
            effective_w_quality, _ignored_lat, effective_w_vram = _renormalize(
                w_quality, 0.0, w_vram
            )
        else:
            effective_w_quality, effective_w_latency, effective_w_vram = (
                w_quality, w_latency, w_vram
            )

        q_vals = [c.quality for c in eligible]
        l_vals = [c.latency_ms for c in eligible if c.latency_ms is not None]
        v_vals = [c.vram_gb for c in eligible]

        min_q, max_q = min(q_vals), max(q_vals)
        min_l, max_l = (min(l_vals), max(l_vals)) if l_vals else (0.0, 0.0)
        min_v, max_v = min(v_vals), max(v_vals)

        ranked: list[RecommendationModelBreakdown] = []
        for c in eligible:
            q_norm = 1.0 if max_q == min_q else (c.quality - min_q) / (max_q - min_q)
            v_norm = 1.0 if max_v == min_v else (max_v - c.vram_gb) / (max_v - min_v)
            if effective_w_latency > 0.0 and c.latency_ms is not None:
                l_norm = 1.0 if max_l == min_l else (max_l - c.latency_ms) / (max_l - min_l)
            else:
                l_norm = 0.0
            composite = (
                effective_w_quality * q_norm
                + effective_w_latency * l_norm
                + effective_w_vram * v_norm
            )
            ranked.append(
                RecommendationModelBreakdown(
                    model_id=c.model_id,
                    model_name=c.model_name,
                    composite_score=round(composite, 4),
                    quality_score=round(c.quality, 4),
                    latency_ms=round(c.latency_ms, 2) if c.latency_ms is not None else None,
                    vram_gb=round(c.vram_gb, 2),
                    normalized_quality=round(q_norm, 4),
                    normalized_latency=round(l_norm, 4) if c.latency_ms is not None else None,
                    normalized_vram=round(v_norm, 4),
                    run_id=c.run_id,
                )
            )

        ranked.sort(
            key=lambda x: (
                -x.composite_score,
                -x.quality_score,
                x.latency_ms if x.latency_ms is not None else float("inf"),
                x.model_id,
            )
        )

        return RecommendationResponse(
            status="success",
            domain=req.domain,
            task_type=req.task_type,
            recommendations=ranked,
            eligible_count=len(ranked),
            limitations=limitations,
            explanation=(
                f"Ranked {len(ranked)} models on one shared evaluation cohort "
                f"({len(selected_ids)} identical samples, protocol '{protocol_id}'). "
                + (
                    "Latency weight was omitted (unavailable measurements); ranking used quality and VRAM."
                    if latency_weight_active and not latency_comparable
                    else f"Effective weights: quality={effective_w_quality:.2f}, latency={effective_w_latency:.2f}, vram={effective_w_vram:.2f}."
                )
            ),
        )


def _renormalize(wq: float, wl: float, wv: float) -> tuple[float, float, float]:
    total = wq + wv
    if total <= 0.0:
        return 1.0, 0.0, 0.0
    return wq / total, 0.0, wv / total
