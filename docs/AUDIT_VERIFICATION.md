# Rapier Bench — Independent Audit Verification Report

**Audit baseline:** `e05078e` (branch `feat/domainbench-mvp`, clean tree)
**Method:** Independent source inspection + failing-test reproduction before any fix; fixes applied only to reproduced defects; all changes re-verified with the full test suites.

## Summary

| Verdict | Count |
| :--- | :--- |
| CONFIRMED (fixed) | 16 |
| PARTIALLY CONFIRMED (fixed where valid) | 6 |
| NOT A BUG / documented limitation | 6 |
| Environment-blocked / PENDING | 4 |

## Finding-by-finding table

| ID | Finding | Verdict | Evidence | Fix | Test |
| -- | ------- | ------- | -------- | --- | ---- |
| A1 | Inference exceptions become wrong answers; run COMPLETED | CONFIRMED | `benchmark/adapters/models/hf_causal.py` returned `GenerationOutput(error=...)` with empty text/zero latency; `benchmark/core/runner.py` recorded + evaluated it as an ordinary wrong prediction; worker set `COMPLETED` | Runner raises `RuntimeError` on `gen_out.error`; worker marks run FAILED with error text | `tests/unit/test_audit_regressions.py::TestA1InferenceErrors` (failed pre-fix, passes post-fix) |
| A2 | Cancellation race / partial results / GPU lock | PARTIALLY | Worker had check-then-set between cancel-check and `COMPLETED`; SIGTERM path could skip release; core returns partial results on cancel (intentional for artifact retention) | Atomic conditional `UPDATE ... WHERE cancel_requested IS FALSE` for terminal transition; SIGTERM → `sys.exit(0)` flows through existing `finally` release; partial artifacts retained on cancel by design | `tests/integration/test_integration_regressions.py` (cancel-not-completed cases already covered; new atomic transition covered by same suite) |
| A3 | Startup reconciliation kills live workers | CONFIRMED | `reconcile_stale_runs()` marked every QUEUED/RUNNING run FAILED and cleared GPU lock unconditionally; a surviving worker could then run inference while a new worker grabs the freed lock | `worker_pid` + `/proc` start-time token persisted at spawn AND self-registered by the worker at startup (covers the spawn-commit race); reconciliation checks identity (defeats PID recycling) and skips live workers and their lock; inline `ALTER TABLE` migration | `test_startup_reconciliation_keeps_live_worker_running` |
| A4 | `full` mode = fixed 1000 samples | CONFIRMED (API path) | `SAMPLE_MODE_COUNTS["full"]=1000` in `benchmark_service.py`; core path (`resolve_sample_count`) was already correct (`None` → all eligible) | API maps `full` → `count=None`; DB column nullable; `progress_total=0` until worker reports | `test_full_mode_creates_null_count_run` |
| A5 | Zero eligible samples → COMPLETED with metrics | CONFIRMED | Runner wrote `{"sample_count": 0}` and returned; worker persisted COMPLETED | Runner raises `RuntimeError`; worker marks FAILED with diagnostic | `TestA5EmptySelection::test_zero_samples_raises` |
| A6 | Dataset revisions not pinned at load | CONFIRMED (datasets); model revision pinning was already correct | `load_dataset(...)` calls in all 5 adapters omitted `revision=`; WDC fetched mutable GitHub `main` | All adapters pass `revision=self.config.get("revision")`; WDC `raw_url` pinned to upstream commit `5546254c0dc7649c4eb0ef11671ecefb9070ecd0` | Adapter smoke via existing `test_adapters.py` (network fixtures not re-downloaded locally) |
| B1 | FaithEval prompt/evaluator mismatch; loose substring 'not' | CONFIRMED | Protocol instructs literal `UNANSWERABLE`; strict only accepted `unknown`; loose matched bare `"not"` substrings (`notebook` counted as abstention) | Strict accepts `unanswerable`/`unknown`; loose uses anchored refusal patterns — standalone tokens count only when the whole response is the token (so "The unknown species is X" on an answerable control is NOT a refusal); verified against all audit vectors | `TestB1FaithEvalStrict` (7 vectors incl. `notebook`, `Paris`, verbose abstention, incidental-word answerables) |
| B2 | FaithEval balanced_score reported as real 0 without controls | CONFIRMED | Evaluator emitted `balanced_score: 0.0`, `answerable_control_accuracy: 0.0` when `control_samples == 0`; recommendation/leaderboard consumed the fake 0 | Metrics omitted when controls absent; leaderboard skips FaithEval runs without genuine `balanced_score`; recommendation no longer falls back to a different metric | `TestB2FaithEvalBalanced` |
| B3 | WDC-PAVE any-overlap credit | PARTIALLY / NOT A BUG (metric semantics) | Evaluator gives attribute-level VC on set intersection (`{"Color":["red"]}` vs `{"Color":["red","blue","green"]}` → full credit). This matches the documented project metric (EVALUATION_PROTOCOL §4.4: Micro-F1 over attribute outcomes, multi-value support explicit) — it is a project-defined extraction metric, not official WDC-PAVE scoring | No scoring change; labeled in report. Parser/gold normalization already separated from schema validity via `parse_status` | Documented here; existing evaluator tests cover exact/missing/wrong/null/unsupported |
| B4 | LegalBench pooled sampling misrepresents subtasks | CONFIRMED | Single pooled `_finalize()` could sample zero rows from a small subtask; absent class → recall 0 silently; macro mean over present subtasks only | Stratified largest-remainder allocation (exact `limit`, every subtask with data ≥1, deterministic); evaluator emits per-subtask `<task>_samples` counts and `<task>_missing_class` flag | `tests/unit/test_legalbench_sampling.py` (5 tests: exact limits incl. undershoot case, determinism, seed sensitivity, full) |
| B5 | IFEval `build_description()` exceptions suppressed | PARTIALLY | `contextlib.suppress(Exception)` matches vendored-official defensive pattern; unknown instruction IDs already counted failed. Suppressing build errors on malformed kwargs can silently score with incomplete instruction state | Kept suppression (official-behavior parity) — classified INTENTIONAL LIMITATION; no rewrite of vendored components | Existing `test_ifeval_vendor.py` |
| B6 | SciQ parser extracts letters from prose | CONFIRMED | Old letter regex matched any `[A-D]` with word boundary; `The vitamin B complex...` → `B`; `I think A, but final answer is D` → `A` | Standalone-token regex: letter must be its own token (start/whitespace/paren + trailing punctuation/end); prefix rule unchanged | Manual vector run + `test_parsers.py` (existing vectors still pass) |
| B7 | Pairing denominator silent shrink | CONFIRMED | `_pair_predictions()` silently dropped missing predictions, double-counted duplicates, discarded unknown IDs | Fail-closed: duplicates/unknown/missing all raise `ValueError` with counts | `TestB7Pairing` (4 tests) |
| C | Failure-analysis contract (`target`, `is_correct`, filters) | CONFIRMED | TS declared `target`/`is_correct`; artifacts never contained them; UI sent `correct`/`incorrect`/`parse_failure` as `status` values the backend compared against `parse_status` | Runner persists `target` + `is_correct` (via new `pair_correctness()` on evaluators; None where not meaningful — WDC-PAVE set-valued); service filter maps `correct`/`incorrect`/`parse_failure` and still accepts raw parse_status values; API validates filter enum; legacy artifacts serve without crash | `tests/integration/test_prediction_contract.py` (filters, legacy artifacts, contract fields) |
| D1 | Comparison without sample-selection metadata | CONFIRMED | Missing IDs skipped the equality check entirely | Comparison rejects with explicit "missing sample-selection metadata" 400 | `test_comparison_rejects_missing_sample_selection` |
| D2 | Leaderboard best-run selection ignores cohort | CONFIRMED | Best per `model.id` by raw score across any sample sets/protocols/splits; runs without selection metadata collapsed into one empty cohort | Cohort key = (model, dataset, protocol, split, selected_sample_ids); runs WITHOUT selection metadata are excluded (unverifiable cohort); missing primary metric skipped instead of 0.0 | Existing leaderboard tests + cohort behavior by construction |
| D3 | All-Domains single raw ranking | CONFIRMED | One global sort mixed SciQ accuracy, WDC micro-F1, IFEval accuracy | Items sorted by dataset+metric then value; `dataset_id` added to items; no cross-metric single rank implied | Existing tests pass |
| D4 | Latency shown across heterogeneous hardware | PARTIALLY | Latency column displays values regardless of hardware; no latency-based ranking exists | Labeled column retained; documented as limitation (below). Hardware-provenance gating deferred | Documented |
| E1 | Recommendation best-run bias | CONFIRMED | Highest quality per model regardless of sample cohort | Largest verified sample cohort wins the model slot; quality tiebreak within cohort; runs without selection metadata excluded | `test_api_recommendation.py` updated suite |
| E2 | Dominant protocol by run count | PARTIALLY | Majority-by-count protocol selection retained; now computed PER DATASET with deterministic tie-break (sorted keys) | Per-dataset dominant protocol; documented as limitation | By construction |
| E3 | VRAM estimate labeled as measured | CONFIRMED | `vram_weight_gb` is catalog model-weight estimate; UI said "VRAM Footprint" with no estimate label | UI labels "(est.)" + tooltip "model-weight estimate, not measured peak"; recommendation response includes explicit limitation string | Frontend typecheck/lint pass; limitation string asserted via engine tests |
| E4 | Cross-hardware latency in recommendation | PARTIALLY | Latency compared across hardware without normalization | Documented limitation; hardware-cohort gating deferred (would shrink MVP cohorts below usability) | Documented |
| E5 | Missing/invalid metric handling | PARTIALLY | Missing quality/latency already excluded; FaithEval fallback removed; zero-latency accepted, NaN weights not validated | FaithEval fallback removed; finite-value validation of weights/metrics left as documented limitation (DB floats, no NaN observed in pipeline) | `test_missing_metrics_excluded_never_invented` |
| E6 | Three-model minimum | CONFIRMED (arbitrary) | `< 3` returned `insufficient_sample` | 1–2 models ranked with explicit "small comparison set" limitation; 0 still refuses | `test_hardware_and_quality_filtering`, `test_insufficient_sample_under_three_models` (updated) |
| E7 | Min-max normalization edge cases | NOT A BUG | Equal-range → 1.0 for all is implemented; single/two candidates can now occur (E6) and normalize trivially | None; behavior documented in response limitations | Existing tests |
| E8 | Cost criterion absent | NOT A BUG (documented) | No cost data source exists; not implemented anywhere | Documented as future enhancement; no fabricated cost prediction | — |
| F1 | Registration without session | CONFIRMED | Backend register returned user without cookie; frontend set user in state and navigated to dashboard → every protected call 401 | Register endpoint creates session + sets `rapier_session` cookie (same as login) | `test_registration_creates_session_cookie` |
| F2 | Session/ownership gaps | NOT A BUG (coverage gap only) | Login/logout/ownership/cancel/export authz verified correct in code + `test_ownership.py` | Added no architecture change; noted uncovered cases (cross-user rerun) as future tests | Existing suite |
| F3 | CSRF protection level | NOT A BUG (proportionate) | `X-Rapier-Action` custom header + CORS allowlist + `SameSite=Lax` blocks form-based CSRF for same-origin deployment; not a defense against XSS | No change; production should set `SECURE_COOKIES=true` (documented in DEPLOYMENT.md) | — |
| F4 | Worker stdout/stderr discarded | CONFIRMED | `DEVNULL` on both streams; crashes left only exit code | Workers log to `logs/workers/<run_id>.log`; abnormal-exit monitor marks non-terminal runs FAILED with pointer to the log | By construction; monitor logic unit-covered via A2 lifecycle tests |
| G1 | `custom` sample mode rejected 422 | CONFIRMED | Frontend sent `sample_size_mode: "custom"`; backend pattern `^(smoke|pilot|standard|full)$` | `custom` accepted; requires `sample_count`; treated as exact requested count | `test_custom_mode_uses_explicit_count`, `test_custom_mode_without_count_rejected` |
| G2 | Full evaluates whole eligible split | CONFIRMED after A4 fix | Core path was already correct; API path fixed (A4) | See A4 | See A4 |
| G3 | Catalog TS/backend schema mismatches | CONFIRMED (stale optional fields) | `metrics`, `documented_subtasks`, `default_protocol_id` never sent by backend; `sample_count` now nullable | TS types aligned to actual schemas; frontend falls back to built-in protocol map | `npm run typecheck` passes |
| G4 | Missing metrics charted as 0; VRAM label | CONFIRMED | `?? 0` in compare chart; "VRAM" without estimate qualifier | Chart keeps `null` gap; VRAM labels "(est.)" with tooltips | Frontend tests pass |
| G5 | Mobile usability | NOT A BUG (minor) | Tables use `overflow-x-auto`; grids collapse | Added `flex-wrap` to compare selection header | Visual |
| H1 | Docker image omits `benchmark/` package | CONFIRMED | Dockerfile copied only `pyproject.toml`, `configs/`, `backend/`; worker imports `benchmark.core.runner` | `COPY benchmark/ /app/benchmark/` added; image built and import verified: `docker build` + `python -c "from benchmark.core.runner import run_benchmark"` inside container — OK | Docker build executed in this audit |
| H2 | Browser pointed at `backend:8000` | CONFIRMED | Compose set `NEXT_PUBLIC_API_BASE_URL=http://backend:8000` (Docker-internal DNS) | Changed to `http://localhost:8000` | Config inspection |
| H3 | Fresh-clone env risks | PARTIALLY | `.gitignore` clean; lockfile committed; torch lives in optional `gpu` extra; Python 3.13 noted pending in pyproject | Documented (torch install path for inference, Python version); no dependency churn performed | Fresh `pip install .` inside Docker image succeeded (CPU deps) |
| H4 | Docs overclaim FaithEval balanced score | CONFIRMED | README listed `balanced_score` as FaithEval primary metric while normal runs have `control_samples: 0` | README now marks strict accuracy as primary with omission rule for unmeasured balanced score | Doc change |

