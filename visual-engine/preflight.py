"""Read-only preflight diagnostics for free-cloud video generation runtimes.

Run in a Kaggle or Colab notebook before downloading model weights.
This script does not install packages, access credentials, or upload anything.
"""
from __future__ import annotations
import json, os, platform, shutil, subprocess, sys
from pathlib import Path

def command_version(command: str) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        p = subprocess.run([command, "--version"], capture_output=True, text=True, timeout=15)
        return (p.stdout or p.stderr).strip().splitlines()[0][:300]
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"

def main() -> None:
    report = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "disk_free_gb": round(shutil.disk_usage(Path.cwd()).free / 1024**3, 2),
        "ffmpeg": command_version("ffmpeg"),
        "git": command_version("git"),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    }
    try:
        import torch
        report["torch"] = torch.__version__
        report["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            report["gpu_count"] = torch.cuda.device_count()
            report["gpus"] = [
                {
                    "name": torch.cuda.get_device_name(i),
                    "vram_gb": round(torch.cuda.get_device_properties(i).total_memory / 1024**3, 2),
                }
                for i in range(torch.cuda.device_count())
            ]
    except Exception as exc:
        report["torch_error"] = f"{type(exc).__name__}: {exc}"
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
