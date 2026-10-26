"""WDC-PAVE dataset adapter."""

import json
from typing import Any
from urllib.request import urlopen

from benchmark.adapters.datasets.base import BaseDatasetAdapter
from benchmark.core.types import NormalizedSample, TaskType


def _normalize_wdc_row(row: dict[str, Any], dataset_id: str = "wdc_pave") -> NormalizedSample:
    target_scores = row["target_scores"]
    gold_json = {}
    for attribute, values in target_scores.items():
        value_keys = [value for value in values if value != "n/a"]
        if not value_keys:
            gold_json[attribute] = None
        elif len(value_keys) == 1:
            gold_json[attribute] = value_keys[0]
        else:
            gold_json[attribute] = value_keys
    text = f"{row['input_title']} {row['input_description']}".strip()
    return NormalizedSample(
        sample_id=f"wdc_pave:test:{row['id']}",
        dataset_id=dataset_id,
        dataset_revision="main",
        domain="ecommerce",
        task_type=TaskType.ATTRIBUTE_VALUE_EXTRACTION,
        input_payload={
            "category": row["category"],
            "target_attributes": ", ".join(sorted(target_scores)),
            "text": text,
        },
        references={"gold_json": gold_json, "target_scores": target_scores},
    )


class WdcPaveDatasetAdapter(BaseDatasetAdapter):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._rows: list[dict[str, Any]] | None = None

    def list_splits(self) -> list[str]:
        return ["test"]

    def _load_rows(self) -> list[dict[str, Any]]:
        if self._rows is None:
            with urlopen(self.config["raw_url"]) as response:
                self._rows = [json.loads(line) for line in response if line.strip()]
        return self._rows

    def load_samples(
        self, split: str, limit: int | None = None, seed: int = 42
    ) -> list[NormalizedSample]:
        if split != "test":
            raise ValueError(f"Unsupported WDC-PAVE split: {split}")
        samples = [_normalize_wdc_row(row, self.config.get("id", "wdc_pave")) for row in self._load_rows()]
        return self._finalize(samples, split, limit, seed)
