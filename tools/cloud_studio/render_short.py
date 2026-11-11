#!/usr/bin/env python3
"""Render a real-footage TV OFF Short in GitHub Actions; no GIF or frame slideshow."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import requests
from scipy.io.wavfile import write

OUT = Path("output")
OUT.mkdir(exist_ok=True)
VIDEO = OUT / "TV_OFF_Midnight_Blue.mp4"
AUDIO = OUT / "original_ambient.wav"
SOURCE = Path(tempfile.gettempdir()) / "tv_off_source.mp4"


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required input: {name}")
    return value


def safe_http_url(value: str, label: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit(f"{label} must be a valid HTTPS URL")
    return value


def download_source(url: str) -> None:
    # Stream to disk with a conservative 500 MB ceiling.
    with requests.get(url, stream=True, timeout=(20, 90), allow_redirects=True) as response:
        response.raise_for_status()
        final = urlparse(response.url)
        if final.scheme != "https":
            raise SystemExit("Source redirected away from HTTPS; refusing download")
        total = 0
        with SOURCE.open("wb") as target:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > 500 * 1024 * 1024:
                    raise SystemExit("Source video exceeds the 500 MB limit")
                target.write(chunk)
    if SOURCE.stat().st_size < 100_000:
        raise SystemExit("Downloaded source is unexpectedly small")


def create_original_ambient(duration: int) -> None:
    # Original synthesized pad; no samples, loops, or third-party recordings.
    sr = 48000
    t = np.arange(sr * duration, dtype=np.float64) / sr
    audio = np.zeros_like(t)
    chord_sets = [
        [146.83, 174.61, 220.00, 293.66],
        [116.54, 146.83, 174.61, 233.08],
        [174.61, 220.00, 261.63, 349.23],
        [130.81, 164.81, 196.00, 261.63],
    ]
    segment = duration / len(chord_sets)
    for idx, freqs in enumerate(chord_sets):
        start, end = idx * segment, (idx + 1) * segment
        mask = (t >= start) & (t < end)
        local = t[mask] - start
        fade = np.minimum(1.0, local / 2.5) * np.minimum(1.0, (segment - local) / 2.5)
        pad = np.zeros_like(local)
        for voice, hz in enumerate(freqs):
            pad += np.sin(2 * np.pi * hz * local + voice * 0.31) / (voice + 1)
            pad += 0.12 * np.sin(2 * np.pi * hz * 2.002 * local + voice * 0.17) / (voice + 1)
        audio[mask] += 0.12 * pad * fade
    # Slow, quiet shimmer; avoid percussive clicks.
    audio += 0.008 * np.sin(2 * np.pi * 523.25 * t + 0.15 * np.sin(2 * np.pi * 0.045 * t))
    edge = np.minimum(1.0, t / 2.0) * np.minimum(1.0, (duration - t) / 3.0)
    audio *= edge
    peak = max(float(np.max(np.abs(audio))), 1e-9)
    audio = (audio / peak * 0.68).astype(np.float32)
    stereo = np.column_stack((audio, np.roll(audio, 700)))
    write(str(AUDIO), sr, (stereo * 32767).astype(np.int16))


def render(duration: int, title: str) -> None:
    # Real continuous source footage is retained as video; only crop, grade and
    # gentle continuous camera drift are applied. No GIF/sprite interpolation.
    escaped_title = re.sub(r"[^A-Za-z0-9 '&-]", "", title)[:48] or "Midnight Blue"
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "fps=30,"
        "eq=contrast=1.06:saturation=1.08:brightness=-0.015,"
        "unsharp=5:5:0.35:3:3:0.0,"
        "format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(SOURCE), "-i", str(AUDIO),
        "-t", str(duration),
        "-vf", vf,
        "-af", f"afade=t=in:st=0:d=1.8,afade=t=out:st={max(0,duration-2.8)}:d=2.8",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-r", "30", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(VIDEO),
    ]
    subprocess.run(cmd, check=True)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(VIDEO)],
        check=True, capture_output=True, text=True,
    )
    actual = float(probe.stdout.strip())
    if abs(actual - duration) > 0.5:
        raise SystemExit(f"Rendered duration mismatch: expected {duration}, got {actual}")


def main() -> None:
    source_url = safe_http_url(required("SOURCE_VIDEO_URL"), "Source video URL")
    source_page = safe_http_url(required("SOURCE_PAGE_URL"), "Source page URL")
    creator = os.environ.get("CREATOR_NAME", "Video creator").strip()[:120]
    title = os.environ.get("VIDEO_TITLE", "Midnight Blue").strip()[:80]
    duration = int(os.environ.get("DURATION_SECONDS", "30"))
    if duration not in (20, 30, 40, 50, 60):
        raise SystemExit("Duration must be 20, 30, 40, 50, or 60 seconds")

    download_source(source_url)
    create_original_ambient(duration)
    render(duration, title)

    manifest = {
        "title": title,
        "duration_seconds": duration,
        "format": "MP4 / H.264 / AAC",
        "resolution": "1080x1920",
        "fps": 30,
        "visual_source_page": source_page,
        "visual_creator": creator,
        "music": "Original TV OFF ambient synthesis; no third-party samples",
        "license_note": "Verify the source page license before production or publication.",
        "published": False,
    }
    (OUT / "production.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Rendered: {VIDEO}")


if __name__ == "__main__":
    main()
