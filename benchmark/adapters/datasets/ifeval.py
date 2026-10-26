"""IFEval dataset adapter."""

from typing import Any

from datasets import load_dataset

from benchmark.adapters.datasets.base import BaseDatasetAdapter
from benchmark.core.types import NormalizedSample, TaskType


def _normalize_row(row: dict[str, Any], config: dict[str, Any]) -> NormalizedSample:
    return NormalizedSample(
        sample_id=f"ifeval:train:{row['key']}",
        dataset_id=config["id"],
        dataset_revision=config.get("revision", "main"),
        domain="general",
        task_type=TaskType.INSTRUCTION_FOLLOWING,
        input_payload={"prompt": row["prompt"]},
        references={
            "instruction_id_list": row["instruction_id_list"],
            "kwargs": row["kwargs"],
        },
    )


class IFEvalDatasetAdapter(BaseDatasetAdapter):
    def list_splits(self) -> list[str]:
        return ["train"]

    def load_samples(self, split: str, limit: int | None = None, seed: int = 42):
        if split != "train":
            raise ValueError(f"Unsupported IFEval split: {split}")
        rows = load_dataset("google/IFEval", "default", split="train")
        samples = [_normalize_row(row, self.config) for row in rows]
        return self._finalize(samples, split, limit, seed)
