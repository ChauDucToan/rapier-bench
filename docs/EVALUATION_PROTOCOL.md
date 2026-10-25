# Rapier Bench: Evaluation Protocol Specification

This document is the implementation specification for the five evaluation suites in Rapier Bench:
1. **SciQ** (Education / Multiple-Choice Science QA)
2. **WDC-PAVE** (E-Commerce / Product Attribute-Value Extraction)
3. **LegalBench — Contract NLI** (Legal / Clause Interpretation)
4. **IFEval** (Instruction Following / Verifiable Constraint Satisfaction)
5. **FaithEval** (Contextual Faithfulness / Abstention & Grounded QA)

All specifications are grounded in verified Hugging Face dataset cards, dataset-viewer API outputs, and official scoring codebases.

---

## 1. Laptop Resource Constraints & Disk Budget

The evaluation environment is constrained to a single machine with ~4 GiB VRAM and a filesystem partition at ~98% capacity. To prevent out-of-disk crashes and long downloads:

1. **Selective Config Downloading**: Subtask-level configurations (e.g., LegalBench) download only their own parquet/TSV files (~30–55 KB each), never the parent repository.
2. **Streaming Support**: Loaders must support `streaming=True` in `load_dataset()` to iterate over records without caching full parquet tables when running smoke or pilot subsets.
3. **Zero Local Fine-Tuning**: All benchmark tasks evaluate inference-only.

### Cache Footprint Budget

| Benchmark Suite | Upstream Dataset ID / Source | Full Split Size (Bytes / MB) | Evaluated Split Rows | Smoke Subset (5–10 rows) | Pilot Subset (20–30 rows) | Streaming Supported? |
|---|---|---|---|---|---|---|
| **SciQ** | `allenai/sciq` | 342,808 B (~0.33 MB) [test split parquet] | 1,000 (test) | < 5 KB | < 15 KB | Yes (`parquet`) |
| **WDC-PAVE** | `siavashsaki/wdc-pave-ave` (HF) / `wbsg-uni-mannheim/wdc-pave` (GH) | 205,420 B (~0.20 MB) [test.jsonl] / 432,220 B (~0.42 MB) | 284 (HF test) / 354 (GH test) | < 8 KB | < 25 KB | Yes (`json`) |
| **LegalBench (Contract NLI)** | `nguha/legalbench` | ~230 KB (core 5 configs) / ~600 KB (all 14 configs) | 790 (core 5) / 1,930 (all 14) | < 10 KB | < 30 KB | Yes (`parquet`) |
| **IFEval** | `google/IFEval` | 96,256 B (~0.09 MB) [parquet] / 207,111 B (~0.20 MB) [jsonl] | 541 (train) | < 5 KB | < 15 KB | Yes (`json` / `parquet`) |
| **FaithEval** | `Salesforce/FaithEval-unanswerable-v1.0` | 3,178,294 B (~3.03 MB) [test parquet] | 2,492 (test) | < 15 KB | < 40 KB | Yes (`parquet`) |
| **FaithEval (Control)** | `rajpurkar/squad` (v1.1 val) or `alvinming/...-w-original_context` | ~2.2 MB (SQuAD val) / ~5.9 MB (original context) | 1,000–2,492 (sample matching) | < 15 KB | < 40 KB | Yes (`parquet`) |
| **TOTAL** | — | **~8.2 MB (raw data)** | — | **< 60 KB** | **< 165 KB** | — |

*Operational Verification & Disk Reality*: Smoke runs across all five suites have now actually executed on the cached LFM2.5-350M model and downloaded their data (WDC-PAVE upstream JSONL 422 KB, LegalBench per-config shards at ~24–48 KB each, IFEval Parquet at 96 KB, and FaithEval Parquet at 3.18 MB). The budget table's estimates were confirmed in practice with these observed sizes. The machine's `/` partition is down to ~2.6 GB free, shared with other projects, which remains healthy under selective downloading and streaming without full-split caching.
*Evaluation Dependencies Footprint*: IFEval vendored execution requires `langdetect` (~1.0 MB), `immutabledict` (~40 KB), `absl-py` (~150 KB), and `nltk` (~1.5 MB wheel + ~4 MB `punkt_tab` tokenizer download). Total third-party dependency disk space: ~7 MB.
---

## 2. Global Sampling Policy

All benchmark runners must follow an explicit, deterministic sampling contract:

### Sample Size Tiers
- **Smoke**: 5–10 samples. Verifies prompt formatting, model API connectivity, and evaluator parsing without scoring significance.
- **Pilot**: 20–30 samples. Rapid validation for prompt sensitivity, parser failures, and edge-case handling.
- **Standard**: 100–200 samples. Production benchmark runs balancing evaluation latency against variance.
- **Full**: 100% of the designated evaluation split.

### Deterministic Selection Algorithm
1. Filter the split by the suite's eligibility filter.
2. Sort eligible records by their canonical `stable_id` in ascending lexicographical order.
3. Compute a deterministic per-sample hash:
   $$\text{hash} = \text{SHA256}(f"{dataset\_id}:{split}:{seed}:{stable\_id}")$$
4. Sort eligible records by `hash` ascending.
5. Take the first $N$ items. Default seed: `42`.
6. **Shortfall Enforcement**: If the count of eligible records $M < N$, the loader **MUST NOT** silently shrink and **MUST NOT** raise an exception. The runner proceeds with all $M$ eligible records, logs a structured WARNING (`Requested {N} samples but only {M} eligible. Shortfall: {N-M}`), serializes `{"requested_samples": N, "actual_samples": M, "shortfall": N - M}` into `run_config.json` and DB `sample_selection`, and surfaces it in the `/status` and `/results` API responses.
7. **Manifest Persistence**: The runner must serialize `manifest_{suite}_{tier}_{seed}.json` recording `[stable_id_1, stable_id_2, ...]` to allow exact re-evaluation and error auditing.

---

## 3. Suite 1: SciQ (Education / Science QA)

### 3.1 Dataset Metadata & Provenance
- **Canonical HF Dataset ID**: `allenai/sciq` (legacy `sciq` redirects here; confirmed via Hugging Face API).
- **Authentication / Gating**: None (public, `gated: false`).
- **Splits & Sizes**:
  - `train`: 11,679 rows (3,993,099 bytes parquet)
  - `validation`: 1,000 rows (338,503 bytes parquet)
  - `test`: 1,000 rows (342,808 bytes parquet)
- **Features**: `question` (string), `distractor1` (string), `distractor2` (string), `distractor3` (string), `correct_answer` (string), `support` (string).
- **Support Presence & Empirical Audit**: The `support` field contains reference evidence text. However, an empirical audit reveals **116 out of 1,000 test rows have empty `support` (`""`)**.

