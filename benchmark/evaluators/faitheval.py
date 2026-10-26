"""FaithEval contextual faithfulness evaluator.

Authoritative source: docs/EVALUATION_PROTOCOL.md §7.4, §9.2, §12.V4.

Project protocol: the unanswerable prompt instructs the model to answer with
the literal token ``UNANSWERABLE`` (configs/protocols/faitheval.yaml). Strict
scoring accepts that instructed token plus the documented normalized variant
``unknown``. Loose scoring detects abstention via word-boundary refusal
phrases — never via bare substring containment (e.g. the ``not`` inside
``notebook`` must not count as abstention).
"""

import re

from benchmark.core.types import NormalizedSample, PredictionRecord
from benchmark.evaluators.base import BaseEvaluator

# Verbose refusal patterns for loose matching. Standalone tokens
# ('unknown', 'unanswerable', ...) only count when the WHOLE response is that
# token, so an answerable response like 'The unknown species is X' is not
# scored as a refusal; incidental substrings ("notebook" contains "not")
# never count either.
_UNANSWERABLE_PATTERNS = [
    re.compile(r"^(?:unknown|unanswerable|unclear|undetermined|unverifiable|unavailable)[.!\s]*$"),
    re.compile(r"\bno\s+answer\b"),
    re.compile(r"\bno\s+information\b"),
    re.compile(r"\bnot\s+(?:provided|mentioned|stated|specified|given|available|found)\b"),
    re.compile(r"\bcannot\s+(?:(?:be|not)\s+)?(?:determin|answer|find|infer|verif|locat)(?:e|ed|ing)\b"),
    re.compile(r"\bcan'?t\s+(?:be\s+)?(?:determin|answer|find|infer|verif|locat)(?:e|ed|ing)\b"),
    re.compile(r"\b(?:do(?:es)?\s+not|don'?t|doesn'?t|didn'?t|did\s+not)\s+know\b"),
    re.compile(r"\bdo(?:es)?\s+not\s+(?:mention|state|specify|provide|contain|include)\b"),
    re.compile(r"\bnot\s+possible\s+to\s+(?:determine|answer|infer)\b"),
    re.compile(r"\bunable\s+to\s+(?:determine|answer|find|infer|verify)\b"),
    re.compile(r"\banswer\s+(?:is\s+)?(?:unknown|unanswerable|unclear|unavailable)\b"),
    re.compile(r"\b(?:context|passage|text|document)\s+(?:does\s+not|doesn'?t)\s+(?:provide|mention|state|contain|specify)\b"),
]

def _norm(text: str) -> str:
    return str(text).strip().lower()

def _is_abstention_loose(norm_text: str) -> bool:
    """Loose abstention detection via anchored refusal patterns."""
    return any(p.search(norm_text) for p in _UNANSWERABLE_PATTERNS)

class FaithEvalEvaluator(BaseEvaluator):
    """Evaluates unanswerable context accuracy and answerable control accuracy.

    Per docs/EVALUATION_PROTOCOL.md §7.3, these metrics measure contextual abstention
    and must never be labeled or conflated with a generic 'hallucination rate'.
    """

    def __init__(self) -> None:
        super().__init__(key="faitheval_evaluator")

    def pair_correctness(self, predictions, samples) -> dict[str, bool | None]:
        """Per-sample verdict: abstention correctness for unanswerable items,
        extractive match for answerable controls."""
        pairs = self._pair_predictions(predictions, samples)
        out: dict[str, bool | None] = {}
        for pred, sample in pairs:
            raw_text = _norm(pred.raw_output)
            item_type = sample.references.get("type", sample.metadata.get("type", "unanswerable"))
            answers = [_norm(a) for a in sample.references.get("answers", []) if str(a).strip()]
            if item_type == "unanswerable":
                out[pred.sample_id] = raw_text in ("unanswerable", "unknown")
            elif item_type == "control_answerable":
                is_refusal = raw_text in ("unanswerable", "unknown") or _is_abstention_loose(raw_text)
                out[pred.sample_id] = (
                    (not is_refusal) and bool(raw_text) and any(a in raw_text for a in answers)
                )
            else:
                out[pred.sample_id] = None
        return out

    def evaluate(
        self, predictions: list[PredictionRecord], samples: list[NormalizedSample]
    ) -> dict[str, float]:
        pairs = self._pair_predictions(predictions, samples)
        if not pairs:
            return {
                "unanswerable_context_accuracy_strict": 0.0,
                "unanswerable_context_accuracy_loose": 0.0,
                "sample_count": 0.0,
                "unanswerable_samples": 0.0,
                "control_samples": 0.0,
            }

        unans_total = 0
        unans_strict_correct = 0
        unans_loose_correct = 0

        ctrl_total = 0
        ctrl_correct = 0

        for pred, sample in pairs:
            raw_text = _norm(pred.raw_output)
            item_type = sample.references.get("type", sample.metadata.get("type", "unanswerable"))
            answers = [
                _norm(a)
                for a in sample.references.get("answers", [])
                if str(a).strip()
            ]

            if item_type == "unanswerable":
                unans_total += 1
                # Strict: normalized output is exactly the instructed abstention
                # token 'unanswerable' or the documented variant 'unknown'.
                if raw_text in ("unanswerable", "unknown"):
                    unans_strict_correct += 1

                # Loose: whole-word/pattern refusal detection
                if _is_abstention_loose(raw_text):
                    unans_loose_correct += 1

            elif item_type == "control_answerable":
                ctrl_total += 1
                # Check for false refusal first
                is_refusal = raw_text in ("unanswerable", "unknown") or _is_abstention_loose(raw_text)
                if not is_refusal:
                    # Extractive match against gold answers
                    matches = bool(raw_text) and any(a in raw_text for a in answers)
                    if matches:
                        ctrl_correct += 1

        unans_strict_acc = (unans_strict_correct / unans_total) if unans_total > 0 else 0.0
        unans_loose_acc = (unans_loose_correct / unans_total) if unans_total > 0 else 0.0
        ctrl_acc = (ctrl_correct / ctrl_total) if ctrl_total > 0 else 0.0

        metrics: dict[str, float] = {
            "unanswerable_context_accuracy_strict": round(unans_strict_acc, 4),
            "unanswerable_context_accuracy_loose": round(unans_loose_acc, 4),
            "sample_count": float(len(pairs)),
            "unanswerable_samples": float(unans_total),
            "control_samples": float(ctrl_total),
        }

        # answerable_control_accuracy is meaningful whenever controls exist;
        # balanced_score additionally requires the unanswerable group too.
        if ctrl_total > 0:
            metrics["answerable_control_accuracy"] = round(ctrl_acc, 4)

        # B2: balanced_score is only mathematically defined when both the
        # unanswerable group AND the answerable control group were evaluated.
        # Reporting a fake 0.0 for control-free runs would let leaderboard and
        # recommendation treat an unmeasured metric as a genuine zero score.
        if unans_total > 0 and ctrl_total > 0:
            denom = unans_loose_acc + ctrl_acc
            balanced_score = (2 * unans_loose_acc * ctrl_acc / denom) if denom > 0 else 0.0
            metrics["balanced_score"] = round(balanced_score, 4)

        return metrics
