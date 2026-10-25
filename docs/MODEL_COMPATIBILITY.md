# Model Compatibility Specification: Rapier Bench

Evidence-backed inference and environment specification for local execution of small instruction-tuned models on NVIDIA GeForce RTX 3050 Laptop GPU (4096 MiB VRAM, Ampere SM 8.6, CUDA 13.0, Driver 580.178.04, 14 GiB RAM, 16 CPU cores).

---

## 1. Model Overview & Hardware Compatibility Matrix

| Parameter | FrontiersMind/Lumma-0.6B-Instruct | swiss-ai/Apertus-v1.1-0.5B-Instruct | LiquidAI/LFM2.5-350M |
| :--- | :--- | :--- | :--- |
| **Exact Repo ID** | `FrontiersMind/Lumma-0.6B-Instruct` | `swiss-ai/Apertus-v1.1-0.5B-Instruct` | `LiquidAI/LFM2.5-350M` |
| **Commit SHA** | `668bc2f2ad9f3858d047e0e39ae57a7ad84effc2` | `a140fd61fb57422c36a26301caea17edee799874` | `9e6c6ccf47cd318696e137d381a7ded8fe4df09f` |
| **Architecture Class** | `LummaForCausalLM` | `ApertusForCausalLM` | `Lfm2ForCausalLM` |
| **Parameter Count** | 649,281,964 (~0.65B) | 572,567,080 (~0.57B) | 354,483,968 (~0.35B) |
| **Weight File (`safetensors`)** | `model.safetensors` | `model.safetensors` | `model.safetensors` |
| **Weight Size (Bytes)** | **1,298,775,408 B** (1.21 GiB / 1.30 GB) | **1,145,165,288 B** (1.07 GiB / 1.15 GB) | **708,984,464 B** (0.66 GiB / 0.71 GB) |
| **Shipped Dtype** | `bfloat16` (649M BF16 + 90k F32) | `bfloat16` (572M BF16) | `bfloat16` (354M BF16) |
| **Ampere SM86 BF16 Support** | Native Hardware Support | Native Hardware Support | Native Hardware Support |
| **Fits 4096 MiB VRAM (FP16/BF16)** | **YES** | **YES** | **YES** |
| **Weight Footprint (2B/param)** | ~1,238.4 MiB | ~1,092.1 MiB | ~676.1 MiB |
| **Total Peak VRAM @ safe budget** | ~2,172 MiB @ 2048 seq | ~1,922 MiB @ 4096 seq | ~1,424 MiB @ 4096 seq |
| **Safe `max_new_tokens` (4GB VRAM)**| **4096 tokens** | **3584 tokens** (context ceiling 4096) | **4096 tokens** |
| **Remote Code Required** | **YES** (`trust_remote_code=True`) | **NO** (`trust_remote_code=False`) | **NO** (`trust_remote_code=False`) |
| **Built-in `transformers`**| No (custom hub module) | Yes (`>= 4.56.0`) | Yes (`>= 4.57.6` / `5.0.0rc1`) |
| **Compatible w/ `v4.57.6`** | **NO** (needs `output_capturing`) | **YES** (native in `4.57.6`) | **YES** (native in `4.57.6`) |
| **Attn Implementation** | `"sdpa"` (preferred) / `"eager"` | `"sdpa"` (preferred) / `"eager"` | `"sdpa"` (preferred) / `"eager"` |
| **Chat Template File** | `chat_template.jinja` | `chat_template.jinja` | `chat_template.jinja` |
| **Direct `apply_chat_template`**| Yes (`add_generation_prompt=False`) | Yes (`add_special_tokens=False`) | Yes (`add_generation_prompt=True`) |
| **BOS / EOS / PAD Token IDs** | `1` / `0` / `3` | `1` / `68` / `10` | `1` / `7` / `0` |
| **License** | Apache-2.0 | Apache-2.0 (with SNAI AUP) | LFM Open License v1.0 ($10M cap) |

