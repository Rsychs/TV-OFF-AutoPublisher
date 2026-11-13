import hashlib
import json
import os
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.io.wavfile import write

SR = 16000
BAR_SECONDS = 60
BARS = 20
DURATION = BAR_SECONDS * BARS
N = SR * DURATION
ROOT = Path(os.environ.get("SOURCE_AUDIO_DIR", Path(__file__).resolve().parent / "generated-audio"))
ROOT.mkdir(parents=True, exist_ok=True)

# Each release chooses a different key, mode, progression and sound profile.
# Frequencies are generated locally; no samples, recordings or third-party melodies.
MODES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
}
PROGRESSIONS = [
    [0, 4, 5, 3], [0, 5, 3, 4], [5, 3, 0, 4],
    [0, 3, 4, 0], [1, 5, 0, 4], [3, 0, 5, 4],
    [0, 6, 3, 4], [5, 1, 4, 0], [0, 2, 5, 3],
    [1, 4, 0, 5], [0, 4, 1, 5], [3, 4, 0, 6],
]
PROFILES = {
    "soft_piano_ambient": {"harmonics": 3, "pad_gain": 0.020, "melody_gain": 0.018, "density": (1, 3), "echo": "0.8:0.72:90|180:0.12|0.07"},
    "warm_analog": {"harmonics": 6, "pad_gain": 0.016, "melody_gain": 0.014, "density": (2, 4), "echo": "0.8:0.78:65|130:0.15|0.08"},
    "deep_cinematic": {"harmonics": 8, "pad_gain": 0.014, "melody_gain": 0.021, "density": (1, 3), "echo": "0.8:0.82:110|220:0.18|0.09"},
    "minimal_drift": {"harmonics": 2, "pad_gain": 0.024, "melody_gain": 0.010, "density": (1, 2), "echo": "0.8:0.68:75|150:0.10|0.05"},
    "dreamy_bells": {"harmonics": 7, "pad_gain": 0.013, "melody_gain": 0.025, "density": (3, 5), "echo": "0.8:0.86:120|240:0.20|0.10"},
}


def add_note(mix, freq, start, length, gain, pan, harmonics, rng, brightness=1.8):
    start_index = int(start * SR)
    count = min(int(length * SR), N - start_index)
    if count <= 0:
        return
    t = np.arange(count, dtype=np.float32) / SR
    attack_seconds = rng.uniform(2.0, 7.0)
    release_seconds = rng.uniform(4.0, 12.0)
    attack = np.minimum(t / attack_seconds, 1.0)
    release = np.minimum((length - t) / release_seconds, 1.0)
    envelope = np.maximum(0.0, np.minimum(attack, release))
    vibrato_rate = rng.uniform(0.025, 0.075)
    vibrato_depth = rng.uniform(0.015, 0.14)
    phase = vibrato_depth * np.sin(2 * np.pi * vibrato_rate * t)
    wave = np.zeros(count, dtype=np.float32)
    for harmonic in range(1, harmonics + 1):
        wave += np.sin(2 * np.pi * freq * harmonic * t + phase).astype(np.float32) / (harmonic ** brightness)
    wave *= envelope.astype(np.float32) * gain
    left = wave * np.sqrt((1.0 - pan) / 2.0)
    right = wave * np.sqrt((1.0 + pan) / 2.0)
    mix[start_index:start_index + count, 0] += left
    mix[start_index:start_index + count, 1] += right


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_chords(rng, mode_name, root_midi, progression):
    scale = MODES[mode_name]
    chords = []
    for degree in progression:
        intervals = [scale[degree % 7], scale[(degree + 2) % 7], scale[(degree + 4) % 7]]
        # Add a mode-aware seventh or ninth for a fuller, less repetitive harmony.
        if rng.random() < 0.72:
            intervals.append(scale[(degree + 6) % 7])
        if rng.random() < 0.35:
            intervals.append(scale[(degree + 1) % 7] + 12)
        chords.append([440.0 * (2.0 ** ((root_midi + interval - 69) / 12.0)) for interval in intervals])
    return chords


