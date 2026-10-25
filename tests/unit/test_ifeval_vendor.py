"""Unit tests for vendored IFEval instruction checkers and offline tokenization.

Authoritative source: docs/EVALUATION_PROTOCOL.md §6.2, §6.3, §12.V3.
"""

from benchmark.vendor.ifeval import instructions_registry, instructions_util


def test_ifeval_registry_and_instruction_types():
    # Verify instruction dictionary is populated with all registered classes
    assert len(instructions_registry.INSTRUCTION_DICT) >= 25

    # Check key types required by evaluation protocol
    assert "keywords:existence" in instructions_registry.INSTRUCTION_DICT
    assert "keywords:forbidden_words" in instructions_registry.INSTRUCTION_DICT
    assert "length_constraints:number_sentences" in instructions_registry.INSTRUCTION_DICT
    assert "length_constraints:number_words" in instructions_registry.INSTRUCTION_DICT
    assert "punctuation:no_comma" in instructions_registry.INSTRUCTION_DICT
    assert "detectable_format:number_highlighted_sections" in instructions_registry.INSTRUCTION_DICT


def test_ifeval_offline_sentence_tokenizer():
    # Test that NLTK punkt_tab tokenizer works offline from vendored data
    text = "Dr. Smith went to Washington D.C. yesterday. He attended an important session."
    count = instructions_util.count_sentences(text)
    assert count == 2


def test_ifeval_instruction_checkers():
    # 1. Punctuation: no comma
    no_comma_cls = instructions_registry.INSTRUCTION_DICT["punctuation:no_comma"]
    no_comma = no_comma_cls("punctuation:no_comma")
    no_comma.build_description()
    assert no_comma.check_following("Clean sentence without prohibited marks.") is True
    assert no_comma.check_following("Sentence, with a comma.") is False

    # 2. Length constraints: number of words
    word_count_cls = instructions_registry.INSTRUCTION_DICT["length_constraints:number_words"]
    word_count = word_count_cls("length_constraints:number_words")
    word_count.build_description(num_words=5, relation="at least")
    assert word_count.check_following("One two three four five six.") is True
    assert word_count.check_following("One two three.") is False
