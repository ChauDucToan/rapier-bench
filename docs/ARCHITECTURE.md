# Rapier Bench Architecture Specification

System architecture, contracts, schema, and API specification for Rapier Bench.

---

## 1. Repository Layout, File Ownership & Hardware Reality

### 1.1 Directory Tree
```text
/home/heheboiz/data/rapier-bench/
├── .gitignore
├── pyproject.toml
├── docker-compose.yml
├── README.md
├── LICENSE
├── flake.nix
├── configs/
│   ├── models.yaml
│   ├── datasets.yaml
│   └── protocols/
│       ├── sciq.yaml
│       ├── wdc_pave.yaml
│       ├── legalbench.yaml
│       ├── ifeval.yaml
│       └── faitheval.yaml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── ENVIRONMENT.md
│   ├── HARDWARE.md
│   ├── MODEL_COMPATIBILITY.md
│   └── EVALUATION_PROTOCOL.md
├── scripts/
│   ├── dev.sh
│   └── setup_env.sh
├── backend/
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── session.py
│       │   └── models.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── auth.py
│       │   ├── model.py
│       │   ├── dataset.py
│       │   ├── benchmark.py
│       │   ├── comparison.py
│       │   ├── leaderboard.py
│       │   └── recommendation.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── deps.py
│       │   ├── auth.py
│       │   ├── models.py
│       │   ├── datasets.py
│       │   ├── benchmarks.py
│       │   ├── comparisons.py
│       │   ├── leaderboard.py
│       │   └── recommendations.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── auth_service.py
│       │   ├── benchmark_service.py
│       │   ├── recommendation_engine.py
│       │   └── gpu_manager.py
│       └── jobs/
│           ├── __init__.py
│           ├── runner.py
│           └── process_manager.py
├── benchmark/
│   ├── __init__.py
│   ├── cli.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── types.py
│   │   ├── registry.py
│   │   ├── runner.py
│   │   ├── metrics.py
│   │   ├── artifacts.py
│   │   ├── hardware.py
│   │   ├── prompt.py
│   │   └── sampling.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── hf_causal.py
│   │   └── datasets/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── sciq.py
│   │       ├── wdc_pave.py
│   │       ├── legalbench.py
│   │       ├── ifeval.py
│   │       └── faitheval.py
│   ├── evaluators/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── sciq.py
│   │   ├── wdc_pave.py
│   │   ├── legalbench.py
│   │   ├── ifeval.py
│   │   └── faitheval.py
│   └── vendor/
│       ├── __init__.py
│       └── ifeval/
│           ├── __init__.py
│           ├── instructions.py
│           ├── instructions_registry.py
│           ├── instructions_util.py
│           ├── evaluation_lib.py
│           ├── SOURCE.md
│           └── nltk_data/
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── eslint.config.mjs
│   ├── vitest.config.ts
│   ├── playwright.config.ts
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx
│       │   ├── globals.css
│       │   ├── login/page.tsx
│       │   ├── register/page.tsx
│       │   ├── dashboard/page.tsx
│       │   ├── models/page.tsx
│       │   ├── datasets/page.tsx
│       │   ├── benchmarks/
│       │   │   ├── page.tsx
│       │   │   ├── new/page.tsx
│       │   │   ├── [id]/page.tsx
│       │   │   └── [id]/BenchmarkDetailClient.tsx
│       │   ├── compare/page.tsx
│       │   ├── leaderboard/page.tsx
│       │   ├── recommend/page.tsx
│       │   ├── history/page.tsx
│       │   └── profile/page.tsx
│       ├── features/
│       │   └── auth/
│       │       ├── index.ts
│       │       ├── AuthContext.tsx
│       │       └── RequireAuth.tsx
│       ├── components/
│       │   ├── Header.tsx
│       │   └── StatusState.tsx
│       ├── lib/
│       │   ├── api.ts
│       │   └── formatters.ts
│       └── types/
│           └── api.ts
├── tests/
│   ├── conftest.py
│   ├── __init__.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_evaluators.py
│   │   ├── test_prompt_builder.py
│   │   ├── test_sampling.py
│   │   ├── test_parsers.py
│   │   └── test_ifeval_vendor.py
│   ├── integration/
│   │   ├── test_api_auth.py
│   │   ├── test_api_benchmarks.py
│   │   ├── test_api_recommendation.py
│   │   ├── test_ownership.py
│   │   └── test_integration_regressions.py
│   └── fixtures/
│       ├── sciq_gold.json
│       ├── wdc_gold.json
│       ├── legalbench_gold.json
│       ├── ifeval_gold.json
│       └── faitheval_gold.json
└── artifacts/                 # Ignored by git, created at runtime
```

