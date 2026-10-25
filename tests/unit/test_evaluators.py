"""Unit tests for all 5 evaluators asserting hand-computed gold fixtures and edge cases.

Authoritative source: docs/EVALUATION_PROTOCOL.md §9.1 and §9.2.
"""

import json
from pathlib import Path

import pytest

from benchmark.core.types import NormalizedSample, PredictionRecord, TaskType
from benchmark.evaluators.faitheval import FaithEvalEvaluator
from benchmark.evaluators.ifeval import IFEvalEvaluator
from benchmark.evaluators.legalbench import LegalBenchEvaluator
from benchmark.evaluators.sciq import SciQEvaluator
from benchmark.evaluators.wdc_pave import WdcPaveEvaluator

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _make_dummy_pred(sample_id: str, raw: str, parsed: any, status: str = "success") -> PredictionRecord:
    return PredictionRecord(
        sample_id=sample_id,
        model_id="test-model",
        model_revision="v1",
        protocol_version="1.0.0",
        prompt_hash="dummy_hash",
        raw_output=raw,
        parsed_output=parsed,
        parse_status=status,
        parse_error=None if status == "success" else "parse error",
        input_tokens=10,
        output_tokens=5,
        latency_ms=25.0,
    )


# ==============================================================================
# 1. SciQ Evaluator Tests
# ==============================================================================

def test_sciq_evaluator_gold_fixture():
    with open(FIXTURES_DIR / "sciq_gold.json", encoding="utf-8") as f:
        fixtures = json.load(f)

    samples = []
    predictions = []

    for item in fixtures:
        sid = item["id"]
        sample = NormalizedSample(
            sample_id=sid,
            dataset_id="sciq",
            dataset_revision="main",
            domain="education",
            task_type=TaskType.MULTIPLE_CHOICE,
            input_payload={"options": item["choices"]},
            references={"correct_answer": item["correct"], "correct_letter": next(k for k, v in item["choices"].items() if v == item["correct"])},
        )
        samples.append(sample)
        # Parse output dynamically
        from benchmark.evaluators.sciq import parse_sciq_output
        parsed_res = parse_sciq_output(item["pred"], item["choices"])
        predictions.append(_make_dummy_pred(sid, item["pred"], parsed_res.parsed_output, parsed_res.parse_status))

    evaluator = SciQEvaluator()
    metrics = evaluator.evaluate(predictions, samples)

    # Hand-computed: accuracy = 2/4 = 0.5000, invalid_parsed_rate = 1/4 = 0.2500
    assert metrics["accuracy"] == 0.5000
    assert metrics["invalid_parsed_rate"] == 0.2500
    assert metrics["sample_count"] == 4.0


def test_sciq_evaluator_edge_cases():
    evaluator = SciQEvaluator()
    # Empty dataset
    assert evaluator.evaluate([], [])["accuracy"] == 0.0

    # Perfect accuracy
    sample = NormalizedSample(
        sample_id="s1",
        dataset_id="sciq",
        dataset_revision="main",
        domain="education",
        task_type=TaskType.MULTIPLE_CHOICE,
        input_payload={"options": {"A": "yes", "B": "no"}},
        references={"correct_letter": "A"},
    )
    pred = _make_dummy_pred("s1", "A", "A")
    assert evaluator.evaluate([pred], [sample])["accuracy"] == 1.0


# ==============================================================================
# 2. WDC-PAVE Evaluator Tests
# ==============================================================================

def test_wdc_pave_evaluator_gold_fixture():
    with open(FIXTURES_DIR / "wdc_pave_gold.json", encoding="utf-8") as f:
        fixtures = json.load(f)

    samples = []
    predictions = []

    for item in fixtures:
        sid = str(item["id"])
        sample = NormalizedSample(
            sample_id=sid,
            dataset_id="wdc_pave",
            dataset_revision="main",
            domain="ecommerce",
            task_type=TaskType.ATTRIBUTE_VALUE_EXTRACTION,
            input_payload={},
            references={"gold_json": item["target"]},
        )
        samples.append(sample)
        predictions.append(_make_dummy_pred(sid, json.dumps(item["pred"]), item["pred"]))

    evaluator = WdcPaveEvaluator()
    metrics = evaluator.evaluate(predictions, samples)

    # Hand-computed: VC=4, NV=1, VN=1, VW=1, NN=1
    assert metrics["vc_count"] == 4.0
    assert metrics["nv_count"] == 1.0
    assert metrics["vn_count"] == 1.0
    assert metrics["vw_count"] == 1.0
    assert metrics["nn_count"] == 1.0
    assert metrics["micro_precision"] == pytest.approx(4 / 6, abs=1e-4)
    assert metrics["micro_recall"] == pytest.approx(4 / 6, abs=1e-4)
    assert metrics["micro_f1"] == pytest.approx(4 / 6, abs=1e-4)


