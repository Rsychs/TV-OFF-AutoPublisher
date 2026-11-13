import hashlib
import json
import os
import re
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path

KIND = os.environ.get("SOUNDSCAPE", "").strip().lower()
ROOT = Path(os.environ.get("SOURCE_AUDIO_DIR", "generated-audio"))
DURATION_SECONDS = int(os.environ.get("TV_OFF_AUDIO_TEST_SECONDS", "3600"))
SAMPLE_RATE = 48000
NOISE_COLORS = {"white_noise": "white", "brown_noise": "brown"}

# The primary layer remains the named noise colour. Quiet independent layers
# add a distinctive texture without turning the result into music or effects.
PROFILES = {
    "white_noise": {
        "soft_air": {
            "texture": "highpass=f=1700,lowpass=f=10500",
            "texture_gain": 0.16,
            "air": "highpass=f=5200,lowpass=f=14500",
            "air_gain": 0.055,
            "description": "smooth full-spectrum bed with a restrained airy upper layer",
        },
        "studio_silk": {
            "texture": "highpass=f=320,lowpass=f=5200",
            "texture_gain": 0.12,
            "air": "highpass=f=6500,lowpass=f=15500",
            "air_gain": 0.045,
            "description": "balanced white-noise bed with subtle midrange body and soft air",
        },
        "wide_neutral": {
            "texture": "highpass=f=900,lowpass=f=7800",
            "texture_gain": 0.10,
            "air": "highpass=f=4200,lowpass=f=12500",
            "air_gain": 0.035,
            "description": "neutral white-noise texture with a gentle, open stereo image",
        },
    },
    "brown_noise": {
        "deep_velvet": {
            "texture": "highpass=f=90,lowpass=f=900",
            "texture_gain": 0.15,
            "air": "highpass=f=650,lowpass=f=2100",
            "air_gain": 0.045,
            "description": "deep brown-noise foundation with a soft, controlled upper body",
        },
        "warm_focus": {
            "texture": "highpass=f=140,lowpass=f=1450",
            "texture_gain": 0.12,
            "air": "highpass=f=900,lowpass=f=2800",
            "air_gain": 0.035,
            "description": "warm low-frequency noise with enough definition to avoid dullness",
        },
        "subtle_room": {
            "texture": "highpass=f=65,lowpass=f=620",
            "texture_gain": 0.17,
            "air": "highpass=f=500,lowpass=f=1600",
            "air_gain": 0.025,
            "description": "rounded sub-bass weight with a restrained, smooth presence layer",
        },
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_seconds(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True, timeout=30,
    )
    return float(result.stdout.strip())


def main() -> None:
    if KIND not in NOISE_COLORS:
        raise RuntimeError(
            f"Unsupported sound category {KIND!r}; only White Noise and Brown Noise are allowed."
        )
    if DURATION_SECONDS < 30:
        raise RuntimeError("Audio duration must be at least 30 seconds.")

    ROOT.mkdir(parents=True, exist_ok=True)
    seed = secrets.randbelow(2**31 - 1) + 1
    seed_r = seed + 104729
    seed_texture = seed + 130363
    seed_air = seed + 155921
    color = NOISE_COLORS[KIND]
    profile_name = secrets.choice(list(PROFILES[KIND]))
    profile = PROFILES[KIND][profile_name]
    target = ROOT / f"{KIND}_original_{seed}.mp3"

    # Two independent noise beds form the left/right channels. Texture layers
    # are intentionally quiet; the primary coloured noise remains dominant.
    graph = (
        "[0:a][1:a]amerge=inputs=2,"
        "pan=stereo|c0=c0|c1=c1[base];"
        f"[2:a]{profile['texture']},volume={profile['texture_gain']},"
        "pan=stereo|c0=0.82*c0|c1=0.48*c0[texture];"
        f"[3:a]{profile['air']},volume={profile['air_gain']},"
        "pan=stereo|c0=0.45*c0|c1=0.82*c0[air];"
        "[base][texture][air]amix=inputs=3:duration=longest:normalize=0,"
        "alimiter=limit=0.88[out]"
    )
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i",
        f"anoisesrc=color={color}:amplitude=0.105:sample_rate={SAMPLE_RATE}:duration={DURATION_SECONDS}:seed={seed}",
        "-f", "lavfi", "-i",
        f"anoisesrc=color={color}:amplitude=0.105:sample_rate={SAMPLE_RATE}:duration={DURATION_SECONDS}:seed={seed_r}",
        "-f", "lavfi", "-i",
        f"anoisesrc=color=white:amplitude=0.025:sample_rate={SAMPLE_RATE}:duration={DURATION_SECONDS}:seed={seed_texture}",
        "-f", "lavfi", "-i",
        f"anoisesrc=color=pink:amplitude=0.012:sample_rate={SAMPLE_RATE}:duration={DURATION_SECONDS}:seed={seed_air}",
        "-filter_complex", graph, "-map", "[out]", "-t", str(DURATION_SECONDS),
        "-c:a", "libmp3lame", "-b:a", "192k", "-ar", str(SAMPLE_RATE),
        str(target),
    ]
    print(
        f"GENERATING {KIND}: profile={profile_name}; {profile['description']}; "
        f"duration={DURATION_SECONDS}s; seeds={seed}/{seed_r}/{seed_texture}/{seed_air}",
        flush=True,
    )
    subprocess.run(command, check=True, timeout=max(480, DURATION_SECONDS // 3))

    actual_duration = probe_seconds(target)
    if actual_duration < DURATION_SECONDS - 1:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Generated audio is too short: {actual_duration:.2f}s")

    digest = sha256(target)
    (ROOT / "manifest.sha256").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    manifest = {
        KIND: {
            "file": target.name,
            "creator": "TV OFF — original procedural noise design",
            "source_url": "Generated locally by TV OFF; no external recordings or samples.",
            "license": "Original synthetic audio generated for TV OFF; no third-party source used.",
            "title": f"TV OFF {KIND.replace('_', ' ').title()} — {profile_name.replace('_', ' ').title()}",
            "platform": "TV OFF / FFmpeg",
            "audio_type": "synthetic",
            "noise_color": color,
            "sound_profile": profile_name,
            "sound_design": profile["description"],
            "random_seeds": [seed, seed_r, seed_texture, seed_air],
            "duration_seconds": round(actual_duration, 2),
            "sample_rate": SAMPLE_RATE,
            "stereo": True,
            "sha256": digest,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"NOISE PREFLIGHT PASSED: {KIND} | {profile_name} | "
        f"{actual_duration:.2f}s | sha256={digest} | local-only",
        flush=True,
    )


if __name__ == "__main__":
    main()
