# Extending Rapier Bench

This document outlines the standard extension patterns for adding models, datasets, metrics, and benchmark protocols to Rapier Bench.

## 1. Adding a New Model

### Step 1: Update Model Registry Configuration

Add an entry to `configs/models.yaml`:

```yaml
- id: "my-model-0.5b"
  name: "My Model 0.5B Instruct"
  hf_id: "org/my-model-0.5b-instruct"
  revision: "abc1234def5678"          # Pinned Git commit SHA
  parameters: 500000000
  context_length: 4096
  vocab_size: 32000
  torch_dtype: "bfloat16"             # bfloat16 or float16 for 4GB VRAM
  attn_implementation: "sdpa"         # Scaled dot-product attention
  device_policy: "cuda"
  trust_remote_code: false
  model_type: "llama"
  architecture: "LlamaForCausalLM"
  chat_template_mode: "jinja"
  # Quirks (optional):
  # add_generation_prompt: false      # Set false if template already emits assistant header
  # add_special_tokens: false         # Set false if template already emits BOS token
  license: "Apache-2.0"
  vram_weight_gb: 1.05
  generation_defaults:
    do_sample: false
    temperature: 0.0
    max_new_tokens: 512
    repetition_penalty: 1.0
```

### Step 2: Smoke-Test Model Definition

Validate loading, prompt formatting, and tokenization quirks without downloading weights:

```bash
.venv/bin/python -m benchmark.cli run \
  --model my-model-0.5b \
  --dataset sciq \
  --protocol sciq_evidence_grounded \
  --samples smoke \
  --dry-run
```

## 2. Adding a New Dataset Adapter

Datasets are decoupled from raw Hugging Face loaders via `DatasetAdapter` (`benchmark/core/dataset.py`).

### Step 1: Implement Dataset Adapter

Create an adapter under `benchmark/datasets/`:

```python
from benchmark.core.dataset import DatasetAdapter
from benchmark.core.types import NormalizedSample, TaskType

class MyDatasetAdapter(DatasetAdapter):
    def load(self, split: str = "test") -> list[NormalizedSample]:
        # Upstream loading (datasets.load_dataset or local JSONL)
        raw_records = ...
        samples = []
        for idx, row in enumerate(raw_records):
            # Enforce Stable ID Rule: dataset:split:index or upstream unique ID
            stable_id = f"my_dataset:{split}:{row.get('id', idx)}"
            samples.append(
                NormalizedSample(
                    sample_id=stable_id,
                    dataset_id="my_dataset",
                    dataset_revision="main",
                    domain="finance",
                    task_type=TaskType.BINARY_CLASSIFICATION,
                    input_payload={"premise": row["text"], "hypothesis": row["claim"]},
                    references={"label": row["gold_label"]},
                )
            )
        return samples
```

### Step 2: Register Dataset Configuration

Add an entry to `configs/datasets.yaml`:

```yaml
- id: "my_dataset"
  name: "Financial Claim Verification"
  hf_id: "org/finance-claims"
  domain: "finance"
  task_type: "binary_classification"
  evaluator_key: "my_evaluator"
  default_split: "test"
  metrics:
    - "balanced_accuracy"
    - "accuracy"
  default_protocol_id: "my_dataset_default"
  sampling_modes:
    smoke: 10
    pilot: 25
    standard: 100
    full: 500
```

## 3. Adding an Evaluator & New Metrics

Evaluators consume raw and parsed predictions alongside normalized references (`benchmark/core/evaluator.py`).

### Step 1: Implement Evaluator Class

```python
from benchmark.core.evaluator import Evaluator
from benchmark.core.types import NormalizedSample, PredictionRecord

class MyEvaluator(Evaluator):
    def evaluate(
        self,
        predictions: list[PredictionRecord],
        samples: list[NormalizedSample],
    ) -> dict[str, float]:
        sample_map = {s.sample_id: s for s in samples}
        correct = 0
        total = len(predictions)

        for pred in predictions:
            sample = sample_map.get(pred.sample_id)
            if not sample:
                continue
            gold = sample.references["label"]
            if pred.parsed_output == gold:
                correct += 1

        accuracy = (correct / total) if total > 0 else 0.0
        return {
            "accuracy": round(accuracy, 4),
            "sample_count": float(total),
        }
```

### Step 2: Wire Evaluator Registry

Register the key in `benchmark/evaluators/__init__.py` and update the recommendation engine primary metric mapping in `backend/app/services/recommendation_engine.py`:

```python
PRIMARY_METRIC_MAP["binary_classification"] = "balanced_accuracy"
DATASET_PRIMARY_METRIC["my_dataset"] = "accuracy"
```

## 4. Creating Protocol Definitions

Protocols specify prompt structure and formatting expectations. Add YAML file to `configs/protocols/<dataset_name>.yaml`:

```yaml
- id: "my_dataset_default"
  name: "Financial Claim Evaluation Protocol"
  version: "1.0.0"
  dataset_id: "my_dataset"
  domain: "finance"
  task_type: "binary_classification"
  prompt_template: |
    Premise: {premise}
    Hypothesis: {hypothesis}
    Is the hypothesis supported by the premise? Answer Yes or No.
  expected_answer_format: "exact_match"
```

### Protocol Versioning Rule

Modifying `prompt_template` changes the calculated SHA-256 `prompt_hash` per record. When altering prompts or instructions, bump the `version` field (e.g. `1.0.0` to `1.1.0`) to avoid conflating benchmark runs.

## 5. End-to-End Suite Checklist

Before submitting a new benchmark suite:

1. **Deterministic Sampling**: Verify stable IDs and SHA-256 sorting produce reproducible subsets across multiple seeds.
2. **Gold Test Fixtures**: Add `tests/fixtures/<name>_gold.json` containing at least 4 known inputs and hand-calculated metric expectations.
3. **Unit Tests**: Implement evaluator assertions in `tests/unit/test_evaluators.py` against the gold fixture.
4. **Prompt Leak Protection**: Verify `DefaultPromptBuilder` rejects templates containing references to gold evaluation fields.
5. **Dry Run**: Confirm `.venv/bin/python -m benchmark.cli run --dataset <id> --protocol <id> --dry-run` exits with code 0.
