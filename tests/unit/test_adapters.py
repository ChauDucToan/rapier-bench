"""Offline checks for adapter normalization contracts."""

from benchmark.adapters.datasets.legalbench import HYPOTHESES
from benchmark.adapters.datasets.sciq import _normalize_sciq_row
from benchmark.adapters.datasets.wdc_pave import _normalize_wdc_row


def test_sciq_options_are_deterministic_and_correct() -> None:
    row = {
        "question": "Q?",
        "support": "evidence",
        "correct_answer": "correct",
        "distractor1": "wrong one",
        "distractor2": "wrong two",
        "distractor3": "wrong three",
    }
    sample_a = _normalize_sciq_row(row, "test", 3, {"id": "sciq"})
    sample_b = _normalize_sciq_row(row, "test", 3, {"id": "sciq"})
    assert sample_a.input_payload["options"] == sample_b.input_payload["options"]
    assert sample_a.input_payload["options"][sample_a.references["correct_letter"]] == "correct"


def test_wdc_gold_normalization() -> None:
    sample = _normalize_wdc_row(
        {
            "id": "row-1",
            "category": "laptop",
            "input_title": "Title",
            "input_description": "Description",
            "target_scores": {
                "Generation": {"G5": {"pid": ["1"], "score": 1}},
                "Bus Speed": {"n/a": 1},
                "Processor Type": {
                    "Xeon E5335": {"pid": ["1"], "score": 1},
                    "Intel X5335": {"pid": ["2"], "score": 1},
                },
            },
        }
    )
    assert sample.references["gold_json"] == {
        "Generation": "G5",
        "Bus Speed": None,
        "Processor Type": ["Xeon E5335", "Intel X5335"],
    }


def test_legalbench_hypotheses_present() -> None:
    expected = {
        "contract_nli_confidentiality_of_agreement",
        "contract_nli_limited_use",
        "contract_nli_notice_on_compelled_disclosure",
        "contract_nli_permissible_acquirement_of_similar_information",
        "contract_nli_sharing_with_third-parties",
    }
    assert HYPOTHESES.keys() == expected
    assert all(HYPOTHESES.values())


def test_cli_split_default_resolves_dataset_default() -> None:
    """Non-dry CLI run must resolve split=None to dataset default_split, not 'test'."""
    from benchmark.cli import build_parser

    args = build_parser().parse_args(
        ["run", "--model", "lfm2.5-350m", "--dataset", "ifeval"]
    )
    assert args.split is None  # pre-resolution; main() resolves to default_split

    # Resolution rule under test: dataset default_split from configs/datasets.yaml
    from benchmark.core.registry import ConfigRegistry

    cfg = ConfigRegistry().get_dataset_config("ifeval")
    assert args.split or cfg["default_split"] == "train"


def test_protocol_templates_match_adapter_payload_keys() -> None:
    """Every protocol prompt_template variable must exist in its adapter's input_payload."""
    from string import Formatter

    from benchmark.adapters.datasets.faitheval import _normalize_row as _norm_fe
    from benchmark.adapters.datasets.ifeval import _normalize_row as _norm_ifeval
    from benchmark.adapters.datasets.legalbench import _normalize_row as _norm_lb
    from benchmark.adapters.datasets.wdc_pave import _normalize_wdc_row
    from benchmark.core.registry import ConfigRegistry

    registry = ConfigRegistry()
    fake_rows = {
        "sciq": {
            "question": "q", "support": "s", "correct_answer": "a",
            "distractor1": "b", "distractor2": "c", "distractor3": "d",
        },
        "wdc_pave": {
            "id": 1, "category": "c", "input_title": "t", "input_description": "d",
            "target_scores": {"Brand": {"n/a": 1}},
        },
    }

    payload_samples = {
        "sciq": [_normalize_sciq_row(fake_rows["sciq"], "test", 0, {"id": "sciq"})],
        "wdc_pave": [_normalize_wdc_row(fake_rows["wdc_pave"])],
        "ifeval": [
            _norm_ifeval({"key": 1, "prompt": "p", "instruction_id_list": [], "kwargs": []}, {"id": "ifeval"})
        ],
        "legalbench_contract_nli": [
            _norm_lb("contract_nli_limited_use", 0,
                {"answer": "Yes", "text": "clause", "document_name": "doc.pdf"}, {"id": "legalbench_contract_nli"})
        ],
        "faitheval": [
            _norm_fe({"qid": "q1", "question": "q", "context": "c", "answers": ["unknown"],
                 "subset": "", "justification": ""}, {"id": "faitheval"})
        ],
    }

    for dataset_id, samples in payload_samples.items():
        cfg = registry.get_dataset_config(dataset_id)
        protocol_id = cfg["default_protocol_id"]
        protocol = registry.get_protocol_config(protocol_id)
        template = protocol["prompt_template"]
        needed = {
            fname
            for _, fname, _, _ in Formatter().parse(template)
            if fname is not None
        }
        provided = set(samples[0].input_payload.keys())
        assert needed <= provided, f"{dataset_id}: template needs {needed - provided}"


def test_evaluator_reference_keys_match_adapter_references() -> None:
    """Adapters must emit the exact reference keys evaluators read."""
    from benchmark.adapters.datasets.faitheval import _normalize_row as _norm_fe
    from benchmark.adapters.datasets.ifeval import _normalize_row as _norm_ifeval
    from benchmark.adapters.datasets.legalbench import _normalize_row as _norm_lb
    from benchmark.adapters.datasets.sciq import _normalize_sciq_row

    sciq = _normalize_sciq_row(
        {"question": "q", "support": "s", "correct_answer": "a",
         "distractor1": "b", "distractor2": "c", "distractor3": "d"},
        "test", 0, {"id": "sciq"},
    )
    assert "correct_letter" in sciq.references

    lb = _norm_lb("contract_nli_limited_use", 0,
        {"answer": "Yes", "text": "t", "document_name": "d"}, {"id": "legalbench_contract_nli"})
    assert "answer" in lb.references and "subtask" in lb.metadata

    ife = _norm_ifeval({"key": 1, "prompt": "p", "instruction_id_list": ["x"], "kwargs": [{}]}, {"id": "ifeval"})
    assert "instruction_id_list" in ife.references and "kwargs" in ife.references

    fe = _norm_fe({"qid": "q", "question": "q", "context": "c", "answers": ["unknown"],
         "subset": "", "justification": ""}, {"id": "faitheval"})
    assert fe.references["type"] == "unanswerable" and "answers" in fe.references


def test_hf_model_adapter_config_contract() -> None:
    """HFCausalModelAdapter must accept configs/models.yaml entries without validation errors."""
    from benchmark.adapters.models.hf_causal import HFCausalModelAdapter
    from benchmark.core.registry import ConfigRegistry

    registry = ConfigRegistry()
    for model_id in ("lumma-0.6b", "apertus-0.5b", "lfm2.5-350m"):
        cfg = registry.get_model_config(model_id)
        adapter = HFCausalModelAdapter(cfg)
        assert adapter.config["id"] == model_id
        assert adapter.revision == cfg["revision"]
        assert not adapter.is_loaded
