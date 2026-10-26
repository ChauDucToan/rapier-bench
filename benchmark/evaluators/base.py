"""Base class for benchmark evaluators."""

from benchmark.core.types import Evaluator, NormalizedSample, PredictionRecord


class BaseEvaluator(Evaluator):
    """Abstract base class for suite-specific metric evaluators."""

    def __init__(self, key: str) -> None:
        self.evaluator_key = key

    def pair_correctness(
        self,
        predictions: list[PredictionRecord],
        samples: list[NormalizedSample],
    ) -> dict[str, bool | None]:
        """Per-sample correctness for the failure-analysis browser.

        Returns {sample_id: is_correct}. None means "correctness is not a
        meaningful single boolean for this sample" (default for tasks whose
        verdict is set-valued or instruction-level).
        """
        return {p.sample_id: None for p in predictions}

    def _pair_predictions(
        self,
        predictions: list[PredictionRecord],
        samples: list[NormalizedSample],
    ) -> list[tuple[PredictionRecord, NormalizedSample]]:
        """Pair prediction records with their corresponding normalized samples by sample_id.

        B7 denominator contract: every selected sample must have exactly one
        prediction, and every prediction must reference a selected sample.
        Mismatches fail closed instead of silently shrinking the denominator
        (missing predictions) or double-counting (duplicates).
        """
        sample_map = {s.sample_id: s for s in samples}

        seen: set[str] = set()
        pairs: list[tuple[PredictionRecord, NormalizedSample]] = []
        unknown: list[str] = []
        for p in predictions:
            if p.sample_id in seen:
                raise ValueError(
                    f"Duplicate predictions for sample_id '{p.sample_id}': "
                    "evaluator denominator would double-count"
                )
            seen.add(p.sample_id)
            sample = sample_map.get(p.sample_id)
            if sample is None:
                unknown.append(p.sample_id)
                continue
            pairs.append((p, sample))

        if unknown:
            raise ValueError(
                f"Predictions reference unknown sample_ids: {unknown[:5]}"
                f"{'...' if len(unknown) > 5 else ''}"
            )

        missing = [sid for sid in sample_map if sid not in seen]
        if missing:
            raise ValueError(
                f"{len(missing)} of {len(sample_map)} selected samples have "
                f"missing predictions (first: {missing[:5]}); refusing to score "
                "a smaller subset without disclosure"
            )

        return pairs
