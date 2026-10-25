"""Artifact storage: path-traversal-safe resolution and atomic file writes.

Authoritative source: docs/ARCHITECTURE.md Section 7.
"""

import contextlib
import json
import os
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from benchmark.core.types import ArtifactStore, PredictionRecord


class DefaultArtifactStore(ArtifactStore):
    """Encapsulates filesystem directory paths, atomic write locks, and path validation."""

    def __init__(self, artifacts_dir: Path | str = "artifacts") -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve()
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def get_run_dir(self, run_id: str) -> Path:
        """Resolve and ensure the directory for a specific run."""
        target = (self.artifacts_dir / run_id).resolve()
        if not target.is_relative_to(self.artifacts_dir) or target == self.artifacts_dir:
            raise ValueError(f"Path traversal detected in run_id: {run_id}")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def get_artifact_path(self, run_id: str, filename: str) -> str:
        """Return path-traversal-safe resolved path to artifact."""
        run_dir = self.get_run_dir(run_id)
        raw_target = run_dir / filename
        if raw_target.is_symlink():
            raise ValueError(f"Symlink detected: {filename}")
        target = raw_target.resolve()
        if not target.is_relative_to(run_dir):
            raise ValueError(f"Path traversal detected: {filename}")
        return str(target)

    def _atomic_write_text(self, target_path: Path, content: str) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_suffix(f".tmp.{uuid.uuid4().hex}")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(temp_path, target_path)
        finally:
            if temp_path.exists():
                with contextlib.suppress(OSError):
                    temp_path.unlink()

    def save_json(self, run_id: str, filename: str, data: dict[str, Any]) -> str:
        """Save a dictionary as a JSON file atomically."""
        final_path = Path(self.get_artifact_path(run_id, filename))
        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._atomic_write_text(final_path, content)
        return str(final_path)

    def save_predictions_jsonl(
        self, run_id: str, predictions: list[PredictionRecord]
    ) -> str:
        """Save prediction records as a JSONL file atomically."""
        final_path = Path(self.get_artifact_path(run_id, "predictions.jsonl"))
        lines: list[str] = []
        for p in predictions:
            record_dict = asdict(p) if is_dataclass(p) else dict(p)
            lines.append(json.dumps(record_dict, ensure_ascii=False))
        content = "\n".join(lines) + ("\n" if lines else "")
        self._atomic_write_text(final_path, content)
        return str(final_path)

    def append_log(self, run_id: str, text: str) -> str:
        """Append log line to logs.txt."""
        final_path = Path(self.get_artifact_path(run_id, "logs.txt"))
        with open(final_path, "a", encoding="utf-8") as f:
            f.write(text + "\n")
        return str(final_path)