### 1.2 File Ownership Table

| Workstream | Owned Paths | Description |
|---|---|---|
| **Architect** | `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_PLAN.md`, `configs/` | System contracts, schema, configs, protocols |
| **Backend Core** | `backend/app/`, `docker-compose.yml`, `pyproject.toml` | FastAPI, DB models, schemas, auth, API routes, jobs supervisor |
| **Benchmark Engine** | `benchmark/core/`, `benchmark/adapters/`, `benchmark/evaluators/`, `benchmark/cli.py` | Model/dataset adapters, evaluators, execution engine, CLI |
| **Frontend UI** | `frontend/` | Next.js App Router, React components, state, API client (`src/lib/api.ts`) |
| **Testing & QA** | `tests/` | Unit, integration, gold fixtures, regression tests |

*Frontend API Contract Rule*: All frontend API calls route exclusively through `src/lib/api.ts` (`ApiError`, `request<T>()` with `credentials: "include"`, `API_BASE` from `NEXT_PUBLIC_API_BASE_URL`). Every state mutation (`POST`, `PUT`, `DELETE`, `PATCH`) MUST send the custom CSRF header: `X-Rapier-Action: 1`.

### 1.3 Execution Environment & Hardware Reality
1. **Physical Host Constraints**:
   - The execution host is a single laptop with an **NVIDIA GeForce RTX 3050 Laptop GPU** with **4096 MiB (4 GiB) VRAM** and a root partition at **98% capacity (~3.7 GiB free)**.
2. **Serialization & Memory Management**:
   - The database row lock (`gpu_locks`) strictly serializes ALL benchmark runs across the system (maximum 1 active inference job).
   - Models are loaded and unloaded strictly sequentially. Between successive runs, the runner MUST execute:
     ```python
     import gc, torch
     if torch.cuda.is_available():
         torch.cuda.empty_cache()
         torch.cuda.ipc_collect()
     gc.collect()
     ```
   - Maximum generation lengths (`max_new_tokens`) are capped at 512 tokens to guarantee operation within 4 GiB VRAM.
3. **CPU Fallback**:
   - `--device cpu` is reserved exclusively for unit/mock testing in CI without a GPU.
4. **Latency Honesty Rule**:
   - All recorded inference latencies, throughputs, and memory metrics reflect this specific 4 GiB mobile workstation. They **MUST NOT** be represented or directly compared against server-grade hardware (A100/H100/L40S).

---

## 2. Python Packaging & Tooling Decision

Single root `pyproject.toml` with editable install (`pip install -e .` or `uv pip install -e .`). Package mapping exports two top-level modules: `app` (from `backend/app`) and `benchmark` (from `benchmark/`). Python target is 3.13 (`requires-python = ">=3.12"`).

*CUDA Torch Distribution Note*: To avoid exhausting the ~3.7 GB free disk with large PyPI binary wheels, PyTorch (`torch 2.14.1+cu130`) is provisioned via shared environment (`.pth` pointer or `scripts/setup_env.sh`). It is excluded from default `dependencies` and declared under `[project.optional-dependencies] gpu`.

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "rapier-bench"
version = "0.1.0"
description = "Domain-aware AI model benchmarking platform"
requires-python = ">=3.12"
dependencies = [
    "fastapi==0.142.2",
    "uvicorn[standard]==0.54.0",
    "pydantic==2.13.5",
    "sqlalchemy==2.0.44",
    "argon2-cffi==25.1.0",
    "httpx==0.28.1",
    "pyyaml==6.0.3",
    "python-multipart==0.0.20",
    "jinja2==3.1.6",
    "orjson==3.11.3",
    # PINNED-BY: docs/MODEL_COMPATIBILITY.md
    "transformers==5.15.0",
    "accelerate==1.4.0",
    "safetensors==0.8.0",
    "numpy==2.5.4",
    "datasets==2.21.0", # Verified: EVALUATION_PROTOCOL §12.6 (Python 3.13 + transformers 5.15.0)
]

