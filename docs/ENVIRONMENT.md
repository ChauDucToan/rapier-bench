# Environment Audit

Audit timestamp: 2026-10-25
Host: heheboiz-Legion-5-15ARH7 (Ubuntu / Linux 7.0.0-38-generic x86_64)
Repository: `/home/heheboiz/data/rapier-bench`
Branch: `feat/domainbench-mvp` (base: `31cd73c feat: Inital structure`)

---

## Verified Facts

| Tool / Component | Version / Status | Command Used |
|---|---|---|
| OS Kernel | `Linux 7.0.0-38-generic #38-Ubuntu SMP PREEMPT_DYNAMIC` | `uname -a` |
| Git branch | `feat/domainbench-mvp` | `git branch --show-current` |
| Git remote | `origin git@github.com:ChauDucToan/rapier-bench.git` | `git remote -v` |
| System Python | `Python 3.14.4` (`/usr/bin/python3`, sys.prefix: `/usr`) | `python3 --version` |
| uv | `uv 0.10.9` (`/home/heheboiz/.local/bin/uv`) | `uv --version` |
| pip | `pip 25.1.1` (`/usr/bin/pip`) | `python3 -m pip --version` |
| python (bare command) | `UNVERIFIED` (not in PATH) | `which -a python` |
| pipx | `UNVERIFIED` (not in PATH) | `which -a pipx` |
| poetry | `UNVERIFIED` (not in PATH) | `which -a poetry` |
| conda | `/home/heheboiz/miniconda3/condabin/conda` | `which -a conda` |
| micromamba | `UNVERIFIED` (not in PATH) | `which -a micromamba` |
| uv preinstalled pythons | CPython `3.13.12`, `3.12.13`, `3.11.15`, `3.10.13`, `3.9.25`, `3.8.20` | `uv python list` |
| Node.js | `v20.19.5` | `node --version` |
| npm | `10.8.2` | `npm --version` |
| pnpm | `10.32.1` | `pnpm --version` |
| npx | `10.8.2` | `npx --version` |
| corepack | `0.33.0` | `corepack --version` |
| Docker | `Docker version 29.9.0, build f415da8` | `docker --version` |
| Docker Compose | `Docker Compose version v5.6.0` | `docker compose version` |
| GPU Driver | `580.178.04` | `nvidia-smi` |
| GPU Model | `NVIDIA GeForce RTX 3050 Laptop GPU` | `nvidia-smi --query-gpu=name...` |
| GPU VRAM | `4096 MiB` (4 GB) | `nvidia-smi --query-gpu=...memory.total...` |
| nvcc | `UNVERIFIED` (command not found) | `nvcc --version` |
| CPU cores | `16` | `nproc` |
| RAM | Total 14Gi, Available 7.5Gi, Swap 16Gi | `free -h` |
| Root Disk (`/`) | 173G total, 160G used, **3.7G available (98% full)** | `df -h /home /tmp` |
| Tmpfs (`/tmp`) | 7.2G total, 5.6G available | `df -h /home /tmp` |
| PyTorch in system Python | `UNVERIFIED` / Absent (`ModuleNotFoundError: No module named 'torch'`) | `python3 -c "import torch"` |
| PyTorch in `cir/.venv` | `2.14.1+cu130`, CUDA available: `True`, device: `NVIDIA GeForce RTX 3050 Laptop GPU` | `/home/heheboiz/data/cir/.venv/bin/python -c "import torch..."` |
| Transformers in `cir/.venv` | `4.57.6` | `/home/heheboiz/data/cir/.venv/bin/python -c "import transformers..."` |
| Accelerate in `cir/.venv` | `UNVERIFIED` / Absent (`ModuleNotFoundError: No module named 'accelerate'`) | `/home/heheboiz/data/cir/.venv/bin/python -c "import accelerate"` |
| huggingface-cli / hf | `UNVERIFIED` (not in PATH) | `which huggingface-cli hf` |
| HF local cache | `~/.cache/huggingface` size: 841M (`hub/`, `xet/`) | `du -sh ~/.cache/huggingface` |

---

## Raw GPU Block

### `nvidia-smi` Output
```text
Sun Oct 25 23:47:33 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 580.178.04             Driver Version: 580.178.04     CUDA Version: 13.0     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 3050 ...    Off |   00000000:01:00.0 Off |                  N/A |
| N/A   42C    P8              3W /   80W |      47MiB /   4096MiB |      0%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A            6730      G   /usr/bin/gnome-shell                      1MiB |
+-----------------------------------------------------------------------------------------+
```

### `nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv`
```csv
name, memory.total [MiB], driver_version
NVIDIA GeForce RTX 3050 Laptop GPU, 4096 MiB, 580.178.04
```

### Verified CUDA PyTorch Execution (via `/home/heheboiz/data/cir/.venv/bin/python`)
```text
Command: python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
Output:  2.14.1+cu130 13.0 True NVIDIA GeForce RTX 3050 Laptop GPU
```