### 3.2 Protocols: Evidence-Grounded vs Closed-Book
SciQ must be evaluated and reported under two distinct, non-fungible protocol names:
1. `sciq:closed-book`: Prompt contains only `question` and 4 candidate choices. Tests parametric scientific knowledge.
2. `sciq:evidence-grounded`: Prompt includes the `support` passage as context before the question. Tests reading comprehension and grounded reasoning.
   - *Eligibility Rule for Evidence-Grounded*: If a row has empty `support`, it must either be filtered out or flagged. In standard Rapier Bench reporting, `sciq:evidence-grounded` evaluates on rows where `len(support.strip()) > 0` (884 test rows). `sciq:closed-book` evaluates on all 1,000 test rows.

### 3.3 Multiple-Choice Construction
To prevent position bias:
1. Candidate list: `[correct_answer, distractor1, distractor2, distractor3]`.
2. Seeded deterministic shuffle:
   ```python
   import hashlib, random
   seed_int = int(hashlib.sha256(f"{row_id}:sciq_choice".encode()).hexdigest()[:8], 16)
   rng = random.Random(seed_int)
   choices = [correct_answer, distractor1, distractor2, distractor3]
   rng.shuffle(choices)
   options = {chr(65 + i): c for i, c in enumerate(choices)} # A, B, C, D
   correct_letter = [k for k, v in options.items() if v == correct_answer][0]
   ```

### 3.4 Parser & Metric Contract
- **Parser Rule**:
  1. Extract single capital option letter `[A-D]` matching `r"(?:^|\b|\()([A-D])(?:\)|\.|\b|$)"` or explicit prefix `r"(?:answer|choice|option):\s*([A-D])"`.
  2. If no option letter is detected, attempt exact case-insensitive normalized match against choice texts (`options.values()`).
  3. If text matches exactly one choice, assign that letter; if zero or multiple match, output `INVALID`.
- **Metric**: Exact Accuracy = $\frac{\sum \mathbb{I}(\text{pred\_letter} == \text{correct\_letter})}{N}$. Invalid parsing counts as 0.0.

---

## 4. Suite 2: WDC-PAVE (Product Attribute-Value Extraction)

### 4.1 Dataset Metadata & Provenance
- **Canonical HF Dataset ID**: `siavashsaki/wdc-pave-ave` (author: Siavash Saki; pre-cleaned JSONL mirror).
- **Official Upstream Repository**: `wbsg-uni-mannheim/wdc-pave` (GitHub).
- **Authentication / Gating**: None (public CC BY 4.0).
- **Splits & Sizes**:
  - HF `siavashsaki/wdc-pave-ave`: `train` (994 rows, 702 KB), `validation` (142 rows, 102 KB), `test` (284 rows, 201 KB). Total: 1,420 rows.
  - Upstream `wbsg-uni-mannheim/wdc-pave` (`data/processed_datasets/wdc_with_all_attributes`): `train.jsonl` (211 rows, 253 KB), `train_large.jsonl` (1,066 rows, 1.25 MB), `test.jsonl` (354 rows, 422 KB). Total: 1,420 rows.
- **Categories (5)**: Computers And Accessories (11 attrs), Home And Garden (8 attrs), Office Products (10 attrs), Jewelry (3 attrs), Grocery And Gourmet Food (5 attrs). Total 24 distinct attributes.

### 4.2 Attribute Representation Schema
In `siavashsaki/wdc-pave-ave`:
- `id`: int64
- `category`: string
- `input_title`: string
- `input_description`: string
- `gold_json`: JSON string or dictionary mapping `attribute_name` to:
  - Single value: string (e.g., `"Color": "Black"`)
  - Multi-valued attribute (3.9% of attributes): sorted list of strings (e.g., `"Manufacturer": ["HP", "Hewlett-Packard"]`)
  - Absent attribute: `null` (or `"n/a"` in upstream raw `target_scores`)

In upstream raw `wbsg-uni-mannheim/wdc-pave`:
- `target_scores`: dictionary mapping `attribute_name` to `{"n/a": 1}` or `{value_string: {"pid": [...], "score": 1}}`.

### 4.3 Task Boundary: Extraction-Only (Not Normalization)
Rapier Bench evaluates **EXTRACTION-ONLY**.
- **Extraction**: The model must extract attribute values *as they appear in the source product title and description text*.
- **Normalization**: In upstream WDC-PAVE, normalization maps extracted strings to standard units (e.g. converting `39 inches` to `99.1 cm`, or normalizing color abbreviations).
- Models must not be penalized for omitting external schema-level unit conversions. Ground truth values in `wdc_with_all_attributes` represent raw extractions.

### 4.4 Official Metric Logic: Micro-F1
Scoring logic is derived from official scorer `pieutils/evaluation.py` (`calculate_evaluation_metrics_multiple_attributes` and `calculate_micro_scores`) in `wbsg-uni-mannheim/wdc-pave`:

For each attribute $a$ of each test record:
- Target $T_a$: set of normalized valid strings, or `None` if `null`/`n/a`.
- Prediction $P_a$: predicted string, or `None` if `null`/`n/a`/empty.

Five mutually exclusive outcomes:
1. **NN (Neither / True Negative)**: $T_a \text{ is None} \land P_a \text{ is None}$.
2. **NV (Negative-Value / False Positive)**: $T_a \text{ is None} \land P_a \text{ is not None}$.
3. **VN (Value-Negative / False Negative)**: $T_a \text{ is not None} \land P_a \text{ is None}$.
4. **VC (Value-Correct / True Positive)**: $T_a \text{ is not None} \land P_a \in T_a$.
5. **VW (Value-Wrong / Misextraction)**: $T_a \text{ is not None} \land P_a \text{ is not None} \land P_a \notin T_a$.

#### Treatment of `n/a`
- If $T_a$ is `n/a` and model predicts `n/a` or `null`, outcome is **NN**.
- **`n/a` predictions NEVER count as true positives (`VC`)!** They are excluded from precision, recall, and F1 denominators.

#### Metric Formulations
$$\text{Micro-Precision} = \frac{\sum VC}{\sum VC + \sum NV + \sum VW}$$
$$\text{Micro-Recall} = \frac{\sum VC}{\sum VC + \sum VN + \sum VW}$$
$$\text{Micro-F1} = \frac{2 \times \text{Micro-Precision} \times \text{Micro-Recall}}{\text{Micro-Precision} + \text{Micro-Recall}}$$

---

## 5. Suite 3: LegalBench — Contract NLI

### 5.1 Dataset Metadata & Subtask Enumeration
- **Canonical HF Dataset ID**: `nguha/legalbench`.
- **Authentication / Gating**: None (public CC BY 4.0).
- **Architecture**: In Hugging Face, LegalBench exposes tasks as independent configurations. Loading a specific config downloads *only* that subtask's files (~30–55 KB parquet per subtask).
- **Contract NLI Subtasks**: LegalBench incorporates ContractNLI by binarizing hypothesis entailment against NDA clauses (hypotheses entailed = `Yes`; contradicted or not mentioned = `No`). There are **14 subtasks** in `nguha/legalbench`:

