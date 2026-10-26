"""LegalBench Contract NLI dataset adapter."""

from typing import Any

from datasets import load_dataset

from benchmark.adapters.datasets.base import BaseDatasetAdapter
from benchmark.core.sampling import select_samples
from benchmark.core.types import NormalizedSample, TaskType

HYPOTHESES = {
    "contract_nli_confidentiality_of_agreement": "Identify if the clause provides that the Receiving Party shall not disclose the fact that Agreement was agreed or negotiated.",
    "contract_nli_limited_use": "Identify if the clause provides that the Receiving Party shall not use any Confidential Information for any purpose other than the purposes stated in Agreement.",
    "contract_nli_notice_on_compelled_disclosure": "Identify if the clause provides that the Receiving Party shall notify Disclosing Party in case Receiving Party is required by law, regulation or judicial process to disclose any Confidential Information.",
    "contract_nli_permissible_acquirement_of_similar_information": "Identify if the clause provides that the Receiving Party may acquire information similar to Confidential Information from a third party.",
    "contract_nli_sharing_with_third-parties": "Identify if the clause provides that the Receiving Party may share some Confidential Information with some third-parties (including consultants, agents and professional advisors).",
}


def _normalize_row(
    subtask: str, row_index: int, row: dict[str, Any], config: dict[str, Any]
) -> NormalizedSample:
    return NormalizedSample(
        sample_id=f"{subtask}:test:{row_index}",
        dataset_id=config["id"],
        dataset_revision=config.get("revision", "main"),
        domain="legal",
        task_type=TaskType.BINARY_CLASSIFICATION,
        input_payload={"text": row["text"], "hypothesis": HYPOTHESES[subtask]},
        references={"answer": row["answer"], "subtask": subtask},
        metadata={
            "subtask": subtask,
            "document_name": row.get("document_name", ""),
        },
    )


class LegalBenchDatasetAdapter(BaseDatasetAdapter):
    def list_splits(self) -> list[str]:
        return ["train", "test"]

    def load_samples(self, split: str, limit: int | None = None, seed: int = 42):
        # B4: stratified sampling. Pooled sampling let hash-order pick any N
        # rows across the five subtasks, so small subtasks could vanish from a
        # sampled run and the macro balanced-accuracy silently averaged over
        # fewer subtasks. Selection is now proportional-within-subtask via the
        # same deterministic SHA-256 rule (per-subtask quota = round(N * share),
        # at least 1 when the subtask has data).
        per_subtask: dict[str, list[NormalizedSample]] = {}
        for subtask in self.config["documented_subtasks"]:
            rows = load_dataset(
                "nguha/legalbench",
                subtask,
                split=split,
                revision=self.config.get("revision"),
            )
            per_subtask[subtask] = [
                _normalize_row(subtask, row_index, row, self.config)
                for row_index, row in enumerate(rows)
            ]

        all_samples = [s for rows in per_subtask.values() for s in rows]
        total = len(all_samples)

        if limit is not None and limit < total:
            # Deterministic largest-remainder allocation: base quota per subtask,
            # then distribute the leftover count to the largest fractional
            # remainders (stable tie-break by subtask name). Guarantees the
            # selected total equals `limit` exactly without dropping a subtask
            # that has data (each gets at least 1).
            subtasks = sorted(per_subtask.keys())
            raw = {s: limit * len(per_subtask[s]) / total for s in subtasks}
            base = {s: min(int(raw[s]), len(per_subtask[s])) for s in subtasks}
            # A subtask may round above its own row count; clamp back.
            for s in subtasks:
                base[s] = min(base[s], len(per_subtask[s]))
            leftover = limit - sum(base.values())
            by_remainder = sorted(
                subtasks,
                key=lambda s: (-(raw[s] - int(raw[s])), -len(per_subtask[s]), s),
            )
            i = 0
            safeguard = 0
            while leftover > 0 and safeguard <= len(subtasks) * 2:
                s = by_remainder[i % len(subtasks)]
                if base[s] < len(per_subtask[s]):
                    base[s] += 1
                    leftover -= 1
                i += 1
                safeguard += 1

            selected: list[NormalizedSample] = []
            for subtask in subtasks:
                quota = base[subtask]
                if quota <= 0:
                    continue
                sub_selected, _ = select_samples(
                    per_subtask[subtask], subtask, split, seed, quota
                )
                selected.extend(sub_selected)
            # Deterministic global order.
            selected, _ = select_samples(selected, self.config["id"], split, seed, limit)
            return selected

        selected, _ = select_samples(all_samples, self.config["id"], split, seed, limit)
        return selected
