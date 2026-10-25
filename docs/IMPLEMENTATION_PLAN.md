# Rapier Bench Implementation Plan

Phased engineering plan, module ownership, dependency ordering, observable acceptance gates, and handoff protocols.

---

## 1. Ownership & Workstream Mapping

| Workstream | Lead Role | Owned Modules & Directories | Primary Dependency |
|---|---|---|---|
| **WS1: Architecture & Contracts** | System Architect | `docs/`, `configs/` | None (Foundation) |
| **WS2: Backend Foundation & API** | Backend Engineer | `backend/app/`, `docker-compose.yml`, `pyproject.toml` | WS1 Spec |
| **WS3: Benchmark Core & Adapters** | Benchmark Engineer | `benchmark/core/`, `benchmark/adapters/`, `benchmark/evaluators/`, `benchmark/cli.py` | WS1 Spec |
| **WS4: Web UI & Dashboard** | Frontend Engineer | `frontend/` | WS2 API Contract |
| **WS5: Verification & Quality Assurance** | QA Engineer | `tests/` | WS2, WS3, WS4 |

---

## 2. Phase-by-Phase Roadmap

### Phase 1: Foundation & Vertical Slice
**Goal**: Working end-to-end slice: DB + FastAPI + Benchmark Engine + LFM2.5-350M + SciQ smoke run (10 samples).

- **Tasks**:
  1. Root `pyproject.toml` created with exact pins matching `docs/ARCHITECTURE.md` §2 (`fastapi==0.142.2`, `transformers==5.15.0`, `torch` under `[project.optional-dependencies] gpu`).
  2. SQLite schema initialized via SQLAlchemy 2 (`models.py`, `Base.metadata.create_all`) with `is_private=True` default and `gpu_locks` single-row lock.
  3. `select_samples()` implemented in `benchmark/core/sampling.py` implementing the canonical SHA-256 hash rule (`hash = SHA256(f"{dataset_id}:{split}:{seed}:{stable_id}")`) and shortfall report dict.
  4. `ModelAdapter` implementation for HuggingFace CausalLM loaded on CUDA/CPU (`LFM2.5-350M` default).
  5. `DatasetAdapter` for `allenai/sciq` (both `sciq_evidence_grounded` and `sciq_closed_book`).
  6. `SciQEvaluator` calculating exact multiple choice accuracy.
  7. Subprocess runner `python -m app.jobs.runner <run_id>` executing smoke run, updating DB progress, and writing `artifacts/<run_id>/`.
  8. Basic FastAPI endpoints: `POST /api/v1/benchmarks` (`is_private: true` default), `GET /api/v1/benchmarks/{id}/status`, `GET /api/v1/benchmarks/{id}/results`.
- **Observable Acceptance Gate**:
  ```bash
  python -m benchmark.cli run --model lfm2.5-350m --dataset sciq --protocol sciq_evidence_grounded --samples 10 --seed 42 --output-dir ./test_artifacts
  ```
  Exits `0`, writes `./test_artifacts/metrics.json` containing `"accuracy"` float in range `[0.0, 1.0]`, and writes `./test_artifacts/predictions.jsonl` with 10 valid lines.

---

### Phase 2: Full Benchmark Core & Suites
**Goal**: Complete model adapters (Lumma, Apertus) and domain benchmark suites (WDC-PAVE, LegalBench Contract NLI, IFEval, FaithEval).

- **Tasks**:
  1. **Lumma 0.6B Adapter**: Enforce `trust_remote_code=True`, `add_generation_prompt=False` quirk workaround, and `attn_implementation="sdpa"`.
  2. **Apertus 0.5B Adapter**: Handle `add_special_tokens=False` quirk to prevent duplicate BOS tokens, and `attn_implementation="sdpa"`.
  3. **WDC-PAVE Suite**: Extraction evaluator computing micro-F1 and error rates (`json_validity_rate`, `missing_attr_rate`, `unsupported_attr_rate`, `parse_failure_rate`). Enforce: `n/a` predictions NEVER count as true positives.
  4. **LegalBench Contract NLI Suite**: Evaluator covering documented core 5 subtasks with task-level and aggregate macro balanced accuracy.
  5. **IFEval Suite**: Faithful implementation of strict and loose prompt/instruction-level accuracy.
  6. **FaithEval Suite**: Contextual faithfulness evaluator reporting `unanswerable_context_accuracy` and answerable control accuracy (never call it "hallucination rate").
  7. **Cancellation & Heartbeat**: Inter-sample cancellation polling in runner checking `cancel_requested` DB flag.
  8. **CLI Dry-Run**: Implement `--dry-run` calling `select_samples()` and listing selected sample IDs and prompt hashes without inference.
  9. **Memory Sanitation**: Ensure `torch.cuda.empty_cache()` + `gc.collect()` runs between all job executions.