def main():
    seed = secrets.randbelow(2**32 - 1) + 1
    rng = np.random.default_rng(seed)
    mode_name = str(rng.choice(list(MODES.keys())))
    profile_name = str(rng.choice(list(PROFILES.keys())))
    profile = PROFILES[profile_name]
    root_midi = int(rng.integers(43, 55))
    progression = list(PROGRESSIONS[int(rng.integers(0, len(PROGRESSIONS)))])
    chords = build_chords(rng, mode_name, root_midi, progression)
    mix = np.zeros((N, 2), dtype=np.float32)

    # Rotate the four-chord motif with randomized inversions and timing,
    # while retaining a coherent 20-minute original ambient composition.
    for bar in range(BARS):
        chord = chords[bar % len(chords)]
        start = bar * BAR_SECONDS
        for index, freq in enumerate(chord):
            octave = 1.0 if index < 3 else 2.0
            add_note(
                mix, freq * octave, start + rng.uniform(0.0, 2.5), 61.0,
                profile["pad_gain"] * (1.0 if index == 0 else 0.72),
                float(np.clip(-0.42 + index * 0.19 + rng.uniform(-0.08, 0.08), -0.7, 0.7)),
                profile["harmonics"], rng, brightness=float(rng.uniform(1.45, 2.35))
            )
            if index < 3 and rng.random() < 0.8:
                add_note(
                    mix, freq * 0.5, start + rng.uniform(0.3, 3.0), 58.0,
                    profile["pad_gain"] * 0.32, float(rng.uniform(-0.35, 0.35)),
                    max(2, profile["harmonics"] - 2), rng
                )

        low, high = profile["density"]
        for _ in range(int(rng.integers(low, high + 1))):
            freq = float(rng.choice(chord)) * float(rng.choice([2.0, 4.0, 8.0]))
            onset = start + float(rng.uniform(5.0, 54.0))
            length = float(rng.uniform(5.0, 15.0))
            add_note(
                mix, freq, onset, length, profile["melody_gain"] * float(rng.uniform(0.65, 1.2)),
                float(rng.choice([-0.48, -0.25, 0.0, 0.25, 0.48])),
                profile["harmonics"] + 1, rng, brightness=float(rng.uniform(1.2, 2.0))
            )

    # Root note follows the selected harmony instead of using the same fixed 55 Hz bass.
    t = np.arange(N, dtype=np.float32) / SR
    for bar in range(BARS):
        root_freq = chords[bar % len(chords)][0] * 0.5
        start = bar * BAR_SECONDS
        count = min(BAR_SECONDS * SR, N - int(start * SR))
        local_t = np.arange(count, dtype=np.float32) / SR
        bass = 0.009 * np.sin(2 * np.pi * root_freq * local_t)
        bass *= (0.88 + 0.12 * np.sin(2 * np.pi * local_t / rng.uniform(70.0, 130.0)))
        mix[int(start * SR):int(start * SR) + count, 0] += bass
        mix[int(start * SR):int(start * SR) + count, 1] += bass

    mix -= np.mean(mix, axis=0, keepdims=True)
    peak = float(np.max(np.abs(mix)))
    mix *= 0.76 / max(peak, 1e-9)

    wav_path = ROOT / "original_music_master.wav"
    mp3_path = ROOT / "original_music_master.mp3"
    write(wav_path, SR, np.int16(np.clip(mix, -1, 1) * 32767))
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(wav_path), "-af", f"aecho={profile['echo']}",
        "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)
    ], check=True)
    wav_path.unlink(missing_ok=True)
    audio_sha256 = sha256_file(mp3_path)

    (ROOT / "manifest.sha256").write_text(
        f"{audio_sha256}  {mp3_path.name}\n", encoding="utf-8"
    )
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest["original_music"] = {
        "file": mp3_path.name,
        "creator": "TV OFF — original procedural composition",
        "audio_type": "synthetic",
        "platform": "TV OFF / local synthesis",
        "source_url": "Original composition synthesized locally by TV OFF; no external source.",
        "license": "Original composition synthesized for TV OFF; no third-party samples, recordings, or melodies used.",
        "duration_seconds": DURATION,
        "random_seed": seed,
        "musical_mode": mode_name,
        "sound_profile": profile_name,
        "root_midi": root_midi,
        "progression_degrees": progression,
        "sha256": audio_sha256,
        "downloaded_at": datetime.now(timezone.utc).isoformat()
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        f"Generated {DURATION // 60}-minute original composition: "
        f"profile={profile_name}, mode={mode_name}, root_midi={root_midi}, "
        f"progression={progression}, sha256={audio_sha256}"
    )


if __name__ == "__main__":
    main()
