#!/usr/bin/env python3
"""One-shot 5-second TV OFF test against the public Lightricks LTX-2.5 Space.

The request deliberately calls the Space API directly: its UI slider is capped
at 5 seconds, but the underlying run() handler accepts duration_s and converts
it to frames. This tests whether the free ZeroGPU reservation permits 20 sec.
No YouTube workflow or production resource is touched.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from gradio_client import Client

SPACE = "Lightricks/LTX-2.5"
DURATION_SECONDS = 5.0
# Portrait-ish 4:5 render: keeps GPU reservation near the free ZeroGPU quota.
# Center-crop to 9:16 and upscale after generation.
HEIGHT, WIDTH = 640, 512
SEED = 42
PROMPT = (
    "One continuous photorealistic cinematic shot inside a luxury bedroom at "
    "midnight. A wide elegant room with floor-to-ceiling rain-covered windows, "
    "warm amber bedside lamps against deep navy shadows, refined natural "
    "materials, realistic glass reflections and detailed soft fabric. The "
    "camera makes an extremely slow, perfectly smooth dolly forward throughout "
    "the entire shot. Rain trails move naturally down the glass; sheer curtains "
    "breathe subtly in a faint indoor draft; lamp light flickers almost "
    "imperceptibly. The room layout, furniture, windows, lamps and lighting "
    "remain consistent from first frame to last. Calm premium sleep ambience, "
    "physically plausible motion, no people, no text, no logos, no cuts, no "
    "transitions, no sudden movement, no morphing, no geometry changes."
)

def main() -> int:
    out = Path("visual-engine-output")
    out.mkdir(parents=True, exist_ok=True)
    token = os.getenv("HF_TOKEN")
    print(
        f"Connecting to {SPACE}; token_present={bool(token)}; "
        f"request={DURATION_SECONDS}s @ {WIDTH}x{HEIGHT}",
        flush=True,
    )
    client = Client(SPACE, token=token or None, verbose=True, httpx_kwargs={"timeout": 600})

    # Current Space app.py _INPUTS order:
    # prompt, image, height, width, duration_s, seed, decoder, auto_len,
    # randomize_seed, enhance_toggle.
    # API call uses the public Space maximum of 5s.
    result = client.predict(
        PROMPT,
        None,
        HEIGHT,
        WIDTH,
        DURATION_SECONDS,
        SEED,
        "conv",
        False,
        False,
        False,
        api_name="/run",
    )
    video_path = result[0] if isinstance(result, (tuple, list)) else result
    if isinstance(video_path, dict):
        video_path = video_path.get("path") or video_path.get("video")
    if not video_path or not Path(str(video_path)).is_file():
        raise RuntimeError(f"Space returned no local MP4 file: {result!r}")

    raw = out / "tv-off-ltx25-bedroom-rain-raw.mp4"
    final = out / "tv-off-ltx25-bedroom-rain-5s-vertical.mp4"
    shutil.copy2(str(video_path), raw)

    # Convert the 4:5 source into a centered 9:16 Shorts master.
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(raw),
            "-vf", "crop=ih*9/16:ih,scale=720:1280:flags=lanczos,fps=24",
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(final),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    manifest = {
        "space": SPACE,
        "api_name": "/run",
        "prompt": PROMPT,
        "height": HEIGHT,
        "width": WIDTH,
        "duration_seconds_requested": DURATION_SECONDS,
        "frames_requested": 121,
        "fps": 24,
        "seed": SEED,
        "decoder": "conv",
        "image_conditioning": False,
        "source_video": raw.name,
        "shorts_master": final.name,
        "result": repr(result),
        "note": "5s request at the current public Space API limit. Verify actual output duration before acceptance.",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        f"SUCCESS: {final} ({final.stat().st_size} bytes); "
        f"source={raw.stat().st_size} bytes",
        flush=True,
    )
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"GENERATION_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise
