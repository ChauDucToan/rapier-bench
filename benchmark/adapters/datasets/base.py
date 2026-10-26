"""Shared dataset adapter helpers."""

from typing import Any

from benchmark.core.sampling import select_samples
from benchmark.core.types import DatasetAdapter, NormalizedSample


class BaseDatasetAdapter(DatasetAdapter):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def _finalize(
        self,
        eligible_samples: list[NormalizedSample],
        split: str,
        limit: int | None,
        seed: int,
    ) -> list[NormalizedSample]:
        selected, _ = select_samples(
            eligible_samples, self.config.get("id", "ds"), split, seed, limit
        )
        return selected
