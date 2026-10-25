"""Unit tests for suite-specific model output parsers.

Authoritative source: docs/EVALUATION_PROTOCOL.md §3.4, §4.4, §5.3.
"""

from benchmark.core.types import ParseStatus
from benchmark.evaluators.legalbench import normalize_legal, parse_legal_output
from benchmark.evaluators.sciq import parse_sciq_output
from benchmark.evaluators.wdc_pave import parse_wdc_output


def test_sciq_parser():
    options = {"A": "oxidants", "B": "antioxidants", "C": "Oxygen", "D": "residues"}

    # Exact letter
    res = parse_sciq_output("A", options)
    assert res.parsed_output == "A"
    assert res.parse_status == ParseStatus.SUCCESS

    # Conversational wrapper
    res2 = parse_sciq_output("The correct choice is (C).", options)
    assert res2.parsed_output == "C"
    assert res2.parse_status == ParseStatus.SUCCESS

    # Text match fallback
    res3 = parse_sciq_output("oxidants", options)
    assert res3.parsed_output == "A"
    assert res3.parse_status == ParseStatus.FALLBACK

    # Invalid / unparseable
    res4 = parse_sciq_output("I am not sure about this.", options)
    assert res4.parsed_output == "INVALID"
    assert res4.parse_status == ParseStatus.FAILED


def test_wdc_pave_parser():
    # Valid raw JSON
    raw = '{"Brand": "Apple", "Color": "Black"}'
    res = parse_wdc_output(raw)
    assert res.parse_status == ParseStatus.SUCCESS
    assert res.parsed_output == {"Brand": "Apple", "Color": "Black"}

    # Code-fenced JSON
    fenced = '```json\n{"Brand": "Dell"}\n```'
    res2 = parse_wdc_output(fenced)
    assert res2.parse_status == ParseStatus.SUCCESS
    assert res2.parsed_output == {"Brand": "Dell"}

    # Malformed JSON
    malformed = "Here is the output: {Brand: 'Apple', incomplete..."
    res3 = parse_wdc_output(malformed)
    assert res3.parse_status == ParseStatus.FAILED
    assert res3.parsed_output == {}


def test_legalbench_parser():
    # Exact Yes / No
    assert parse_legal_output("Yes").parsed_output == "Yes"
    assert parse_legal_output("No").parsed_output == "No"

    # With punctuation
    assert parse_legal_output("No.").parsed_output == "No"
    assert parse_legal_output("Yes!").parsed_output == "Yes"

    # Conversational
    assert parse_legal_output("The clause entails it: Yes").parsed_output == "Yes"
    assert parse_legal_output("No, it does not apply.").parsed_output == "No"

    # Unknown
    res = parse_legal_output("Maybe, depending on circumstances.")
    assert res.parse_status == ParseStatus.FAILED

    # Normalization helper
    assert normalize_legal("Yes, indeed.") == "yes indeed"
