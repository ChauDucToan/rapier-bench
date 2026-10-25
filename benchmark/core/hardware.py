"""Hardware and environment telemetry collector.

Authoritative source: docs/ARCHITECTURE.md Section 7.1 and docs/ENVIRONMENT.md.
"""

import contextlib
import platform
import shutil
import subprocess
from typing import Any


def capture_hardware_info() -> dict[str, Any]:
    """Capture GPU name, VRAM, driver, torch, and CUDA version. Never crashes if no GPU."""
    info: dict[str, Any] = {
        "gpu_available": False,
        "gpu_name": None,
        "vram_total_mib": 0.0,
        "cuda_version": None,
        "torch_version": None,
        "driver_version": None,
        "device_count": 0,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }

    # PyTorch telemetry
    try:
        import torch

        info["torch_version"] = torch.__version__
        if torch.cuda.is_available():
            info["gpu_available"] = True
            info["device_count"] = torch.cuda.device_count()
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["cuda_version"] = torch.version.cuda
            props = torch.cuda.get_device_properties(0)
            info["vram_total_mib"] = round(props.total_memory / (1024 * 1024), 2)
    except Exception:
        pass

    # nvidia-smi fallback/supplement
    if shutil.which("nvidia-smi"):
        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split("\n")[0].split(",")]
                if len(parts) >= 3:
                    if not info["gpu_name"]:
                        info["gpu_name"] = parts[0]
                    if info["vram_total_mib"] == 0.0:
                        with contextlib.suppress(ValueError):
                            info["vram_total_mib"] = float(parts[1])
                    info["driver_version"] = parts[2]
        except Exception:
            pass

    return info