| Subtask Config Name | Train (few-shot) | Test (eval split) | Class Balance (Test) | Target Legal Dimension |
|---|---:|---:|---|---|
| `contract_nli_confidentiality_of_agreement` | 8 | 82 | Yes: 41, No: 41 (50.0%) | Non-disclosure of discussions/agreement |
| `contract_nli_explicit_identification` | 8 | 109 | Yes: 20, No: 89 (18.3%) | Requirement of written confidentiality stamp |
| `contract_nli_inclusion_of_verbally_conveyed_information` | 8 | 139 | Yes: 68, No: 71 (48.9%) | Coverage of oral disclosures |
| `contract_nli_limited_use` | 8 | 208 | Yes: 97, No: 111 (46.6%) | Use restricted strictly to specified purpose |
| `contract_nli_no_licensing` | 8 | 162 | Yes: 80, No: 82 (49.4%) | Disclaimers of intellectual property licenses |
| `contract_nli_notice_on_compelled_disclosure` | 8 | 142 | Yes: 71, No: 71 (50.0%) | Notification prior to subpoena disclosure |
| `contract_nli_permissible_acquirement_of_similar_information` | 8 | 178 | Yes: 89, No: 89 (50.0%) | Exclusions: independent development |
| `contract_nli_permissible_copy` | 8 | 87 | Yes: 18, No: 69 (20.7%) | Authorization to make copies |
| `contract_nli_permissible_development_of_similar_information` | 8 | 136 | Yes: 68, No: 68 (50.0%) | Non-restriction on similar product development |
| `contract_nli_permissible_post-agreement_possession` | 8 | 111 | Yes: 28, No: 83 (25.2%) | Retention of archival copies |
| `contract_nli_return_of_confidential_information` | 8 | 66 | Yes: 32, No: 34 (48.5%) | Obligation to destroy/return materials |
| `contract_nli_sharing_with_employees` | 8 | 170 | Yes: 88, No: 82 (51.8%) | Internal need-to-know disclosure rules |
| `contract_nli_sharing_with_third-parties` | 8 | 180 | Yes: 71, No: 109 (39.4%) | Disclosure to contractors/advisors |
| `contract_nli_survival_of_obligations` | 8 | 157 | Yes: 74, No: 83 (47.1%) | Survival post termination |
| **All 14 Subtasks Total** | **112** | **1,930** | — | — |

### 5.2 Designated Rapier Bench Subset
To fit within pilot and standard evaluation runs while remaining balanced and representative, Rapier Bench evaluates a core documented subset of **5 subtasks** (790 test samples total):
1. `contract_nli_confidentiality_of_agreement` (82 samples, 50% Pos)
2. `contract_nli_limited_use` (208 samples, 46.6% Pos)
3. `contract_nli_notice_on_compelled_disclosure` (142 samples, 50% Pos)
4. `contract_nli_permissible_acquirement_of_similar_information` (178 samples, 50% Pos)
5. `contract_nli_sharing_with_third-parties` (180 samples, 39.4% Pos)

*Scope Disclaimer*: This suite evaluates contextual clause interpretation on Contract NLI. It **does NOT** represent the entirety of LegalBench (which comprises 162 tasks across 6 distinct legal reasoning categories).

### 5.3 Column Schema & Evaluation Metric
- **Row Columns**: `index` (int64), `text` (string, the NDA clause), `document_name` (string), `answer` (string: `"Yes"` or `"No"`).
- **Official Evaluation Code**: `evaluation.py` in `HazyResearch/legalbench` (`evaluate_exact_match_balanced_accuracy`).
- **Normalization**:
  ```python
  import string
  def normalize_legal(text: str) -> str:
      return str(text).translate(str.maketrans("", "", string.punctuation)).strip().lower()
  ```
- **Official Metric**: **Balanced Accuracy** per subtask:
  $$\text{Balanced-Acc} = \frac{1}{2} \left( \frac{\text{TP}}{\text{TP} + \text{FN}} + \frac{\text{TN}}{\text{TN} + \text{FP}} \right) = \frac{\text{Recall}_{\text{Yes}} + \text{Recall}_{\text{No}}}{2}$$
- **Aggregation**: Report individual task balanced accuracies, followed by unweighted macro-average balanced accuracy across evaluated subtasks.

---

## 6. Suite 4: IFEval (Instruction Following)

### 6.1 Dataset Metadata & Provenance
- **Canonical HF Dataset ID**: `google/IFEval`.
- **Official Upstream Repository**: `google-research/google-research` under `instruction_following_eval`.
- **Authentication / Gating**: None (public, Apache-2.0).
- **Config & Split**: `config="default"`, `split="train"` (contains all 541 canonical evaluation prompts; 96,256 bytes parquet, 207,111 bytes raw jsonl).
- **Row Schema**:
  - `key`: int64 (e.g. 1000)
  - `prompt`: string
  - `instruction_id_list`: list of strings (1 to 4 instructions per prompt)
  - `kwargs`: list of dictionaries specifying parameters (e.g. `num_words`, `relation`, `forbidden_words`).

### 6.2 Instruction Type Catalog
All 25 instruction types registered in `instructions_registry.py` are present across the 541 instances:
1. `keywords:existence`
2. `keywords:frequency`
3. `keywords:forbidden_words`
4. `keywords:letter_frequency`
5. `language:response_language`
6. `length_constraints:number_sentences`
7. `length_constraints:number_paragraphs`
8. `length_constraints:number_words`
9. `length_constraints:nth_paragraph_first_word`
10. `detectable_content:number_placeholders`
11. `detectable_content:postscript`
12. `detectable_format:number_bullet_lists`
13. `detectable_format:constrained_response`
14. `detectable_format:number_highlighted_sections`
15. `detectable_format:multiple_sections`
16. `detectable_format:json_format`
17. `detectable_format:title`
18. `combination:two_responses`
19. `combination:repeat_prompt`
20. `startend:end_checker`
21. `change_case:capital_word_frequency`
22. `change_case:english_capital`
23. `change_case:english_lowercase`
24. `punctuation:no_comma`
25. `startend:quotation`

### 6.3 Implementation Policy: Faithful Port vs Vendor
A naive regex or keyword checker is strictly disallowed. The evaluator must vendor or faithfully port `instructions.py`, `instructions_registry.py`, `instructions_util.py`, and `evaluation_lib.py`:
- **Vendoring Dependencies**: `langdetect` (language checker), `immutabledict`, `nltk` (for `sent_tokenize`).
- **Consequences of Exclusion**: If `langdetect` is omitted, `language:response_language` (13 prompts) fails evaluation. If `nltk` is replaced with naive punctuation splitting, `length_constraints:number_sentences` produces divergences on abbreviations. Both dependencies must be retained.

