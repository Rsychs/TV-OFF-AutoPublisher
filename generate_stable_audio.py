#!/usr/bin/env python3
"""Generate original TV OFF music through the official Stability AI Stable Audio API.

This provider is opt-in. It generates a 36-second arrangement for Shorts and a
380-second master for long-form, which the existing video builder loops with
crossfades. API credentials are read only from environment variables.
"""
import hashlib
import json
import os
import secrets
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API_BASE = "https://api.stability.ai"
SUBMIT_URL = f"{API_BASE}/v2beta/audio/stable-audio/text-to-audio"
RESULT_URL = f"{API_BASE}/v2beta/audio/results"
SHORT_MODE = bool(os.environ.get("TARGET_SLOT", "").strip())
DURATION = 36 if SHORT_MODE else 380
MODEL = os.environ.get("STABILITY_AUDIO_MODEL", "stable-audio-3").strip()
ROOT = Path(os.environ.get("SOURCE_AUDIO_DIR", Path(__file__).resolve().parent / "generated-audio"))
ROOT.mkdir(parents=True, exist_ok=True)

PROMPTS = [
    (
        "Soft cinematic ambient instrumental music for sleep and quiet focus. "
        "A complete evolving musical composition with a memorable gentle piano motif, "
        "warm sustained string and analog synthesizer chords, a rounded melodic bass line, "
        "subtle bell counter-melody, and delicate rhythmic arpeggios. "
        "Clearly changing chord progression and distinct A-B-A sections, natural melodic phrasing, "
        "rich layered harmony, gradual development and a resolved ending. "
        "Slow 72 BPM, intimate, warm, spacious, polished studio production. Instrumental only."
    ),
    (
        "Dreamlike modern ambient instrumental with felt piano, soft marimba-like plucks, "
        "wide analog pads, gentle low bass and a delicate repeating rhythmic motif. "
        "Write a real melody and evolving chord progression with contrasting sections, "
        "counter-melodies and a satisfying harmonic resolution. "
        "Slow 78 BPM, peaceful nighttime mood, detailed organic arrangement, instrumental."
    ),
    (
        "Warm neo-classical electronic instrumental: expressive piano theme over lush strings, "
        "soft synth textures, rounded bass and restrained pulsing percussion. "
        "A complete arrangement with a clear opening, melodic development, a lifted middle section "
        "and a calm resolved outro. Multiple chord changes, memorable motif and layered counterpoint. "
        "Slow 76 BPM, elegant, comforting, cinematic, instrumental only."
    ),
    (
        "Gentle lo-fi ambient instrumental for reading and concentration, with mellow electric piano, "
        "soft tape-like synth chords, subtle plucked melody, warm bass and understated brushed rhythm. "
        "Develop a coherent tune with changing harmony, melodic variations and a clear musical arc. "
        "Relaxed 82 BPM, intimate and polished, instrumental only."
    ),
    (
        "Celestial ambient instrumental built from glassy piano, airy synth strings, "
        "soft bell accents, deep warm bass and flowing arpeggios. "
        "A complete musical piece with a distinct melody, changing extended chords, "
        "gentle tension and release, evolving layers and a graceful ending. "
        "Slow 70 BPM, spacious and emotionally calm, instrumental only."
    ),
]

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def api_error(response):
    try:
        body = response.json()
    except ValueError:
        body = response.text[:1200]
    return f"Stability API HTTP {response.status_code}: {body}"


