#!/usr/bin/env python3
"""One-shot 5-second TV OFF test against the public Lightricks LTX-2.5 Space.

The request tests a static-camera rain-and-fire scene suitable for crossfaded looping.
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
    "A locked-off tripod camera, absolutely static composition, inside a "
    "beautiful realistic cozy luxury cabin living room at night. Wide view: "
    "large rain-covered window on the left, a stone fireplace with visible "
    "natural orange flames on the right, warm amber practical lighting, "
    "deep navy evening shadows, realistic wood and stone textures. The camera "
    "does not move at all: no pan, no tilt, no zoom, no dolly, no shake, no "
    " reframing. Only two things move: fine rain droplets slowly travel down "
    "the window glass, and the fireplace flames flicker naturally with subtle "
    "changing embers. All furniture, architecture, reflections, lighting and "
    "framing remain perfectly fixed. Calm premium sleep ambience, photorealistic "
    "cinematography, stable geometry, no people, no text, no logos, no cuts, "
    "no transitions, no sudden motion, no morphing. The motion is gentle and "
    "continuous, with the beginning and ending composition visually similar "
    "so the clip can be crossfaded into a seamless long loop."
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

    raw = out / "tv-off-ltx25-static-rain-fire-raw.mp4"
    final = out / "tv-off-ltx25-static-rain-fire-5s-vertical.mp4"
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

    # Build a 30-second review draft from this fresh 5-second generation.
    # Normalize every segment to CFR before crossfading to avoid timestamp drift.
    draft = out / "tv-off-static-camera-rain-fire-30s-draft.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(final), "-i", str(final), "-i", str(final),
            "-i", str(final), "-i", str(final), "-i", str(final), "-i", str(final),
            "-filter_complex",
            "[0:v]fps=24,settb=1/24,setpts=PTS-STARTPTS[v0];"
            "[1:v]fps=24,settb=1/24,setpts=PTS-STARTPTS[v1];"
            "[2:v]fps=24,settb=1/24,setpts=PTS-STARTPTS[v2];"
            "[3:v]fps=24,settb=1/24,setpts=PTS-STARTPTS[v3];"
            "[4:v]fps=24,settb=1/24,setpts=PTS-STARTPTS[v4];"
            "[5:v]fps=24,settb=1/24,setpts=PTS-STARTPTS[v5];"
            "[6:v]fps=24,settb=1/24,setpts=PTS-STARTPTS[v6];"
            "[v0][v1]xfade=transition=fade:duration=0.20:offset=4.80[x1];"
            "[x1][v2]xfade=transition=fade:duration=0.20:offset=9.60[x2];"
            "[x2][v3]xfade=transition=fade:duration=0.20:offset=14.40[x3];"
            "[x3][v4]xfade=transition=fade:duration=0.20:offset=19.20[x4];"
            "[x4][v5]xfade=transition=fade:duration=0.20:offset=24.00[x5];"
            "[x5][v6]xfade=transition=fade:duration=0.20:offset=28.80,trim=duration=30,setpts=PTS-STARTPTS[v]",
            "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "medium",
            "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(draft),
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
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