### 6.4 Official Scoring Protocol
Defined in `instruction_following_eval/evaluation_lib.py`:
- **Strict Scoring**: The raw model response is passed directly to `instruction.check_following(response)`.
- **Loose Scoring**: Evaluates 8 response variants stripping markdown asterisks (`*`), leading greeting lines, trailing postscript lines, or both:
  1. `response`
  2. `response.replace("*", "")`
  3. `"\n".join(r[1:]).strip()`
  4. `"\n".join(r[:-1]).strip()`
  5. `"\n".join(r[1:-1]).strip()`
  6–8. Combinations of line removal and asterisk stripping.
  If *any* variant satisfies the condition, the instruction is counted as followed loosely.
- **Metric Definitions**:
  1. `prompt_level_strict_acc`: Fraction of prompts where *all* associated instructions are strictly satisfied.
  2. `prompt_level_loose_acc`: Fraction of prompts where *all* associated instructions are loosely satisfied.
  3. `instruction_level_strict_acc`: Total strictly satisfied instructions divided by total instructions ($\sum N_{\text{inst}} = 1,061$).
  4. `instruction_level_loose_acc`: Total loosely satisfied instructions divided by total instructions.

---

## 7. Suite 5: FaithEval (Contextual Faithfulness)

### 7.1 Dataset Metadata & Provenance
- **Canonical HF Dataset Collection**: `Salesforce/faitheval-benchmark-66ff102cda291ca0875212d4` (Paper: ICLR 2025; arXiv:2410.03727).
- **Authentication / Gating**: None (public Apache-2.0 / research release).
- **Canonical Subsets**:
  - `Salesforce/FaithEval-unanswerable-v1.0`: `test` split (2,492 rows, 3.18 MB parquet).
  - `Salesforce/FaithEval-inconsistent-v1.0`: `test` split (1,500 rows, 2.65 MB parquet).
  - `Salesforce/FaithEval-counterfactual-v1.0`: `test` split (1,000 rows, 1.64 MB parquet).
- **Answerable Control Mirror**: `alvinming/FaithEval-unanswerable-v1.0-w-original_context` (provides `original_context` for each unanswerable item) or paired evaluation on standard SQuAD v1.1.

### 7.2 Row Schema
Columns in `Salesforce/FaithEval-unanswerable-v1.0`:
- `qid`: string (MD5 hash)
- `question`: string
- `context`: string (modified passage stripped of the answer)
- `answers`: list of strings (e.g. `["unanswerable", "unknown", "no answer", "no information", "not", "unclear"]`)
- `subset`: string (source origin: SQuAD, NewsQA, TriviaQA, NQ, SearchQA, HotpotQA, BioASQ, DROP, RACE, TQA, ARC)
- `justification`: string (editorial explanation of context modification)

### 7.3 Methodological Rule: Unanswerable Accuracy vs "Hallucination Rate"
`unanswerable_context_acc` measures the model's willingness to **abstain** when evidence is missing, resisting parametric intrusions.
- **Why it must NOT be reported as a universal hallucination rate**:
  1. A model that collapses to answering `"I don't know"` or `"unknown"` to every prompt achieves a perfect 1.0 (100%) on unanswerable accuracy while possessing zero factual utility.
  2. Without an **Answerable Control**, false refusal (sycophancy / over-abstention) cannot be separated from genuine context faithfulness.
  3. Hallucination encompasses multiple distinct error modes (closed-book hallucination, contradictory-context hallucination, and unfaithful extrapolation). Unanswerable accuracy measures only silent-context abstention.

### 7.4 Scoring Logic & Phased Rollout
Rapier Bench Phase 1 implements **Unanswerable Context + Answerable Control**:
- **Prompt Structure**:
  ```
  You are an expert in retrieval question answering.
  Please respond with the exact answer only. Do not be verbose or provide extra information.
  If there is no information available from the context, the answer should be 'unknown'.

  Context: {context}
  Question: {question}
  Answer:
  ```
- **Evaluation Rules**:
  - `faitheval_unanswerable_acc_strict`: Normalized predicted string exactly equals `"unknown"`.
  - `faitheval_unanswerable_acc_loose`: Normalized prediction contains any phrase in `['unknown', 'no answer', 'no information', 'not', 'unclear', 'unanswerable']`.
  - `faitheval_answerable_control_acc`: Evaluated on answerable counterparts (using `original_context` or matching SQuAD items). Model must produce the ground truth entity without false refusal.
  - `faitheval_balanced_score`: Harmonic mean of unanswerable loose accuracy and answerable control accuracy:
    $$\text{Balanced-Score} = \frac{2 \times \text{Acc}_{\text{unans}} \times \text{Acc}_{\text{ans}}}{\text{Acc}_{\text{unans}} + \text{Acc}_{\text{ans}}}$$
- **Protocol Boundary & Matcher Note**: The SQuAD-derived answerable control (`faitheval_answerable_control_acc`) is OUR protocol addition and must never be presented as an official FaithEval metric (the code implements this explicit separation, and a regression test covers a subtle matching bug where empty string or single-character predictions erroneously counted as correct due to bidirectional substring containment).

---

## 8. Dataset Adapter Contracts

| Suite | Canonical Dataset ID | Config | Split | Eligible Sample Count | Stable ID Field | Required Extraction Fields | Eligibility Filter | Exact HF Loading Call |
|---|---|---|---|---|---|---|---|---|
| **SciQ** | `allenai/sciq` | `default` | `test` | 1,000 (closed-book) / 884 (grounded) | `f"sciq:{test}:{row_index}"` | `question`, `correct_answer`, `distractor[1-3]`, `support` | Grounded: `len(support.strip()) > 0`. Closed-book: all rows. | `load_dataset("allenai/sciq", "default", split="test", streaming=True)` |
| **WDC-PAVE** | `siavashsaki/wdc-pave-ave` | `default` | `test` | 284 | `id` (int64) | `id`, `category`, `input_title`, `input_description`, `gold_json` | Valid JSON in `gold_json` with $\ge 1$ defined attribute key. | `load_dataset("siavashsaki/wdc-pave-ave", "default", split="test", streaming=True)` |
| **LegalBench (Contract NLI)** | `nguha/legalbench` | `contract_nli_*` (5 core configs) | `test` | 790 (core 5 sum) | `f"{config}:{index}"` | `index`, `text`, `document_name`, `answer` | `answer` in `["Yes", "No"]` and non-empty `text`. | `load_dataset("nguha/legalbench", config, split="test", streaming=True)` |
| **IFEval** | `google/IFEval` | `default` | `train` | 541 | `key` (int64) | `key`, `prompt`, `instruction_id_list`, `kwargs` | Non-empty `instruction_id_list`. | `load_dataset("google/IFEval", "default", split="train", streaming=True)` |
| **FaithEval** | `Salesforce/FaithEval-unanswerable-v1.0` | `default` | `test` | 2,492 | `qid` (hex string) | `qid`, `question`, `context`, `answers`, `subset` | Non-empty `question` and `context`. | `load_dataset("Salesforce/FaithEval-unanswerable-v1.0", "default", split="test", streaming=True)` |

