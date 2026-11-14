#!/usr/bin/env python3
"""One-shot TV OFF test against the public Lightricks LTX-2.5 Gradio Space.

This calls the hosted GPU. It does not download model weights or touch YouTube.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from gradio_client import Client

SPACE = "Lightricks/LTX-2.5"
PROMPT = (
    "Photorealistic cinematic luxury bedroom at midnight, a wide elegant room "
    "with floor-to-ceiling windows covered in gentle rain, warm amber bedside "
    "lamps contrasting with deep navy shadows, refined natural materials, "
    "realistic glass reflections and soft fabric texture. A very slow, smooth "
    "camera dolly forward. Subtle rain trails moving down the glass and sheer "
    "curtains gently breathing in a faint indoor draft. Calm premium sleep "
    "ambience, physically plausible lighting, stable room geometry, no people, "
    "no text, no logos, no cuts, no sudden movement."
)

def main() -> int:
    out = Path("visual-engine-output")
    out.mkdir(parents=True, exist_ok=True)
    token = os.getenv("HF_TOKEN")
    print(f"Connecting to {SPACE}; token_present={bool(token)}", flush=True)
    client = Client(SPACE, hf_token=token or None, verbose=True)
    # Input order is taken from the Space's live app.py _INPUTS declaration.
    result = client.predict(
        PROMPT,
        None,       # no conditioning image: true text-to-video
        832,        # height
        1472,       # width
        2.0,        # seconds; smallest practical acceptance test
        42,         # deterministic seed
        "conv",     # fast convolutional decoder
        False,      # no auto-length (avoid reserving maximum GPU time)
        False,      # fixed seed
        False,      # skip optional prompt-enhancer to avoid second GPU queue
        api_name="/run",
    )
    # Gradio returns a filepath for the Video output.
    video_path = result[0] if isinstance(result, (tuple, list)) else result
    if isinstance(video_path, dict):
        video_path = video_path.get("path") or video_path.get("video")
    if not video_path or not Path(str(video_path)).is_file():
        raise RuntimeError(f"Space returned no local MP4 file: {result!r}")
    dest = out / "tv-off-ltx25-bedroom-rain.mp4"
    shutil.copy2(str(video_path), dest)
    manifest = {
        "space": SPACE,
        "api_name": "/run",
        "prompt": PROMPT,
        "height": 832,
        "width": 1472,
        "duration_seconds_requested": 2.0,
        "seed": 42,
        "decoder": "conv",
        "image_conditioning": False,
        "video_file": dest.name,
        "result": repr(result),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"SUCCESS: {dest} ({dest.stat().st_size} bytes)", flush=True)
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"GENERATION_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise
