# Project Handover Document

This document records the verified status, runtime constraints, known regressions, and operational commands for Rapier Bench as of October 2026.

## 1. Verified Project State & Evidence

The implementation is verified functional across backend, benchmark core, and frontend components:

- **Backend Test Suite**: **62 passed** tests (`.venv/bin/python -m pytest tests -q`, re-verified after the sampling unification and the comparison gate; ruff clean).
  - Unit tests: evaluators (11), parsers (3), prompt builder (3), sampling (5), IFEval offline vendor (3).
  - Integration tests: auth API (7), benchmark API (12, incl. the two comparison-gate regressions), recommendation engine (9), ownership & privacy (3), regression tests (5).
- **Frontend Test Suite**: **23 passed** tests (`cd frontend && npm test -- --run`).
  - Formatter tests (12), API client tests (7), status & component tests (4).
- **Real GPU Run Artifacts (`artifacts/`)**:
  - `lfm2.5-350m`: verified on **all 5 suites** — sciq (`cli_25ef779a30c5`, accuracy 1.0), wdc_pave (`smoke_wdc_pave/cli_d1eb5dc95ead`), ifeval (`smoke_ifeval/cli_fe34e961fb55`), legalbench (`smoke_legalbench/cli_27e9d96cf698`), faitheval (`smoke_faitheval/cli_37787baa0d65`). Each `run_config.json` confirms `model_id: lfm2.5-350m`.
  - `lumma-0.6b`: SciQ only, 10 samples, accuracy 0.2, model load 5.18 s (`artifacts/84c4c9f3-8d4e-4814-9cca-66ddf2b038e6/`). Remaining 4 suites not run.
  - `apertus-0.5b`: SciQ only, accuracy 0.0 with 408 output tokens (degenerate output, not a load failure) (`artifacts/smoke_apertus/cli_486359668121/`). Remaining 4 suites not run.

## 2. Unverified Scope & Limitations

To maintain strict technical honesty, the following areas remain unverified:

- **Lumma & Apertus Non-SciQ Suites**: `lumma-0.6b` and `apertus-0.5b` have been run on GPU only against SciQ; the other four suites (WDC-PAVE, LegalBench, IFEval, FaithEval) remain unrun for those two models. Coverage matrix: 7 of 15 model×suite combinations.
- **FaithEval answerable control not measured in the real run**: `smoke_faitheval/cli_37787baa0d65` reports `control_samples: 0`, so its `balanced_score: 0.0` is an unmeasured placeholder, NOT a control accuracy. The SQuAD control path exists (`load_answerable_control`) and must be exercised separately.
- **WDC-PAVE micro-F1 = 0.0 for lfm2.5-350m is a genuine result**, not an evaluator fault: `json_validity_rate: 1.0`, `vn_count: 27`, `nn_count: 44` — the model emits valid JSON but extracts no attribute values.
- **Independent security review incomplete**: the authorization matrix is covered by integration tests, but the deeper traversal/IDOR/symlink probes were never run (the worker died mid-turn).
- **Legacy sampling hash in pre-existing GPU artifacts**: the 7 recorded GPU runs were selected under the historical formula `SHA256(suite_name:seed:sample_id)`. The code now uses the single canonical rule `SHA256(dataset_id:split:seed:stable_id)` (docs/ARCHITECTURE.md §11.1). The old sample sets therefore cannot be regenerated with the same seed, and the `/comparisons` gate will return 400 for any request mixing a pre-change run with a post-change run on the same dataset/protocol (it compares evaluated sample IDs). Re-run a benchmark if a like-for-like comparison across the change is needed.
- **Full Dataset Runs**: Evaluations were executed with `smoke` (5–10 samples); full splits (e.g., 2,492 FaithEval samples, 790 LegalBench samples) have not been run.
- **Docker GPU Passthrough**: Docker Compose runs API and frontend in containers, but GPU passthrough is unconfigured. Real inference must be run on host.

## 3. Workstation Hardware Constraints

- **GPU**: NVIDIA GeForce RTX 3050 Laptop GPU (GA107, 4096 MiB VRAM). Driver: `580.178.04`, CUDA: `13.0`.
- **Root Partition Headroom**: `/` has ~2.6 GB free space and is shared with other workspaces (`cir`, `PlantGuard`).
- **Cache Isolation**: Always use `UV_CACHE_DIR=/tmp/uv-cache` to avoid filling root disk.
- **Shared PyTorch**: Environment shares CUDA PyTorch 2.14.1 via `_shared_cir_torch.pth` pointing to `/home/heheboiz/data/cir/.venv`.

## 4. Operational Commands

```bash
# 1. Environment initialization (idempotent)
bash scripts/setup_env.sh

# 2. Run backend API server (http://localhost:8000)
bash scripts/dev.sh

# 3. Run frontend interface (http://localhost:3000)
cd frontend && npm run dev

# 4. Verify test suites
.venv/bin/python -m pytest tests -q
cd frontend && npm test -- --run

# 5. Execute dry run CLI check
.venv/bin/python -m benchmark.cli run \
  --model apertus-0.5b \
  --dataset sciq \
  --protocol sciq_evidence_grounded \
  --samples smoke \
  --dry-run
```

## 5. Notable Incidents & Bug Fixes

The following issues were identified and resolved during implementation (see `tests/integration/test_integration_regressions.py`):

1. **Artifact Directory Path Nesting (Bug 1)**: Runner inadvertently passed nested run path to benchmark engine, creating double directories (`artifacts/{id}/{id}`). Resolved by passing base `settings.artifacts_path`.
2. **Cancellation Session Staleness (Bug 2)**: Subprocess polling missed cancellation flags because SQLAlchemy cached model instances. Resolved by querying with `populate_existing()`.
3. **Cancellation Status Overwrite (Bug 3)**: Cancelled runs were erroneously marked `COMPLETED` when worker loop exited. Fixed status transition logic.
4. **Sample Alias Parameter Rejection (Bug 4)**: `CreateBenchmarkRequest` rejected JSON payloads sending `"samples"` instead of `"sample_count"`. Added Pydantic field alias.
5. **Startup Stale Run Reconciliation (Bug 5)**: Server reboot left orphaned `RUNNING` or `QUEUED` records and locked the GPU mutex. Added startup lifespan reconciliation to mark them `FAILED` and release `GpuLock`.
6. **Prompt Reference Leakage**: Templates attempting to interpolate gold label fields directly are caught and rejected by `DefaultPromptBuilder`.
7. **Tokenizer BOS / Assistant Duplication**: Apertus required `add_special_tokens=false` to avoid double `<s>` tokens; Lumma required `add_generation_prompt=false` because the Jinja template unconditionally emits `<|assistant|>\n`.

## 6. Next Steps Roadmap

1. **Expand Model Smokes**: Execute smoke runs for `lumma-0.6b` and `apertus-0.5b` on the remaining 4 suites (WDC-PAVE, LegalBench, IFEval, FaithEval), and run the FaithEval answerable control.
2. **Automate Cron Benchmarking**: Wire periodic pilot-scale (25-sample) benchmark jobs for newly registered models.
3. **NVIDIA Container Toolkit**: Add GPU device reservations to `docker-compose.yml` for environments supporting containerized CUDA.