---

## Network Reachability Results

All checks executed with `--max-time 15`:

| Target URL | HTTP Code | Status |
|---|---|---|
| `https://huggingface.co/api/models/LiquidAI/LFM2.5-350M` | `200` | Reachable |
| `https://huggingface.co/api/models/FrontiersMind/Lumma-0.6B-Instruct` | `200` | Reachable |
| `https://huggingface.co/api/models/swiss-ai/Apertus-v1.1-0.5B-Instruct` | `200` | Reachable |
| `https://pypi.org/simple/` | `200` | Reachable |
| `https://registry.npmjs.org/` | `200` | Reachable |
| `https://raw.githubusercontent.com/` | `301` | Reachable (Redirect) |
| `https://github.com` | `200` | Reachable |

---

## Implications

1. **GPU Inference Capability**:
   - **Yes, GPU inference can run here**, with strict constraints.
   - Physical VRAM is **4096 MiB (4 GB)**, NOT 16 GB.
   - The 3 target models are small:
     - `LiquidAI/LFM2.5-350M` (~350M params: ~700 MB in fp16/bf16)
     - `swiss-ai/Apertus-v1.1-0.5B-Instruct` (~0.5B params: ~1.0 GB in fp16/bf16)
     - `FrontiersMind/Lumma-0.6B-Instruct` (~0.6B params: ~1.2 GB in fp16/bf16)
   - Each model can run individually on the 4 GB GPU in fp16 or int8. Models **cannot** be loaded simultaneously. Sequential loading with explicit CUDA cache cleanup is required.
   - **Critical Storage Constraint**: Root disk partition `/` has only **3.7 GB free (98% full)**. Total downloaded weights for all three models + cache will exceed 3 GB if not purged or carefully managed.

2. **Network Access to Hugging Face Hub**:
   - **Yes**. Direct HTTPS reachability to `huggingface.co` API and model metadata endpoints is confirmed (all returned HTTP 200).
   - PyPI and npm registries are also reachable (HTTP 200).

3. **Python Interpreter and Virtual Environment**:
   - System `/usr/bin/python3` is **Python 3.14.4**, which lacks prebuilt PyTorch binary wheels.
   - `uv` is installed and ready at `/home/heheboiz/.local/bin/uv` (v0.10.9).
   - The project should use **`uv` with Python 3.12 or 3.13** (e.g. `uv venv --python 3.12 .venv` or `uv venv --python 3.13 .venv`). Python 3.13 is already verified working with PyTorch + CUDA 13 on this machine in `cir/.venv`.

---

## Disk & Interpreter Plan

### Repo Mount & Partition Details

| Path | Partition | Filesystem | Total Size | Used | Available | Use% |
|---|---|---|---|---|---|---|
| `/home/heheboiz/data/rapier-bench` | `/dev/nvme0n1p6` (mounted at `/`) | `ext4` | `173G` | `159G` | **`5.2G`** | `97%` |
| `/tmp` | `tmpfs` | `tmpfs` (RAM) | `7.2G` | `1.6G` | **`5.6G`** | `23%` |
| `/dev/shm` | `tmpfs` | `tmpfs` (RAM) | `7.2G` | `2.0G` | **`5.2G`** | `28%` |
| (Unmounted Windows partition) | `/dev/nvme0n1p3` | `ntfs` | `313G` | — | — | — |

### Reclaimable Space Inventory (Sizes Only — No Deletions)

| Target / Path | Size | Description |
|---|---|---|
| `~/.cache/uv` | `54M` | uv package cache |
| `~/.cache/pip` | `48M` | pip download cache |
| `~/.cache/huggingface` | `841M` | HF model cache (`hub/models--bert`, `models--bert-base-uncased`) |
| `~/.cache/torch` | `12K` | PyTorch cache |
| `~/.npm` | `1.1G` | npm package cache (reclaimable with `npm cache clean --force`) |
| `/home/heheboiz/miniconda3` | `2.1G` | Miniconda installation |
| Docker reclaimable | `204.8M` | Dangling docker images/cache (`docker system df`) |
| `/home/heheboiz/data/cir/.venv` | `6.0G` | Existing virtualenv (contains torch 2.14.1+cu130, nvidia libs) |
| `/home/heheboiz/data/tmp` | `913M` | Data folder tmp artifacts |
| `/home/heheboiz/data/temp` | `493M` | Data folder temp artifacts |
| `/home/heheboiz/data/PlantGuard` | `2.2G` | Local project |
| `/home/heheboiz/data/note` | `2.5G` | Local project |
| `/home/heheboiz/data/cir` | `59G` | Large local project / datasets |

### Probe Results
1. **System-site-packages probe**: Tested `~/.local/bin/uv venv --python 3.13 --system-site-packages /tmp/rb-probe-venv`.
   - Result: `ModuleNotFoundError: No module named 'torch'`.
   - Reason: `system-site-packages` only inherits the base interpreter (`/usr` or `uv` CPython), not sibling virtualenvs like `cir/.venv`.
   - Decision: **Reusing cir's interpreter or site-packages is NOT allowed**. Rapier Bench requires its own clean, isolated venv.