[project.optional-dependencies]
gpu = [
    "torch==2.14.1", # torch is provided by scripts/setup_env.sh (shared CUDA install or --index-url https://download.pytorch.org/whl/cu130)
]
dev = [
    "pytest==9.1.1",
    "pytest-asyncio==1.3.0",
    "ruff==0.14.2",
]

[tool.setuptools.package-dir]
app = "backend/app"
benchmark = "benchmark"

[tool.setuptools.packages.find]
where = ["backend", "."]
include = ["app*", "benchmark*"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]

[tool.pytest.ini_options]
minversion = "8.0"
addopts = "-ra -q --strict-markers"
testpaths = ["tests"]
asyncio_mode = "auto"
```

---

## 3. Benchmark Core Interfaces

All interfaces use strict typing.

### 3.1 ABC vs Protocol Rationale
- `ModelAdapter` (**ABC**): Requires shared state (model reference, tokenizer, device mapping, loaded status).
- `DatasetAdapter` (**ABC**): Requires common validation, dataset caching, and split inspection helpers.
- `AnswerParser` (**Protocol**): Stateless parsing function with signature polymorphism.
- `Evaluator` (**ABC**): Requires shared aggregation helpers, error rate computation, and summary metric logging.
- `PromptProtocol` / `PromptBuilder` (**ABC**): Needs template variable substitution, validation, and SHA-256 prompt hashing.
- `MetricsCollector` (**ABC**): Needs state accumulation, CUDA synchronization hooks, and quantile computation.
- `ArtifactStore` (**ABC**): Encapsulates filesystem directory paths, atomic write locks, and path validation.
- `ModelRegistry` / `DatasetRegistry` (**Protocol**): Stateless lookup by ID.
- `BenchmarkRunner` (**ABC**): Manages run loop, cancellation polling, DB heartbeat, and artifact serialization.

### 3.2 Interface Signatures (`benchmark/core/types.py`)

```python
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

class ModelAdapter(ABC):
    @abstractmethod
    def load(self, device: str = "cuda") -> None: ...
    @abstractmethod
    def generate(self, prompt: str, generation_config: dict[str, Any]) -> GenerationOutput: ...
    @abstractmethod
    def unload(self) -> None: ...
    @property
    @abstractmethod
    def is_loaded(self) -> bool: ...

class DatasetAdapter(ABC):
    @abstractmethod
    def list_splits(self) -> list[str]: ...
    @abstractmethod
    def load_samples(self, split: str, limit: int | None = None, seed: int = 42) -> list[NormalizedSample]: ...

class PromptBuilder(ABC):
    @abstractmethod
    def build_prompt(self, sample: NormalizedSample) -> tuple[str, str]:
        """Returns (formatted_prompt_text, sha256_prompt_hash). Never leaks ground-truth references."""
        ...

@runtime_checkable
class AnswerParser(Protocol):
    def parse(self, raw_output: str, sample: NormalizedSample) -> ParseResult: ...

class Evaluator(ABC):
    @abstractmethod
    def evaluate(self, predictions: list[PredictionRecord], samples: list[NormalizedSample]) -> dict[str, float]: ...

class MetricsCollector(ABC):
    @abstractmethod
    def record_inference(self, latency_ms: float, in_tokens: int, out_tokens: int, is_warmup: bool = False) -> None: ...
    @abstractmethod
    def compute_summary(self) -> dict[str, float]: ...

class ArtifactStore(ABC):
    @abstractmethod
    def save_json(self, run_id: str, filename: str, data: dict[str, Any]) -> str: ...
    @abstractmethod
    def save_predictions_jsonl(self, run_id: str, predictions: list[PredictionRecord]) -> str: ...
    @abstractmethod
    def get_artifact_path(self, run_id: str, filename: str) -> str: ...

@runtime_checkable
class ModelRegistry(Protocol):
    def get(self, model_id: str) -> ModelAdapter: ...
    def list_ids(self) -> list[str]: ...

@runtime_checkable
class DatasetRegistry(Protocol):
    def get(self, dataset_id: str) -> DatasetAdapter: ...
    def list_ids(self) -> list[str]: ...

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
        """
        Executes sample selection, inference, parsing, evaluation, and artifact emission.
        If sample_count exceeds eligible records M, proceeds with M samples, logs a WARNING,
        and records shortfall without raising an exception.
        """
        ...
