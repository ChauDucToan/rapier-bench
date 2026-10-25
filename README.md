# Rapier Bench

Rapier Bench is a domain-aware, reproducible benchmarking platform for local open-weight language models. It executes real, deterministic inference on constrained hardware (4 GB VRAM) and provides multi-objective model recommendations across domain tasks, throughput, latency, and memory footprints.

## Key Features

- **Local Inference Engine**: Direct Hugging Face PyTorch/SDPA execution without external API dependencies.
- **Five Domain Benchmark Suites**: Pre-configured evaluation across education, e-commerce, legal, instruction following, and contextual faithfulness.
- **Strict Concurrency Control**: SQLite-backed GPU mutex guarantees single-model execution on constrained VRAM.
- **Deterministic Sampling**: SHA-256 hash-ranked record selection with reproducible random seeds.
- **Leak-Proof Prompt Generation**: Automated verification preventing reference answer interpolation into model inputs.
- **Multi-Objective Recommendation**: Min-max normalized composite scoring balancing quality, latency, and memory with hard constraint filtering.
- **Session-Based Privacy**: Argon2id password authentication with private-by-default run isolation.

## Registered Models

| Model ID | Display Name | Hugging Face ID | Revision | Parameters | License |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `apertus-0.5b` | Apertus v1.1 0.5B Instruct | `swiss-ai/Apertus-v1.1-0.5B-Instruct` | `a140fd6` | 572M | Apache-2.0 |
| `lumma-0.6b` | Lumma 0.6B Instruct | `FrontiersMind/Lumma-0.6B-Instruct` | `668bc2f` | 649M | Apache-2.0 |
| `lfm2.5-350m` | Liquid LFM2.5 350M | `LiquidAI/LFM2.5-350M` | `9e6c6cc` | 354M | LFM-Open-1.0* |

*\*LFM-Open-1.0 includes an annual commercial revenue ceiling ($10M). See license terms before commercial deployment.*

## Evaluation Suites

