"""Unit tests for prompt builder and no-leak assertion.

Authoritative source: docs/ARCHITECTURE.md Section 3 and Section 4.
"""

import pytest

from benchmark.core.prompt import DefaultPromptBuilder
from benchmark.core.types import NormalizedSample, TaskType


def test_prompt_builder_rendering_and_hash():
    template = "Question: {question}\nA: {choice_a}\nB: {choice_b}\nAnswer:"
    builder = DefaultPromptBuilder(prompt_template=template)

    sample = NormalizedSample(
        sample_id="s1",
        dataset_id="sciq",
        dataset_revision="v1",
        domain="education",
        task_type=TaskType.MULTIPLE_CHOICE,
        input_payload={"question": "What is 2+2?", "choice_a": "4", "choice_b": "5"},
        references={"correct_answer": "4", "correct_letter": "A"},
    )

    prompt_text, prompt_hash = builder.build_prompt(sample)
    assert "Question: What is 2+2?" in prompt_text
    assert "A: 4" in prompt_text
    assert len(prompt_hash) == 64  # Valid SHA-256 hex string

    # Hash stability
    _, prompt_hash_2 = builder.build_prompt(sample)
    assert prompt_hash == prompt_hash_2


def test_prompt_builder_no_leak_reference_variable():
    # Template attempts to interpolate reference field directly -> must raise ValueError
    template = "Question: {question}\nCorrect answer: {correct_answer}"
    builder = DefaultPromptBuilder(prompt_template=template)

    sample = NormalizedSample(
        sample_id="s1",
        dataset_id="sciq",
        dataset_revision="v1",
        domain="education",
        task_type=TaskType.MULTIPLE_CHOICE,
        input_payload={"question": "What is water?"},
        references={"correct_answer": "H2O"},
    )

    with pytest.raises(ValueError, match="leaked reference field"):
        builder.build_prompt(sample)


def test_prompt_builder_no_leak_explicit_answer():
    # Template has explicit Answer: B
    template = "Question: {question}\nAnswer: B"
    builder = DefaultPromptBuilder(prompt_template=template)

    sample = NormalizedSample(
        sample_id="s2",
        dataset_id="sciq",
        dataset_revision="v1",
        domain="education",
        task_type=TaskType.MULTIPLE_CHOICE,
        input_payload={"question": "Test question"},
        references={"correct_letter": "B"},
    )

    with pytest.raises(ValueError, match="leaked into prompt text"):
        builder.build_prompt(sample)
