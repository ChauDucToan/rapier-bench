"""WDC-PAVE attribute-value extraction evaluator.

Authoritative source: docs/EVALUATION_PROTOCOL.md §4.4 and §9.2.
"""

import json
import re
from typing import Any

from benchmark.core.types import (
    NormalizedSample,
    ParseResult,
    ParseStatus,
    PredictionRecord,
)
from benchmark.evaluators.base import BaseEvaluator


def parse_wdc_output(raw_output: str) -> ParseResult:
    """Parse JSON attribute-value dictionary from model generation text."""
    text = raw_output.strip()

    # Look for markdown code fence
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            parsed = json.loads(fence_match.group(1))
            if isinstance(parsed, dict):
                return ParseResult(raw_output=raw_output, parsed_output=parsed, parse_status=ParseStatus.SUCCESS)
        except json.JSONDecodeError:
            pass

    # Look for first balanced JSON block { ... }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_cand = text[first_brace : last_brace + 1]
        try:
            parsed = json.loads(json_cand)
            if isinstance(parsed, dict):
                return ParseResult(raw_output=raw_output, parsed_output=parsed, parse_status=ParseStatus.SUCCESS)
        except json.JSONDecodeError:
            pass

    # Parse failure
    return ParseResult(
        raw_output=raw_output,
        parsed_output={},
        parse_status=ParseStatus.FAILED,
        parse_error="Failed to extract valid JSON dictionary from output.",
    )


def _normalize_val(val: Any) -> set[str] | None:
    """Normalize ground-truth or predicted attribute value into a set of lowercased strings or None."""
    if val is None:
        return None
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("", "n/a", "null", "none"):
            return None
        return {v}
    if isinstance(val, (list, tuple, set)):
        items = {str(x).strip().lower() for x in val if str(x).strip().lower() not in ("", "n/a", "null", "none")}
        return items if items else None
    if isinstance(val, dict):
        # Nested target_scores dict e.g. {"value": ...}
        items = {str(k).strip().lower() for k in val if str(k).strip().lower() not in ("", "n/a", "null", "none")}
        return items if items else None
    v = str(val).strip().lower()
    return {v} if v not in ("", "n/a", "null", "none") else None


class WdcPaveEvaluator(BaseEvaluator):
    """Evaluates WDC-PAVE Micro-F1, Precision, Recall, and error rates per §4.4."""

    def __init__(self) -> None:
        super().__init__(key="wdc_pave_evaluator")

    def evaluate(
        self, predictions: list[PredictionRecord], samples: list[NormalizedSample]
    ) -> dict[str, float]:
        pairs = self._pair_predictions(predictions, samples)
        if not pairs:
            return {
                "micro_f1": 0.0,
                "micro_precision": 0.0,
                "micro_recall": 0.0,
                "json_validity_rate": 0.0,
                "missing_attr_rate": 0.0,
                "unsupported_attr_rate": 0.0,
                "parse_failure_rate": 0.0,
                "sample_count": 0.0,
            }

        vc_count = 0
        nv_count = 0
        vn_count = 0
        vw_count = 0
        nn_count = 0

        valid_json_count = 0
        parse_failure_count = 0

        for pred, sample in pairs:
            # Check parse status
            pred_dict = pred.parsed_output if isinstance(pred.parsed_output, dict) else {}
            if pred.parse_status == ParseStatus.SUCCESS and isinstance(pred.parsed_output, dict):
                valid_json_count += 1
            elif pred.parse_status == ParseStatus.FAILED:
                parse_failure_count += 1

            gold_json = sample.references.get("gold_json", {})
            if not isinstance(gold_json, dict):
                continue

            for attr, raw_target in gold_json.items():
                target_set = _normalize_val(raw_target)
                pred_val = pred_dict.get(attr)
                pred_set = _normalize_val(pred_val)

                # Five mutually exclusive outcomes:
                # 1. NN: Target is None and Pred is None
                if target_set is None and pred_set is None:
                    nn_count += 1
                # 2. NV: Target is None and Pred is not None
                elif target_set is None and pred_set is not None:
                    nv_count += 1
                # 3. VN: Target is not None and Pred is None
                elif target_set is not None and pred_set is None:
                    vn_count += 1
                # 4. VC: Target is not None and Pred in Target
                # (Intersection is non-empty; n/a never counts as VC)
                elif target_set is not None and pred_set is not None and bool(target_set & pred_set):
                    vc_count += 1
                # 5. VW: Target is not None and Pred not in Target
                else:
                    vw_count += 1

            # Extra unsupported attributes predicted by the model not in gold schema (NV)
            for attr, pred_val in pred_dict.items():
                if attr not in gold_json:
                    pred_set = _normalize_val(pred_val)
                    if pred_set is not None:
                        nv_count += 1

        total_samples = len(pairs)
        denom_p = vc_count + nv_count + vw_count
        denom_r = vc_count + vn_count + vw_count

        precision = (vc_count / denom_p) if denom_p > 0 else 0.0
        recall = (vc_count / denom_r) if denom_r > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        missing_attr_rate = (vn_count / denom_r) if denom_r > 0 else 0.0
        unsupported_attr_rate = (nv_count / (nv_count + nn_count)) if (nv_count + nn_count) > 0 else 0.0

        return {
            "micro_f1": round(f1, 4),
            "micro_precision": round(precision, 4),
            "micro_recall": round(recall, 4),
            "json_validity_rate": round(valid_json_count / total_samples, 4),
            "missing_attr_rate": round(missing_attr_rate, 4),
            "unsupported_attr_rate": round(unsupported_attr_rate, 4),
            "parse_failure_rate": round(parse_failure_count / total_samples, 4),
            "vc_count": float(vc_count),
            "nv_count": float(nv_count),
            "vn_count": float(vn_count),
            "vw_count": float(vw_count),
            "nn_count": float(nn_count),
            "sample_count": float(total_samples),
        }
