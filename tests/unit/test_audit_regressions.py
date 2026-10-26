"""Regression tests for audit-verified defects (A1, A2, A5, B1, B2, B7)."""


import pytest

from benchmark.adapters.datasets.base import BaseDatasetAdapter
from benchmark.core.types import (
    GenerationOutput,
    NormalizedSample,
    ParseStatus,
    PredictionRecord,
    TaskType,
)

# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------


class _FakeAdapter(BaseDatasetAdapter):
    """Deterministic dataset adapter for runner tests (no network)."""

    def __init__(self, config, samples):
        super().__init__(config)
        self._samples = samples

    def list_splits(self):
        return ["test"]

    def load_samples(self, split, limit=None, seed=42):
        return self._finalize(self._samples, split, limit, seed)


class _FailingModel:
    def __init__(self, fail_on=1):
        self.fail_on = fail_on
        self.calls = 0
        self.revision = "rev"
        self.load_time_s = 0.0
        self.unloaded = False

    def load(self, device="cuda"):
        pass

    def generate(self, prompt, generation_config=None):
        self.calls += 1
        if self.calls >= self.fail_on:
            # Same failure shape as HFCausalModelAdapter.generate()
            return GenerationOutput(
                raw_text="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=0.0,
                model_id="m",
                model_revision="rev",
                error="CUDA error: out of memory",
            )
        return GenerationOutput(
            raw_text="A",
            input_tokens=1,
            output_tokens=1,
            latency_ms=5.0,
            model_id="m",
            model_revision="rev",
        )

    def unload(self):
        self.unloaded = True


class _RegMockRunner:
    """Test-local variant of DefaultBenchmarkRunner with minimal subclassing.

    Reuses production run() by monkeypatching registry deps.
    """


def _mk_samples(n):
    return [
        NormalizedSample(
            sample_id=f"sciq:test:{i}",
            dataset_id="sciq",
            dataset_revision="main",
            domain="education",
            task_type=TaskType.MULTIPLE_CHOICE,
            input_payload={"question": f"q{i}", "options": {"A": "x", "B": "y"}},
            references={"correct_letter": "A"},
        )
        for i in range(n)
    ]


def _mk_record(sample_id, raw="A", parse_status=ParseStatus.SUCCESS):
    return PredictionRecord(
        sample_id=sample_id,
        model_id="m",
        model_revision="rev",
        protocol_version="1.0.0",
        prompt_hash="h",
        raw_output=raw,
        parsed_output="A" if parse_status == ParseStatus.SUCCESS else raw,
        parse_status=str(parse_status),
        parse_error=None,
        input_tokens=1,
        output_tokens=1,
        latency_ms=1.0,
        error=None,
    )


# ---------------------------------------------------------------------------
# A1: generation errors must fail the run, not count as wrong answers
# ---------------------------------------------------------------------------


class TestA1InferenceErrors:
    def test_generation_error_raises_runtime_error(self, tmp_path, monkeypatch):
        """Adapter returning GenerationOutput(error=...) must raise, not produce COMPLETED metrics."""
        from benchmark.core.runner import DefaultBenchmarkRunner

        class _Reg:
            def __init__(self, model_adapter, ds_adapter):
                self._m = model_adapter
                self._d = ds_adapter

            def get_model_config(self, mid):
                return {"id": mid}

            def get_dataset_config(self, did):
                return {"id": "sciq", "default_protocol_id": "p"}

            def get_protocol_config(self, pid):
                return {"prompt_template": "{text}", "version": "1.0.0"}

            def get_evaluator(self, key):
                from benchmark.evaluators.sciq import SciQEvaluator

                return SciQEvaluator()

            def get_model_adapter(self, mid):
                return self._m

            def get_dataset_adapter(self, did, protocol_id=None):
                return self._d

        failing_model = _FailingModel(fail_on=2)  # sample 0 warmup ok, sample 0 fails? see below
        # warmup uses samples[0]; loop starts again at samples[0]. fail_on=2 -> warmup ok, first real sample fails.
        ds = _FakeAdapter({"id": "sciq"}, _mk_samples(3))
        runner = DefaultBenchmarkRunner.__new__(DefaultBenchmarkRunner)
        runner.registry = _Reg(failing_model, ds)
        runner.artifact_store = __import__(
            "benchmark.core.artifacts", fromlist=["DefaultArtifactStore"]
        ).DefaultArtifactStore(tmp_path)

        with pytest.raises(RuntimeError, match="inference failed"):
            runner.run(
                run_id="a1",
                model_id="m",
                dataset_id="sciq",
                split="test",
                sample_count=3,
                seed=42,
                protocol_id="p",
                device="cpu",
            )