## Verified defects (code fixed)

A1, A3, A4, A5, A6, B1, B2, B4, B6, B7, C, D1, D2, D3, E1, E3 (label), E6, F1, F4, G1, G3, G4, H1, H2.

## Design limitations (documented, not changed)

- **B3:** WDC-PAVE attribute-level any-overlap metric is the documented project protocol (Micro-F1 over attribute outcomes); extra predicted values within a gold attribute are not penalized at attribute level. Renaming or changing to exact-set scoring would alter the metric contract mid-project.
- **B5:** IFEval `build_description()` exception suppression mirrors official defensive behavior; vendored components intentionally unmodified.
- **D4/E4:** Latency values from different hardware appear side-by-side; no latency ranking exists; hardware-cohort gating deferred.
- **E2:** dominant-protocol selection by run count retained but computed per dataset with deterministic tie-break; explicit protocol pinning is future work.
- **E7:** Min-max normalization sensitivity to outliers is disclosed in every response.
- **E8:** Cost criterion not implemented; no cost data source.
- **F3:** CSRF posture is proportionate for a same-origin student deployment; set `SECURE_COOKIES=true` behind HTTPS in production.

## Research-methodology decisions

- **B2:** unmeasured FaithEval `balanced_score`/`answerable_control_accuracy` are omitted, never zero. Leaderboard/recommendation skip runs lacking a genuine balanced score.
- **B4:** stratified LegalBench sampling guarantees every subtask ≥1 sample in sampled runs; per-subtask sample counts and missing-class flags are emitted metrics.
- **D2/D3:** leaderboard comparability is cohort-scoped (model, dataset, protocol, split, selected sample IDs).

