"""Deterministic hash-based sample selection and shortfall reporting.

Authoritative source: docs/ARCHITECTURE.md Section 11.1 and
docs/EVALUATION_PROTOCOL.md Section 2.

There is exactly ONE selection path in this project: :func:`select_samples`.
Adapters, the CLI and the runner all route through it so that the same
(dataset, split, seed) always yields the same sample ids.
"""

import hashlib
from typing import Any


def resolve_sample_count(
    mode_or_int: str | int | None,
    dataset_config: dict[str, Any] | None = None,
) -> int | None:
    """Resolve a sampling mode string ('smoke', 'pilot', 'standard', 'full') or int string to count."""
    if mode_or_int is None:
        return None
    if isinstance(mode_or_int, int):
        return mode_or_int
    val = str(mode_or_int).strip().lower()
    if val == "full":
        return None
    if val.isdigit():
        return int(val)
    if dataset_config and "sampling_modes" in dataset_config:
        modes = dataset_config["sampling_modes"]
        if val in modes:
            return int(modes[val])
    defaults = {"smoke": 5, "pilot": 25, "standard": 100}
    if val in defaults:
        return defaults[val]
    raise ValueError(f"Unknown sampling mode or count: {mode_or_int}")


def select_samples(
    eligible_samples: list[Any],
    dataset_id: str,
    split: str,
    seed: int,
    requested_count: int | None,
) -> tuple[list[Any], dict[str, Any]]:
    """Deterministically select ``requested_count`` samples using the project-wide SHA-256 rule.

    Rule (docs/ARCHITECTURE.md §11.1):
        hash = SHA256(f"{dataset_id}:{split}:{seed}:{stable_id}")  ->  sort ascending  ->  take first N.

    Shortfall policy (docs/EVALUATION_PROTOCOL.md §2): never silently shrink and never raise.
    All eligible samples are returned, and the report carries an explicit ``shortfall``/
    ``status`` so the caller can warn and persist it.

    Returns:
        (selected_samples, report) where report has keys
        ``status`` ("ok" | "shortfall"), ``requested_samples``, ``actual_samples``, ``shortfall``.
    """
    total_eligible = len(eligible_samples)
    if requested_count is None or requested_count >= total_eligible:
        target_count = total_eligible
        shortfall = max(0, (requested_count or total_eligible) - total_eligible)
    else:
        target_count = requested_count
        shortfall = 0

    scored: list[tuple[str, str, Any]] = []
    for sample in eligible_samples:
        stable_id = getattr(sample, "sample_id", getattr(sample, "id", str(sample)))
        hash_key = f"{dataset_id}:{split}:{seed}:{stable_id}"
        sample_hash = hashlib.sha256(hash_key.encode("utf-8")).hexdigest()
        scored.append((sample_hash, stable_id, sample))

    # Tie-break by stable_id so the ordering is total and reproducible.
    scored.sort(key=lambda x: (x[0], x[1]))
    selected = [sample for _, _, sample in scored[:target_count]]

    shortfall_report = {
        "status": "shortfall" if shortfall > 0 else "ok",
        "requested_samples": requested_count if requested_count is not None else total_eligible,
        "actual_samples": len(selected),
        "shortfall": shortfall,
    }
    return selected, shortfall_report