*Note on Stable IDs*: Where an explicit unique key is not published upstream (SciQ, LegalBench), the adapter constructs a deterministic compound identifier: `f"{dataset_tag}:{split}:{row_index}"`. Shuffling or sampling operates solely on this stable string.

---

## 9. Evaluator Contracts & Gold Test Fixtures

### 9.1 Evaluator Contracts Summary Table

| Suite | Evaluator Input | Output Metric Keys | Handled Edge Cases |
|---|---|---|---|
| **SciQ** | `pred_text`, `correct_answer`, `choices_map` | `accuracy`, `invalid_parsed_rate` | Missing answer, verbose markdown ("The answer is B"), lowercase letters, out-of-range letters. |
| **WDC-PAVE** | `pred_json_dict`, `gold_json_dict`, `category` | `micro_precision`, `micro_recall`, `micro_f1`, `nn_count`, `nv_count`, `vn_count`, `vc_count`, `vw_count` | Malformed JSON (counts as all-null), missing keys, predicting `"n/a"` for present value, predicting value for `"n/a"`. |
| **LegalBench** | `pred_text`, `gold_answer` | `balanced_accuracy`, `accuracy`, `yes_recall`, `no_recall` | Punctuation appended ("Yes."), lowercase ("yes"), conversational text ("I believe the answer is No"). |
| **IFEval** | `pred_text`, `instruction_id_list`, `kwargs_list` | `prompt_level_strict_acc`, `prompt_level_loose_acc`, `inst_level_strict_acc`, `inst_level_loose_acc` | Conversational wrappers, missing markdown asterisks, multiple responses, empty response string. |
| **FaithEval** | `pred_text`, `answers_list` | `unanswerable_acc_strict`, `unanswerable_acc_loose`, `answerable_control_acc`, `balanced_score` | Parametric hallucination, verbose abstention ("I do not see the answer in the text"), over-refusal. |

---

### 9.2 Gold Test Fixtures (Hand-Computable Verification Data)

#### SciQ Test Fixtures
```json
[
  {"id": "sciq:test:0", "correct": "oxidants", "choices": {"A": "oxidants", "B": "antioxidants", "C": "Oxygen", "D": "residues"}, "pred": "A", "exp_correct": true},
  {"id": "sciq:test:1", "correct": "clone", "choices": {"A": "phenotype", "B": "male", "C": "clone", "D": "adult"}, "pred": "The answer is (C)", "exp_correct": true},
  {"id": "sciq:test:2", "correct": "gravity", "choices": {"A": "friction", "B": "gravity", "C": "magnetism", "D": "inertia"}, "pred": "friction", "exp_correct": false},
  {"id": "sciq:test:3", "correct": "photosynthesis", "choices": {"A": "respiration", "B": "digestion", "C": "photosynthesis", "D": "osmosis"}, "pred": "I am not sure.", "exp_correct": false}
]
```
- **Expected SciQ Metrics**:
  - `accuracy`: $2 / 4 = 0.5000$ (50.0%)
  - `invalid_parsed_rate`: $1 / 4 = 0.2500$ (25.0%)

#### WDC-PAVE Test Fixtures
```json
[
  {"id": 1, "target": {"Brand": ["Apple"], "Color": ["Black"]}, "pred": {"Brand": "Apple", "Color": "Black"}},
  {"id": 2, "target": {"Brand": ["Dell"], "Color": null}, "pred": {"Brand": "Dell", "Color": "Red"}},
  {"id": 3, "target": {"Brand": ["Sony"], "Weight": ["1kg"]}, "pred": {"Brand": "Sony", "Weight": null}},
  {"id": 4, "target": {"Brand": ["Samsung"]}, "pred": {"Brand": "LG"}},
  {"id": 5, "target": {"Color": null}, "pred": {"Color": null}}
]
```
- Outcome breakdown by attribute:
  - Record 1: Brand $\to$ VC, Color $\to$ VC.
  - Record 2: Brand $\to$ VC, Color $\to$ NV (target null, predicted "Red").
  - Record 3: Brand $\to$ VC, Weight $\to$ VN (target "1kg", predicted null).
  - Record 4: Brand $\to$ VW (target "Samsung", predicted "LG").
  - Record 5: Color $\to$ NN (target null, predicted null).
- Cumulative counts: `VC = 4`, `NV = 1`, `VN = 1`, `VW = 1`, `NN = 1`.
- **Expected WDC-PAVE Metrics**:
  $$\text{Micro-Precision} = \frac{4}{4 + 1 + 1} = \frac{4}{6} \approx 0.6667 \quad (66.67\%)$$
  $$\text{Micro-Recall} = \frac{4}{4 + 1 + 1} = \frac{4}{6} \approx 0.6667 \quad (66.67\%)$$
  $$\text{Micro-F1} = \frac{2 \times 0.6667 \times 0.6667}{0.6667 + 0.6667} \approx 0.6667 \quad (66.67\%)$$

#### LegalBench (Contract NLI) Test Fixtures
```json
[
  {"id": "cnli:0", "task": "limited_use", "answer": "Yes", "pred": "Yes", "exp_norm": "yes", "exp_correct": true},
  {"id": "cnli:1", "task": "limited_use", "answer": "No", "pred": "No.", "exp_norm": "no", "exp_correct": true},
  {"id": "cnli:2", "task": "limited_use", "answer": "Yes", "pred": "No", "exp_norm": "no", "exp_correct": false},
  {"id": "cnli:3", "task": "limited_use", "answer": "No", "pred": "The clause allows it.", "exp_norm": "the clause allows it", "exp_correct": false}
]
```
- Positive class (Yes): 2 items, 1 correct $\to \text{Recall}_{\text{Yes}} = 1/2 = 0.5000$.
- Negative class (No): 2 items, 1 correct $\to \text{Recall}_{\text{No}} = 1/2 = 0.5000$.
- **Expected LegalBench Metrics**:
  $$\text{Balanced-Accuracy} = \frac{0.5000 + 0.5000}{2} = 0.5000 \quad (50.0\%)$$
  $$\text{Raw Accuracy} = 2 / 4 = 0.5000 \quad (50.0\%)$$