```

---

## 4. Inference Contract

### 4.1 Prediction Record JSON Shape (`predictions.jsonl`)
Every line in `predictions.jsonl` strictly follows this shape:
```json
{
  "sample_id": "sciq:test:0014",
  "model_id": "LiquidAI/LFM2.5-350M",
  "model_revision": "9e6c6ccf47cd318696e137d381a7ded8fe4df09f",
  "protocol_version": "1.0.0",
  "prompt_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "raw_output": "The correct answer is B.",
  "parsed_output": "B",
  "parse_status": "success",
  "parse_error": null,
  "input_tokens": 128,
  "output_tokens": 8,
  "latency_ms": 32.4,
  "error": null
}
```

### 4.2 Decoding and Execution Policy
1. **Greedy Decoding Default**:
   ```python
   generation_defaults = {
       "do_sample": False,
       "temperature": 0.0,
       "max_new_tokens": 512,
       "repetition_penalty": 1.0,
   }
   ```
2. **Warmup**: Always execute 1 warmup inference sample before benchmarking; discard latency from metrics.
3. **Inference Context & Synchronization**:
   ```python
   with torch.inference_mode():
       if torch.cuda.is_available():
           torch.cuda.synchronize()
       t0 = time.perf_counter()
       output = model.generate(**inputs, **gen_config)
       if torch.cuda.is_available():
           torch.cuda.synchronize()
       latency_ms = (time.perf_counter() - t0) * 1000.0
   ```

### 4.3 Aggregated Metrics JSON Shape (`metrics.json`)
The benchmark engine computes summary latency and throughput metrics via `DefaultMetricsCollector` (`benchmark/core/metrics.py`). The authoritative summary metric keys are:
```json
{
  "latency_ms_mean": 32.45,
  "latency_ms_median": 31.80,
  "latency_ms_p50": 31.80,
  "latency_ms_p95": 45.20,
  "tokens_per_sec": 38.50,
  "model_load_time_s": 1.25,
  "total_input_tokens": 1280.0,
  "total_output_tokens": 80.0,
  "sample_count": 10.0,
  "accuracy": 0.80
}
```
*Latency Metric Key Rule*: Summary latency statistics MUST be named `latency_ms_mean`, `latency_ms_median`, `latency_ms_p50`, and `latency_ms_p95`. Informal or legacy names such as `avg_latency_ms` are prohibited across the API, comparison, leaderboard, and recommendation engines. Per-prediction lines in `predictions.jsonl` continue to record `latency_ms` for individual sample execution times.

---

## 5. Persistence Schema (SQLAlchemy 2)

All DB operations enforce foreign keys: `PRAGMA foreign_keys = ON;`.

*Privacy Default Rule*: All runs have `is_private = True` by default. Private runs are visible and manageable solely by their owner. Owners can explicitly set `is_private = False` to publish results to the public leaderboard and comparison views.

```python
import enum
from datetime import datetime
from typing import Any
from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, JSON, Index, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class RunStatusEnum(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    runs: Mapped[list["BenchmarkRun"]] = relationship(back_populates="user")

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True) # SHA-256 of session token
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    user: Mapped["User"] = relationship(back_populates="sessions")

class ModelDefinition(Base):
    __tablename__ = "model_definitions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True) # e.g. "lfm2.5-350m"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    hf_id: Mapped[str] = mapped_column(String(255), nullable=False)
    revision: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[int] = mapped_column(Integer, nullable=False)
    context_length: Mapped[int] = mapped_column(Integer, nullable=False)
    torch_dtype: Mapped[str] = mapped_column(String(32), default="bfloat16")
    vram_weight_gb: Mapped[float] = mapped_column(Float, nullable=False)
    trust_remote_code: Mapped[bool] = mapped_column(Boolean, default=False)
    license: Mapped[str] = mapped_column(String(64), nullable=False)

class DatasetDefinition(Base):
    __tablename__ = "dataset_definitions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True) # e.g. "sciq"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    hf_id: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    default_split: Mapped[str] = mapped_column(String(32), default="test")
    evaluator_key: Mapped[str] = mapped_column(String(64), nullable=False)

class BenchmarkProtocol(Base):
    __tablename__ = "benchmark_protocols"
    id: Mapped[str] = mapped_column(String(64), primary_key=True) # e.g. "sciq_evidence_grounded"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_definitions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer_format: Mapped[str] = mapped_column(String(64), nullable=False)