def main():
    api_key = os.environ.get("STABILITY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("STABILITY_API_KEY is required when Stable Audio is enabled.")

    seed = secrets.randbelow(4294967294) + 1
    prompt_index = secrets.randbelow(len(PROMPTS))
    prompt = PROMPTS[prompt_index]
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    # Submit exactly once. Poll the returned job id rather than resubmitting a
    # potentially billable generation after a timeout.
    response = requests.post(
        SUBMIT_URL,
        headers=headers,
        data={
            "model": MODEL,
            "prompt": prompt,
            "duration": str(DURATION),
            "seed": str(seed),
            "steps": "8",
            "cfg_scale": "7",
            "output_format": "mp3",
        },
        files={"none": ("", b"")},
        timeout=(30, 180),
    )
    if response.status_code not in (200, 202):
        raise RuntimeError(api_error(response))
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Stable Audio submit response was not valid JSON.") from exc
    job_id = payload.get("id")
    if not isinstance(job_id, str) or not job_id:
        raise RuntimeError(f"Stable Audio did not return a generation id: {payload}")
    print(f"STABLE AUDIO JOB ACCEPTED: id={job_id}; duration={DURATION}s; model={MODEL}")

    result_url = f"{RESULT_URL}/{job_id}"
    deadline = time.monotonic() + 20 * 60
    audio_bytes = None
    delay = 5
    while time.monotonic() < deadline:
        time.sleep(delay)
        result = requests.get(
            result_url,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "audio/*"},
            timeout=(30, 180),
        )
        if result.status_code == 200:
            audio_bytes = result.content
            break
        if result.status_code == 202:
            print(f"STABLE AUDIO STILL GENERATING: HTTP 202; next poll in {delay}s")
            delay = min(15, delay + 2)
            continue
        if result.status_code == 429:
            print("STABLE AUDIO RATE LIMITED: waiting 30 seconds before polling the same job.")
            time.sleep(30)
            continue
        raise RuntimeError(api_error(result))
    if not audio_bytes:
        raise TimeoutError(
            f"Stable Audio job {job_id} did not finish within 20 minutes. "
            "Do not resubmit automatically; check the same job/result first."
        )

    audio_path = ROOT / "original_music_master.mp3"
    if len(audio_bytes) < 4096:
        raise RuntimeError("Stable Audio returned an unexpectedly small audio file.")
    audio_path.write_bytes(audio_bytes)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        check=True, capture_output=True, text=True, timeout=60,
    )
    actual_duration = float(probe.stdout.strip())
    if abs(actual_duration - DURATION) > 2.0:
        raise RuntimeError(
            f"Stable Audio output duration {actual_duration:.2f}s does not match "
            f"requested {DURATION}s (±2s); refusing to build a video."
        )

    digest = sha256_file(audio_path)
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    style_names = ["cinematic_ambient", "soft_keys", "neo_classical", "lofi_ambient", "celestial"]
    style_name = style_names[prompt_index]
    profile_names = ["stable_audio_3"]
    manifest["original_music"] = {
        "file": audio_path.name,
        "creator": "TV OFF — original AI-generated instrumental composition",
        "audio_type": "synthetic",
        "platform": "TV OFF / Stability AI Stable Audio API",
        "provider": "stability",
        "model": MODEL,
        "provider_job_id": job_id,
        "source_url": "Generated directly through the official Stability AI API; no third-party recording or sample.",
        "license": (
            "Generated output under Stability AI Platform Terms of Service; commercial use subject to "
            "current Stability AI terms and applicable law."
        ),
        "duration_seconds": int(round(actual_duration)),
        "composition_mode": (
            "stable_audio_short_form" if SHORT_MODE else "long_form_ai_composed_master"
        ),
        "bar_seconds": None if SHORT_MODE else 60,
        "sample_rate": 44100,
        "random_seed": seed,
        "musical_mode": "ai_composed",
        "sound_profile": profile_names[0],
        "music_style": style_name,
        "music_style_description": prompt,
        "prompt": prompt,
        "layers": ["AI-composed melody", "evolving harmony", "multi-instrument arrangement"],
        "sha256": digest,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest_digest = sha256_file(manifest_path)
    (ROOT / "manifest.sha256").write_text(
        f"{digest}  {audio_path.name}\n{manifest_digest}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    print(
        f"STABLE AUDIO COMPLETE: duration={actual_duration:.2f}s; style={style_name}; "
        f"sha256={digest}; job_id={job_id}"
    )


if __name__ == "__main__":
    main()