## Environment-dependent validation (PENDING)

- **GPU inference:** no CUDA device in this audit environment. All five suites ran only via fake-adapter fault injection. Real-GPU validation commands:
  ```bash
  backend/.venv/bin/python -m benchmark.cli run --model lfm2.5-350m --dataset sciq --sample-mode smoke --device cuda
  ```
  (equivalent per model/dataset). Verify persisted `predictions.jsonl` contains `target`/`is_correct` and that no inference error was recorded as a wrong answer.
- **Full docker-compose stack up/run:** backend image build + import verified; compose end-to-end (frontend browser flow) not executed here.

## Test results (this audit)

- Backend/benchmark: `backend/.venv/bin/python -m pytest tests -q` → **100 passed** (69 pre-existing + 31 new/updated)
- Lint: `backend/.venv/bin/ruff check backend benchmark tests` → **All checks passed**
- Frontend: `npm run typecheck` → clean; `npm run lint` → clean; `npm test -- --run` → **23 passed**
- Docker: `docker build -f docker/backend/Dockerfile` → success; in-container `import run_benchmark` → OK

## New/updated regression tests

- `tests/unit/test_audit_regressions.py` — A1, A5, B1, B2, B7 (18 tests)
- `tests/unit/test_legalbench_sampling.py` — B4 stratified sampling (5 tests)
- `tests/integration/test_prediction_contract.py` — C, D1, A4, G1, F1 (7 tests)
- `tests/integration/test_integration_regressions.py` — A3 live-worker reconciliation (1 test)
- Updated: `test_api_recommendation.py` (E6 semantics + cohort metadata), `test_api_benchmarks.py` (D1 required metadata, D2 cohort metadata)