class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True) # UUID4
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    model_id: Mapped[str] = mapped_column(ForeignKey("model_definitions.id"), index=True, nullable=False)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_definitions.id"), index=True, nullable=False)
    protocol_id: Mapped[str] = mapped_column(ForeignKey("benchmark_protocols.id"), nullable=False)
    split: Mapped[str] = mapped_column(String(32), default="test")
    sample_size_mode: Mapped[str] = mapped_column(String(32), default="smoke")
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, default=42)
    is_private: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False) # PRIVATE BY DEFAULT
    status: Mapped[RunStatusEnum] = mapped_column(Enum(RunStatusEnum), default=RunStatusEnum.QUEUED, index=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_selection: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True) # Includes sample_shortfall dict
    generation_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    hardware_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="runs")
    metrics: Mapped[list["BenchmarkMetric"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="run", cascade="all, delete-orphan")

class BenchmarkMetric(Base):
    __tablename__ = "benchmark_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)

    run: Mapped["BenchmarkRun"] = relationship(back_populates="metrics")
    __table_args__ = (Index("ix_run_metric", "run_id", "metric_name"),)

class PredictionIndex(Base):
    __tablename__ = "prediction_indices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    sample_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)

class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False) # "predictions", "metrics", "logs"
    relative_path: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    run: Mapped["BenchmarkRun"] = relationship(back_populates="artifacts")

class RecommendationPreference(Base):
    __tablename__ = "recommendation_preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    weight_quality: Mapped[float] = mapped_column(Float, default=0.5)
    weight_latency: Mapped[float] = mapped_column(Float, default=0.3)
    weight_vram: Mapped[float] = mapped_column(Float, default=0.2)
    max_vram_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

class GpuLock(Base):
    __tablename__ = "gpu_locks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True) # Always 1
    holder_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

---

## 6. Job Execution & Concurrency Protocol

1. **Submission**:
   - Backend commits `BenchmarkRun` row with status `QUEUED`.
   - Backend spawns background subprocess via:
     `[sys.executable, "-m", "app.jobs.runner", run_id]`
   - NEVER `shell=True`. Arguments are validated from allowlisted model and dataset IDs.
2. **Single GPU Slot (`gpu_lock` row)**:
   - *Rationale*: A single SQLite table `gpu_locks` with a single row (`id=1`) guarantees mutual exclusion across processes without external brokers like Redis.
   - Worker attempts: `UPDATE gpu_locks SET holder_run_id = :run_id, acquired_at = CURRENT_TIMESTAMP WHERE id = 1 AND holder_run_id IS NULL;`
   - If rowcount == 0, worker waits/retries with exponential backoff. On finish/failure, worker sets `holder_run_id = NULL`.
3. **Progress & Cancellation**:
   - Child runner writes `progress_done` and `progress_total` into DB every $N$ samples (or 5s).
   - Parent signals cancellation by updating DB: `cancel_requested = True`.
   - Child checks `cancel_requested` in DB between samples; if `True`, it stops inference, unloads model, cleans GPU memory (`torch.cuda.empty_cache()`, `gc.collect()`), marks run `CANCELLED`, releases `gpu_lock`, and exits 0.
4. **Stale Run Reconciliation at Startup**:
   - When FastAPI server starts:
     `UPDATE benchmark_runs SET status = 'failed', error_text = 'Orphaned run reconciled at startup' WHERE status IN ('queued', 'running');`
     `UPDATE gpu_locks SET holder_run_id = NULL, acquired_at = NULL WHERE id = 1;`

---

## 7. Artifact Layout & Serving

### 7.1 Filesystem Structure
```text
artifacts/
└── <run_id>/
    ├── predictions.jsonl   # Exact JSON per inference line
    ├── metrics.json         # Aggregated metrics dict
    ├── run_config.json      # Frozen config, sample selection, seed, shortfall report
    ├── hardware.json        # GPU model, driver, VRAM, platform
    └── logs.txt             # Runner stdout/stderr logs
```

### 7.2 Atomic Writes
Every file is written to `<path>.tmp.<uuid>` first, then committed via `os.replace(temp_path, final_path)`.

### 7.3 Path-Traversal-Safe Serving
```python
def safe_artifact_path(artifacts_dir: Path, run_id: str, filename: str) -> Path:
    target = (artifacts_dir / run_id / filename).resolve()
    base = artifacts_dir.resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return target
```

---

## 8. API Contract

