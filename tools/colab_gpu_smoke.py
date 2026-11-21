import json
import platform
import sys

try:
    import torch
except Exception as exc:
    raise SystemExit(f"PyTorch import failed: {exc}")

if not torch.cuda.is_available():
    raise SystemExit("Colab CLI session has no CUDA GPU")

name = torch.cuda.get_device_name(0)
memory_gib = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)

report = {
    "status": "ok",
    "python": sys.version,
    "platform": platform.platform(),
    "pytorch": torch.__version__,
    "cuda_runtime": torch.version.cuda,
    "gpu": name,
    "vram_gib": round(memory_gib, 2),
}
print(json.dumps(report, indent=2))

if "T4" not in name:
    raise SystemExit(f"Expected T4 for the first free-tier test, got: {name}")
if memory_gib < 13:
    raise SystemExit(f"Expected about 16 GB VRAM, got {memory_gib:.2f} GiB")
print("COLAB GPU SMOKE TEST PASSED")
