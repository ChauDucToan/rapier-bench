# Rapier Bench — Final System Audit & Verified Repairs

**Branch:** `fix/final-system-verification` (from `fix/final-correctness` @ `b59df842afc2197c6cdb029c19d80df92dc927b0`)
**Mode:** Every finding independently reproduced before fixing. No change without evidence.

## Verdicts

| ID | Finding | Verdict | Root cause | Fix / Reason rejected | Test |
| -- | ------- | ------- | ---------- | --------------------- | ---- |
| A1 | Migration index-name collision on real legacy schema | **CONFIRMED (P0)** | SQLite index names are DB-global. Rebuild created `benchmark_runs_new` (with model-declared indexes `ix_benchmark_runs_user_id` etc.) BEFORE dropping the old table whose same-named indexes still existed. Repro on genuine e05078e DDL: `sqlite3.OperationalError: index ix_benchmark_runs_user_id already exists`. The prior simplified fixture omitted indexes, masking it | Drop the legacy table's named indexes before creating the replacement (PK autoindex untouched; child indexes have distinct names); then temp-name rebuild as before. Verified end-to-end on TRUE e05078e-generated DB: notnull 1→0, runs/metrics/artifacts preserved, FK check clean, all 4 indexes + query-plan usage retained, Full-mode NULL insert works, idempotent, no leftover temp tables | `tests/integration/test_db_migration.py` rewritten with real named indexes (6 tests) + end-to-end true-DDL verification above |
| B1 | SciQ parser rewards letters in prose | **CONFIRMED (P1)** | Rule 1b accepted any standalone letter token: "The vitamin B complex..." → `B`; "Vitamin D is important for bones." → `D`; "The answer might be A or C." → `A` (first-letter wins); "A: This is the explanation." → `A` | New policy: (1) explicit answer-statement prefix (answer/choice/option/select/pick), (2) whole response is a single letter + punctuation, (3) exact choice-text match, else INVALID. All audit counterexamples now INVALID; legit vectors ("A", "(C)", "Answer: D", "**A**", "d.", "oxidants") still parse | `TestB1SciqParser` (17 parametrized vectors) |
| C1 | Unknown hardware latency treated as comparable | **CONFIRMED (P1)** | `_hardware_key` mapped missing GPU metadata → `"unknown"`; when ALL runs shared "unknown", one hw-group formed and latency was scored. Unverified ≠ same environment | Latency comparability requires a VERIFIED hardware key: unknown-hw runs are excluded from the latency cohort when any known group exists, and latency is never scored when the chosen group is `"unknown"`; disclosed in limitations | `TestC1UnknownHardware` (2 tests) |
| C2 | One corrupted metric fails whole request | **CONFIRMED (P1)** | `_finite()` raised `ValueError` on inf stored latency (NaN cannot be stored in the NOT NULL SQLite column — inserts fail at write time; inf CAN be stored) | Per-candidate exclusion: non-finite/negative stored quality/latency/vram excludes that run; request succeeds with valid models. Request-side weights still validated (400) | `TestC2CorruptedMetrics` (4 tests) |
| C3 | Max-score cherry-picking of repeated runs | **CONFIRMED (P1)** | Per-model selection kept highest `(quality, run_id)` — optimistic bias (max-of-N trials) undocumented; comment claimed "first eligible" | Deterministic LATEST-run policy (`created_at`, run_id tiebreak); disclosed in every response: "the LATEST run represents it (no best-of-N cherry-picking)" | `TestC3LatestRunPolicy` (2 tests) |
| C4 | Single-model display semantics | PARTIAL — already correct | Round 3 added the "not a recommendation" limitation | No code change; verified | `TestSingleModelAfterConstraints` (round 3) |
| D1 | Cohort identity incomplete (revision/protocol version) | **CONFIRMED (P1)** | Runner persists full `dataset_config`/`protocol_config` in `sample_selection` (via run_config.json), but cohort keys used only (dataset, protocol, split, IDs) | Cohort key now includes dataset revision + protocol version, read from the PERSISTED run row (not mutable registry). Same samples under a different revision/protocol version no longer share a cohort | `TestD1CohortRevisionIdentity` (2 tests) |
| D2 | `revision: "main"` on 4 HF datasets | CONFIRMED — kept as disclosed limitation | SciQ/LegalBench/IFEval/FaithEval use mutable `main` refs; loaders DO pass them (A6) | Rejected pinning: inventing commit SHAs without network verification would be worse; the loader pins what config says, run artifacts persist revision, and cohort identity (D1) now separates differing revisions. Documented in README limitations | — |
| D3 | Comparison accepts non-completed runs | **CONFIRMED (P1)** | `/comparisons` never checked `run.status` | Reject with 400 listing non-completed IDs before comparability scoring | `TestD3ComparisonStatus` (5 tests: queued/running/failed/cancelled rejected, completed ok) |
| D4 | Leaderboard consistency | NOT A BUG (verified post-fix) | Round 3 grouping holds: metric names match values, cohort_id hash, missing metrics excluded, non-completed filtered by status predicate | No change | existing tests + `test_api_flow` |
| E1 | 120 s queue timeout fails legitimate waiters | **CONFIRMED (P1)** | `GpuManager.acquire(timeout_sec=120)` → second job FAILED "Timed out waiting to acquire GPU lock" while job A legitimately runs long | Indefinite cancel-aware wait; 30 s dead-holder check (PID + /proc start-token, same identity as reconciliation) recovers stale locks; `try_acquire` now self-seeds the lock row so subprocess callers cannot spin forever on a missing row | `TestE1QueueSemantics` (2 tests) |
| E2 | New lifecycle races | NOT A BUG | Round 3 guards (conditional RUNNING/COMPLETED, terminal overwrite prevention, spawn identity) hold; concurrent creates are separate rows + atomic lock acquisition | No change | existing lifecycle tests |
| E3 | Worker log contents | INTENTIONAL | Logs contain operational events only (load, warmup latency, cancel, unload); no prompts/outputs/secrets found | No change | — |
| F1 | Missing-class subtask pollutes LegalBench macro | **CONFIRMED (P1)** | Absent-class recall placeholder 0.0 entered `aggregate_macro_balanced_accuracy` as a measured zero | Missing-class subtasks excluded from the macro mean; per-subtask `*_missing_class` flag + `*_samples` still disclosed | `TestF1LegalBenchMissingClass` |
| F2 | FaithEval suite invisible (primary=balanced_score, controls never load) | **CONFIRMED (P1)** | Round 3 excluded strict-only runs from leaderboard/recommendation → the default unanswerable-only protocol produced NO rankings at all, contradicting README (primary: `unanswerable_context_accuracy_strict`) | Primary metric = `unanswerable_context_accuracy_strict` (the actually-measured protocol metric, matching README). Unanswerable-only runs now rank under their real name; `balanced_score` remains reported as a metric when present, never substituted | `TestFaithEvalMetricIntegrity` (updated), `test_api_flow` |
| F3 | WDC-PAVE metric labeled as official | PARTIAL — docs mostly correct | README/audit docs describe the project-specific attribute-level any-overlap metric, but the metric table implied parity | README metric table now says "project-specific attribute-level metric" | doc change |
| F4 | IFEval parity | UNVERIFIED | Full differential test vs official scorer not executed in this environment (network fetch of official eval harness + fixtures required) | No change; vendored code untouched | — |
| F5 | Cross-evaluator invariants | NOT A BUG | All five evaluators use fail-closed `_pair_predictions` (duplicates/unknown/missing rejected) | No change | existing B7 tests |
| G1 | Comparison UI run selection | NOT A BUG | Frontend disables incompatible options; backend gate is authoritative | No change | existing |
| G2 | Stale "Fewer than 3 unique models" copy | **CONFIRMED (P2)** | Backend allows 2-model informational rankings since round 3 | Fallback text now describes the actual cohort-based reason | frontend change |
| G3–G5 | Auth/creation/export | NOT A BUG / no reproducible defect | Registration session, ownership, export perms verified in rounds 2–3 | No change | existing suites |
| H1 | Fresh clone deps | PARTIAL — no defect found | pyproject declares benchmark deps; torch lives in `gpu` extra by design (CPU API-only installs) | No change | Docker build passes |
| H2 | Docker GPU claims | INTENTIONAL | DEPLOYMENT.md + Dockerfile explicitly state API-only, no CUDA passthrough | No change | — |
| H3 | Docs consistency | **CONFIRMED (P2)** | Test-count claims lagged (100/130 vs current) | Round-4 section added with current counts; historical sections remain marked as historical | this doc |