Plain Pydantic models. Errors use standard FastAPI envelope: `{"detail": "Error description"}`. Pagination uses query params `limit` (default 50, max 100) and `offset` (default 0).

### 8.1 Endpoint Table & Unambiguous Auth Contract

| Method | Path | Auth Requirement | Request Body | Response Status & Body | Non-200 Statuses |
|---|---|---|---|---|---|
| `POST` | `/api/v1/auth/register` | `public` | `RegisterRequest` | `201` `UserResponse` | `400` (exists), `422` |
| `POST` | `/api/v1/auth/login` | `public` | `LoginRequest` | `200` `UserResponse` + Set-Cookie | `401` (invalid creds) |
| `POST` | `/api/v1/auth/logout` | `auth-required` | None | `200` `{"status": "logged_out"}` | `401` |
| `GET` | `/api/v1/auth/me` | `auth-required` | None | `200` `UserResponse` | `401` |
| `GET` | `/api/v1/models` | `public` | Query: `?domain=&limit=&offset=` | `200` `list[ModelResponse]` | `422` |
| `GET` | `/api/v1/models/{id}` | `public` | None | `200` `ModelResponse` | `404` |
| `GET` | `/api/v1/datasets` | `public` | Query: `?domain=&limit=&offset=` | `200` `list[DatasetResponse]` | `422` |
| `GET` | `/api/v1/datasets/{id}` | `public` | None | `200` `DatasetResponse` | `404` |
| `POST` | `/api/v1/benchmarks` | `auth-required` | `CreateBenchmarkRequest` | `202` `BenchmarkRunResponse` | `400`, `409` (busy) |
| `GET` | `/api/v1/benchmarks` | `public` | Query: `?model_id=&domain=&status=&limit=&offset=` | `200` `PaginatedRunsResponse` | `422` |
| `GET` | `/api/v1/benchmarks/{id}`| `owner-or-public` | None | `200` `BenchmarkRunResponse` | `404` |
| `GET` | `/api/v1/benchmarks/{id}/status` | `owner-or-public` | None | `200` `RunStatusResponse` | `404` |
| `GET` | `/api/v1/benchmarks/{id}/results` | `owner-or-public` | None | `200` `RunResultsResponse` | `404` |
| `GET` | `/api/v1/benchmarks/{id}/predictions` | `owner-or-public` | Query: `?status=&limit=&offset=` | `200` `PaginatedPredictionsResponse` | `404` |
| `POST` | `/api/v1/benchmarks/{id}/cancel` | `owner-only` | None | `200` `RunStatusResponse` | `401`, `403`, `404`, `409` |
| `POST` | `/api/v1/benchmarks/{id}/rerun` | `owner-only` | None | `202` `BenchmarkRunResponse` | `401`, `403`, `404` |
| `GET` | `/api/v1/benchmarks/{id}/export` | `owner-or-public` | Query: `?format=jsonl|csv` | `200` File stream | `404` |
| `GET` | `/api/v1/comparisons` | `public` | Query: `?run_ids=id1,id2,id3` | `200` `ComparisonResponse` | `400` (<2 ids), `404` |
| `GET` | `/api/v1/leaderboard` | `public` | Query: `?domain=&task_type=` | `200` `LeaderboardResponse` | `422` |
| `POST` | `/api/v1/recommendations` | `public` | `RecommendationRequest` | `200` `RecommendationResponse` | `400`, `422` |

### 8.2 Privacy & 403 vs 404 Access Rule
1. **Creation Default**: `CreateBenchmarkRequest` includes `"is_private": true` by default.
2. **GET Requests (`owner-or-public`)**: If a run has `is_private == True` and the requester is unauthenticated or `requester.id != run.user_id`, the API returns **`404 Not Found`**. This avoids leaking whether a specific run ID exists.
3. **Mutation Requests (`owner-only`)**: For `/cancel` and `/rerun`:
   - If unauthenticated $\to$ **`401 Unauthorized`**.
   - If authenticated but `requester.id != run.user_id` $\to$ **`403 Forbidden`** (the requester explicitly knows the run exists and attempted an unauthorized state change).
   - If run does not exist $\to$ **`404 Not Found`**.

---

## 9. Auth & Security Contract

1. **Password Hashing**:
   - `argon2-cffi` (argon2id variant).
   - Parameters: `time_cost=2`, `memory_cost=65536` (64 MiB), `parallelism=1`.