- **Observable Acceptance Gate**:
  ```bash
  python -m benchmark.cli run --model apertus-0.5b --dataset sciq --protocol sciq_closed_book --samples 5 --dry-run
  ```
  Exits `0`, prints 5 sample IDs without loading model into VRAM.
  Running unit tests against gold fixtures:
  ```bash
  pytest tests/unit/test_evaluators.py
  ```
  Exits `0` with 5 passed tests.

---

### Phase 3: Web UI Integration
**Goal**: Full Next.js frontend integrated with FastAPI session auth and benchmark lifecycle.

- **Tasks**:
  1. **Session Auth**: Login and registration forms submitting to `/api/v1/auth/*` with HttpOnly cookie.
  2. **Model & Dataset Catalogs**: Browser views fetching from `/api/v1/models` and `/api/v1/datasets` via `src/lib/api.ts`.
  3. **Benchmark Creator**: Form allowing model, dataset, protocol, and sample mode selection (`smoke`, `pilot`, `standard`) with `is_private` toggle (defaults checked/private).
  4. **Mutation Header**: Ensure all mutations (`POST`, `PUT`, `DELETE`, `PATCH`) in `src/lib/api.ts` transmit `X-Rapier-Action: 1`.
  5. **Run Inspector**: Real-time status polling (2s interval), progress bar, metrics table, and paginated predictions inspection.
  6. **Run Comparison**: Side-by-side run comparison page at `/compare?run_ids=id1,id2`.
  7. **Leaderboard View**: Domain/task filtering with ranking based on primary metrics of public completed runs.
- **Observable Acceptance Gate**:
  `npm run build` inside `frontend/` succeeds with zero TypeScript or lint errors.
  End-to-end smoke test: user can login, submit a benchmark, watch status transition `queued -> running -> completed`, and view results in browser.

---

### Phase 4: Explainable Recommendation Engine
**Goal**: Deterministic model recommendations based on domain, constraints, and weights.

- **Tasks**:
  1. Implement `RecommendationEngine` in `backend/app/services/recommendation_engine.py`.
  2. Hard constraints filtering (max VRAM, max latency evaluated against `latency_ms_mean`, min quality).
  3. Insufficient sample guard: return `insufficient_sample` if $<3$ models evaluated.
  4. Min-max normalization and composite scoring formula.
  5. Deterministic tie-breaking (`composite_score DESC`, `primary_metric DESC`, `latency_ms_mean ASC`, `model_id ASC`).
  6. Explanation and limitations generator.
  7. Offline constraint: Recommendations calculate strictly over historical completed runs and NEVER trigger live inference.
- **Observable Acceptance Gate**:
  `POST /api/v1/recommendations` with education domain returns ranked list with evidence and explanation matching unit test assertions.

---

### Phase 5: Verification, Hardening & Review
**Goal**: End-to-end test suite, clean error handling, security review, and release verification.

- **Tasks**:
  1. Security audit: CSRF header check, path-traversal prevention on `/export` and `/artifacts`, password hashing parameters.
  2. Private run access audit: Verify non-owner receives `404 Not Found` on private run GET endpoints and `403 Forbidden` on mutation endpoints.
  3. Startup reconciliation test: Verify abandoned `RUNNING` rows are marked `FAILED` on server reboot and `gpu_locks` cleared.
  4. GPU slot concurrency test: Verify concurrent run attempts queue safely behind `gpu_locks`.
  5. Full test run:
     ```bash
     pytest -v
     ruff check .
     ```
- **Observable Acceptance Gate**:
  All unit and integration tests pass; linter reports zero errors.

---

## 3. Worker Handoff Protocol

Every worker completing a phase or ticket MUST report in this exact format:

```markdown
### Worker Handoff Report
- **Workstream**: [e.g. Backend Core]
- **Deliverables**: [List of created/edited files]
- **Contracts Implemented**: [Section numbers from ARCHITECTURE.md]
- **Verification Command Executed**: [Exact terminal command run]
- **Command Output / Observable Proof**: [Paste output showing exit code 0 or test passes]
- **Next Consumer**: [Workstream / worker that should proceed next]
```