| Suite ID | Domain | Task Type | Canonical Dataset | Primary Metric |
| :--- | :--- | :--- | :--- | :--- |
| `sciq` | Education | Multiple Choice | [`allenai/sciq`](https://huggingface.co/datasets/allenai/sciq) | `accuracy` |
| `wdc_pave` | E-Commerce | Attribute-Value Extraction | [WDC-PAVE](https://github.com/wbsg-uni-mannheim/wdc-pave) | `micro_f1` |
| `legalbench_contract_nli` | Legal | Binary Classification | [`nguha/legalbench`](https://huggingface.co/datasets/nguha/legalbench) | `balanced_accuracy` |
| `ifeval` | General | Instruction Following | [`google/IFEval`](https://huggingface.co/datasets/google/IFEval) | `prompt_level_strict_acc` |
| `faitheval` | Faithfulness | Contextual Faithfulness | [`Salesforce/FaithEval`](https://huggingface.co/datasets/Salesforce/FaithEval-unanswerable-v1.0) | `balanced_score` |

## System Architecture

```text
+-----------------------------------------------------------------+
|                       Next.js Frontend                          |
|         (Leaderboard, Run Management, Model Recommender)        |
+--------------------------------+--------------------------------+
                                 | HTTP / JSON (Port 3000 -> 8000)
+--------------------------------v--------------------------------+
|                       FastAPI Backend                           |
|       (Session Auth, Run Queuing, Recommendation Engine)        |
+---------------+--------------------------------+----------------+
                |                                |
+---------------v---------------+ +--------------v----------------+
|       SQLite (rapier.db)      | |      Benchmark Subprocess      |
|  - Users & Session Cookies    | |  - Subprocess Isolation        |
|  - GpuLock Row Mutex          | |  - PyTorch / Transformers      |
|  - Run Configurations         | |  - Evaluators & Metric Calculators
|  - Normalized Metric Records  | |  - Artifact Storage: JSONL/JSON |
+-------------------------------+ +-------------------------------+
```

## Quick Start

### 1. Environment Configuration

```bash
# Clone and configure isolated virtual environment
git clone git@github.com:ChauDucToan/rapier-bench.git
cd rapier-bench
bash scripts/setup_env.sh
```

### 2. Start Backend Server

```bash
# Launches FastAPI on http://localhost:8000
bash scripts/dev.sh
```

### 3. Start Frontend Client

```bash
# In a separate terminal session
cd frontend
npm install
npm run dev
# Frontend interface available at http://localhost:3000
# OpenAPI documentation available at http://localhost:8000/docs
```

## Running Benchmarks

### Via CLI

The CLI executes runs either against physical weights or in dry-run mode (prompt verification without GPU memory allocation):

```bash
# Dry run verification (validates sampling, prompt construction, and hash computation)
.venv/bin/python -m benchmark.cli run \
  --model apertus-0.5b \
  --dataset sciq \
  --protocol sciq_evidence_grounded \
  --samples smoke \
  --dry-run

# Execute real local inference run
.venv/bin/python -m benchmark.cli run \
  --model apertus-0.5b \
  --dataset sciq \
  --protocol sciq_evidence_grounded \
  --samples 10 \
  --device cuda
```

### Via API

```bash
# 1. Authenticate user session
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"devpassword"}' \
  -c cookies.txt

# 2. Queue benchmark run
curl -s -X POST http://localhost:8000/api/v1/benchmarks \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "apertus-0.5b",
    "dataset_id": "sciq",
    "protocol_id": "sciq_evidence_grounded",
    "samples": 10,
    "is_private": false
  }'
```

## Interpreting Results & Metrics

### System & Performance Metrics

- `latency_ms_mean` / `latency_ms_median` / `latency_ms_p50` / `latency_ms_p95`: End-to-end sample latency in milliseconds.
- `tokens_per_sec`: Aggregate generation throughput across completed iterations.
- `model_load_time_s`: Cold-start checkpoint loading and GPU memory allocation duration.

### Evaluation Suite Quality Metrics

- **SciQ**: `accuracy` (exact letter match), `invalid_parsed_rate` (output failed extraction).
- **WDC-PAVE**: `micro_f1`, `micro_precision`, `micro_recall`, `json_validity_rate`, `missing_attr_rate`, `unsupported_attr_rate`, `parse_failure_rate`.
- **LegalBench**: `balanced_accuracy` (mean recall of Yes and No classes), `accuracy`, `aggregate_macro_balanced_accuracy`.
- **IFEval**: `prompt_level_strict_acc`, `prompt_level_loose_acc`, `inst_level_strict_acc`, `inst_level_loose_acc`.
- **FaithEval**: `unanswerable_context_accuracy_strict`, `unanswerable_context_accuracy_loose`, `answerable_control_accuracy`, `balanced_score` (harmonic mean guarding against blind abstention).

### Critical Methodological Warnings

1. **Hardware Non-Comparability**: Latency and throughput figures reflect local hardware constraints (RTX 3050 Laptop GPU) and MUST NOT be compared across different host environments.
2. **SciQ Protocol Isolation**: `sciq_evidence_grounded` includes context passages; `sciq_closed_book` strips them. Scores across these protocols are strictly non-comparable.
3. **WDC-PAVE Scope**: Measures attribute extraction only. Predicting `"n/a"` for an absent attribute never earns true-positive (`VC`) credit.
4. **LegalBench Scope**: Rapier Bench evaluates a 5-task Contract NLI subset, not the full 162-task LegalBench collection.
5. **FaithEval Faithfulness**: `unanswerable_context_accuracy` measures refusal precision on unanswerable contexts. It MUST NOT be labeled as a general "hallucination rate".

## Authentication & Privacy Model

- **Session Authentication**: Managed via HTTP-only cookie containing cryptographic session token (`session_id`).
- **Private by Default**: Benchmark runs default to `is_private: true`.
- **Information Leak Protection**: Unauthenticated requests to private runs return `404 Not Found` (never `403 Forbidden`), preventing run existence probing. Mutations (/cancel, /rerun) return `403` to authenticated non-owners.

## Recommendation Engine

The recommendation endpoint (`POST /api/v1/recommendations`) performs deterministic multi-criteria decision analysis across historical benchmark records:

1. **Eligibility Filtering**: Filters runs matching requested `domain` and optional `task_type`. Discards candidates violating hard constraints (`max_vram_gb`, `max_latency_ms`, `min_quality`).
2. **Protocol Harmonization**: Restricts comparisons to the dominant protocol version within the candidate set.
3. **Sample Size Guard**: If fewer than 3 distinct models satisfy the constraints, returns `status: "insufficient_sample"` rather than publishing an unrepresentative ranking.
4. **Min-Max Normalization**:
   $$Q_{\text{norm}} = \frac{Q - Q_{\min}}{Q_{\max} - Q_{\min}}, \quad L_{\text{norm}} = \frac{L_{\max} - L}{L_{\max} - L_{\min}}, \quad V_{\text{norm}} = \frac{V_{\max} - V}{V_{\max} - V_{\min}}$$
5. **Composite Ranking**: Scores candidate models via $S = w_q Q_{\text{norm}} + w_l L_{\text{norm}} + w_v V_{\text{norm}}$. Zero inference is triggered during recommendation.

## Verification & Testing

```bash
# Run backend test suite (60 unit and integration tests)
.venv/bin/python -m pytest tests -q

# Run frontend test suite (23 unit and component tests)
cd frontend && npm test -- --run

# Code quality and style audits
.venv/bin/ruff check backend benchmark tests
cd frontend && npm run lint
```

## Known Limitations

- **Single GPU Worker Slot**: Physical host features 4096 MiB VRAM. Parallel GPU inference is prohibited; jobs queue sequentially behind `gpu_locks`.
- **Vendored Dependencies**: IFEval sentence segmentation uses vendored punkt tokenizer data to eliminate runtime network requirements.
- **Model Checkpoints**: Model weights are downloaded to local HF cache and never committed to version control.

## Documentation Index

- [Architecture Specification](docs/ARCHITECTURE.md): Database schema, API specification, job states.
- [Evaluation Protocol](docs/EVALUATION_PROTOCOL.md): Detailed dataset contracts, schemas, and metrics.
- [Deployment Guide](docs/DEPLOYMENT.md): Production setup, environment configuration, Docker constraints.
- [Model Compatibility](docs/MODEL_COMPATIBILITY.md): Architectural notes, tokenization quirks, memory profiles.
- [Hardware Specification](docs/HARDWARE.md): Local GPU benchmarking constraints and honesty guidelines.
- [Extending Rapier Bench](docs/EXTENDING.md): Adding models, datasets, metrics, and protocols.
- [Project Handover](docs/HANDOVER.md): Test verification status, resolved bugs, and operational notes.
