"""FaithEval adapter. Answerable-control SQuAD loading remains a documented future addition."""

from typing import Any

from datasets import load_dataset

from benchmark.adapters.datasets.base import BaseDatasetAdapter
from benchmark.core.types import NormalizedSample, TaskType


def _normalize_row(row: dict[str, Any], config: dict[str, Any]) -> NormalizedSample:
    return NormalizedSample(
        sample_id=f"faitheval:test:{row['qid']}",
        dataset_id=config["id"],
        dataset_revision=config.get("revision", "main"),
        domain="contextual_faithfulness",
        task_type=TaskType.CONTEXTUAL_FAITHFULNESS,
        input_payload={"context": row["context"], "question": row["question"]},
        references={"type": "unanswerable", "answers": row["answers"]},
        metadata={
            "subset": row.get("subset", ""),
            "justification": row.get("justification", ""),
        },
    )


class FaithEvalDatasetAdapter(BaseDatasetAdapter):
    def list_splits(self) -> list[str]:
        return ["test"]

    def load_samples(self, split: str, limit: int | None = None, seed: int = 42):
        if split != "test":
            raise ValueError(f"Unsupported FaithEval split: {split}")
        rows = load_dataset(
            "Salesforce/FaithEval-unanswerable-v1.0",
            "default",
            split="test",
            revision=self.config.get("revision"),
        )
        samples = [_normalize_row(row, self.config) for row in rows]
        return self._finalize(samples, split, limit, seed)