---

## 2. Hardware Capabilities & Sizing Constraints

### 2.1 GPU Architecture & BF16 Hardware Capability
- **Target GPU**: NVIDIA GeForce RTX 3050 Laptop GPU (GA107, Compute Capability SM 8.6).
- **BF16 Support**: **VERIFIED NATIVE**. NVIDIA Ampere (SM 8.0, 8.6) includes hardware Bfloat16 Tensor Cores and vector ALU instructions. No emulation or performance penalty occurs when running `torch.bfloat16`.
- **Dtype Recommendation**: Pin `torch_dtype=torch.bfloat16`. Matches repository-shipped weights directly, eliminates range-clipping hazards present in fp16, and uses identical memory (2 bytes/param). `torch_dtype=torch.float16` also fits within identical memory.
- **Attention Kernel**: `attn_implementation="sdpa"` (PyTorch Scaled Dot Product Attention) is **safer and faster** on 4 GiB VRAM. On Ampere SM86, SDPA automatically dispatches to memory-efficient FlashAttention/Cutlass kernels, computing attention in $O(1)$ intermediate memory instead of allocating $O(N^2)$ full attention tensors. `"eager"` is supported as fallback but consumes more VRAM on long contexts.

### 2.2 Disk Budget Constraint
- **Root Free Space**: Only ~5.3 GiB available on `/dev/nvme0n1p6`.
- **Exact Download Sizes**:
  - Lumma: `model.safetensors` = `1,298,775,408` bytes (~1.21 GiB / 1.30 GB)
  - Apertus: `model.safetensors` = `1,145,165,288` bytes (~1.07 GiB / 1.15 GB)
  - LFM2.5: `model.safetensors` = `708,984,464` bytes (~0.66 GiB / 0.71 GB)
  - **Total Disk for All 3 Models**: **3,152,925,160 bytes (~2.94 GiB / 3.15 GB)**.
- **Disk Strategy**: Simultaneous caching consumes ~3.15 GB (60% of free space). If disk falls below safe headroom (<1 GB), evaluate models sequentially and purge cache (`rm -rf ~/.cache/huggingface/hub/models--...`), or set `HF_HOME` to an external mount.

---

## 3. FrontiersMind/Lumma-0.6B-Instruct

### 3.1 Metadata & Files
- **Repo ID**: `FrontiersMind/Lumma-0.6B-Instruct` (SHA: `668bc2f2ad9f3858d047e0e39ae57a7ad84effc2`).
- **Files Needed**: `config.json`, `configuration_lumma.py`, `modeling_lumma.py`, `tokenizer.json`, `tokenizer_config.json`, `chat_template.jinja`, `model.safetensors`.
- **Weights File**: `model.safetensors` (exact: **1,298,775,408 bytes**).
- **Shipped Dtype**: `bfloat16` (`safetensors` contains 649,191,424 BF16 + 90,540 F32 params; `config.json` specifies `"dtype": "bfloat16"`).
- **Remote Code**: `trust_remote_code=True` **MANDATORY**. Architecture `Lumma` is not in official `transformers`.

### 3.2 4 GiB VRAM Budget Breakdown (FP16/BF16)
- **Weight Footprint**: 649,281,964 params × 2 bytes = 1,298,563,928 bytes ≈ **1,238.4 MiB**.
- **KV Cache Estimate**:
  - Configuration: 30 hidden layers, 8 key-value heads, head_dim 90.
  - Mode: `shared_kv=True`, `kv_cache_mode="shared"` (stores 1 key tensor per token, values shared).
  - Formula: $30 \times 8 \times 90 \times 2 \times 1 = 43,200 \text{ bytes/token} \approx 0.0412 \text{ MiB/token}$ `[ESTIMATE]`.
  - At sequence length 1,024: ~42.2 MiB `[ESTIMATE]`.
  - At sequence length 2,048: ~84.4 MiB `[ESTIMATE]`.
  - At sequence length 4,096: ~168.8 MiB `[ESTIMATE]`.
  - At sequence length 12,288 (context ceiling): ~506.3 MiB `[ESTIMATE]`.
