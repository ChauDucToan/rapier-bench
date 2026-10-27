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
            # B4/FIX 6: stratified sampling with coverage guarantee.
            # Policy (documented):
            #   1. When limit >= number of nonempty subtasks, every nonempty
            #      subtask contributes at least 1 sample.
            #   2. Remaining capacity is distributed proportionally to subtask
            #      size via capped largest-remainder allocation.
            #   3. When limit < number of nonempty subtasks, covering every
            #      subtask is mathematically impossible; a deterministic subset
            #      is chosen by the same proportional rule (largest subtasks
            #      first, stable tie-break by name).
            #   4. The selected total always equals `limit` when enough
            #      eligible data exists (guaranteed by the caller's limit <
            #      total check plus capacity clamping).
            subtasks = sorted(per_subtask.keys())
            nonempty = [s for s in subtasks if per_subtask[s]]

            quotas = {s: 0 for s in subtasks}
            remaining = limit
            if limit >= len(nonempty):
                # Coverage first: one per nonempty subtask (capped at size).
                for s in nonempty:
                    quotas[s] = min(1, len(per_subtask[s]))
                remaining = limit - sum(quotas.values())

            # Proportional largest-remainder distribution of the remainder over
            # subtasks with spare capacity, weight = subtask size.
            capacity = {s: len(per_subtask[s]) - quotas[s] for s in subtasks}
            total_capacity = sum(capacity.values())
            if remaining > 0 and total_capacity > 0:
                raw = {
                    s: remaining * capacity[s] / total_capacity
                    for s in subtasks
                    if capacity[s] > 0
                }
                for s in raw:
                    add = min(int(raw[s]), capacity[s])
                    quotas[s] += add
                    capacity[s] -= add
                leftover = remaining - sum(int(r) for r in raw.values())
                by_remainder = sorted(
                    (s for s in raw),
                    key=lambda s: (-(raw[s] - int(raw[s])), -len(per_subtask[s]), s),
                )
                i = 0
                while leftover > 0:
                    s = by_remainder[i % len(by_remainder)]
                    if capacity[s] > 0:
                        quotas[s] += 1
                        capacity[s] -= 1
                        leftover -= 1
                    i += 1

            selected: list[NormalizedSample] = []
            for subtask in subtasks:
                quota = quotas[subtask]
                if quota <= 0:
                    continue
                sub_selected, _ = select_samples(
                    per_subtask[subtask], subtask, split, seed, quota
                )
                selected.extend(sub_selected)
            # Deterministic global order; trim impossible oversupply (cannot
            # happen when limit < total, kept as a safety net).
            selected, _ = select_samples(selected, self.config["id"], split, seed, limit)
            return selected

        selected, _ = select_samples(all_samples, self.config["id"], split, seed, limit)
        return selected