#### IFEval Test Fixtures
```json
[
  {
    "key": 1,
    "instructions": ["length_constraints:number_words", "punctuation:no_comma"],
    "kwargs": [{"num_words": 10, "relation": "at least"}, {}],
    "response": "This is a clean sentence written without any prohibited punctuation marks.",
    "exp_strict": [true, true], "exp_loose": [true, true]
  },
  {
    "key": 2,
    "instructions": ["punctuation:no_comma"],
    "kwargs": [{}],
    "response": "Here is an answer, containing an illicit comma.",
    "exp_strict": [false], "exp_loose": [false]
  },
  {
    "key": 3,
    "instructions": ["detectable_format:number_highlighted_sections", "punctuation:no_comma"],
    "kwargs": [{"num_highlights": 1}, {}],
    "response": "*Important Section*\nThis line is clean and carries no comma",
    "exp_strict": [true, true], "exp_loose": [true, true]
  }
]
```
- Prompts: 3 total. Prompt 1 follows all (strict & loose). Prompt 2 fails comma. Prompt 3 follows all.
- Instructions: 5 total (Key 1: 2, Key 2: 1, Key 3: 2). Followed strictly: 4. Followed loosely: 4.
- **Expected IFEval Metrics**:
  - `prompt_level_strict_acc`: $2 / 3 \approx 0.6667$ (66.67%)
  - `prompt_level_loose_acc`: $2 / 3 \approx 0.6667$ (66.67%)
  - `inst_level_strict_acc`: $4 / 5 = 0.8000$ (80.0%)
  - `inst_level_loose_acc`: $4 / 5 = 0.8000$ (80.0%)

#### FaithEval Test Fixtures
```json
[
  {"qid": "f1", "type": "unanswerable", "answers": ["unknown", "no answer", "no information"], "pred": "unknown", "exp_strict": true, "exp_loose": true},
  {"qid": "f2", "type": "unanswerable", "answers": ["unknown", "no answer", "no information"], "pred": "There is no information provided in the context.", "exp_strict": false, "exp_loose": true},
  {"qid": "f3", "type": "unanswerable", "answers": ["unknown", "no answer", "no information"], "pred": "The treaty was signed in 1804.", "exp_strict": false, "exp_loose": false},
  {"qid": "f4", "type": "control_answerable", "answers": ["Paris"], "pred": "Paris", "exp_strict": true, "exp_loose": true},
  {"qid": "f5", "type": "control_answerable", "answers": ["1999"], "pred": "unknown", "exp_strict": false, "exp_loose": false}
]
```
- Unanswerable items (f1–f3): 3 total. Strict correct: 1 (`f1`). Loose correct: 2 (`f1`, `f2`).
- Answerable control items (f4–f5): 2 total. Correct: 1 (`f4`). Item `f5` is a false refusal (`unknown`).
- **Expected FaithEval Metrics**:
  - `unanswerable_acc_strict`: $1 / 3 \approx 0.3333$ (33.33%)
  - `unanswerable_acc_loose`: $2 / 3 \approx 0.6667$ (66.67%)
  - `answerable_control_acc`: $1 / 2 = 0.5000$ (50.0%)
  - `balanced_score`: $\frac{2 \times (2/3) \times (1/2)}{(2/3) + (1/2)} = \frac{2/3}{7/6} = \frac{4}{7} \approx 0.5714$ (57.14%)

---

## 10. Known Pitfalls & Benchmark Validity Threats

1. **SciQ Support Bleed in Closed-Book**:
   - Accidental inclusion of the `support` column during `closed-book` runs elevates performance artificially by 20–35 accuracy points. Loaders must explicitly strip the `support` key when instantiating closed-book prompt builders.
2. **SciQ Empty-Support Conflation**:
   - Evaluating `sciq:evidence-grounded` on rows with `support == ""` creates ill-defined prompts where the model is told to refer to context that is missing.
3. **WDC-PAVE `n/a` Rewarding**:
   - Any scorer that credits `n/a` predictions as true positives (`VC`) will grant models near-perfect F1 scores simply for outputting all-null dictionaries (since 70%+ of category attribute values are absent in real product listings).
4. **WDC-PAVE Normalization Confusion**:
   - Penalizing raw substring extractions because they lack unit conversion (e.g. demanding `99.1 cm` when the text says `39 in`) breaks comparability against published baseline extraction numbers.
5. **LegalBench Imbalanced Subtasks & Naive Accuracy**:
   - Tasks such as `contract_nli_explicit_identification` (18.3% Yes) or `contract_nli_permissible_copy` (20.7% Yes) yield 80%+ naive accuracy under a trivial constant `"No"` prediction. Evaluators must strictly report **Balanced Accuracy**.
6. **IFEval Sentence Segmentation Discrepancies**:
   - Naive Python splitting on `.` miscounts titles ("Mr.", "Dr.") and numbered lists ("1. First item") as sentence boundaries. Evaluating `length_constraints:number_sentences` without NLTK's `sent_tokenize` invalidates strict alignment with Google Leaderboard scores.
7. **FaithEval Sycophancy & Degenerate Abstention**:
   - Without an answerable control, prompt engineering that forces `"unknown"` yields deceptively high faithfulness scores while destroying general QA capability.

---

## 11. Reference Sources & URLs Verified

1. **SciQ**:
   - Hugging Face Dataset Card & Viewer API: `https://datasets-server.huggingface.co/info?dataset=allenai/sciq`
   - Split & Storage API: `https://datasets-server.huggingface.co/size?dataset=allenai/sciq`
   - Original Paper: Welbl et al., "Crowdsourcing Multiple Choice Science Questions" (2017): `https://arxiv.org/abs/1707.06209`
2. **WDC-PAVE**:
   - Official Project Repository: `https://github.com/wbsg-uni-mannheim/wdc-pave`
   - Scorer Implementation: `https://raw.githubusercontent.com/wbsg-uni-mannheim/wdc-pave/main/pieutils/evaluation.py`
   - Data Descriptions: `https://raw.githubusercontent.com/wbsg-uni-mannheim/wdc-pave/main/data/processed_datasets/README.md`
   - Hugging Face Pre-split Mirror: `https://huggingface.co/datasets/siavashsaki/wdc-pave-ave`
   - Paper: Primpeli & Bizer, "Using LLMs for the Extraction and Normalization of Product Attribute Values" (ADBIS 2024 / arXiv:2403.02130): `https://arxiv.org/abs/2403.02130`
3. **LegalBench (Contract NLI)**:
   - Hugging Face Dataset Card: `https://datasets-server.huggingface.co/info?dataset=nguha/legalbench`
   - Official LegalBench Repository: `https://github.com/HazyResearch/legalbench`
   - Scorer Implementation: `https://raw.githubusercontent.com/HazyResearch/legalbench/main/evaluation.py`
   - Task Prompts & Documentation: `https://raw.githubusercontent.com/HazyResearch/legalbench/main/tasks/contract_nli_confidentiality_of_agreement/README.md`
   - Original ContractNLI Paper: Koreeda & Manning, "ContractNLI: A dataset for document-level natural language inference for contracts" (Findings of EMNLP 2021): `https://arxiv.org/abs/2110.01799`
4. **IFEval**:
   - Hugging Face Dataset Viewer: `https://datasets-server.huggingface.co/first-rows?dataset=google/IFEval&config=default&split=train`
   - Official Google Research Repository: `https://github.com/google-research/google-research/tree/master/instruction_following_eval`
   - Scorer & Registry Source: `https://raw.githubusercontent.com/google-research/google-research/master/instruction_following_eval/evaluation_lib.py` and `instructions_registry.py`
   - Paper: Zhou et al., "Instruction-Following Evaluation for Large Language Models" (arXiv:2311.07911): `https://arxiv.org/abs/2311.07911`
