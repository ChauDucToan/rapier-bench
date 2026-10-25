"""IFEval instruction following evaluator.

Authoritative source: docs/EVALUATION_PROTOCOL.md §6.4 and §9.2.
"""

import contextlib

from benchmark.core.types import NormalizedSample, PredictionRecord
from benchmark.evaluators.base import BaseEvaluator
from benchmark.vendor.ifeval import instructions_registry


def _generate_loose_variants(response: str) -> list[str]:
    """Generate the official 8 loose response variants per EVALUATION_PROTOCOL §6.4."""
    variants: set[str] = {response}

    # Variant 2: strip asterisks
    stripped_asterisks = response.replace("*", "")
    variants.add(stripped_asterisks)

    # Line removals on original response
    lines = response.split("\n")
    if len(lines) > 1:
        variants.add("\n".join(lines[1:]).strip())
        variants.add("\n".join(lines[:-1]).strip())
    if len(lines) > 2:
        variants.add("\n".join(lines[1:-1]).strip())

    # Line removals on asterisk-stripped response
    ast_lines = stripped_asterisks.split("\n")
    if len(ast_lines) > 1:
        variants.add("\n".join(ast_lines[1:]).strip())
        variants.add("\n".join(ast_lines[:-1]).strip())
    if len(ast_lines) > 2:
        variants.add("\n".join(ast_lines[1:-1]).strip())

    return list(variants)


class IFEvalEvaluator(BaseEvaluator):
    """Evaluates IFEval prompt-level and instruction-level strict and loose accuracy."""

    def __init__(self) -> None:
        super().__init__(key="ifeval_evaluator")

    def evaluate(
        self, predictions: list[PredictionRecord], samples: list[NormalizedSample]
    ) -> dict[str, float]:
        pairs = self._pair_predictions(predictions, samples)
        if not pairs:
            return {
                "prompt_level_strict_acc": 0.0,
                "prompt_level_loose_acc": 0.0,
                "inst_level_strict_acc": 0.0,
                "inst_level_loose_acc": 0.0,
                "sample_count": 0.0,
            }

        total_prompts = len(pairs)
        strict_prompts_followed = 0
        loose_prompts_followed = 0

        total_instructions = 0
        strict_instructions_followed = 0
        loose_instructions_followed = 0

        for pred, sample in pairs:
            instruction_id_list = sample.references.get("instruction_id_list", [])
            kwargs_list = sample.references.get("kwargs", [])

            response = pred.raw_output
            loose_variants = _generate_loose_variants(response)

            prompt_strict_all = True
            prompt_loose_all = True

            for idx, inst_id in enumerate(instruction_id_list):
                kw = kwargs_list[idx] if idx < len(kwargs_list) else {}
                # Clean None values in kwargs
                clean_kw = {k: v for k, v in kw.items() if v is not None} if isinstance(kw, dict) else {}

                inst_cls = instructions_registry.INSTRUCTION_DICT.get(inst_id)
                if inst_cls is None:
                    prompt_strict_all = False
                    prompt_loose_all = False
                    total_instructions += 1
                    continue

                instruction = inst_cls(inst_id)
                with contextlib.suppress(Exception):
                    instruction.build_description(**clean_kw)

                total_instructions += 1

                # Strict check
                strict_pass = bool(instruction.check_following(response))
                if strict_pass:
                    strict_instructions_followed += 1
                else:
                    prompt_strict_all = False

                # Loose check across variants
                loose_pass = strict_pass or any(
                    bool(instruction.check_following(v)) for v in loose_variants
                )
                if loose_pass:
                    loose_instructions_followed += 1
                else:
                    prompt_loose_all = False

            if prompt_strict_all:
                strict_prompts_followed += 1
            if prompt_loose_all:
                loose_prompts_followed += 1

        prompt_strict_acc = strict_prompts_followed / total_prompts if total_prompts > 0 else 0.0
        prompt_loose_acc = loose_prompts_followed / total_prompts if total_prompts > 0 else 0.0
        inst_strict_acc = (
            strict_instructions_followed / total_instructions if total_instructions > 0 else 0.0
        )
        inst_loose_acc = (
            loose_instructions_followed / total_instructions if total_instructions > 0 else 0.0
        )

        return {
            "prompt_level_strict_acc": round(prompt_strict_acc, 4),
            "prompt_level_loose_acc": round(prompt_loose_acc, 4),
            "inst_level_strict_acc": round(inst_strict_acc, 4),
            "inst_level_loose_acc": round(inst_loose_acc, 4),
            "sample_count": float(total_prompts),
            "total_instructions": float(total_instructions),
        }
