"""FaithEval contextual faithfulness evaluator.

Authoritative source: docs/EVALUATION_PROTOCOL.md §7.4, §9.2, §12.V4.
"""

from benchmark.core.types import NormalizedSample, PredictionRecord
from benchmark.evaluators.base import BaseEvaluator

UNANSWERABLE_PHRASES = [
    "unknown",
    "no answer",
    "no information",
    "not",
    "unclear",
    "unanswerable",
]


class FaithEvalEvaluator(BaseEvaluator):
    """Evaluates unanswerable context accuracy and answerable control accuracy.

    Per docs/EVALUATION_PROTOCOL.md §7.3, these metrics measure contextual abstention
    and must never be labeled or conflated with a generic 'hallucination rate'.
    """

    def __init__(self) -> None:
        super().__init__(key="faitheval_evaluator")

    def evaluate(
        self, predictions: list[PredictionRecord], samples: list[NormalizedSample]
    ) -> dict[str, float]:
        pairs = self._pair_predictions(predictions, samples)
        if not pairs:
            return {
                "unanswerable_context_accuracy_strict": 0.0,
                "unanswerable_context_accuracy_loose": 0.0,
                "answerable_control_accuracy": 0.0,
                "balanced_score": 0.0,
                "sample_count": 0.0,
            }

        unans_total = 0
        unans_strict_correct = 0
        unans_loose_correct = 0

        ctrl_total = 0
        ctrl_correct = 0

        for pred, sample in pairs:
            raw_text = pred.raw_output.strip().lower()
            item_type = sample.references.get("type", sample.metadata.get("type", "unanswerable"))
            answers = [
                str(a).strip().lower()
                for a in sample.references.get("answers", [])
                if str(a).strip()
            ]

            if item_type == "unanswerable":
                unans_total += 1
                # Strict: exact normalized string equals 'unknown'
                if raw_text == "unknown":
                    unans_strict_correct += 1

                # Loose: contains any refusal phrase
                if any(phrase in raw_text for phrase in UNANSWERABLE_PHRASES):
                    unans_loose_correct += 1

            elif item_type == "control_answerable":
                ctrl_total += 1
                # Check for false refusal first
                is_refusal = (raw_text == "unknown") or any(
                    phrase in raw_text for phrase in ["unanswerable", "no information"]
                )
                if not is_refusal:
                    # Extractive match against gold answers
                    matches = bool(raw_text) and any(a in raw_text for a in answers)
                    if matches:
                        ctrl_correct += 1

        unans_strict_acc = (unans_strict_correct / unans_total) if unans_total > 0 else 0.0
        unans_loose_acc = (unans_loose_correct / unans_total) if unans_total > 0 else 0.0
        ctrl_acc = (ctrl_correct / ctrl_total) if ctrl_total > 0 else 0.0

        # Balanced score: harmonic mean between unanswerable loose accuracy and answerable control accuracy
        denom = unans_loose_acc + ctrl_acc
        balanced_score = (2 * unans_loose_acc * ctrl_acc / denom) if denom > 0 else 0.0

        return {
            "unanswerable_context_accuracy_strict": round(unans_strict_acc, 4),
            "unanswerable_context_accuracy_loose": round(unans_loose_acc, 4),
            "answerable_control_accuracy": round(ctrl_acc, 4),
            "balanced_score": round(balanced_score, 4),
            "sample_count": float(len(pairs)),
            "unanswerable_samples": float(unans_total),
            "control_samples": float(ctrl_total),
        }