def test_wdc_pave_na_never_true_positive():
    """Verify that predicting n/a or null never increments VC."""
    evaluator = WdcPaveEvaluator()
    sample = NormalizedSample(
        sample_id="1",
        dataset_id="wdc_pave",
        dataset_revision="main",
        domain="ecommerce",
        task_type=TaskType.ATTRIBUTE_VALUE_EXTRACTION,
        input_payload={},
        references={"gold_json": {"Color": None, "Brand": None}},
    )
    # Model correctly outputs null for both absent attributes (NN outcome)
    pred = _make_dummy_pred("1", '{"Color": null, "Brand": "n/a"}', {"Color": None, "Brand": "n/a"})
    metrics = evaluator.evaluate([pred], [sample])

    assert metrics["vc_count"] == 0.0
    assert metrics["nn_count"] == 2.0
    assert metrics["micro_f1"] == 0.0  # Zero VC -> 0 F1


# ==============================================================================
# 3. LegalBench Evaluator Tests
# ==============================================================================

def test_legalbench_evaluator_gold_fixture():
    with open(FIXTURES_DIR / "legalbench_gold.json", encoding="utf-8") as f:
        fixtures = json.load(f)

    samples = []
    predictions = []

    for item in fixtures:
        sid = item["id"]
        sample = NormalizedSample(
            sample_id=sid,
            dataset_id="legalbench_contract_nli",
            dataset_revision="main",
            domain="legal",
            task_type=TaskType.BINARY_CLASSIFICATION,
            input_payload={"subtask": item["task"]},
            references={"answer": item["answer"], "subtask": item["task"]},
        )
        samples.append(sample)
        predictions.append(_make_dummy_pred(sid, item["pred"], None))

    evaluator = LegalBenchEvaluator()
    metrics = evaluator.evaluate(predictions, samples)

    # Hand-computed: Recall_Yes = 1/2 = 0.5, Recall_No = 1/2 = 0.5, Balanced-Acc = 0.5000, Acc = 0.5000
    assert metrics["balanced_accuracy"] == 0.5000
    assert metrics["accuracy"] == 0.5000
    assert metrics["yes_recall"] == 0.5000
    assert metrics["no_recall"] == 0.5000


def test_legalbench_edge_cases():
    evaluator = LegalBenchEvaluator()
    assert evaluator.evaluate([], [])["balanced_accuracy"] == 0.0


# ==============================================================================
# 4. IFEval Evaluator Tests
# ==============================================================================

def test_ifeval_evaluator_gold_fixture():
    with open(FIXTURES_DIR / "ifeval_gold.json", encoding="utf-8") as f:
        fixtures = json.load(f)

    samples = []
    predictions = []

    for item in fixtures:
        sid = str(item["key"])
        sample = NormalizedSample(
            sample_id=sid,
            dataset_id="ifeval",
            dataset_revision="main",
            domain="general",
            task_type=TaskType.INSTRUCTION_FOLLOWING,
            input_payload={},
            references={"instruction_id_list": item["instructions"], "kwargs": item["kwargs"]},
        )
        samples.append(sample)
        predictions.append(_make_dummy_pred(sid, item["response"], item["response"]))

    evaluator = IFEvalEvaluator()
    metrics = evaluator.evaluate(predictions, samples)

    # Hand-computed: prompt: 2/3 (0.6667), instruction: 4/5 (0.8000)
    assert metrics["prompt_level_strict_acc"] == pytest.approx(2 / 3, abs=1e-4)
    assert metrics["prompt_level_loose_acc"] == pytest.approx(2 / 3, abs=1e-4)
    assert metrics["inst_level_strict_acc"] == pytest.approx(4 / 5, abs=1e-4)
    assert metrics["inst_level_loose_acc"] == pytest.approx(4 / 5, abs=1e-4)


# ==============================================================================
# 5. FaithEval Evaluator Tests
# ==============================================================================

