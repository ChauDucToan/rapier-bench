"""Base class for benchmark evaluators."""

from benchmark.core.types import Evaluator, NormalizedSample, PredictionRecord


class BaseEvaluator(Evaluator):
    """Abstract base class for suite-specific metric evaluators."""

    def __init__(self, key: str) -> None:
        self.evaluator_key = key

    def _pair_predictions(
        self,
        predictions: list[PredictionRecord],
        samples: list[NormalizedSample],
    ) -> list[tuple[PredictionRecord, NormalizedSample]]:
        """Pair prediction records with their corresponding normalized samples by sample_id."""
        sample_map = {s.sample_id: s for s in samples}
        pairs: list[tuple[PredictionRecord, NormalizedSample]] = []
        for p in predictions:
            sample = sample_map.get(p.sample_id)
            if sample is not None:
                pairs.append((p, sample))
        return pairs
