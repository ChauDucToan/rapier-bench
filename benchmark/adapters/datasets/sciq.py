"""SciQ dataset adapter."""

import hashlib
import random
from typing import Any

from datasets import load_dataset

from benchmark.adapters.datasets.base import BaseDatasetAdapter
from benchmark.core.types import NormalizedSample, TaskType


def _normalize_sciq_row(
    row: dict[str, Any], split: str, index: int, config: dict[str, Any]
) -> NormalizedSample:
    stable_id = f"sciq:{split}:{index}"
    correct_answer = row["correct_answer"]
    choices = [correct_answer, row["distractor1"], row["distractor2"], row["distractor3"]]
    seed_int = int(hashlib.sha256(f"{stable_id}:sciq_choice".encode()).hexdigest()[:8], 16)
    random.Random(seed_int).shuffle(choices)
    options = {chr(65 + j): choice for j, choice in enumerate(choices)}
    correct_letter = next(k for k, value in options.items() if value == correct_answer)
    return NormalizedSample(
        sample_id=stable_id,
        dataset_id=config["id"],
        dataset_revision=config.get("revision", "main"),
        domain="education",
        task_type=TaskType.MULTIPLE_CHOICE,
        input_payload={
            "question": row["question"],
            "support": row["support"],
            "choice_a": options["A"],
            "choice_b": options["B"],
            "choice_c": options["C"],
            "choice_d": options["D"],
            "options": options,
        },
        references={"correct_letter": correct_letter, "correct_answer": correct_answer},
    )


class SciQDatasetAdapter(BaseDatasetAdapter):
    def __init__(self, config: dict[str, Any], protocol_id: str | None = None) -> None:
        super().__init__(config)
        self.protocol_id = protocol_id

    def list_splits(self) -> list[str]:
        return ["train", "validation", "test"]

    def load_samples(
        self, split: str, limit: int | None = None, seed: int = 42
    ) -> list[NormalizedSample]:
        rows = load_dataset("allenai/sciq", "default", split=split, streaming=False)
        samples = []
        evidence_required = self.protocol_id is None or "evidence" in self.protocol_id
        for i, row in enumerate(rows):
            if evidence_required and not row["support"].strip():
                continue
            samples.append(_normalize_sciq_row(row, split, i, self.config))
        return self._finalize(samples, split, limit, seed)