- **Runtime Overheads**: PyTorch CUDA context (~350 MiB) + activation memory (~500 MiB) `[ESTIMATE]`.
- **Total Peak VRAM**:
  - At 2,048 tokens: 1,238.4 (weights) + 84.4 (KV) + 500 (act) + 350 (context) ≈ **2,172.8 MiB** (~2.12 GiB).
  - VRAM Headroom on 4096 MiB GPU: **~1,923 MiB**.
- **Safe `max_new_tokens` Budget**: **4096 tokens** (assuming prompt $\le 1024$ tokens, total VRAM remains under ~2.4 GiB).

### 3.3 Chat Template & Quirk
- **Direct Template**: Supported via `chat_template.jinja`.
- **System Prompt**: Enforces hardcoded default header:
  `You are Lumma developed by FrontiersMind. You are a helpful assistant who follows all instructions given by the user.`
  User-supplied system content is appended after `\n\n`.
- **CRITICAL QUIRK (Generation Prompt Duplication)**:
  `chat_template.jinja` user-role branch ends with `<|assistant|>\n`. Calling `tokenizer.apply_chat_template(..., add_generation_prompt=True)` causes duplicate `<|assistant|>` tokens.
  **Rule**: Call with `add_generation_prompt=False`.
- **Special Tokens**: BOS: `<|im_start|>` (1), EOS: `<|endoftext|>` (0), PAD: `<|pad|>` (3).

### 3.4 Pinned Loading Snippet
```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "FrontiersMind/Lumma-0.6B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    trust_remote_code=True,
    torch_dtype=torch.bfloat16,
    device_map="cuda:0",
    attn_implementation="sdpa",
).eval()
```
- **Sampling Config**: Benchmark uses greedy `do_sample=False`, `repetition_penalty=1.0` (card default is `temperature=0.3`, `top_p=0.90`, `top_k=20`, `repetition_penalty=1.1`).
- **License**: Apache-2.0. Outputs redistributable. Do not commit weights.

---

## 4. swiss-ai/Apertus-v1.1-0.5B-Instruct

### 4.1 Metadata & Files
- **Repo ID**: `swiss-ai/Apertus-v1.1-0.5B-Instruct` (SHA: `a140fd61fb57422c36a26301caea17edee799874`).
- **Files Needed**: `config.json`, `generation_config.json`, `model.safetensors`, `special_tokens_map.json`, `tokenizer.json`, `tokenizer_config.json`, `chat_template.jinja`.
- **Weights File**: `model.safetensors` (exact: **1,145,165,288 bytes**).
- **Shipped Dtype**: `bfloat16` (`safetensors` contains 572,567,080 BF16 params; `config.json` specifies `"dtype": "bfloat16"`).
- **Remote Code**: `trust_remote_code=False` (native in `transformers >= 4.56.0`).
- **Hub Gating**: Repo has `extra_gated_prompt` (SNAI Acceptable Use Policy). An authenticated session / `HF_TOKEN` must be present if downloading on an account subject to terms check.

### 4.2 4 GiB VRAM Budget Breakdown (FP16/BF16)
- **Weight Footprint**: 572,567,080 params × 2 bytes = 1,145,134,160 bytes ≈ **1,092.1 MiB**.
- **KV Cache Estimate**:
  - Configuration: 20 hidden layers, 4 key-value heads, head_dim 64 (1024 / 16).
  - Mode: Standard GQA (both K and V cached).
  - Formula: $20 \times 2 \times 4 \times 64 \times 2 = 20,480 \text{ bytes/token} \approx 0.0195 \text{ MiB/token}$ `[ESTIMATE]`.
  - At sequence length 1,024: ~20.0 MiB `[ESTIMATE]`.
  - At sequence length 2,048: ~40.0 MiB `[ESTIMATE]`.
  - At sequence length 4,096 (context ceiling): ~80.0 MiB `[ESTIMATE]`.
