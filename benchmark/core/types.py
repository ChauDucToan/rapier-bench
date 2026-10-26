"""Core benchmark domain interfaces and data types.

Authoritative source: docs/ARCHITECTURE.md Section 3.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class TaskType(StrEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    ATTRIBUTE_VALUE_EXTRACTION = "attribute_value_extraction"
    BINARY_CLASSIFICATION = "binary_classification"
    INSTRUCTION_FOLLOWING = "instruction_following"
    CONTEXTUAL_FAITHFULNESS = "contextual_faithfulness"


class ParseStatus(StrEnum):
    SUCCESS = "success"
    FALLBACK = "fallback"
    FAILED = "failed"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class GenerationOutput:
    raw_text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    model_id: str
    model_revision: str
    error: str | None = None


@dataclass(frozen=True)
class NormalizedSample:
    sample_id: str
    dataset_id: str
    dataset_revision: str
    domain: str
    task_type: TaskType
    input_payload: dict[str, Any]
    references: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParseResult:
    raw_output: str
    parsed_output: Any
    parse_status: ParseStatus
    parse_error: str | None = None


@dataclass(frozen=True)
class PredictionRecord:
    sample_id: str
    model_id: str
    model_revision: str
    protocol_version: str
    prompt_hash: str
    raw_output: str
    parsed_output: Any
    parse_status: str
    parse_error: str | None
    input_tokens: int
    output_tokens: int
    latency_ms: float
    error: str | None = None
    # C (Failure Analysis): reference target and evaluator verdict, persisted so
    # the prediction browser/API can display gold values and correctness without
    # re-evaluating. is_correct is None when correctness is not meaningful for
    # the task (e.g. IFEval multi-instruction, WDC-PAVE set-valued extraction).
    target: Any = None
    is_correct: bool | None = None


class ModelAdapter(ABC):
    @abstractmethod
    def load(self, device: str = "cuda") -> None:
        """Load model weights and tokenizer into memory."""
        ...

    @abstractmethod
    def generate(
        self, prompt: str, generation_config: dict[str, Any] | None = None
    ) -> GenerationOutput:
        """Run inference on the given prompt."""
        ...

    @abstractmethod
    def unload(self) -> None:
        """Unload model and free GPU memory completely."""
        ...

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Return True if model is loaded and ready for inference."""
        ...


class DatasetAdapter(ABC):
    @abstractmethod
    def list_splits(self) -> list[str]:
        """List available dataset splits."""
        ...

    @abstractmethod
    def load_samples(
        self, split: str, limit: int | None = None, seed: int = 42
    ) -> list[NormalizedSample]:
        """Load and normalize eligible dataset samples."""
        ...


class PromptBuilder(ABC):
    @abstractmethod
    def build_prompt(self, sample: NormalizedSample) -> tuple[str, str]:
        """Returns (formatted_prompt_text, sha256_prompt_hash). Never leaks ground-truth references."""
        ...


@runtime_checkable
class AnswerParser(Protocol):
    def parse(self, raw_output: str, sample: NormalizedSample) -> ParseResult:
        """Extract structured prediction from raw model generation text."""
        ...


class Evaluator(ABC):
    @abstractmethod
    def evaluate(
        self, predictions: list[PredictionRecord], samples: list[NormalizedSample]
    ) -> dict[str, float]:
        """Compute evaluation metrics from prediction records and samples."""
        ...


class MetricsCollector(ABC):
    @abstractmethod
    def record_inference(
        self, latency_ms: float, in_tokens: int, out_tokens: int, is_warmup: bool = False
    ) -> None:
        """Record timing and token metrics for a single inference call."""
        ...

    @abstractmethod
    def compute_summary(self) -> dict[str, float]:
        """Compute summary statistics."""
        ...


class ArtifactStore(ABC):
    @abstractmethod
    def save_json(self, run_id: str, filename: str, data: dict[str, Any]) -> str:
        """Save a dictionary as a JSON file atomically."""
        ...

    @abstractmethod
    def save_predictions_jsonl(
        self, run_id: str, predictions: list[PredictionRecord]
    ) -> str:
        """Save prediction records as a JSONL file atomically."""
        ...

    @abstractmethod
    def get_artifact_path(self, run_id: str, filename: str) -> str:
        """Return path-traversal-safe resolved path to artifact."""
        ...


@runtime_checkable
class ModelRegistry(Protocol):
    def get(self, model_id: str) -> ModelAdapter:
        ...

    def list_ids(self) -> list[str]:
        ...


@runtime_checkable
class DatasetRegistry(Protocol):
    def get(self, dataset_id: str) -> DatasetAdapter:
        ...

    def list_ids(self) -> list[str]:
        ...


class BenchmarkRunner(ABC):
    @abstractmethod
    def run(
        self,
        run_id: str,
        model_id: str,
        dataset_id: str,
        split: str,
        sample_count: int | None,
        seed: int,
        progress_callback: Any = None,
        cancel_check: Any = None,
    ) -> dict[str, Any]:
        ...
