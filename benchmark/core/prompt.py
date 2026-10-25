"""Prompt builder: template substitution, chat template application, SHA-256 hashing, no-leak assertion.

Authoritative source: docs/ARCHITECTURE.md Section 3 and Section 4.
"""

import hashlib
import string
from collections.abc import Mapping
from typing import Any

from benchmark.core.types import NormalizedSample, PromptBuilder


class DefaultPromptBuilder(PromptBuilder):
    """Standard prompt builder implementing template rendering, chat formatting, and no-leak assertion."""

    def __init__(
        self,
        prompt_template: str,
        tokenizer: Any = None,
        add_generation_prompt: bool = True,
        system_prompt: str | None = None,
    ) -> None:
        self.prompt_template = prompt_template
        self.tokenizer = tokenizer
        self.add_generation_prompt = add_generation_prompt
        self.system_prompt = system_prompt

        # Validate template variable names do not reference ground truth
        formatter = string.Formatter()
        self.template_keys = {
            field_name
            for _, field_name, _, _ in formatter.parse(prompt_template)
            if field_name is not None
        }

    def _render_template(self, input_payload: Mapping[str, Any]) -> str:
        # ponytail: standard string format with SafeDict to keep unpopulated non-critical keys
        class SafeDict(dict):
            def __missing__(self, key: str) -> str:
                return f"{{{key}}}"

        return self.prompt_template.format_map(SafeDict(input_payload))

    def _assert_no_ground_truth_leak(self, prompt_text: str, sample: NormalizedSample) -> None:
        """Verify that ground-truth references never leaked into the prompt."""
        # 1. Ensure template fields did not draw from references
        ground_truth_target_keys = {
            "correct_answer",
            "correct_letter",
            "gold_answer",
            "gold_json",
            "target_scores",
            "answers",
        }
        for ref_key in sample.references:
            if (ref_key in ground_truth_target_keys or ref_key not in sample.input_payload) and ref_key in self.template_keys:
                raise ValueError(
                    f"Prompt template leaked reference field '{ref_key}' into template variables."
                )

        # 2. Assert explicit target labels (like correct_letter) are not directly labeled as answer
        # e.g., 'Answer: B' in multiple-choice prompt
        correct_letter = sample.references.get("correct_letter")
        if correct_letter and f"Answer: {correct_letter}" in prompt_text:
            raise ValueError(f"Ground truth answer '{correct_letter}' leaked into prompt text!")

    def build_prompt(self, sample: NormalizedSample) -> tuple[str, str]:
        """Returns (formatted_prompt_text, sha256_prompt_hash). Never leaks ground-truth references."""
        # 1. Render template solely with input_payload
        rendered_text = self._render_template(sample.input_payload)

        # 2. Run no-leak assertion
        self._assert_no_ground_truth_leak(rendered_text, sample)

        # 3. Apply chat template if tokenizer is provided
        final_prompt = rendered_text
        if self.tokenizer is not None and hasattr(self.tokenizer, "apply_chat_template"):
            messages: list[dict[str, str]] = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            messages.append({"role": "user", "content": rendered_text})

            try:
                final_prompt = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=self.add_generation_prompt,
                )
            except Exception:
                # Fallback to rendered text if tokenizer fails chat template formatting
                final_prompt = rendered_text

        # 4. Deterministic SHA-256 hash
        prompt_hash = hashlib.sha256(final_prompt.encode("utf-8")).hexdigest()
        return final_prompt, prompt_hash