## Before / After (confirmed P0–P1)

| ID | Before | After |
| -- | ------ | ----- |
| A1 | Legacy DB with real indexes: migration crashes `index ix_benchmark_runs_user_id already exists` | Migration succeeds; data, FKs, indexes preserved; Full mode works |
| B1 | "The vitamin B complex supports metabolism." scored as answer `B` | INVALID (counted as invalid parse, never a lucky correct answer) |
| C1 | All-unknown-hardware cohort scored latency as speed evidence | Latency omitted with explicit disclosure |
| C2 | One `inf` latency run failed the entire recommendation request | Corrupted candidate excluded; valid models ranked |
| C3 | Model with runs 0.85/0.72/0.60 represented by 0.85 (max cherry-pick) | Latest run (0.60) represents it; policy disclosed |
| D3 | QUEUED/RUNNING/FAILED runs could enter scored comparisons | 400 with explicit non-completed ID list |
| E1 | Job B failed after 120 s behind a long job A | B waits (cancel-aware); dead-holder lock takeover after 30 s |
| F1 | Macro balanced accuracy dragged by unmeasurable 0-recall subtasks | Macro over measurable subtasks only; flags disclose the rest |
| F2 | FaithEval produced zero leaderboard/recommendation entries | Ranks under `unanswerable_context_accuracy_strict` (real name) |