- **Runtime Overheads**: PyTorch CUDA context (~350 MiB) + activation memory (~400 MiB) `[ESTIMATE]`.
- **Total Peak VRAM**:
  - At max context 4,096 tokens: 1,092.1 (weights) + 80.0 (KV) + 400 (act) + 350 (context) ≈ **1,922.1 MiB** (~1.88 GiB).
  - VRAM Headroom on 4096 MiB GPU: **~2,174 MiB**.
- **Safe `max_new_tokens` Budget**: **3584 tokens** (fills the entire physical context ceiling of 4096 with prompt $\le 512$ tokens, consuming under 2 GiB total).

### 4.3 Chat Template & Quirk
- **Direct Template**: Supported via `chat_template.jinja`. Delimiters: system `<SPECIAL_61>`/`<SPECIAL_62>`, developer `<SPECIAL_63>`/`<SPECIAL_64>`, user `<SPECIAL_65>`/`<SPECIAL_66>`, assistant `<SPECIAL_67>`/`<SPECIAL_68>`.
- **CRITICAL QUIRK (`add_special_tokens=False`)**:
  `chat_template.jinja` line 1 starts with `{{ bos_token }}` (`<s>`, ID 1). Tokenizing the rendered prompt string with default `add_special_tokens=True` prepends a second duplicate `<s>`.
  **Rule**: You MUST call `tokenizer([text], return_tensors="pt", add_special_tokens=False)`.
- **Special Tokens**: BOS: `<s>` (1), EOS: `<SPECIAL_68>` (68), PAD: `<pad>` (10).

### 4.4 Pinned Loading Snippet
```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "swiss-ai/Apertus-v1.1-0.5B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    device_map="cuda:0",
    attn_implementation="sdpa",
).eval()
```
- **Sampling Config**: Benchmark uses greedy `do_sample=False` (card default is `temperature=0.8`, `top_p=0.9`).
- **License**: Apache-2.0 with SNAI Acceptable Use Policy. Outputs redistributable. Do not commit weights.

---

## 5. LiquidAI/LFM2.5-350M

### 5.1 Metadata & Files
- **Repo ID**: `LiquidAI/LFM2.5-350M` (SHA: `9e6c6ccf47cd318696e137d381a7ded8fe4df09f`).
- **Files Needed**: `config.json`, `generation_config.json`, `model.safetensors`, `tokenizer.json`, `tokenizer_config.json`, `chat_template.jinja`, `LICENSE`.
- **Weights File**: `model.safetensors` (exact: **708,984,464 bytes**).
- **Shipped Dtype**: `bfloat16` (`safetensors` contains 354,483,968 BF16 params; `config.json` specifies `"dtype": "bfloat16"`).
- **Remote Code**: `trust_remote_code=False` (native in `transformers >= 4.57.6` / `5.0.0`).

### 5.2 4 GiB VRAM Budget Breakdown (FP16/BF16)
- **Weight Footprint**: 354,483,968 params × 2 bytes = 708,967,936 bytes ≈ **676.1 MiB**.
- **KV Cache Estimate**:
  - Configuration: Hybrid 16 layers (10 conv blocks + 6 full attention blocks).
  - Conv cache: `conv_L_cache=3` (negligible constant buffer, < 100 KiB).
  - Attention KV cache: 6 layers, 8 key-value heads, head_dim 64.
  - Formula: $6 \times 2 \times 8 \times 64 \times 2 = 12,288 \text{ bytes/token} \approx 0.0117 \text{ MiB/token}$ `[ESTIMATE]`.
  - At sequence length 1,024: ~12.0 MiB `[ESTIMATE]`.
  - At sequence length 4,096: ~48.0 MiB `[ESTIMATE]`.
  - At sequence length 16,384: ~192.0 MiB `[ESTIMATE]`.
  - At sequence length 32,768 (card recommended): ~384.0 MiB `[ESTIMATE]`.