2. **Session Token & Storage**:
   - Generated via `secrets.token_urlsafe(32)` (256 bits).
   - SHA-256 hash stored in `sessions.id` with `expires_at` (7 days expiry). Raw token is never stored in DB.
3. **Session Cookie**:
   - Name: `rapier_session`.
   - Attributes: `HttpOnly=True`, `SameSite="Lax"`, `Secure` (controlled by `SECURE_COOKIES=true` in production), `Max-Age=604800` (7 days), `Path="/"`.
   - Never store auth tokens in browser `localStorage` or `sessionStorage`.
4. **CSRF Strategy**:
   - SameSite="Lax" protects against standard cross-site form posts.
   - For all state-changing API requests (`POST`, `PUT`, `DELETE`, `PATCH`), client must provide custom header: `X-Rapier-Action: 1`. Browsers prevent cross-origin JS from setting custom headers without explicit CORS preflight.
   - Frontend `src/lib/api.ts` automatically attaches `X-Rapier-Action: 1` on all mutations.
5. **Authorization Semantics**:
   - Missing or expired session on protected route $\to$ `401 Unauthorized`.
   - Valid session but user does not own resource on mutation $\to$ `403 Forbidden`.

---

## 10. Recommendation Contract

### 10.1 Input Schema (`RecommendationRequest`)
```json
{
  "domain": "education",
  "task_type": "multiple_choice",
  "constraints": {
    "max_vram_gb": 4.0,
    "max_latency_ms": 150.0,
    "min_quality": 0.50
  },
  "weights": {
    "quality": 0.5,
    "latency": 0.3,
    "vram": 0.2
  }
}
```

### 10.2 Normalization & Scoring Formula
1. **Eligibility Filter**: Runs must match `domain`, have `status == 'completed'`, and satisfy hard constraints:
   $\text{VRAM} \le \text{max\_vram\_gb}$, $\text{Latency} \le \text{max\_latency\_ms}$, $\text{PrimaryMetric} \ge \text{min\_quality}$.
   - Evaluates $\text{Latency}$ using summary metric `latency_ms_mean` (falling back to `latency_ms_median` if mean is absent).
2. **Comparable Models Check**:
   - If fewer than 3 unique models have completed runs for the target domain/task, return status `insufficient_sample`. **Never invent scores or fabricate synthetic rankings.**
3. **Normalization (Min-Max)**:
   For model $m$ among eligible candidates:
   $$Q_{\text{norm}}(m) = \frac{\text{Quality}(m) - \min(Q)}{\max(Q) - \min(Q) + \epsilon}$$
   $$L_{\text{norm}}(m) = \frac{\max(L) - \text{Latency}(m)}{\max(L) - \min(L) + \epsilon} \quad \text{(lower latency is better, using } \text{latency\_ms\_mean)}$$
   $$V_{\text{norm}}(m) = \frac{\max(V) - \text{VRAM}(m)}{\max(V) - \min(V) + \epsilon} \quad \text{(lower VRAM is better)}$$
   $$\text{CompositeScore}(m) = w_q \cdot Q_{\text{norm}} + w_l \cdot L_{\text{norm}} + w_v \cdot V_{\text{norm}}$$
4. **Deterministic Tie-Breaking**:
   Sort order: `CompositeScore DESC`, `PrimaryMetric DESC`, `latency_ms_mean ASC`, `ModelID ASC`.
5. **Output**: Ranked list + per-model breakdown + limitations + explanation string.
6. **Hard Rule**: Recommendations calculate solely over historical DB runs and **NEVER trigger inference**.

---

## 11. Sampling Contract

### 11.1 Hash-Based Sampling Algorithm
Sampling uses a deterministic hash rule to guarantee that upstream record reordering does not alter sample selection.
The function `select_samples()` lives in `benchmark/core/sampling.py` and is the **SOLE** sample selection path used by the CLI, the benchmark runner, and dataset adapters:

