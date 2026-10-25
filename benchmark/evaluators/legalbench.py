"""LegalBench Contract NLI evaluator and normalizer.

Authoritative source: docs/EVALUATION_PROTOCOL.md §5.3 and §9.2.
"""

import string
from collections import defaultdict

from benchmark.core.types import (
    NormalizedSample,
    ParseResult,
    ParseStatus,
    PredictionRecord,
)
from benchmark.evaluators.base import BaseEvaluator


def normalize_legal(text: str) -> str:
    """Official LegalBench text normalization: strip punctuation, lowercase, strip whitespace."""
    return str(text).translate(str.maketrans("", "", string.punctuation)).strip().lower()


def parse_legal_output(raw_output: str) -> ParseResult:
    """Parse binary Yes/No classification from model response."""
    norm = normalize_legal(raw_output)
    words = norm.split()

    if norm == "yes" or (words and words[0] == "yes") or (words and words[-1] == "yes"):
        return ParseResult(raw_output=raw_output, parsed_output="Yes", parse_status=ParseStatus.SUCCESS)
    if norm == "no" or (words and words[0] == "no") or (words and words[-1] == "no"):
        return ParseResult(raw_output=raw_output, parsed_output="No", parse_status=ParseStatus.SUCCESS)

    if "yes" in words and "no" not in words:
        return ParseResult(raw_output=raw_output, parsed_output="Yes", parse_status=ParseStatus.FALLBACK)
    if "no" in words and "yes" not in words:
        return ParseResult(raw_output=raw_output, parsed_output="No", parse_status=ParseStatus.FALLBACK)

    return ParseResult(
        raw_output=raw_output,
        parsed_output=norm,
        parse_status=ParseStatus.FAILED,
        parse_error=f"Could not unambiguously resolve Yes/No from: '{norm}'",
    )


class LegalBenchEvaluator(BaseEvaluator):
    """Evaluates LegalBench Contract NLI balanced accuracy per subtask and macro-average."""

    def __init__(self) -> None:
        super().__init__(key="legalbench_contract_nli_evaluator")

    def evaluate(
        self, predictions: list[PredictionRecord], samples: list[NormalizedSample]
    ) -> dict[str, float]:
        pairs = self._pair_predictions(predictions, samples)
        if not pairs:
            return {
                "balanced_accuracy": 0.0,
                "accuracy": 0.0,
                "yes_recall": 0.0,
                "no_recall": 0.0,
                "aggregate_macro_balanced_accuracy": 0.0,
                "sample_count": 0.0,
            }

        # Group by subtask
        by_subtask: dict[str, list[tuple[PredictionRecord, NormalizedSample]]] = defaultdict(list)
        for pred, sample in pairs:
            subtask = sample.metadata.get("subtask", sample.references.get("subtask", "contract_nli_default"))
            by_subtask[subtask].append((pred, sample))

        subtask_balanced_accs: list[float] = []
        metrics: dict[str, float] = {}

        global_tp = 0
        global_fp = 0
        global_tn = 0
        global_fn = 0

        for subtask_name, sub_pairs in by_subtask.items():
            tp = 0
            fp = 0
            tn = 0
            fn = 0

            for pred, sample in sub_pairs:
                gold = sample.references.get("answer", sample.references.get("gold_answer", "")).strip()

                parsed = pred.parsed_output
                if parsed is None or parsed not in ("Yes", "No"):
                    parsed_res = parse_legal_output(pred.raw_output)
                    parsed = parsed_res.parsed_output

                if gold == "Yes":
                    if parsed == "Yes":
                        tp += 1
                        global_tp += 1
                    else:
                        fn += 1
                        global_fn += 1
                elif gold == "No":
                    if parsed == "No":
                        tn += 1
                        global_tn += 1
                    else:
                        fp += 1
                        global_fp += 1

            pos_total = tp + fn
            neg_total = tn + fp
            rec_yes = (tp / pos_total) if pos_total > 0 else 0.0
            rec_no = (tn / neg_total) if neg_total > 0 else 0.0
            bal_acc = (rec_yes + rec_no) / 2.0
            subtask_balanced_accs.append(bal_acc)

            # Record task-level metrics
            sub_key = subtask_name.replace("contract_nli_", "")
            metrics[f"{sub_key}_balanced_acc"] = round(bal_acc, 4)
            metrics[f"{sub_key}_acc"] = round((tp + tn) / len(sub_pairs), 4)

        macro_bal_acc = (
            sum(subtask_balanced_accs) / len(subtask_balanced_accs) if subtask_balanced_accs else 0.0
        )
        total_samples = len(pairs)
        global_rec_yes = (global_tp / (global_tp + global_fn)) if (global_tp + global_fn) > 0 else 0.0
        global_rec_no = (global_tn / (global_tn + global_fp)) if (global_tn + global_fp) > 0 else 0.0
        global_bal_acc = (global_rec_yes + global_rec_no) / 2.0
        global_acc = (global_tp + global_tn) / total_samples if total_samples > 0 else 0.0

        metrics.update({
            "balanced_accuracy": round(global_bal_acc, 4),
            "accuracy": round(global_acc, 4),
            "yes_recall": round(global_rec_yes, 4),
            "no_recall": round(global_rec_no, 4),
            "aggregate_macro_balanced_accuracy": round(macro_bal_acc, 4),
            "sample_count": float(total_samples),
        })
        return metrics
