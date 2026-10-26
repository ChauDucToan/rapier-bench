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

    1. Extract single capital option letter [A-D] matching r"(?:^|\b|\()([A-D])(?:\)|\.|\b|$)"
       or explicit prefix r"(?:answer|choice|option):\s*([A-D])".
    2. If no option letter detected, attempt exact case-insensitive normalized match against choice texts.
    3. If zero or multiple match, output INVALID.
    """
    text = raw_output.strip()

    # Rule 1a: Prefix match (e.g. "Answer: B", "The correct choice is: C", "Option D")
    prefix_match = re.search(r"(?:answer|choice|option)\s*(?:is|:|\sis)?\s*\(?([A-D])\)?", text, re.IGNORECASE)
    if prefix_match:
        return ParseResult(raw_output=raw_output, parsed_output=prefix_match.group(1).upper(), parse_status=ParseStatus.SUCCESS)

    # Rule 1b: Standalone option letter [A-D] as its own token (e.g. "B", "(C)",
    # "D.", "**A**"). B6: a letter embedded in prose ("vitamin B complex",
    # "I think A but final answer is D") is NOT a standalone selection and must
    # not be extracted as the model's answer.
    letter_match = re.search(r"(?:^|[\s\(*])([A-D])(?=[\s\).,:;!?\]}*$]|$)", text)
    if letter_match:
        return ParseResult(raw_output=raw_output, parsed_output=letter_match.group(1).upper(), parse_status=ParseStatus.SUCCESS)

    # Rule 2: Case-insensitive normalized match against choice texts
    normalized_text = text.lower().strip()
    matching_letters = [
        letter for letter, choice_val in options.items()
        if choice_val.lower().strip() == normalized_text
    ]
    if len(matching_letters) == 1:
        return ParseResult(raw_output=raw_output, parsed_output=matching_letters[0], parse_status=ParseStatus.FALLBACK)

    # Rule 3: Zero or multiple choices matched -> INVALID
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
