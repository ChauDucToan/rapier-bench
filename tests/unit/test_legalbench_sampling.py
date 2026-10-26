"""B4 regression: LegalBench stratified sampling must select exactly `limit`
samples with proportional subtask coverage, deterministically."""

from unittest.mock import patch

from benchmark.adapters.datasets.legalbench import LegalBenchDatasetAdapter


def _mk_adapter(sizes: dict[str, int]) -> LegalBenchDatasetAdapter:
    cfg = {
        "id": "legalbench_contract_nli",
        "revision": "main",
        "documented_subtasks": list(sizes.keys()),
    }
    return LegalBenchDatasetAdapter(cfg)


def _fake_rows(n: int):
    return [{"answer": "Yes" if i % 2 == 0 else "No", "text": f"t{i}", "document_name": "d"} for i in range(n)]


def _run_selection(sizes: dict[str, int], limit: int | None, seed: int = 42):
    adapter = _mk_adapter(sizes)

    def fake_load(hf_id, subtask, split, revision=None):
        return _fake_rows(sizes[subtask])

    fake_hyp = {subtask: "hypothetical clause" for subtask in sizes}
    with (
        patch("benchmark.adapters.datasets.legalbench.load_dataset", side_effect=fake_load),
        patch.dict("benchmark.adapters.datasets.legalbench.HYPOTHESES", fake_hyp),
    ):
        return adapter.load_samples("test", limit=limit, seed=seed)


_S = ["contract_nli_a", "contract_nli_b", "contract_nli_c", "contract_nli_d", "contract_nli_e"]


def test_stratified_selection_matches_requested_limit_exactly():
    sizes = dict(zip(_S, [82, 208, 142, 178, 180], strict=True))
    for limit in (1, 5, 6, 10, 25, 100, 400, 789):
        samples = _run_selection(sizes, limit)
        assert len(samples) == limit, f"limit={limit} got {len(samples)}"
        # every subtask with data is represented whenever limit >= #subtasks
        if limit >= len(sizes):
            got = {s.metadata["subtask"] for s in samples}
            assert got == set(sizes), f"limit={limit} missing subtasks: {set(sizes) - got}"


def test_stratified_selection_is_deterministic():
    sizes = dict(zip(_S[:3], [82, 208, 142], strict=True))
    s1 = _run_selection(sizes, 30, seed=42)
    s2 = _run_selection(sizes, 30, seed=42)
    assert [x.sample_id for x in s1] == [x.sample_id for x in s2]


def test_stratified_selection_seed_changes_set():
    sizes = dict(zip(_S[:3], [82, 208, 142], strict=True))
    s1 = _run_selection(sizes, 30, seed=42)
    s2 = _run_selection(sizes, 30, seed=7)
    assert [x.sample_id for x in s1] != [x.sample_id for x in s2]


def test_full_selection_returns_all_rows():
    sizes = {_S[0]: 82, _S[1]: 208}
    samples = _run_selection(sizes, None)
    assert len(samples) == 290


def test_small_limit_still_exactly_limit():
    # 5 equal subtasks, limit=6: naive round() gives 1 each -> 5 (undershoot).
    sizes = dict(zip(_S, [100] * 5, strict=True))
    samples = _run_selection(sizes, 6)
    assert len(samples) == 6
