"""SciQ multiple-choice evaluator and answer parser.

Authoritative source: docs/EVALUATION_PROTOCOL.md §3.4 and §9.2.
"""

import re

from benchmark.core.types import (
    NormalizedSample,
    ParseResult,
    ParseStatus,
    PredictionRecord,
)
from benchmark.evaluators.base import BaseEvaluator


def parse_sciq_output(raw_output: str, options: dict[str, str]) -> ParseResult:
    r"""Parse option letter [A-D] from model output per EVALUATION_PROTOCOL §3.4.

    Policy (B1): the SciQ protocol instructs the model to answer with only
    the correct choice letter. A prediction is accepted only when it is
    UNAMBIGUOUS:
      1. Explicit answer statement prefix ("Answer: B", "the correct choice
         is C", "Option D", "I select C").
      2. The ENTIRE response is a single option letter plus punctuation
         ("B", "(C)", "D.", "**A**").
      3. Exact case-insensitive choice-text match as fallback.
    Anything else — prose mentioning letters ("The vitamin B complex..."),
    multiple candidate letters ("might be A or C"), labeled explanations
    ("A: This is the explanation.") — is INVALID. Ambiguous prose is never
    rewarded with a score merely because it contains A/B/C/D.
    """
    text = raw_output.strip()

    # Rule 1: explicit answer statement. Unambiguous by construction.
    prefix_match = re.search(
        r"(?:answer|choice|option|select|pick)\s*(?:is|:|\sis)?\s*\(?([A-D])\)?",
        text,
        re.IGNORECASE,
    )
    if prefix_match:
        return ParseResult(raw_output=raw_output, parsed_output=prefix_match.group(1).upper(), parse_status=ParseStatus.SUCCESS)

    # Rule 2: the whole response is a single option letter (plus decoration).
    whole = re.fullmatch(r"[\s\(\[\{\*]*([A-D])[\s\)\]\}\*.,:!;\?]*", text, re.IGNORECASE)
    if whole:
        return ParseResult(raw_output=raw_output, parsed_output=whole.group(1).upper(), parse_status=ParseStatus.SUCCESS)

    # Rule 3: Case-insensitive normalized match against choice texts
    normalized_text = text.lower().strip()
    matching_letters = [
        letter for letter, choice_val in options.items()
        if choice_val.lower().strip() == normalized_text
    ]
    if len(matching_letters) == 1:
        return ParseResult(raw_output=raw_output, parsed_output=matching_letters[0], parse_status=ParseStatus.FALLBACK)

    # Rule 4: no unambiguous selection -> INVALID
    return ParseResult(
        raw_output=raw_output,
        parsed_output="INVALID",
        parse_status=ParseStatus.FAILED,
        parse_error="Failed to extract single valid option letter [A-D] or matching choice text.",
    )

class SciQEvaluator(BaseEvaluator):
    """Evaluates SciQ exact accuracy and invalid parse rate."""

    def __init__(self) -> None:
        super().__init__(key="sciq_evaluator")

    def pair_correctness(self, predictions, samples) -> dict[str, bool | None]:
        pairs = self._pair_predictions(predictions, samples)
        out: dict[str, bool | None] = {}
        for pred, sample in pairs:
            correct_letter = sample.references.get("correct_letter", "")
            options = sample.input_payload.get("options", {})
            parsed = pred.parsed_output
            if parsed is None or parsed == "":
                parsed = parse_sciq_output(pred.raw_output, options).parsed_output
            out[pred.sample_id] = parsed == correct_letter if parsed != "INVALID" else False
        return out

    def evaluate(
        self, predictions: list[PredictionRecord], samples: list[NormalizedSample]
    ) -> dict[str, float]:
        pairs = self._pair_predictions(predictions, samples)
        if not pairs:
            return {"accuracy": 0.0, "invalid_parsed_rate": 0.0, "sample_count": 0.0}

        correct_count = 0
        invalid_count = 0

        for pred, sample in pairs:
            correct_letter = sample.references.get("correct_letter", "")
            options = sample.input_payload.get("options", {})

            # Use prediction record's parsed_output or parse raw_output
            parsed = pred.parsed_output
            if parsed is None or parsed == "":
                parsed_res = parse_sciq_output(pred.raw_output, options)
                parsed = parsed_res.parsed_output

            if parsed == "INVALID" or pred.parse_status == ParseStatus.FAILED:
                invalid_count += 1
            elif parsed == correct_letter:
                correct_count += 1

        total = len(pairs)
        return {
            "accuracy": round(correct_count / total, 4),
            "invalid_parsed_rate": round(invalid_count / total, 4),
            "sample_count": float(total),
        }
