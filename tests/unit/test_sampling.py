"""Unit tests for deterministic sample selection and shortfall reporting.

Authoritative source: docs/EVALUATION_PROTOCOL.md Section 2 and Section 12.V2.
"""

from benchmark.core.artifacts import DefaultArtifactStore
from benchmark.core.sampling import (
    resolve_sample_count,
    select_samples,
)
from benchmark.core.types import NormalizedSample, TaskType


def _make_dummy_samples(n: int, prefix: str = "item") -> list[NormalizedSample]:
    return [
        NormalizedSample(
            sample_id=f"{prefix}:{i}",
            dataset_id="test_ds",
            dataset_revision="v1",
            domain="test",
            task_type=TaskType.MULTIPLE_CHOICE,
            input_payload={"index": i},
            references={"target": i},
        )
        for i in range(n)
    ]


def test_resolve_sample_count():
    assert resolve_sample_count(5) == 5
    assert resolve_sample_count("5") == 5
    assert resolve_sample_count("smoke") == 5
    assert resolve_sample_count("pilot") == 25
    assert resolve_sample_count("standard") == 100
    assert resolve_sample_count("full") is None
    assert resolve_sample_count(None) is None


def test_deterministic_sampling_reproducibility():
    samples = _make_dummy_samples(100)

    # Two runs with same seed must yield exact same order and subset
    sel1, rep1 = select_samples(
        samples, dataset_id="sciq", split="test", seed=42, requested_count=10
    )
    sel2, rep2 = select_samples(
        samples, dataset_id="sciq", split="test", seed=42, requested_count=10
    )

    assert [s.sample_id for s in sel1] == [s.sample_id for s in sel2]
    assert rep1["status"] == "ok"
    assert rep1["actual_samples"] == 10
    assert rep1["shortfall"] == 0

    # Run with different seed should produce different permutation
    sel3, _ = select_samples(
        samples, dataset_id="sciq", split="test", seed=999, requested_count=10
    )
    assert [s.sample_id for s in sel1] != [s.sample_id for s in sel3]


def test_deterministic_sampling_shortfall():
    # Only 5 samples available, requested 20
    samples = _make_dummy_samples(5)
    selected, report = select_samples(
        samples, dataset_id="wdc_pave", split="test", seed=42, requested_count=20
    )

    assert len(selected) == 5
    assert report["status"] == "shortfall"
    assert report["requested_samples"] == 20
    assert report["actual_samples"] == 5
    assert report["shortfall"] == 15


def test_deterministic_sampling_full():
    samples = _make_dummy_samples(15)
    selected, report = select_samples(
        samples, dataset_id="ifeval", split="train", seed=42, requested_count=None
    )

    assert len(selected) == 15
    assert report["status"] == "ok"
    assert report["actual_samples"] == 15
    assert report["shortfall"] == 0


def test_select_samples_architecture_spec():
    """Verify select_samples per ARCHITECTURE.md §11.1."""
    samples = _make_dummy_samples(10)
    sel, rep = select_samples(samples, "sciq", "test", seed=42, requested_count=5)
    assert len(sel) == 5
    assert rep["requested_samples"] == 5
    assert rep["actual_samples"] == 5
    assert rep["shortfall"] == 0

    # Shortfall path
    sel2, rep2 = select_samples(samples, "sciq", "test", seed=42, requested_count=20)
    assert len(sel2) == 10
    assert rep2["shortfall"] == 10


def test_artifact_store_path_traversal_rejection(tmp_path):
    """Verify that path traversal attempts (like prefix collision) are rejected."""
    store = DefaultArtifactStore(tmp_path / "artifacts")
    import pytest

    with pytest.raises(ValueError, match="Path traversal detected"):
        store.get_run_dir("../artifacts_evil")

    with pytest.raises(ValueError, match="Path traversal detected"):
        store.get_artifact_path("run1", "../../etc/passwd")