# ---------------------------------------------------------------------------
# A5: empty sample selection must not be COMPLETED
# ---------------------------------------------------------------------------


class TestA5EmptySelection:
    def test_zero_samples_raises(self, tmp_path):
        from benchmark.core.runner import DefaultBenchmarkRunner

        class _Reg:
            def get_model_config(self, mid):
                return {"id": mid}

            def get_dataset_config(self, did):
                return {"id": "sciq", "default_protocol_id": "p"}

            def get_protocol_config(self, pid):
                return {"prompt_template": "{text}", "version": "1.0.0"}

            def get_evaluator(self, key):
                from benchmark.evaluators.sciq import SciQEvaluator

                return SciQEvaluator()

            def get_model_adapter(self, mid):
                raise AssertionError("model must not load for empty selection")

            def get_dataset_adapter(self, did, protocol_id=None):
                return _FakeAdapter({"id": "sciq"}, [])

        runner = DefaultBenchmarkRunner.__new__(DefaultBenchmarkRunner)
        runner.registry = _Reg()
        runner.artifact_store = __import__(
            "benchmark.core.artifacts", fromlist=["DefaultArtifactStore"]
        ).DefaultArtifactStore(tmp_path)
        with pytest.raises(RuntimeError, match="eligible samples"):
            runner.run(
                run_id="a5",
                model_id="m",
                dataset_id="sciq",
                split="test",
                sample_count=5,
                seed=42,
                protocol_id="p",
                device="cpu",
            )


# ---------------------------------------------------------------------------
# B1: FaithEval strict evaluator must match instructed response
# ---------------------------------------------------------------------------


class TestB1FaithEvalStrict:
    def _eval(self):
        from benchmark.evaluators.faitheval import FaithEvalEvaluator

        return FaithEvalEvaluator()

    def _unans_sample(self, sid="f1"):
        return NormalizedSample(
            sample_id=sid,
            dataset_id="faitheval",
            dataset_revision="main",
            domain="contextual_faithfulness",
            task_type=TaskType.CONTEXTUAL_FAITHFULNESS,
            input_payload={"context": "c", "question": "q"},
            references={"type": "unanswerable", "answers": []},
        )

    def _pred(self, sid, raw):
        return _mk_record(sid, raw=raw)

    def test_strict_accepts_instructed_unanswerable_token(self):
        """Protocol prompt instructs 'UNANSWERABLE' -> strict must accept it."""
        metrics = self._eval().evaluate([self._pred("f1", "UNANSWERABLE")], [self._unans_sample("f1")])
        assert metrics["unanswerable_context_accuracy_strict"] == 1.0

    def test_strict_accepts_lowercase_unknown(self):
        metrics = self._eval().evaluate([self._pred("f1", "unknown")], [self._unans_sample("f1")])
        assert metrics["unanswerable_context_accuracy_strict"] == 1.0

    def test_loose_rejects_incidental_not(self):
        """'The answer is Paris.' contains no abstention semantics; but audit example
        'notebook' must not count as abstention via 'not' substring."""
        m = self._eval()
        metrics = m.evaluate([self._pred("f1", "notebook")], [self._unans_sample("f1")])
        assert metrics["unanswerable_context_accuracy_loose"] == 0.0

    def test_loose_rejects_real_answer(self):
        metrics = self._eval().evaluate([self._pred("f1", "The answer is Paris.")], [self._unans_sample("f1")])
        assert metrics["unanswerable_context_accuracy_loose"] == 0.0

    def test_loose_accepts_verbose_abstention(self):
        """'cannot determine' whole-word refusal counts as abstention."""
        m = self._eval()
        metrics = m.evaluate([self._pred("f1", "I cannot determine this from the context.")], [self._unans_sample("f1")])
        assert metrics["unanswerable_context_accuracy_loose"] == 1.0

    def test_loose_rejects_incidental_unknown_word_on_answerable(self):
        """'The unknown species is X' is an answer, not a refusal."""
        from benchmark.evaluators.faitheval import _is_abstention_loose

        assert not _is_abstention_loose("the unknown species is panthera tigris")
        assert not _is_abstention_loose("an unanswerable question in the exam was hard")
        assert _is_abstention_loose("unknown")
        assert _is_abstention_loose("unanswerable.")
        assert _is_abstention_loose("the answer is unknown")
        assert _is_abstention_loose("there is no information in the context")