def test_faitheval_evaluator_gold_fixture():
    with open(FIXTURES_DIR / "faitheval_gold.json", encoding="utf-8") as f:
        fixtures = json.load(f)

    samples = []
    predictions = []

    for item in fixtures:
        sid = item["qid"]
        sample = NormalizedSample(
            sample_id=sid,
            dataset_id="faitheval",
            dataset_revision="main",
            domain="contextual_faithfulness",
            task_type=TaskType.CONTEXTUAL_FAITHFULNESS,
            input_payload={},
            references={"answers": item["answers"], "type": item["type"]},
        )
        samples.append(sample)
        predictions.append(_make_dummy_pred(sid, item["pred"], item["pred"]))

    evaluator = FaithEvalEvaluator()
    metrics = evaluator.evaluate(predictions, samples)

    # Hand-computed: unans_strict=1/3 (~0.3333), unans_loose=2/3 (~0.6667), ctrl=1/2 (0.5000), balanced=4/7 (~0.5714)
    assert metrics["unanswerable_context_accuracy_strict"] == pytest.approx(1 / 3, abs=1e-4)
    assert metrics["unanswerable_context_accuracy_loose"] == pytest.approx(2 / 3, abs=1e-4)
    assert metrics["answerable_control_accuracy"] == pytest.approx(1 / 2, abs=1e-4)
    assert metrics["balanced_score"] == pytest.approx(4 / 7, abs=1e-4)


def test_faitheval_always_abstain_model():
    """Verify that a model collapsing to 'unknown' achieves 0.0 on answerable control and 0.0 balanced score."""
    evaluator = FaithEvalEvaluator()
    sample_unans = NormalizedSample(
        sample_id="u1",
        dataset_id="faitheval",
        dataset_revision="main",
        domain="contextual_faithfulness",
        task_type=TaskType.CONTEXTUAL_FAITHFULNESS,
        input_payload={},
        references={"answers": ["unknown"], "type": "unanswerable"},
    )
    sample_ctrl = NormalizedSample(
        sample_id="c1",
        dataset_id="faitheval",
        dataset_revision="main",
        domain="contextual_faithfulness",
        task_type=TaskType.CONTEXTUAL_FAITHFULNESS,
        input_payload={},
        references={"answers": ["George Washington"], "type": "control_answerable"},
    )
    pred_unans = _make_dummy_pred("u1", "unknown", "unknown")
    pred_ctrl = _make_dummy_pred("c1", "unknown", "unknown")  # False refusal on answerable item

    metrics = evaluator.evaluate([pred_unans, pred_ctrl], [sample_unans, sample_ctrl])
    assert metrics["unanswerable_context_accuracy_loose"] == 1.0
    assert metrics["answerable_control_accuracy"] == 0.0
    assert metrics["balanced_score"] == 0.0  # Harmonic mean drops to 0!


def test_faitheval_empty_or_substring_prediction_does_not_match():
    """Verify that empty string or random substring does not match gold answerable control."""
    evaluator = FaithEvalEvaluator()
    sample = NormalizedSample(
        sample_id="c1",
        dataset_id="faitheval",
        dataset_revision="main",
        domain="contextual_faithfulness",
        task_type=TaskType.CONTEXTUAL_FAITHFULNESS,
        input_payload={},
        references={"answers": ["Paris"], "type": "control_answerable"},
    )
    # Empty string must not match
    pred_empty = _make_dummy_pred("c1", "", "")
    m_empty = evaluator.evaluate([pred_empty], [sample])
    assert m_empty["answerable_control_accuracy"] == 0.0

    # Partial substring 'a' inside 'Paris' must not match
    pred_a = _make_dummy_pred("c1", "a", "a")
    m_a = evaluator.evaluate([pred_a], [sample])
    assert m_a["answerable_control_accuracy"] == 0.0

    # True match
    pred_correct = _make_dummy_pred("c1", "Paris", "Paris")
    m_correct = evaluator.evaluate([pred_correct], [sample])
    assert m_correct["answerable_control_accuracy"] == 1.0


def test_wdc_pave_extra_unsupported_attribute_counts_as_nv():
    """Verify that a model predicting extra unsupported attributes is penalized as NV."""
    evaluator = WdcPaveEvaluator()
    sample = NormalizedSample(
        sample_id="1",
        dataset_id="wdc_pave",
        dataset_revision="main",
        domain="ecommerce",
        task_type=TaskType.ATTRIBUTE_VALUE_EXTRACTION,
        input_payload={},
        references={"gold_json": {"Brand": "Apple"}},
    )
    # Model extracts correct Brand, but also hallucinates an unsupported attribute
    pred = _make_dummy_pred(
        "1",
        '{"Brand": "Apple", "HallucinatedColor": "Red"}',
        {"Brand": "Apple", "HallucinatedColor": "Red"},
    )
    metrics = evaluator.evaluate([pred], [sample])
    assert metrics["vc_count"] == 1.0
    assert metrics["nv_count"] == 1.0
    assert metrics["micro_precision"] == 0.5
    assert metrics["unsupported_attr_rate"] == 1.0