- **Runtime Overheads**: PyTorch CUDA context (~350 MiB) + activation memory (~350 MiB) `[ESTIMATE]`.
- **Total Peak VRAM**:
  - At 4,096 tokens: 676.1 (weights) + 48.0 (KV) + 350 (act) + 350 (context) ≈ **1,424.1 MiB** (~1.39 GiB).
  - At 32,768 tokens: 676.1 (weights) + 384.0 (KV) + 600 (act) + 350 (context) ≈ **2,010.1 MiB** (~1.96 GiB).
  - VRAM Headroom on 4096 MiB GPU: **> 2,000 MiB**.
- **Safe `max_new_tokens` Budget**: **4096 tokens** (easily handles extended sequence lengths up to 32k within 4 GiB VRAM).

### 5.3 Chat Template
- **Direct Template**: Supported via `chat_template.jinja`. Standard ChatML format (`<|im_start|>system...<|im_end|>`, `<|im_start|>user...<|im_end|>`, `<|im_start|>assistant`).
- **Generation Prompt**: `tokenizer.apply_chat_template(..., add_generation_prompt=True, tokenize=True)`.
- **Special Tokens**: BOS: `<|startoftext|>` (1), EOS: `<|im_end|>` (7), PAD: `<|pad|>` (0).

### 5.4 Pinned Loading Snippet
```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "LiquidAI/LFM2.5-350M"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    device_map="cuda:0",
    torch_dtype=torch.bfloat16,
    attn_implementation="sdpa",
).eval()
```
- **Sampling Config**: Benchmark uses greedy `do_sample=False` (card default is `temperature=0.1`, `top_k=50`, `repetition_penalty=1.05`).
- **License**: LFM Open License v1.0. Commercial threshold $10,000,000 annual revenue. Non-commercial and benchmarking use unconstrained. Outputs redistributable. Do not commit weights.

---

## 6. Dependency Set & Version Conflict Analysis

### 6.1 Verified Host Environment vs Model Compatibility
Verified sibling environment: `torch==2.14.1+cu130` + `transformers==4.57.6`.

| Model | Compatible with `transformers 4.57.6`? | Verified Evidence / Root Cause |
| :--- | :---: | :--- |
| **Apertus-v1.1-0.5B** | **YES** | Native class `ApertusForCausalLM` built into `4.57.6`. `config.json` specifies `transformers_version: 4.57.6`. |
| **LFM2.5-350M** | **YES** | Native class `Lfm2ForCausalLM` present in `4.57.6` (`src/transformers/models/lfm2/`). |
| **Lumma-0.6B-Instruct** | **NO (CONFLICT)** | `modeling_lumma.py` imports `capture_outputs` from `transformers.utils.output_capturing` and `merge_with_config_defaults` from `transformers.utils.generic`. These symbols do not exist in `4.57.6` (`ModuleNotFoundError: No module named 'transformers.utils.output_capturing'`). |

### 6.2 Recommended Resolutions
- **Option A (Unified Environment Upgrade - Preferred)**:
  Upgrade `transformers` in the venv to **`5.15.0`** (or `>=5.4.0`) while retaining `torch 2.14.1+cu130`.
  - Evidence: `transformers 5.15.0` resolves cleanly with `torch==2.14.1` and `accelerate==1.15.0`.
  - Retains full native support for Apertus and LFM2.5, while satisfying Lumma's custom code imports.
- **Option B (Dual Virtual Environments)**:
  - Venv 1 (`torch 2.14.1+cu130` + `transformers 4.57.6`): Run Apertus and LFM2.5.
  - Venv 2 (`torch 2.14.1+cu130` + `transformers 5.15.0`): Run Lumma.

---

## 7. Runtime Quirks Matrix