5. **FaithEval**:
   - Hugging Face Dataset Hub: `https://huggingface.co/datasets/Salesforce/FaithEval-unanswerable-v1.0`
   - Hugging Face Dataset Viewer API: `https://datasets-server.huggingface.co/first-rows?dataset=Salesforce/FaithEval-unanswerable-v1.0&config=default&split=test`
   - Official GitHub Repository: `https://github.com/SalesforceAIResearch/FaithEval`
   - Paper: Ming et al., "FaithEval: Can Your Language Model Stay Faithful to Context, Even If 'The Moon is Made of Marshmallows'" (ICLR 2025 / arXiv:2410.03727): `https://arxiv.org/abs/2410.03727`

---

## 12. Verification Pass

### V1. WDC-PAVE Mirror Legality, Candidate Search, and Schema Audit

#### 1. Mirror Provenance (`siavashsaki/wdc-pave-ave`)
- **Metadata query**: `curl -sS "https://huggingface.co/api/datasets/siavashsaki/wdc-pave-ave"`
  ```json
  {
    "id": "siavashsaki/wdc-pave-ave",
    "author": "siavashsaki",
    "downloads": 56,
    "lastModified": "2026-03-26T19:41:00.000Z",
    "license": "cc-by-4.0",
    "tags": ["task_categories:token-classification", "task_categories:text-generation", "e-commerce"]
  }
  ```
- **Author Relationship**: Unrelated third-party account (`siavash-saki/wdc-pave-finetuning` on GitHub). The upstream paper authors are Anna Primpeli and Christian Bizer from the Web-based Systems Group, University of Mannheim (`wbsg-uni-mannheim`). The account `siavashsaki` does NOT own or represent the upstream publication.

#### 2. Candidate Search for Official Release on Hugging Face
- Queries: `search=wdc-pave`, `search=wdc&full=true`, `search=pave`.
- Search Results:
  - `wdc-pave`: Only `siavashsaki/wdc-pave-ave` exists (56 downloads).
  - `wdc`: Official `wdc` organization hosts only `wdc/products-2017` (2,327 downloads; entity matching, not attribute extraction).
  - `pave`: Pavement inspection datasets (`VVQNN/PaveBench`, `reannayang/FL_pavement`), video models (`zhuomingliu/PAVEDataset`), zero official product extraction datasets.
- **Finding**: There is NO official Hugging Face upload from the University of Mannheim for WDC-PAVE.

#### 3. Real Schema: HF Mirror (`siavashsaki/wdc-pave-ave`)
- First-rows viewer endpoint failed with `Job manager crashed while running this job (missing heartbeats)` because raw JSONL is not pre-converted to Parquet on datasets-server.
- Direct row inspection of `test.jsonl`:
  ```json
  {
    "id": 11097788,
    "category": "Computers And Accessories",
    "input_title": "400291-001 HP Battery Backup HZX 70-80\", New 400291-001 70-80 Wholesale Price 400291-001",
    "input_description": "Description:Battery Backup HZX 70-80Part Number(s) Hewlett-Packard Part# 400291-001",
    "gold_json": {
      "Generation": null,
      "Part Number": "400291001",
      "Product Type": "Storage Solutions",
      "Cache": null,
      "Processor Type": null,
      "Processor Core": null,
      "Interface": null,
      "Manufacturer": "Hewlett-Packard",
      "Capacity": null,
      "Ports": null,
      "Rotational Speed": null
    }
  }
  ```
- Multi-valued attribute instance (Row 3, id 8624731, Office Products):
  `"Color(s)": ["Green", "White"]`
- Multi-valued attribute instance (Row 8, id 16767368, Computers And Accessories):
  `"Manufacturer": ["Hewlett-Packard", "Hewlett-Packard Enterprise"]`
- **Schema Type**: `gold_json` is an unescaped dictionary (nested JSON object), mapping string keys to single strings, sorted string arrays, or `null`.

#### 4. Official Upstream Raw File (`wbsg-uni-mannheim/wdc-pave`)
- Inspection of `https://raw.githubusercontent.com/wbsg-uni-mannheim/wdc-pave/main/data/processed_datasets/wdc_with_all_attributes/test.jsonl`:
  - Line count: exactly 354 lines (432,219 bytes).
  - First record:
    ```json
    {
      "id": 7230884,
      "cluster_id": 14208681.0,
      "category": "Computers And Accessories",
      "input_title": "435952-B21 HP Xeon E5335 2.0GHz DL360 G5\" Null",
      "input_description": "Description:Intel Xeon E5335 DL360 G5(2.0GHz/4-core/8MB-2x4MB/80W)Full Processor Option KitPart Number(s) Part# 435952-B21 Spare 437948-001 Assembly 437426-001\"",
      "target_scores": {
        "Generation": {"G5": {"pid": [0, 1], "score": 1}},
        "Part Number": {"435952-B21": {"pid": [0, 1], "score": 1}},
        "Product Type": {"Processor Option Kit": {"pid": [1], "score": 1}},
        "Cache": {"8MB-2x4MB": {"pid": [1], "score": 1}},
        "Processor Type": {"Xeon E5335": {"pid": [0], "score": 1}, "Intel Xeon E5335": {"pid": [1], "score": 1}},
        "Processor Core": {"4-core": {"pid": [1], "score": 1}},
        "Bus Speed": {"n/a": 1},
        "Capacity": {"n/a": 1},
        "Interface": {"n/a": 1},
        "Ports": {"n/a": 1},
        "Rotational Speed": {"n/a": 1}
      }
    }
    ```
- Temporary file `/tmp/pave.jsonl` was verified and immediately removed.

#### 5. Explicit Adapter Loading Decision
- **DEFAULT (Canonical Official)**: Load directly from the official University of Mannheim GitHub repository:
  `URL: https://raw.githubusercontent.com/wbsg-uni-mannheim/wdc-pave/main/data/processed_datasets/wdc_with_all_attributes/test.jsonl`
  - Implementation: Python stdlib `urllib.request` + `json.loads` per line.
  - Disk cost: 422 KB total. Zero Hugging Face datasets dependency. Avoids datasets-server worker crashes.
  - Row count: 354 test rows (the exact test set evaluated in published benchmark papers).
- **DOCUMENTED FALLBACK**: `siavashsaki/wdc-pave-ave` on Hugging Face (`split="test"`). Note: this mirror re-split the 1,420 records into 284 test rows (70/10/20) and flattened `target_scores` into `gold_json`.

---

### V2. SciQ Streaming, Enumeration, and Stable IDs

