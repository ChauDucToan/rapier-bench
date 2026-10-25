# Deployment and Operations Guide

This guide details operational procedures, environment configurations, and deployment strategies for Rapier Bench.

## Local Development Setup

### 1. Prerequisites

- Linux (x86_64) kernel >= 6.0
- Python 3.13 via `uv` (installed at `~/.local/bin/uv` or in system `$PATH`)
- Node.js v20.x and npm v10.x
- NVIDIA GPU with minimum 4096 MiB VRAM and CUDA driver >= 580.x

### 2. Verified Setup Workflow

```bash
# 1. Initialize virtual environment and resolve pinned dependencies
bash scripts/setup_env.sh

# 2. Launch FastAPI backend on http://127.0.0.1:8000
bash scripts/dev.sh

# 3. Launch Next.js frontend on http://127.0.0.1:3000 (in separate shell)
cd frontend
npm install
npm run dev
```

## Environment Configuration

Configuration is managed via environment variables or a root `.env` file (`backend/app/config.py`):

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///./rapier.db` | SQLAlchemy SQLite connection string. |
| `ARTIFACTS_DIR` | `./artifacts` | Directory for benchmark logs, predictions, and metrics. |
| `SECRET_KEY` | `dev-insecure-secret-key-change-in-prod` | Cryptographic secret for session cookie signing. |
| `CUDA_VISIBLE_DEVICES` | `0` | Physical GPU index assigned to inference workers. |
| `HF_HOME` | `~/.cache/huggingface` | Local cache directory for Hugging Face model weights. |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated CORS allowed origins. |
| `SECURE_COOKIES` | `false` | Enforce `Secure` cookie flag (set `true` when behind HTTPS). |
| `ENV` | `development` | Deployment environment (`development` or `production`). |

## Database Initialization & State Management

- **Table Creation**: SQLAlchemy creates all tables automatically on application startup via `Base.metadata.create_all()` in `app/main.py`.
- **Foreign Key Constraints**: SQLite foreign key support is explicitly enabled on every connection via `PRAGMA foreign_keys = ON;`.
- **Catalog Synchronization**: System automatically parses `configs/models.yaml`, `configs/datasets.yaml`, and `configs/protocols/*.yaml` at startup to seed or update catalog definitions.
- **Orphaned Run Reconciliation**: If the server terminates unexpectedly, uncompleted runs in `RUNNING` or `QUEUED` state are marked as `FAILED` during startup lifespan, and the `gpu_locks` row is reset.

## Artifacts Storage Layout

Every execution stores self-contained, path-traversal-protected run records under `ARTIFACTS_DIR`:

```text
artifacts/
└── {run_id}/
    ├── run_config.json      # Resolved configuration, sample IDs, and model specs
    ├── hardware.json        # Snapshot of driver, GPU model, VRAM, and platform
    ├── predictions.jsonl    # Line-delimited raw and parsed model predictions
    ├── metrics.json         # Evaluated accuracy, micro-F1, latency, throughput
    └── logs.txt             # Timestamped execution trace and error outputs
```

## Hardware & CUDA Configuration

### Target Host: RTX 3050 Laptop (4096 MiB VRAM)

The primary development environment operates on an NVIDIA GeForce RTX 3050 Laptop GPU with 4096 MiB VRAM and driver 580.178.04 (CUDA 13.0).

- **Shared PyTorch Virtual Environment**: To avoid duplicating ~5.3 GB of PyTorch and CUDA runtime binaries on an almost-full root partition, `scripts/setup_env.sh` links existing CUDA PyTorch packages from `/home/heheboiz/data/cir/.venv` via `_shared_cir_torch.pth`.
- **Standalone Installation**: On systems with sufficient disk capacity (>10 GB free), set `RB_SHARED_TORCH=0 bash scripts/setup_env.sh` to install dedicated PyTorch wheels from the official PyTorch index (`cu130`).

## Docker Compose Deployment

> **Verification status:** the Docker path below has NOT been executed on this workstation. Only the native path (`scripts/setup_env.sh` → `scripts/dev.sh` → `cd frontend && npm run dev`) has been run and verified. Treat `docker compose up --build` as untested scaffolding until someone runs it.

The repository includes a containerized multi-service definition:

```bash
docker compose up --build
```

### Scope & Constraints

- **Containers Provided**:
  - `backend`: Runs FastAPI on port 8000 using Python 3.13-slim.
  - `frontend`: Runs Next.js production build on port 3000.
- **Inference Limitations**: The default `docker-compose.yml` does **not** include NVIDIA container toolkit GPU passthrough configurations. In Docker mode, API serving, leaderboard inspection, and recommendation queries operate fully, but **GPU inference runs must be executed natively on the host**.

## Shared-Machine Etiquette

The current deployment workstation shares root partition space with other active research workspaces (`cir`, `PlantGuard`). Adhere to these operational rules:

1. **Root Partition Disk Budget**: Root (`/`) typically maintains <3 GB free space.
   - Redirect package build caches to RAM: `export UV_CACHE_DIR=/tmp/uv-cache`.
   - Never delete sibling caches (`~/.cache/huggingface`, `~/.npm`, or `/home/heheboiz/data/*`) without explicit confirmation.
2. **GPU Mutex Exclusivity**:
   - Exactly one GPU job may execute at any given time.
   - Concurrency is strictly guarded in the database via the `gpu_locks` table. Do not bypass the job scheduler or spawn parallel CLI runs simultaneously on GPU.
3. **Model Weight Management**:
   - Keep only targeted evaluation models (≤650M parameters) in the local cache.
   - Unload models and trigger `torch.cuda.empty_cache()` between consecutive test runs.