## Verification

- **Backend:** `pytest tests -q` → **179 passed** (was 130 at branch start; +49 including rewritten migration suite and round-4 regressions); `ruff check backend benchmark tests` → clean
- **Frontend:** `npm run typecheck` clean; `npm run lint` clean; `npm test -- --run` → **23 passed**
- **Database migration:** verified against a legacy DB generated from the ACTUAL `e05078e` models (real `NOT NULL` sample_count, real named indexes, dependent metrics/artifacts rows, FK targets) — data preserved, FK check clean, Full-mode NULL insert works, idempotent, no temp-table leftovers
- **API integration:** full flow test passes (register → session → private full-mode run → privacy → cohort/metric integrity → grouped leaderboard → rerun)
- **GPU smoke:** **PENDING** — no CUDA device. Command: `backend/.venv/bin/python -m benchmark.cli run --model lfm2.5-350m --dataset sciq --samples smoke --device cuda`
- **Browser E2E:** **PENDING** — not executed (component tests only)

## Remaining limitations

- **Environment blocker:** GPU inference validation; browser E2E
- **Environment blocker:** IFEval official-parity differential test (F4)
- **Intentional:** HF dataset `revision: "main"` refs (D2) — loaders pin what config declares, artifacts persist the revision, cohort identity separates revisions; pinning requires verified commit SHAs
- **Intentional:** WDC-PAVE attribute-level any-overlap metric (project protocol, now labeled)
- **Intentional:** VRAM = catalog model-weight estimate (labeled in UI)
- **Future:** answerable-control loading for FaithEval balanced scoring; explicit per-protocol recommendation pinning

## Git

- Start: `b59df842afc2197c6cdb029c19d80df92dc927b0`
- Branch: `fix/final-system-verification`
- Final SHA + push confirmation: see commit history (pushed after this report was committed)
