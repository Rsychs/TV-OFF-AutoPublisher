#!/usr/bin/env python3
"""Generate independent ACE-Step sections on an already prepared Colab T4.

Run inside the Python 3.12 ACE-Step venv created by the unified Colab notebook.
This module deliberately does not allocate/stop Colab, render video, or upload.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import secrets
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from acestep.handler import AceStepHandler
from acestep.inference import GenerationConfig, GenerationParams, generate_music

SECTION_SECONDS = 204
SAMPLE_RATE = 48000
CHANNELS = 2
TARGET_HOURS = (1, 3, 8, 10)
CROSSFADE_SECONDS = 2.0

GENRES = {
    "Jazz": {
        "bpm": [82, 88, 94, 100, 108],
        "titles": ["Blue Hour Conversation", "The Last Table by the Window", "Velvet in the City", "A Little After Midnight", "Smoke and Satin", "The Long Way Home", "Autumn on the Avenue", "One More for the Road", "Moonlit Sidewalk", "A Quiet Kind of Swing", "Between Two Heartbeats", "The Art of Staying"],
        "prompt": "Create a sophisticated original instrumental modern jazz ensemble composition with a memorable piano-led theme, warm upright acoustic bass, expressive brushed jazz drums and tasteful tenor saxophone responses. Use rich extended harmony, ii-V-I colors, tasteful substitutions, melodic voice leading, syncopation and natural swing. Develop a real arrangement with an opening theme, contrasting bridge, expressive improvisational solo, varied reprise and deliberate musical ending. Distinct melodic phrases, harmonic movement and interplay; intimate late-night club atmosphere, polished acoustic production. No vocals, no speech, no static chord loop, no synthetic drone."
    },
    "Lo-fi": {
        "bpm": [72, 76, 80, 84, 88],
        "titles": ["Windowlight Reverie", "Midnight on the Balcony", "Coffee Before Sunrise", "Soft Focus Memories", "The Quiet Side Street", "Letters in the Rain", "Golden Hour Drift", "A Room Full of Sunday", "Velvet Afternoon", "After the Last Train", "Blue Notes in the Dust", "Somewhere Slowly"],
        "prompt": "Create a fully developed original instrumental lo-fi hip-hop composition for focused work and late-night listening. Warm dusty boom-bap drums, relaxed pocket, swung hi-hats, deep rounded bass, mellow Rhodes and electric piano chords, jazz-influenced extensions, delicate guitar or muted keyboard motifs, subtle tape saturation. Develop a memorable melodic theme through changing voicings, countermelodies, drum variations, fills, breakdowns and a satisfying ending. Organic human feel, warm detailed mix. No vocals, no speech, no long single-note drones, no static loop, no nature sounds."
    },
    "Electro Instrumental": {
        "bpm": [96, 102, 108, 114, 120],
        "titles": ["Neon Afterglow", "Signals in the Dark", "Electric Daydream", "Beyond the Skyline", "After the Blue Lights", "Parallel Horizons", "Midnight Transmission", "A Thousand Quiet Stars", "Glass City Dreams", "The Shape of Tomorrow", "Fading Into Motion", "Luminous Distance"],
        "prompt": "Create an original melodic electro instrumental track blending sophisticated downtempo electronica and warm analog synth textures. Use defined kick and snare groove, crisp syncopated percussion, rounded electronic bass, evolving analog arpeggios, lush polyphonic synthesizer chords, a distinctive lead melody and subtle atmosphere. Develop a complete arrangement with opening motif, rhythmic entrance, evolving main theme, contrasting breakdown, energetic return and intentional outro. Changing harmony, countermelodies, rhythmic variation and expressive filter movement; memorable, emotionally engaging, not repetitive. No vocals, no speech, no single-note stretching, no generic four-bar loop."
    },
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def required_sections(hours: int) -> int:
    if hours not in TARGET_HOURS:
        raise ValueError(f"Unsupported target duration: {hours}h")
    # Ensure enough independent source time after every crossfade.
    return math.ceil((hours * 3600) / (SECTION_SECONDS - CROSSFADE_SECONDS))

def unique_title(genre: str, used: set[str], ordinal: int) -> str:
    options = GENRES[genre]["titles"]
    for offset in range(len(options)):
        candidate = options[(ordinal + offset) % len(options)]
        if candidate not in used:
            used.add(candidate)
            return candidate
    raise RuntimeError(f"Exhausted unique title pool for {genre}; refusing repeated metadata.")

def generate(hours: int, output: Path) -> dict:
    count = required_sections(hours)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required; refusing CPU fallback.")
    devices = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    if not any("T4" in name for name in devices):
        raise RuntimeError(f"Expected Colab Tesla T4; found {devices}")

    output.mkdir(parents=True, exist_ok=True)
    handler = AceStepHandler()
    message, initialized = handler.initialize_service(
        project_root="/tmp/ACE-Step-1.5",
        config_path="acestep-v15-turbo",
        device="cuda",
        offload_to_cpu=True,
        quantization="int8_weight_only",
    )
    print("ACE-Step initialization:", message, flush=True)
    if not initialized:
        raise RuntimeError("ACE-Step initialization failed.")

    used_titles: set[str] = set()
    used_seeds: set[int] = set()
    used_hashes: set[str] = set()
    section_records = []
    genres = list(GENRES)
    for index in range(count):
        # Rotate genres so a long mix is not a single unchanging texture.
        genre_name = genres[index % len(genres)]
        genre = GENRES[genre_name]
        seed = secrets.randbelow(2**31 - 1) + 1
        while seed in used_seeds:
            seed = secrets.randbelow(2**31 - 1) + 1
        used_seeds.add(seed)
        title = unique_title(genre_name, used_titles, index // len(genres))
        bpm = genre["bpm"][secrets.randbelow(len(genre["bpm"]))]
        section_dir = output / f"section-{index + 1:03d}"
        section_dir.mkdir(parents=True, exist_ok=False)

        params = GenerationParams(
            task_type="text2music",
            caption=genre["prompt"] + f" Tempo: {bpm} BPM. Compose a complete, evolving instrumental arrangement lasting approximately {SECTION_SECONDS} seconds, with a proper musical ending.",
            lyrics="",
            instrumental=True,
            vocal_language="unknown",
            bpm=bpm,
            duration=SECTION_SECONDS,
            inference_steps=8,
            shift=3.0,
            seed=seed,
            thinking=False,
            use_cot_metas=False,
            use_cot_caption=False,
            use_cot_language=False,
        )
        config = GenerationConfig(
            batch_size=1,
            allow_lm_batch=False,
            use_random_seed=False,
            seeds=[seed],
            audio_format="wav",
        )
        result = generate_music(handler, None, params, config, save_dir=str(section_dir))
        if not result.success or not result.audios:
            raise RuntimeError(f"ACE-Step section {index + 1}/{count} failed: {getattr(result, 'error', 'no audio')}")
        source = Path(result.audios[0]["path"])
        if not source.is_file():
            raise RuntimeError(f"ACE-Step returned a missing audio path: {source}")
        audio_path = section_dir / "section.wav"
        if source.resolve() != audio_path.resolve():
            shutil.copy2(source, audio_path)

        info = sf.info(str(audio_path))
        audio, sr = sf.read(str(audio_path), always_2d=True, dtype="float32")
        peak = float(np.max(np.abs(audio)))
        rms = float(np.sqrt(np.mean(np.square(audio))))
        duration = float(info.duration)
        if abs(duration - SECTION_SECONDS) > 1.0:
            raise RuntimeError(f"Section duration mismatch: {duration:.2f}s")
        if sr != SAMPLE_RATE or info.channels != CHANNELS or info.subtype != "PCM_16":
            raise RuntimeError(f"Unexpected audio format: {sr}Hz/{info.channels}ch/{info.subtype}")
        if not np.isfinite(audio).all() or peak >= 1.0 or peak < 0.01 or rms < 0.005:
            raise RuntimeError(f"Audio quality gate failed: peak={peak:.5f}, rms={rms:.5f}")
        digest = sha256_file(audio_path)
        if digest in used_hashes:
            raise RuntimeError("ACE-Step produced duplicate audio bytes; refusing repeated section.")
        used_hashes.add(digest)
        manifest = {
            "status": "ok",
            "provider": "ACE-Step-1.5",
            "release": "v0.1.8",
            "model": "acestep-v15-turbo",
            "gpu": devices,
            "cuda": True,
            "instrumental": True,
            "publishing_enabled": True,
            "section_index": index + 1,
            "section_count": count,
            "duration_seconds": round(duration, 3),
            "requested_duration_seconds": SECTION_SECONDS,
            "sample_rate": int(sr),
            "channels": int(info.channels),
            "subtype": info.subtype,
            "seed": seed,
            "title": title,
            "style": genre_name,
            "bpm": bpm,
            "audio_file": audio_path.name,
            "sha256": digest,
            "peak": round(peak, 6),
            "rms": round(rms, 6),
            "prompt": params.caption,
        }
        (section_dir / "ace_step_smoke_result.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        section_records.append({
            "directory": section_dir.name,
            "title": title,
            "style": genre_name,
            "seed": seed,
            "duration_seconds": round(duration, 3),
            "sha256": digest,
        })
        print(f"SECTION_OK {index + 1}/{count}: {title} | {genre_name} | {duration:.1f}s | sha256={digest}", flush=True)
        del audio
        torch.cuda.empty_cache()

    summary = {
        "status": "sections_generated",
        "published": False,
        "target_hours": hours,
        "section_count": count,
        "provider": "ACE-Step-1.5",
        "gpu": devices,
        "unique_audio_hashes": len(used_hashes),
        "unique_seeds": len(used_seeds),
        "sections": section_records,
    }
    (output / "longform_sections_manifest.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, choices=TARGET_HOURS, required=True)
    parser.add_argument("--output", type=Path, default=Path("/content/longform-sections"))
    args = parser.parse_args()
    print(json.dumps(generate(args.hours, args.output), indent=2, ensure_ascii=False))