1. **Split Enumerable & Column Verification**:
   - `/size` response: `test` split has exactly 1,000 rows (342,808 bytes parquet).
   - `/info` response: features are `correct_answer`, `distractor1`, `distractor2`, `distractor3`, `question`, `support`. No `id` column exists.
2. **Deterministic Stable ID Rule**:
   - Adapter iterates the test split sequentially and generates:
     `stable_id = f"sciq:test:{row_index}"` for `row_index in range(1000)`.
   - The test split is stored in a single immutable parquet file (`data/test-00000-of-00001.parquet`), guaranteeing deterministic index assignment across runs.
3. **Deterministic Sampling Rule**:
   - Compute `hash = hashlib.sha256(f"{dataset_id}:{split}:{seed}:{stable_id}".encode()).hexdigest()`.
   - Sort eligible items by `hash` ascending and select the first $N$.
   - Cost: Streaming all 1,000 test rows consumes 342 KB network transfer and <0.1s CPU.
4. **Empty `support` Behavior**:
   - `sciq:closed-book`: All 1,000 rows are eligible (`support` is omitted from prompt).
   - `sciq:evidence-grounded`: Exactly 116 test rows have `support == ""` (e.g. Saylor book citations lacking scraped body text). These 116 rows MUST be filtered out by `len(support.strip()) > 0`, leaving 884 eligible test rows.

---

### V3. IFEval Vendoring Feasibility & Dependency Resolution

1. **License Verification**:
   - File header across all `instruction_following_eval/*.py` files:
     ```python
     # Copyright 2026 The Google Research Authors.
     # Licensed under the Apache License, Version 2.0 (the "License");
     ```
   - Permissive Apache-2.0 allows vendoring into `vendor/instruction_following_eval/`.
2. **Vendored File Catalog (Total: 88,924 bytes ~ 87 KB)**:
   - `evaluation_lib.py`: 6,984 bytes
   - `instructions.py`: 55,162 bytes
   - `instructions_registry.py`: 7,240 bytes
   - `instructions_util.py`: 19,538 bytes
3. **Exact Pinned Dependencies (Python 3.13 via uv)**:
   - Command: `uv pip compile - --python-version 3.13`
     ```
     absl-py==2.5.1
     click==8.5.0
     cloudpickle==3.1.2
     defusedxml==0.7.1
     immutabledict==4.3.1
     joblib==1.6.0
     langdetect==1.0.9
     nltk==3.10.4
     regex==2026.9.29
     six==1.17.0
     tqdm==4.70.1
     ```
4. **NLTK Tokenizer Offline Requirement**:
   - NLTK $\ge 3.9$ requires the `punkt_tab` data resource for `sent_tokenize`.
   - Download size: `punkt_tab.zip` is 4,319,076 bytes (~4.12 MB). Uncompressed size: ~14 MB.
   - Offline pre-download:
     `python -c "import nltk; nltk.download('punkt_tab', download_dir='vendor/nltk_data')"`
   - Set environment variable `NLTK_DATA=vendor/nltk_data` for air-gapped evaluation.

---

### V4. FaithEval Answerable Control & Upstream Pairing Audit

1. **Mirror Audit (`alvinming/FaithEval-unanswerable-v1.0-w-original_context`)**:
   - Parquet inspection of `data/train-00000-of-00001.parquet` (2,492 rows):
     ```json
     {
       "qid": "00db38fb517e4923b81b5efa298e532e",
       "subset": "SQuAD",
       "question": "What did the Mongol elites wish Buyantu didn't do?",
       "context": "The fourth Yuan emperor, Buyantu Khan (Ayurbarwada)... [sentence removed]",
       "original_context": "The fourth Yuan emperor, Buyantu Khan (Ayurbarwada)... He was the first Yuan emperor to actively support and adopt mainstream Chinese culture after the reign of Kublai, to the discontent of some Mongol elite...",
       "justification": "The sentence mentioning Buyantu Khan's support... has been removed.",
       "answers": ["unanswerable", "unknown", "no answer", "no information", "not", "unclear"]
     }
     ```
2. **Critical Ground-Truth Answer Finding**:
   - While `original_context` is preserved, the `answers` column in `alvinming/...` contains **ONLY the unanswerable refusal labels**, NOT the original ground-truth answer phrase ("actively support and adopt mainstream Chinese culture").
   - This holds across all 2,492 rows: FaithEval never bundled the extractive ground-truth answers for the answerable precursors.
3. **Explicit Protocol Designation**:
   - The upstream FaithEval benchmark evaluates *only* unanswerable abstention accuracy.
   - Adding an **Answerable Control** is **OUR documented protocol addition** to protect against trivial always-abstain models.
   - **Implementation**: The answerable control must be evaluated by sampling a deterministic subset from `rajpurkar/squad` (validation split, seed=42) using standard SQuAD exact match / token F1 scoring, alongside FaithEval unanswerable accuracy.

---

### V5. LegalBench Config Loading Cost & Parquet Sharding

1. **Config Parquet Verification**:
   - `/parquet?dataset=nguha/legalbench` confirms each of the 14 Contract NLI configs is hosted as a dedicated, standalone Parquet file:
     - `contract_nli_confidentiality_of_agreement`: `test/0000.parquet` (24,169 bytes ~ 23.6 KB)
     - `contract_nli_limited_use`: `test/0000.parquet` (47,073 bytes ~ 46.0 KB)
     - `contract_nli_notice_on_compelled_disclosure`: `test/0000.parquet` (37,236 bytes ~ 36.4 KB)
     - `contract_nli_permissible_acquirement_of_similar_information`: `test/0000.parquet` (41,212 bytes ~ 40.2 KB)
     - `contract_nli_sharing_with_third-parties`: `test/0000.parquet` (48,164 bytes ~ 47.0 KB)
2. **Download Isolation**:
   - Executing `load_dataset("nguha/legalbench", "contract_nli_limited_use", split="test", streaming=True)` downloads ONLY that single 46 KB Parquet file.
   - It does NOT pull the 193 MB repository or other unrelated tasks.

---

### V6. `datasets` Version Pin & Python 3.13 Compatibility

1. **PyPI Metadata Check (`datasets==2.21.0`)**:
   - `requires_python: ">=3.8.0"`
   - `pyarrow>=15.0.0`
   - `numpy>=1.17`
   - `dill<0.3.9,>=0.3.0`
2. **Joint Resolution Test with Python 3.13**:
   - Command: `uv pip compile - --python-version 3.13` with `datasets==2.21.0` and `transformers==5.15.0`:
     - `datasets==2.21.0`
     - `transformers==5.15.0`
     - `dill==0.3.8`
     - `fsspec==2024.6.1`
     - `numpy==2.5.4`
     - `pyarrow==26.0.0`
3. **Compatibility Status**:
   - **VERIFIED**: Zero dependency conflicts. `datasets==2.21.0` installs and runs on Python 3.13, natively supports `streaming=True`, and handles all benchmark formats (Parquet and JSONL).
