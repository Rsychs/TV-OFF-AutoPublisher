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
CHORDS = [
    [130.81, 164.81, 196.00, 246.94, 293.66],  # Cmaj9
    [110.00, 130.81, 164.81, 196.00, 246.94],  # Am9
    [87.31, 110.00, 130.81, 164.81, 196.00],   # Fmaj7
    [98.00, 123.47, 146.83, 196.00, 220.00],   # G6
    [73.42, 87.31, 110.00, 130.81, 164.81],    # Dm9
    [116.54, 146.83, 174.61, 220.00, 261.63],  # Bbmaj7
    [110.00, 130.81, 174.61, 220.00, 261.63],  # F/A
    [98.00, 130.81, 164.81, 196.00, 246.94],   # Cmaj7/G
    [82.41, 98.00, 123.47, 146.83, 196.00],    # Em7
    [110.00, 130.81, 164.81, 196.00, 246.94],  # Am9
    [73.42, 87.31, 110.00, 146.83, 174.61],    # Dm7
    [98.00, 130.81, 146.83, 196.00, 220.00],   # G7sus4
    [130.81, 164.81, 196.00, 246.94, 293.66],  # Cmaj9
    [87.31, 110.00, 130.81, 174.61, 220.00],   # Fmaj9
    [82.41, 98.00, 123.47, 146.83, 196.00],    # Em7
    [110.00, 130.81, 164.81, 196.00, 246.94],  # Am9
    [73.42, 87.31, 110.00, 130.81, 164.81],    # Dm9
    [98.00, 123.47, 146.83, 196.00, 220.00],   # G6
    [130.81, 164.81, 196.00, 246.94, 293.66],  # Cmaj9
    [130.81, 164.81, 196.00, 246.94, 293.66],  # Cmaj9 resolution
]
DURATION = BAR_SECONDS * len(CHORDS)
N = SR * DURATION
ROOT = Path(os.environ.get("SOURCE_AUDIO_DIR", Path(__file__).resolve().parent / "generated-audio"))
ROOT.mkdir(parents=True, exist_ok=True)

def add_note(mix, freq, start, length, gain, pan, harmonics, rng):
    start_index = int(start * SR)
    count = min(int(length * SR), N - start_index)
    if count <= 0:
        return
    t = np.arange(count, dtype=np.float32) / SR
    attack = np.minimum(t / rng.uniform(3.0, 5.0), 1.0)
    release = np.minimum((length - t) / rng.uniform(5.0, 9.0), 1.0)
    envelope = np.maximum(0.0, np.minimum(attack, release))
    vibrato_rate = rng.uniform(0.025, 0.055)
    vibrato_depth = rng.uniform(0.03, 0.12)
    phase = vibrato_depth * np.sin(2 * np.pi * vibrato_rate * t)
    wave = np.zeros(count, dtype=np.float32)
    for harmonic in range(1, harmonics + 1):
        wave += np.sin(2 * np.pi * freq * harmonic * t + phase).astype(np.float32) / (harmonic ** 1.8)
    wave *= envelope.astype(np.float32) * gain
    left = wave * np.sqrt((1.0 - pan) / 2.0)
    right = wave * np.sqrt((1.0 + pan) / 2.0)
    mix[start_index:start_index+count, 0] += left
    mix[start_index:start_index+count, 1] += right

def main():
    seed = secrets.randbelow(2**32 - 1) + 1
    rng = np.random.default_rng(seed)
    mix = np.zeros((N, 2), dtype=np.float32)

    # Twenty minutes of original, slow-evolving ambient harmony.
    # All tones are synthesized from oscillators; no samples or external recordings.
    for bar, chord in enumerate(CHORDS):
        start = bar * BAR_SECONDS
        for index, freq in enumerate(chord):
            add_note(mix, freq, start + rng.uniform(0.0, 1.8), 62.0,
                     0.019 if index else 0.028,
                     float(np.clip(-0.34 + index * 0.16 + rng.uniform(-0.05, 0.05), -0.65, 0.65)),
                     5, rng)
            add_note(mix, freq * 0.5, start + rng.uniform(0.5, 2.5), 59.0,
                     0.008, float(rng.uniform(-0.3, 0.3)), 3, rng)

        # Sparse bell-like notes are selected from the current chord, with a fresh pattern per release.
        melody_count = int(rng.integers(2, 5))
        for _ in range(melody_count):
            freq = float(rng.choice(chord)) * float(rng.choice([2.0, 4.0]))
            onset = start + float(rng.uniform(7.0, 52.0))
            length = float(rng.uniform(7.0, 13.0))
            add_note(mix, freq, onset, length, float(rng.uniform(0.012, 0.024)),
                     float(rng.choice([-0.42, -0.2, 0.2, 0.42])), 7, rng)

    # A very quiet bass foundation; no percussion or environmental effects.
    t = np.arange(N, dtype=np.float32) / SR
    sub = 0.012 * np.sin(2 * np.pi * 55.0 * t) * (0.84 + 0.16 * np.sin(2 * np.pi * t / 97.0))
    mix[:, 0] += sub
    mix[:, 1] += sub
    mix -= np.mean(mix, axis=0, keepdims=True)
    peak = float(np.max(np.abs(mix)))
    mix *= 0.76 / max(peak, 1e-9)

    wav_path = ROOT / "original_deep_sleep_ambient.wav"
    mp3_path = ROOT / "original_deep_sleep_ambient.mp3"
    write(wav_path, SR, np.int16(np.clip(mix, -1, 1) * 32767))
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(wav_path), "-af",
        "aecho=0.8:0.82:70|140:0.16|0.09",
        "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)
    ], check=True)
    wav_path.unlink(missing_ok=True)

    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest["original_music"] = {
        "file": mp3_path.name,
        "creator": "TV OFF — original procedural composition",
        "audio_type": "synthetic",
        "platform": "TV OFF / local synthesis",
        "source_url": "https://github.com/Rsychs/TV-OFF-AutoPublisher/blob/main/generate_original_music.py",
        "license": "Original composition synthesized for TV OFF; no third-party samples, recordings, or melodies used.",
        "duration_seconds": DURATION,
        "random_seed": seed,
        "downloaded_at": datetime.now(timezone.utc).isoformat()
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Generated original {DURATION // 60}-minute Deep Sleep Ambient master: {mp3_path}")

if __name__ == "__main__":
    main()