# ---------------------------------------------------------------------------
# B2: FaithEval balanced_score must be unavailable without controls
# ---------------------------------------------------------------------------


class TestB2FaithEvalBalanced:
    def test_balanced_score_not_reported_when_no_controls(self):
        """Unanswerable-only runs (normal adapter) must not report balanced_score=0 as real."""
        from benchmark.evaluators.faitheval import FaithEvalEvaluator

        sample = NormalizedSample(
            sample_id="f1",
            dataset_id="faitheval",
            dataset_revision="main",
            domain="contextual_faithfulness",
            task_type=TaskType.CONTEXTUAL_FAITHFULNESS,
            input_payload={"context": "c", "question": "q"},
            references={"type": "unanswerable", "answers": []},
        )
        metrics = FaithEvalEvaluator().evaluate([_mk_record("f1", raw="unknown")], [sample])
        assert "balanced_score" not in metrics
        assert "answerable_control_accuracy" not in metrics
        assert metrics["control_samples"] == 0.0
    def test_balanced_score_present_with_controls(self):
        from benchmark.evaluators.faitheval import FaithEvalEvaluator

        samples = [
            NormalizedSample(
                sample_id="f1",
                dataset_id="faitheval",
                dataset_revision="main",
                domain="contextual_faithfulness",
                task_type=TaskType.CONTEXTUAL_FAITHFULNESS,
                input_payload={"context": "c", "question": "q"},
                references={"type": "unanswerable", "answers": []},
            ),
            NormalizedSample(
                sample_id="f2",
                dataset_id="faitheval",
                dataset_revision="main",
                domain="contextual_faithfulness",
                task_type=TaskType.CONTEXTUAL_FAITHFULNESS,
                input_payload={"context": "c", "question": "q"},
                references={"type": "control_answerable", "answers": ["Paris"]},
            ),
        ]
        preds = [_mk_record("f1", raw="unknown"), _mk_record("f2", raw="Paris")]
        metrics = FaithEvalEvaluator().evaluate(preds, samples)
        assert metrics["balanced_score"] == 1.0
        assert metrics["answerable_control_accuracy"] == 1.0
        assert metrics["control_samples"] == 1.0


# ---------------------------------------------------------------------------
# B7: evaluator pairing must be 1:1 and disclose mismatches
# ---------------------------------------------------------------------------


class TestB7Pairing:
    def _sciq(self, n):
        from benchmark.evaluators.sciq import SciQEvaluator

        return SciQEvaluator(), _mk_samples(n)

    def test_missing_predictions_fail_closed(self):
        evaluator, samples = self._sciq(3)
        with pytest.raises(ValueError, match="missing predictions"):
            evaluator.evaluate([_mk_record(samples[0].sample_id)], samples)

    def test_duplicate_predictions_fail_closed(self):
        evaluator, samples = self._sciq(2)
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            evaluator.evaluate(
                [_mk_record(samples[0].sample_id), _mk_record(samples[0].sample_id)], samples
            )

    def test_unknown_prediction_ids_fail_closed(self):
        evaluator, samples = self._sciq(1)
        with pytest.raises(ValueError, match="unknown"):
            evaluator.evaluate([_mk_record("ghost:id")], samples)

    def test_perfect_prediction_scores_full_accuracy(self):
        evaluator, samples = self._sciq(2)
        metrics = evaluator.evaluate(
            [_mk_record(samples[0].sample_id), _mk_record(samples[1].sample_id)], samples
        )
        assert metrics["accuracy"] == 1.0
        assert metrics["sample_count"] == 2.0