## Independent review round

All P0/P1 fixes were reviewed by an independent GPT Luna xhigh subagent against the actual diff. The reviewer confirmed 4 files OK and raised 8 actionable objections (LegalBench quota undershoot, PID recycling, empty-cohort conflation, FaithEval loose false-positives, log-handle leak, spawn/PID race, protocol selection scope, test gaps). All were fixed in a second pass and re-verified: quota allocation now uses largest-remainder (exact limits pinned by tests), process identity uses `/proc` start-time tokens plus worker self-registration, unverifiable cohorts are excluded from leaderboard/recommendation, standalone refusal tokens only match whole-response answers, log handles close on spawn failure, dominant protocol is per-dataset, and dedicated tests pin each behavior.

---

# Round 3 — Final Correctness Audit (branch `fix/final-correctness`)

**Base:** `6636d43` on `fix/audit-verification`. All findings independently
reproduced (scratch SQLite DB, quota-allocation simulation) before fixing.

| ID | Finding | Verdict | Evidence | Fix | Tests |
| -- | ------- | ------- | -------- | --- | ----- |
| F1 | FaithEval leaderboard fallback labels strict accuracy as `balanced_score` | CONFIRMED (P0) | `leaderboard.py` tried `[balanced_score, unanswerable_context_accuracy_strict]` but always emitted `primary_metric_name=balanced_score` | Fallback removed: runs lacking the dataset's primary metric are excluded; metric name always equals the metric value's source | `TestFaithEvalMetricIntegrity` (3 tests) |
| F2 | Recommendation selects runs per-model across incompatible cohorts | CONFIRMED (P0) | Per-model largest-cohort pick; three models with disjoint 200-ID sets ranked together | Cohort-first algorithm: partition by (dataset, protocol, split, sorted sample IDs), require ≥2 distinct models, deterministic cohort choice (most models → largest sample set → lexicographic), one run per model inside cohort | `TestCommonCohort` (8 tests, cases A–H) |
| F3 | Private runs invisible to owner's recommendations | CONFIRMED (P1) | Query had `is_private.is_(False)` only; endpoint had no user dependency | Optional current-user dependency; `is_private=false OR user_id=current_user` visibility filter applied before cohort selection; anonymous = public only; no private IDs in error bodies | `TestPrivateRunVisibility` (3 tests) |
| F4 | Cross-hardware latency compared as equivalent | CONFIRMED (P1) | Latency weight (default 0.3) directly scored composite; no hardware check; prior report's "no latency ranking" claim was wrong for recommendations | Hardware key = GPU name + CUDA + torch from `hardware_metadata`; latency compared only within one hardware group; mixed cohorts pick the group with most models and disclose the exclusion; missing latency disclosed, weight never silently redistributed; quality-only weights ignore hardware | `TestHardwareLatencyGating` (4 tests) |
| F5 | Legacy SQLite DBs reject Full mode (`sample_count NOT NULL`) | CONFIRMED (P1) | Scratch legacy-schema DB: `INSERT ... sample_count=NULL` → `IntegrityError: NOT NULL constraint failed`; startup migration only added worker columns | Idempotent table rebuild (`app/db/migrations.py`): create replacement under temp name from current model schema → copy rows → DROP old → RENAME (SQLite rewrites dependent FK references back to `benchmark_runs`); `PRAGMA foreign_keys` toggled on the raw connection before the rebuild transaction (no-op inside one). Independent review caught and fixed the initial version that ran the pragma inside the transaction and left child FKs pointing at the dropped temp table | `tests/integration/test_db_migration.py` (5 tests: legacy upgrade, idempotency, fresh DB, FK preservation, dependent-row survival + enforcement on rebuilt relationship) |
| F6 | LegalBench quota allocation gives 0 to tiny subtasks | CONFIRMED (P1) | Simulated `[1,1,1,1,1000]` limit 5 → quotas `[0,0,0,0,5]`, contradicting the documented ≥1 guarantee | Coverage-first allocation: 1 per nonempty subtask when `limit >= nonempty count`, then capped largest-remainder over spare capacity; `limit < subtasks` documented as impossible-to-cover with deterministic proportional subset | `tests/unit/test_legalbench_sampling.py` extended (11 tests incl. all required vectors) |
| F7 | Leaderboard renders one global rank list across cohorts | CONFIRMED (P1) | Flat items sorted by dataset/metric; frontend numbered `#{idx+1}` across the whole response | `LeaderboardGroup` schema: response groups by (dataset, protocol, split, sample IDs); rank implicit per group; frontend renders per-group sections with cohort headers; deprecated flat `items` kept for legacy consumers | `TestLeaderboardCohortGroups` (4 tests) |
| F8 | NaN/Inf/negative values can produce meaningless scores | CONFIRMED (P1) | No `isfinite` checks; `or`-chain latency fallback | `_finite()` validation on weights and metrics; negative latency/quality runs excluded; zero latency accepted; latency/normalized_latency now nullable (`None` = not measured) | `TestNumericRobustness` (4 tests) |
| S11 | Terminal-status overwrite race | CONFIRMED (edge) | COMPLETED transition lacked status guard; queued-cancel could be flipped to RUNNING | Both transitions require `status IN (queued, running)` AND `cancel_requested=false`; worker exits when run already terminal | `tests/integration/test_lifecycle_guards.py` (3 tests) |