```python
import hashlib
from typing import Any

def select_samples(
    eligible_samples: list[Any],
    dataset_id: str,
    split: str,
    seed: int,
    requested_count: int | None
) -> tuple[list[Any], dict[str, int]]:
    """
    Deterministically selects N samples using the project-wide SHA-256 hash rule.
    Returns (selected_samples, shortfall_report).
    """
    total_eligible = len(eligible_samples)
    if requested_count is None or requested_count >= total_eligible:
        target_count = total_eligible
        shortfall = max(0, (requested_count or total_eligible) - total_eligible)
    else:
        target_count = requested_count
        shortfall = 0

    # Deterministic SHA256 score per record
    scored = []
    for sample in eligible_samples:
        stable_id = sample.sample_id
        hash_key = f"{dataset_id}:{split}:{seed}:{stable_id}"
        sample_hash = hashlib.sha256(hash_key.encode("utf-8")).hexdigest()
        scored.append((sample_hash, sample))

    # Sort ascending by hash
    scored.sort(key=lambda x: x[0])
    selected = [s for _, s in scored[:target_count]]

    shortfall_report = {
        "requested_samples": requested_count or total_eligible,
        "actual_samples": len(selected),
        "shortfall": shortfall,
    }
    return selected, shortfall_report
```

### 11.2 Shortfall Behavior
- If $M < N$ eligible records exist:
  1. The loader **MUST NOT** silently shrink and **MUST NOT** raise an exception.
  2. The runner proceeds with all $M$ eligible samples (ensuring smoke runs on small sets succeed).
  3. The runner writes `shortfall_report` into `run_config.json`.
  4. The runner records `sample_shortfall` into `benchmark_runs.sample_selection` JSON in SQLite.
  5. The runner logs a structured `WARNING: Requested {N} samples but only {M} eligible. Shortfall: {N-M}`.
  6. The shortfall is surfaced in the `/results` and `/status` API responses.

### 11.3 Sample Size Tiers
- `smoke`: 5–10 samples.
- `pilot`: 20–30 samples.
- `standard`: 100–200 samples.
- `full`: 100% of the designated evaluation split.

---

## 12. Testing & CLI Contracts

### 12.1 Testing Strategy
- **Unit**:
  - `test_evaluators.py`: Test all 5 evaluators against deterministic gold fixture JSON files (`tests/fixtures/*_gold.json`).
  - `test_prompt_builder.py`: Verify prompt string rendering and SHA-256 reproducibility without ground-truth leaks.
  - `test_sampling.py`: Verify deterministic SHA-256 sample selection, hash ordering, and shortfall reporting.
- **Integration**:
  - `test_runner_dry_run.py`: Verify benchmark CLI and runner with `--dry-run` against SQLite in-memory DB.
  - `test_api_auth.py`: Verify registration, login cookie, logout, me, and 401/403/404 guards.
  - `test_api_benchmarks.py`: Verify benchmark creation, status polling, private run 404 guard, and result retrieval.

### 12.2 CLI Contract (`benchmark.cli`)
```bash
python -m benchmark.cli run \
    --model <model_id> \
    --dataset <dataset_id> \
    --split <split> \
    --protocol <protocol_id> \
    --samples <mode_or_int> \
    --seed <int> \
    [--dry-run] \
    [--device <cuda|cpu>] \
    [--output-dir <path>]
```
- `--dry-run`: Selects samples via `select_samples()`, renders prompts, logs IDs and prompt hashes, verifies configs, and exits `0` without loading model weights or running GPU inference.

---

## 13. Environment Variables & Configuration

Default values defined in `backend/app/config.py`:

| Variable | Default Value | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./rapier.db` | SQLite connection URL |
| `ARTIFACTS_DIR` | `./artifacts` | Directory for run artifacts |
| `SECRET_KEY` | `dev-insecure-secret-key-change-in-prod` | Key for cryptographic hashing |
| `CUDA_VISIBLE_DEVICES` | `0` | GPU device ID |
| `HF_HOME` | `~/.cache/huggingface` | Hugging Face cache root |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS permitted origins |
| `SECURE_COOKIES` | `false` | Enable Secure flag on session cookies |
| `ENV` | `development` | `development` or `production` |

---

## 14. Deliberately Excluded Requirements & Rationale

1. **Celery / Redis / Background Brokers**: Single SQLite `gpu_locks` row lock and subprocess runner eliminate operational dependencies and process management bloat.
2. **LangChain / LlamaIndex / Agent Frameworks**: Raw HuggingFace transformers calls are strictly reproducible, lighter, and eliminate framework churn.
3. **Microservices / gRPC**: Modular monolith in a single repository with editable install is trivial to deploy and maintain.
4. **WebSocket Server**: Polling HTTP status endpoint every 2 seconds is simple and resilient for benchmark progress.
5. **Docker Orchestration inside App**: Native subprocess execution avoids Docker-in-Docker complexity and GPU passthrough friction.