2. **CUDA torch download probe**:
   - Tested downloading `torch==2.14.1` with `--python-version 3.13` from `--index-url https://download.pytorch.org/whl/cu130`.
   - Verified exact wheel: `torch-2.14.1+cu130-cp313-cp313-manylinux_2_28_x86_64.whl` (554.6 MB wheel download size).
   - Resolution: Resolves 29 packages (including `nvidia-cublas==13.1.1.3`, `nvidia-cudnn-cu13==9.24.0.43`, `nvidia-cuda-runtime==13.0.96`, `triton==3.8.0`).
   - Installed disk cost: **~5.3 GB** (torch 1.2 GB, nvidia packages 3.2 GB, triton 895 MB).
   - Compare CPU-only wheel: `torch-2.14.1+cpu` is 196.3 MB download, ~650 MB installed (CPU-only is rejected per product owner directive).

### Does CUDA Torch Fit on the Repo Partition?
- **Tight / borderline (`5.2G` available vs `~5.3G` installed)**.
- If downloaded without precautions, pip/uv cache on `/` (`~/.cache/uv`) will exhaust disk mid-install.
- **Solution to guarantee fit**:
  1. Redirect cache to tmpfs RAM: `export UV_CACHE_DIR=/tmp/uv-cache` (tmpfs has 5.6 GB free, zero footprint on `/`).
  2. Reclaim ~1–2 GB on `/` before heavy installs (e.g. `npm cache clean --force` reclaims 1.1 GB; miniconda3 holds 2.1 GB).
  3. Fallback if `/` becomes full: Symlink `.venv` to `/tmp/.rapier-bench-venv` (tmpfs RAM) or mount partition `/dev/nvme0n1p3`.

### Interpreter/Venv Decision & Commands

```bash
# 1. Redirect uv cache to tmpfs (avoids filling root disk with wheel archives)
export UV_CACHE_DIR=/tmp/uv-cache

# 2. Create isolated Python 3.13 venv for rapier-bench
~/.local/bin/uv venv --python 3.13 .venv

# 3. Install CUDA 13.0 PyTorch 2.14.1
~/.local/bin/uv pip install \
  --index-url https://download.pytorch.org/whl/cu130 \
  "torch==2.14.1"

# 4. Install backend dependencies from PyPI
~/.local/bin/uv pip install \
  "transformers==4.57.6" \
  "accelerate" \
  "fastapi" \
  "uvicorn" \
  "pydantic"
```

### Cache Policy
- `HF_HOME`: Keeps default `~/.cache/huggingface` (841 MB already cached). Do NOT delete without explicit permission.
- If disk headroom falls below 1.5 GB during model downloads, set `export HF_HOME=/tmp/huggingface` to use the 5.6 GB tmpfs RAM drive.

---

## Laptop-Target Deployment Constraints

1. **Target Hardware Reality vs Specification**:
   - **Original requirement document target**: ~16 GB VRAM desktop/server GPU.
   - **Actual deployment target**: **4096 MiB (4 GB) VRAM** NVIDIA GeForce RTX 3050 Laptop GPU (Driver `580.178.04`, CUDA `13.0`).
   - **Feasibility verdict**: **CONFIRMED FEASIBLE** for small models (≤0.6B parameters) with strict memory management. PyTorch CUDA execution on this GPU is verified.

2. **VRAM Management Rules (4096 MiB Target)**:
   - **Sequential Single-Model Loading**: Only ONE model may reside in VRAM at any time. Multi-model concurrent benchmarking in VRAM is strictly prohibited.
   - **Precision**: Must use `torch_dtype=torch.float16` (or `torch.bfloat16`). FP32 is prohibited as weights alone would exceed memory.
     - `LiquidAI/LFM2.5-350M` (~350M params): ~700 MB in fp16.
     - `swiss-ai/Apertus-v1.1-0.5B-Instruct` (~0.5B params): ~1.0 GB in fp16.
     - `FrontiersMind/Lumma-0.6B-Instruct` (~0.6B params): ~1.2 GB in fp16.
   - **Model Swap Lifecycle**: Before switching models, unload completely:
     ```python
     del model
     del tokenizer
     import gc; gc.collect()
     import torch; torch.cuda.empty_cache()
     ```
   - **Generation Budget**: Batch size = 1. `max_new_tokens` must stay budgeted (e.g. 128 to 256 tokens) to prevent KV cache allocation from spilling over the remaining ~2.8 GB VRAM.

3. **Disk Headroom Summary**:
   - Available on `/`: `5.2 GB`.
   - CUDA Torch install: `~5.3 GB` installed footprint.
   - Net headroom: `~0 GB` without cache isolation. With `UV_CACHE_DIR=/tmp/uv-cache` and reclaiming `~/.npm` (1.1 GB) or other caches, safe working headroom of ~1.5 to 2.5 GB is achievable.

