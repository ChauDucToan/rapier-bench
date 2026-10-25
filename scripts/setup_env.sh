#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV="${HOME}/.local/bin/uv"
if ! command -v "$UV" >/dev/null 2>&1; then
  UV="$(command -v uv || true)"
fi

if [ -z "$UV" ]; then
  echo "Error: uv not found in ~/.local/bin/uv or PATH" >&2
  exit 1
fi

echo "==> Configuring virtual environment at ${REPO_DIR}/.venv"
if [ ! -d "${REPO_DIR}/.venv" ]; then
  "$UV" venv --python 3.13 "${REPO_DIR}/.venv"
fi

SP="$("${REPO_DIR}/.venv/bin/python" -c 'import site; print(site.getsitepackages()[0])')"
CIR_SP="/home/heheboiz/data/cir/.venv/lib/python3.13/site-packages"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
mkdir -p "$UV_CACHE_DIR"

EXCLUDES_ARG=()
if [ "${RB_SHARED_TORCH:-1}" != "0" ] && [ -d "${CIR_SP}/torch" ]; then
  echo "==> Using shared CUDA PyTorch from ${CIR_SP}"
  echo "$CIR_SP" > "${SP}/_shared_cir_torch.pth"
  EXCLUDES_FILE="$(mktemp /tmp/rb-excludes.XXXXXX)"
  cat << 'EOF' > "$EXCLUDES_FILE"
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
  EXCLUDES_ARG=("--excludes" "$EXCLUDES_FILE")
else
  echo "==> Installing standalone CUDA PyTorch from PyTorch index"
  rm -f "${SP}/_shared_cir_torch.pth"
  "$UV" pip install --python "${REPO_DIR}/.venv/bin/python" \
    --index-url https://download.pytorch.org/whl/cu130 "torch==2.14.1"
fi

echo "==> Installing pinned project dependencies"
"$UV" pip install --python "${REPO_DIR}/.venv/bin/python" ${EXCLUDES_ARG[@]+"${EXCLUDES_ARG[@]}"} \
  "fastapi==0.142.2" "uvicorn[standard]==0.54.0" "pydantic==2.13.5" "pydantic-settings==2.9.1" \
  "sqlalchemy==2.0.44" "argon2-cffi==25.1.0" "httpx==0.28.1" "orjson==3.11.3" \
  "pyyaml==6.0.3" "python-multipart==0.0.20" "jinja2==3.1.6" \
  "pytest==9.1.1" "pytest-asyncio==1.3.0" "ruff==0.14.2" \
  "transformers==5.15.0" "datasets==2.21.0" "accelerate==1.4.0" "safetensors==0.8.0" \
  "sentencepiece==0.2.1" "protobuf==6.33.0" "einops==0.8.2" \
  "numpy==2.5.4" "pillow==13.0.0" "tqdm==4.68.0"

if [ -n "${EXCLUDES_FILE:-}" ] && [ -f "$EXCLUDES_FILE" ]; then
  rm -f "$EXCLUDES_FILE"
fi

echo "==> Verifying environment"
"${REPO_DIR}/.venv/bin/python" -c "
import transformers, torch, datasets, accelerate, numpy
print(f'Verified: torch={torch.__version__} (cuda={torch.cuda.is_available()}), transformers={transformers.__version__}, datasets={datasets.__version__}, numpy={numpy.__version__}')
"