| Model | Quirk / Behavior | Status | Source Evidence | Workaround / Implementation Contract |
| :--- | :--- | :--- | :--- | :--- |
| **Lumma** | Duplicate `<|assistant|>` on `add_generation_prompt=True` | **VERIFIED** | `chat_template.jinja` lines 14 & 20 | Pass `add_generation_prompt=False` when calling `apply_chat_template`. |
| **Lumma** | Remote code import failure on `transformers < 5.4.0` | **VERIFIED** | `modeling_lumma.py` lines 18-19 | Upgrade `transformers >= 5.4.0` or use Option B dual-venv. Set `trust_remote_code=True`. |
| **Apertus** | Duplicate `<s>` BOS token | **VERIFIED** | `chat_template.jinja` line 1 & README.md | Tokenize chat template output with `add_special_tokens=False`. |
| **Apertus** | Hub Terms Click-through / Gate | **VERIFIED** | Model API `cardData.extra_gated_prompt` | Provide `HF_TOKEN` in environment if downloading on accounts requiring AUP acceptance. |
| **LFM2.5** | Hybrid Conv-Attention KV Cache | **VERIFIED** | `config.json` `layer_types` | Handled automatically by native model class; no manual state passing required. |
| **LFM2.5** | Commercial use revenue threshold | **VERIFIED** | `LICENSE` Section 5 | Benchmark and research use is unconstrained; commercial deployments > $10M revenue require Liquid AI agreement. |
| **All** | Left-padding for batched inference | **VERIFIED** | Tokenizer defaults (`tokenizer_config.json`) | Ensure adapter code explicitly sets `tokenizer.padding_side = "left"`. |

---

## 8. Model Smoke Test Commands

Run each command in the target environment:

### 8.1 Lumma-0.6B-Instruct Smoke Test
```bash
python -c '
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

model_id = "FrontiersMind/Lumma-0.6B-Instruct"
tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
mod = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, torch_dtype=torch.bfloat16, device_map="cuda:0", attn_implementation="sdpa")
prompt = tok.apply_chat_template([{"role": "user", "content": "What is 2+2?"}], tokenize=False, add_generation_prompt=False)
inputs = tok(prompt, return_tensors="pt").to(mod.device)
out = mod.generate(**inputs, max_new_tokens=10, do_sample=False)
print("LUMMA_OUTPUT:", tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip())
'
```
*Expected log output*: `LUMMA_OUTPUT: 2 + 2 = 4.`

### 8.2 Apertus-v1.1-0.5B-Instruct Smoke Test
```bash
python -c '
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

model_id = "swiss-ai/Apertus-v1.1-0.5B-Instruct"
tok = AutoTokenizer.from_pretrained(model_id)
mod = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map="cuda:0", attn_implementation="sdpa")
text = tok.apply_chat_template([{"role": "user", "content": "What is 2+2?"}], tokenize=False, add_generation_prompt=True)
inputs = tok([text], return_tensors="pt", add_special_tokens=False).to(mod.device)
out = mod.generate(**inputs, max_new_tokens=10, do_sample=False)
print("APERTUS_OUTPUT:", tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip())
'
```
*Expected log output*: `APERTUS_OUTPUT: 2 + 2 = 4`

### 8.3 LiquidAI/LFM2.5-350M Smoke Test
```bash
python -c '
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

model_id = "LiquidAI/LFM2.5-350M"
tok = AutoTokenizer.from_pretrained(model_id)
mod = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map="cuda:0", attn_implementation="sdpa")
inputs = tok.apply_chat_template([{"role": "user", "content": "What is 2+2?"}], tokenize=True, add_generation_prompt=True, return_tensors="pt").to(mod.device)
out = mod.generate(inputs, max_new_tokens=10, do_sample=False)
print("LFM2_OUTPUT:", tok.decode(out[0][inputs.shape[1]:], skip_special_tokens=True).strip())
'
```
*Expected log output*: `LFM2_OUTPUT: 2 + 2 = 4`