---

## Venv Strategy Decision

### Complete Mount Inventory (Non-tmpfs & Persistent)

| Mount / Partition | Device | Filesystem | Total | Used | Avail | Use% | Writable? |
|---|---|---|---|---|---|---|---|
| `/` | `/dev/nvme0n1p6` | `ext4` | `173G` | `159G` | **`5.3G`** | `97%` | Yes (User `heheboiz`) |
| `/boot/efi` | `/dev/nvme0n1p1` | `vfat` | `96M` | `70M` | `27M` | `72%` | System only |
| `/media` | — | — | — | — | — | — | Empty (No mounts) |
| `/mnt` | — | — | — | — | — | — | Empty (No mounts) |
| `/run/media` | — | — | — | — | — | — | Empty (No mounts) |
| (Unmounted Windows) | `/dev/nvme0n1p3` | `ntfs` | `313.8G` | — | — | — | Unmounted (requires root mount) |

**Big mount verdict**: **NONE**. There is no mounted filesystem with ≥10 GB free space on this system.

### Reclaimable Space Inventory (Sizes Only — Nothing Deleted)

#### Safe Caches (Zero Project Impact)
| Target | Path | Size | Safe Reclaim Action |
|---|---|---|---|
| npm cache | `~/.npm` | `1.3G` | `npm cache clean --force` |
| pip cache | `~/.cache/pip` | `765M` | `rm -rf ~/.cache/pip` |
| uv cache | `~/.cache/uv` | `75M` | `uv cache clean` |
| pnpm store | `~/.cache/pnpm` | `103M` | `pnpm store prune` |
| Docker dangling images | Docker Engine | `204.8M` | `docker image prune -f` |
| **Total Safe Caches** | | **`~2.45G`** | Pure throwaway cache data |

#### High-Impact Existing Installations (Requires Explicit Decision)
| Target | Path | Size | Description |
|---|---|---|---|
| Miniconda | `/home/heheboiz/miniconda3` | `2.1G` | Standalone Conda environment |
| Tmp project folder | `/home/heheboiz/data/tmp` | `913M` | Temporary directory in user data |
| Hugging Face Hub cache | `~/.cache/huggingface` | `841M` | Cached models (`bert`, `bert-base-uncased`) |
| Existing CIR venv | `/home/heheboiz/data/cir/.venv` | `6.0G` | Contains torch 2.14.1+cu130 (1.2G), nvidia (3.2G), triton (895M) |

### Probe Results (Verbatim)

1. **Probe C (.pth sharing of existing CUDA torch)**:
   ```bash
   rm -rf /tmp/rb-share && ~/.local/bin/uv venv --python 3.13 /tmp/rb-share
   SP=$(/tmp/rb-share/bin/python -c 'import site; print(site.getsitepackages()[0])')
   echo "/home/heheboiz/data/cir/.venv/lib/python3.13/site-packages" > "$SP/_shared_cir.pth"
   /tmp/rb-share/bin/python -c "import torch, sys; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
   /tmp/rb-share/bin/python -c "import transformers; print('transformers', transformers.__version__)"
   /tmp/rb-share/bin/python -c "import sys; print([p for p in sys.path if 'cir' in p])"
   ```
   **Output**:
   ```text
   Using CPython 3.13.12
   Creating virtual environment at: /tmp/rb-share
   torch 2.14.1+cu130 cuda True NVIDIA GeForce RTX 3050 Laptop GPU
   transformers 4.57.6
   ['/home/heheboiz/data/cir/.venv/lib/python3.13/site-packages']
   ```
   **Verdict**: **PROVEN WORKING**. PyTorch, CUDA, and GPU hardware recognition work immediately with zero bytes added to disk.

