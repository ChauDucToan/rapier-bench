"""LegalBench Contract NLI dataset adapter."""

from typing import Any

from datasets import load_dataset

from benchmark.adapters.datasets.base import BaseDatasetAdapter
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
        samples: list[NormalizedSample] = []
        for subtask in self.config["documented_subtasks"]:
            rows = load_dataset("nguha/legalbench", subtask, split=split)
            for row_index, row in enumerate(rows):
                samples.append(_normalize_row(subtask, row_index, row, self.config))
        return self._finalize(samples, split, limit, seed)