## Round 3 verification

- Backend: **130 passed** (`pytest tests -q`); ruff clean
- Frontend: typecheck clean, lint clean, **23 passed**
- Legacy-DB migration: proven on exact `e05078e` schema with data preservation,
  idempotent second run, FK integrity, and working Full-mode NULL insert
- GPU inference: still **PENDING** (no CUDA device in this environment)
- Docker compose E2E: not executed (browser flow untested)

## Corrections to Round 2 claims

- "No latency ranking exists" (D4/E4) was inaccurate for the recommendation
  engine: latency weight contributed directly to composite ranking. Fixed by
  the F4 hardware-cohort policy above.

## Round 3 independent review round

GPT Luna (high) reviewed the integrated diff. Findings and dispositions:

- **Migration FK handling (critical, confirmed):** the first implementation
  issued `PRAGMA foreign_keys=OFF` inside the rebuild transaction (a no-op in
  SQLite) and `ALTER TABLE ... RENAME` rewrote child FK references to the temp
  table name, which was then dropped. Fixed with the temp-name rebuild
  procedure verified against SQLite 3.53: create replacement from the current
  model schema under `benchmark_runs_new`, copy, DROP old, RENAME — SQLite
  rewrites child references back to `benchmark_runs`. Dependent-row survival
  and post-rebuild FK enforcement are now covered by tests.
- **Dependent-row coverage gap (confirmed):** migration tests seeded only
  `benchmark_runs`. Fixed: legacy fixture now seeds `benchmark_metrics` and
  `artifacts` rows; test asserts survival, linkage, and enforcement.
- **Effective-weight explanation (confirmed):** response claimed the original
  latency weight even when latency was omitted. Fixed: explanation now states
  the omission or the effective weights.
- **Single-model-after-constraints labeling (confirmed):** result is returned
  for completeness but explicitly labeled "not a recommendation".
- **Per-candidate `_finite` (confirmed):** malformed stored metric values now
  exclude the candidate instead of failing the whole request; weight validation
  still rejects non-finite inputs with 400.
- **Leaderboard group React-key collision (confirmed):** groups now carry a
  `cohort_id` (SHA-256 of the exact sample IDs); frontend key uses it.
- **Leaderboard sample-ID normalization (confirmed):** IDs normalized to
  strings before cohort-key construction, matching the recommendation engine.
- False positive: reviewer's `cd backend && pytest` invocation — tests live at
  repository root `tests/`; suite runs green (`130 passed`).