2. **Shadowing and Collision Probe**:
   - Existing common packages in `cir/.venv`:
     - `fastapi` (`0.142.2`)
     - `uvicorn` (`0.54.0`)
     - `pydantic` (`2.13.5`)
     - `starlette` (`1.7.0`)
     - `huggingface_hub` (`0.36.2`)
     - `tokenizers` (`0.22.2`)
     - `safetensors` (`0.8.0`)
     - `numpy` (`2.5.4`)
     - `pillow` (`13.0.0`)
     - `pytest` (`9.1.1`)
     *(Note: `datasets` and `accelerate` are NOT present in `cir`'s site-packages and must be installed).*
   - **Priority Test**: Installed `packaging==24.2` into `/tmp/rb-share`.
     - Output: `packaging file: /tmp/rb-share/lib/python3.13/site-packages/packaging/__init__.py`
     - **Result**: Packages installed in the project's own `.venv` take strict precedence over `.pth` paths. Any package specified in rapier-bench's requirements will override `cir`'s version.

3. **Probe D (cir interpreter as uv base)**:
   - Command: `~/.local/bin/uv venv --python /home/heheboiz/data/cir/.venv/bin/python /tmp/rb-baseprobe`
   - Output: `ModuleNotFoundError: No module named 'torch'`. Standard venv isolation prevents inheriting site-packages; requires `.pth` or full install.

### Ranked Recommendations

1. **RANK 1 (RECOMMENDED): `.pth`-shared CUDA Torch in Project `.venv`**
   - **Pros**: **0 MB added to root disk**. Zero risk of disk exhaustion. Full CUDA acceleration on RTX 3050 GPU confirmed working. Local site-packages take precedence, allowing rapier-bench to install its own specific versions of FastAPI, Accelerate, Datasets, etc.
   - **Cons**: Depends on `/home/heheboiz/data/cir/.venv` remaining on disk.
   - **Exact Commands**:
     ```bash
     ~/.local/bin/uv venv --python 3.13 .venv
     SP=$(.venv/bin/python -c 'import site; print(site.getsitepackages()[0])')
     echo "/home/heheboiz/data/cir/.venv/lib/python3.13/site-packages" > "$SP/_shared_cir.pth"
     # Verify
     .venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
     # Install rapier-bench specific requirements (takes priority over .pth)
     ~/.local/bin/uv pip install accelerate datasets
     ```

2. **RANK 2: Reclaim Safe Caches (~2.45 GB) + Standalone CUDA Install**
   - **Pros**: Fully standalone, 100% independent virtual environment.
   - **Cons**: Requires deleting `~/.npm` (1.3G), `~/.cache/pip` (765M), `~/.cache/uv` (75M), `~/.cache/pnpm` (103M), and docker images (204.8M) to expand free space from 5.3G to ~7.75G. Post-install headroom will be ~2.4G. Must use `UV_CACHE_DIR=/tmp/uv-cache` during install.
   - **Action**: Must ask user before deleting caches.

3. **RANK 3: Alternate Mount (Windows partition `/dev/nvme0n1p3`)**
   - **Pros**: 313 GB of space.
   - **Cons**: Partition is currently unmounted. Requires root/sudo privileges to mount NTFS filesystem, handle file permissions, and configure auto-mount.

4. **RANK 4: CPU-Only Torch Install**
   - **Pros**: Fits comfortably (~650 MB installed).
   - **Cons**: Completely loses GPU capability. Target models would run on CPU (5x-10x slower). Directly conflicts with project target of benchmarking local GPU inference on the RTX 3050.

---

## Provisioned Project Environment

### Provisioning Summary
- **Venv path**: `/home/heheboiz/data/rapier-bench/.venv`
- **Python base**: CPython `3.13.12`
- **Shared CUDA PyTorch link**:
  - File: `/home/heheboiz/data/rapier-bench/.venv/lib/python3.13/site-packages/_shared_cir_torch.pth`
  - Content: `/home/heheboiz/data/cir/.venv/lib/python3.13/site-packages`
- **Disk usage delta (`df -h /`)**:
  - Free before install: `5.2 GB`
  - Free after install: `4.7 GB`
  - Net disk consumed: **`~500 MB`** (vs ~5.3 GB for a full redundant CUDA wheel installation).

### Exact Commands Executed
```bash
cd /home/heheboiz/data/rapier-bench
~/.local/bin/uv venv --python 3.13 .venv
SP=$(.venv/bin/python -c 'import site; print(site.getsitepackages()[0])')
echo "/home/heheboiz/data/cir/.venv/lib/python3.13/site-packages" > "$SP/_shared_cir_torch.pth"

export UV_CACHE_DIR=/tmp/uv-cache
cat << 'EOF' > /tmp/torch-excludes.txt
torch
triton
nvidia-cublas
nvidia-cuda-cupti
nvidia-cuda-nvrtc
nvidia-cuda-runtime
nvidia-cudnn-cu13
nvidia-cufft
nvidia-cufile
nvidia-curand
nvidia-cusolver
nvidia-cusparse
nvidia-cusparselt-cu13
nvidia-nccl-cu13
nvidia-nvjitlink
nvidia-nvshmem-cu13
nvidia-nvtx
cuda-bindings
cuda-pathfinder
cuda-toolkit
EOF

~/.local/bin/uv pip install --python .venv/bin/python --excludes /tmp/torch-excludes.txt \
  "fastapi==0.142.2" "uvicorn[standard]==0.54.0" "pydantic==2.13.5" "pydantic-settings==2.9.1" \
  "sqlalchemy==2.0.44" "argon2-cffi==25.1.0" "httpx==0.28.1" "orjson==3.11.3" \
  "pyyaml==6.0.3" "python-multipart==0.0.20" "jinja2==3.1.6" \
  "pytest==9.1.1" "pytest-asyncio==1.3.0" "ruff==0.14.2" \
  "transformers==5.15.0" "datasets==2.21.0" "accelerate==1.4.0" "safetensors==0.8.0" \
  "sentencepiece==0.2.1" "protobuf==6.33.0" "einops==0.8.2" \
  "numpy==2.5.4" "pillow==13.0.0" "tqdm==4.68.0"
rm -f /tmp/torch-excludes.txt
```

### Version Substitutions
- `sentencepiece==0.2.0` → **`sentencepiece==0.2.1`**: `0.2.0` has no prebuilt wheel for Python 3.13 on PyPI and its source build fails on the bundled build script. `0.2.1` provides official `cp313-cp313-manylinux_2_27_x86_64` prebuilt wheels.
- `transformers==5.15.0` was installed as required (no substitution).

### Verification Output
```text
transformers 5.15.0
torch 2.14.1+cu130 True
datasets 2.21.0
numpy 2.5.4 /home/heheboiz/data/rapier-bench/.venv/lib/python3.13/site-packages/numpy/__init__.py
torch file /home/heheboiz/data/cir/.venv/lib/python3.13/site-packages/torch/__init__.py
output_capturing OK
backend deps OK
pytest 9.1.1
ruff 0.14.2
```

### Full `uv pip list`
```text
Package              Version
-------------------- ----------
accelerate           1.4.0
aiohappyeyeballs     2.7.1
aiohttp              3.14.5
aiosignal            1.4.0
annotated-doc        0.0.5
annotated-types      0.8.0
anyio                4.15.1
argon2-cffi          25.1.0
argon2-cffi-bindings 26.1.0
attrs                26.1.0
certifi              2026.10.23
cffi                 2.1.1
charset-normalizer   3.5.2
click                8.5.0
datasets             2.21.0
dill                 0.3.8
einops               0.8.2
fastapi              0.142.2
filelock             4.2.4
frozenlist           1.8.0
fsspec               2024.6.1
greenlet             3.5.6
h11                  0.16.0
hf-xet               1.7.0
httpcore             1.0.9
httptools            0.9.0
httpx                0.28.1
huggingface-hub      1.33.0
idna                 3.20
iniconfig            2.3.1
jinja2               3.1.6
markdown-it-py       4.2.0
markupsafe           3.0.4
mdurl                0.1.2
multidict            7.2.1
multiprocess         0.70.16
numpy                2.5.4
opentelemetry-api    1.45.1
orjson               3.11.3
packaging            26.3
pandas               3.1.0
pillow               13.0.0
pluggy               1.7.0
propcache            0.5.4
protobuf             6.33.0
psutil               7.2.2
pyarrow              26.0.0
pycparser            3.12
pydantic             2.13.5
pydantic-core        2.46.5
pydantic-settings    2.9.1
pygments             2.21.0
pytest               9.1.1
pytest-asyncio       1.3.0
python-dateutil      3.0.0
python-dotenv        1.2.4
python-multipart     0.0.20
pyyaml               6.0.3
regex                2026.9.29
requests             2.34.2
rich                 15.0.0
ruff                 0.14.2
safetensors          0.8.0
sentencepiece        0.2.1
shellingham          1.5.4
six                  1.17.0
sqlalchemy           2.0.44
starlette            1.10.0
tokenizers           0.22.2
tqdm                 4.68.0
transformers         5.15.0
typer                0.27.3
typing-extensions    4.16.0
typing-inspection    0.4.4
tzdata               2026.5
urllib3              2.8.0
uvicorn              0.54.0
uvloop               0.23.0
watchfiles           1.3.0
websockets           17.3
xxhash               4.0.2
yarl                 1.25.1
```

---

## Risk Register

1. **Dependency on `/home/heheboiz/data/cir/.venv`**:
   - **Risk**: The project environment does not physically store PyTorch, CUDA libraries (`nvidia-*`), or Triton on `/`. It references them via `_shared_cir_torch.pth`. If `/home/heheboiz/data/cir/.venv` is removed or modified, `import torch` will break.
   - **Likelihood**: Low (cir is a primary research project).
   - **Severity**: High (inference halts).
   - **Decoupling / Standalone Fallback Command**:
     If `cir/.venv` is ever deleted, execute the following to convert `rapier-bench` to a standalone installation:
     ```bash
     # 1. Reclaim ~2.45 GB from safe throwaway caches to ensure disk headroom
     npm cache clean --force
     rm -rf ~/.cache/pip ~/.cache/uv
     docker image prune -f

     # 2. Remove the shared link
     rm -f /home/heheboiz/data/rapier-bench/.venv/lib/python3.13/site-packages/_shared_cir_torch.pth

     # 3. Install standalone CUDA PyTorch directly
     export UV_CACHE_DIR=/tmp/uv-cache
     ~/.local/bin/uv pip install \
       --python /home/heheboiz/data/rapier-bench/.venv/bin/python \
       --index-url https://download.pytorch.org/whl/cu130 \
       "torch==2.14.1"
     ```

2. **Single-GPU Laptop VRAM Cap (4096 MiB)**:
   - **Risk**: Concurrent model loads or large generation contexts will trigger CUDA OOM.
   - **Mitigation**: Architecture contract strictly mandates sequential benchmarking (load 1 model → evaluate → unload with `gc.collect()` + `torch.cuda.empty_cache()` → load next model).

---

## Hardware-Bench Feasibility (RTX 3050 Laptop, 4 GiB)

Audit timestamp: 2026-10-26
Mode: HARDWARE-BENCH (Local GPU throughput/latency characterization)
Target model parameter class: 8B – 30B open-weight / GGUF checkpoints

### 1. VRAM Reality Check

#### Empty GPU Baseline
Command:
```bash
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu --format=csv
```
Raw Output:
```csv
name, memory.total [MiB], memory.used [MiB], memory.free [MiB], utilization.gpu [%]
NVIDIA GeForce RTX 3050 Laptop GPU, 4096 MiB, 44 MiB, 3725 MiB, 0 %
```
- Total physical VRAM: `4096 MiB`
- Active process usage: `44 MiB` (gnome-shell display server)
- Driver/firmware overhead: `~327 MiB`
- Usable free VRAM: `3725 MiB`

#### Theoretical Peak VRAM Table (8B – 30B)
Formulas and assumptions:
- **Weights (fp16/bf16)**: $\text{params} \times 2.0\text{ bytes}$
- **Weights (4-bit)**: $\text{params} \times 0.55\text{ bytes}$ [ESTIMATE: 0.50 bytes for 4 bits/param + 0.05 bytes scale/quantization overhead]
- **KV Cache**: $\text{Bytes} = 2 \text{ (K+V)} \times 2 \text{ (fp16)} \times n_{\text{layers}} \times (n_{\text{kv\_heads}} \times d_{\text{head}}) \times L$
  - Representative architectures (Batch Size $b = 1$):
    - **8B** (Llama-3 8B GQA): 32 layers, $8 \times 128 = 1024$ KV dim $\implies 131,072\text{ bytes/token}$
    - **13B** (Llama-2 13B MHA): 40 layers, $16 \times 128 = 2048$ KV dim $\implies 327,680\text{ bytes/token}$
    - **20B** (20B class GQA): 44 layers, $16 \times 128 = 2048$ KV dim $\implies 360,448\text{ bytes/token}$
    - **30B** (30B/32B class GQA): 64 layers, $8 \times 128 = 1024$ KV dim $\implies 262,144\text{ bytes/token}$
- **CUDA Context & Activations**: NOT included in weights+KV sums below; adds $\ge 500\text{ MiB}$ overhead.

| Model | Precision | Weights | KV Cache (2048) | KV Cache (8192) | Peak (L=2048) | Peak (L=8192) | Verdict (4096 MiB) |
|---|---|---|---|---|---|---|---|
| **8B** | fp16 | 15,258.8 MiB | 256.0 MiB | 1,024.0 MiB | 15,514.8 MiB | 16,282.8 MiB | **DOES NOT FIT** |
| **8B** | 4-bit [ESTIMATE] | 4,196.2 MiB | 256.0 MiB | 1,024.0 MiB | 4,452.2 MiB | 5,220.2 MiB | **DOES NOT FIT** |
| **13B** | fp16 | 24,795.5 MiB | 640.0 MiB | 2,560.0 MiB | 25,435.5 MiB | 27,355.5 MiB | **DOES NOT FIT** |
| **13B** | 4-bit [ESTIMATE] | 6,818.8 MiB | 640.0 MiB | 2,560.0 MiB | 7,458.8 MiB | 9,378.8 MiB | **DOES NOT FIT** |
| **20B** | fp16 | 38,147.0 MiB | 704.0 MiB | 2,816.0 MiB | 38,851.0 MiB | 40,963.0 MiB | **DOES NOT FIT** |
| **20B** | 4-bit [ESTIMATE] | 10,490.4 MiB | 704.0 MiB | 2,816.0 MiB | 11,194.4 MiB | 13,306.4 MiB | **DOES NOT FIT** |
| **30B** | fp16 | 57,220.5 MiB | 512.0 MiB | 2,048.0 MiB | 57,732.5 MiB | 59,268.5 MiB | **DOES NOT FIT** |
| **30B** | 4-bit [ESTIMATE] | 15,735.6 MiB | 512.0 MiB | 2,048.0 MiB | 16,247.6 MiB | 17,783.6 MiB | **DOES NOT FIT** |

**Verdict**: None of 8B, 13B, 20B, or 30B models can run in VRAM on this GPU. Even 8B 4-bit weights alone (4,196 MiB) exceed physical VRAM (4096 MiB) and free VRAM (3725 MiB).

### 2. What CAN Run Here

VRAM headroom calculation:
- Available free VRAM: `3725 MiB`
- CUDA runtime context margin: `~350 MiB`
- Working activation buffer & KV cache margin ($b=1, L \le 1024$): `~300 MiB` [ESTIMATE]
- Remaining budget for model weights: $3725 - 350 - 300 = 3075\text{ MiB}$ (`3.22 GB`)

Maximum parameter counts:
- **Largest in fp16**: $\frac{3075 \times 1024^2 \text{ bytes}}{2.0\text{ bytes/param}} \approx \mathbf{1.61\text{B parameters}}$ (e.g. Qwen2.5-1.5B fits comfortably).
- **Largest in 4-bit [ESTIMATE]**: $\frac{3075 \times 1024^2 \text{ bytes}}{0.55\text{ bytes/param}} \approx \mathbf{5.86\text{B parameters}}$ (e.g. 3B models such as Llama-3.2-3B or 3.8B Phi-3.5-mini fit; 7B/8B strictly exceed capacity).

### 3. Existing Local Models Inventory

Commands executed:
1. `ls -la /home/heheboiz/data /home/heheboiz/models 2>/dev/null`
   - `/home/heheboiz/models`: Directory does not exist.
   - `/home/heheboiz/data`: Contains project trees (`cir`, `PlantGuard`, etc.). No LLM weights found.
2. `find /home/heheboiz -maxdepth 4 -name "*.gguf" -o -maxdepth 4 -name "*.safetensors" -o -name "config.json" 2>/dev/null | head -40`
   - Zero `.gguf` files found across `/home/heheboiz`.
   - Zero `.safetensors` model weights found.
   - Only application configuration JSON files detected (`.copilot/config.json`, npm configs).
3. `du -sh /home/heheboiz/.cache/huggingface/hub/* 2>/dev/null | head -20`
   Raw Output:
   ```text
   12K    /home/heheboiz/.cache/huggingface/hub/models--bert
   841M   /home/heheboiz/.cache/huggingface/hub/models--bert-base-uncased
   4.0K   /home/heheboiz/.cache/huggingface/hub/version.txt
   ```
   Only BERT-base uncased (841 MB) exists in HF cache.

**Verdict**: **Zero local open-weight 8B–30B models or GGUF files exist on this machine.**

### 4. Measurement Tooling Feasibility

#### Telemetry Query Loop (`nvidia-smi`)
Command:
```bash
timeout 3 nvidia-smi --query-gpu=power.draw,clocks.sm,clocks.mem,temperature.gpu --format=csv -l 1
```
Raw Output:
```csv
power.draw [W], clocks.current.sm [MHz], clocks.current.memory [MHz], temperature.gpu
3.28 W, 210 MHz, 405 MHz, 43
3.28 W, 210 MHz, 405 MHz, 43
3.29 W, 210 MHz, 405 MHz, 43
```
- Status: **WORKING**. Telemetry polling interval of 1 second is functional via CLI.

#### `pynvml` / In-Process Sampling
- In `/home/heheboiz/data/cir/.venv/bin/python`:
  `ModuleNotFoundError: No module named 'pynvml'`
- In `/home/heheboiz/data/rapier-bench/.venv/bin/python`:
  `ModuleNotFoundError: No module named 'pynvml'`
- In system `/usr/bin/python3`:
  Available at `/usr/lib/python3/dist-packages/pynvml.py`.
- **Verdict & Tooling Strategy**:
  - **VRAM tracking**: Fully supported in `.venv` via native PyTorch APIs `torch.cuda.memory_allocated()` and `torch.cuda.max_memory_allocated()` without new packages.
  - **Power / Clocks / Thermal tracking**: Supported via background `nvidia-smi --query-gpu=... -l 1` subprocess logging to file, or requires explicit owner approval to install `nvidia-ml-py` in `.venv`.

### 5. Disk Budget for Hardware Bench

- **Current Free Space on `/`**: `5.1 GB` (97% full on `/dev/nvme0n1p6`).
- **Cost of a Single GGUF 4-bit 8B Model**: `~4.9 – 5.2 GB` (e.g. Q4_K_M checkpoint is ~4.92 GB).
- **Fit with Margin**: **DOES NOT FIT WITH MARGIN**. Downloading a ~5.0 GB model onto a drive with 5.1 GB free reduces disk headroom to `<100 MB`, risking filesystem lockups and write failures.
- **Safe Reclaimable Space**:
  Quote from Section "Disk & Interpreter Plan":
  > `Total Safe Caches: ~2.45G` (`~/.npm` 1.3G, `~/.cache/pip` 765M, `~/.cache/uv` 75M, `~/.cache/pnpm` 103M, docker images 204.8M).
- **High-Impact Reclaimable Items (Requires Explicit Owner Approval)**:
  - Miniconda (`/home/heheboiz/miniconda3`): `2.1 GB`
  - CIR venv (`/home/heheboiz/data/cir/.venv`): `6.0 GB` (DO NOT DELETE: rapier-bench `.venv` links to this for PyTorch CUDA)
  - Tmp project folder (`/home/heheboiz/data/tmp`): `913 MB`
  - Hugging Face cache (`~/.cache/huggingface`): `841 MB`
  - Unmounted NTFS partition (`/dev/nvme0n1p3`): `313 GB` (requires sudo mount)
