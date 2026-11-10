import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.io.wavfile import write

SR = 22050
DURATION = 240
N = SR * DURATION
ROOT = Path(os.environ.get("SOURCE_AUDIO_DIR", Path(__file__).resolve().parent / "generated-audio"))
ROOT.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "original_deep_sleep_ambient.wav"

def note(freq, start, length, gain, pan=0.0, harmonics=4):
    i0 = int(start * SR)
    count = min(int(length * SR), N - i0)
    if count <= 0:
        return np.zeros((N, 2), dtype=np.float64)
    t = np.arange(count) / SR
    attack = np.minimum(t / 4.0, 1.0)
    release = np.minimum((length - t) / 5.0, 1.0)
    env = np.maximum(0.0, np.minimum(attack, release))
    env *= 0.82 + 0.18 * np.sin(2 * np.pi * 0.035 * t + freq)
    wave = np.zeros(count)
    for h in range(1, harmonics + 1):
        wave += np.sin(2 * np.pi * freq * h * t + 0.08 * np.sin(2*np.pi*0.07*t)) / (h ** 1.7)
    wave *= env * gain
    left = wave * np.sqrt((1.0 - pan) / 2.0)
    right = wave * np.sqrt((1.0 + pan) / 2.0)
    out = np.zeros((N, 2), dtype=np.float64)
    out[i0:i0+count, 0] = left
    out[i0:i0+count, 1] = right
    return out

def main():
    # Original four-minute ambient piece: Cmaj9 -> Am7 -> Fmaj7 -> G6.
    # All tones are synthesized from oscillators; no samples or external recordings.
    chords = [
        [261.63, 329.63, 392.00, 493.88, 587.33],
        [220.00, 261.63, 329.63, 392.00, 493.88],
        [174.61, 220.00, 261.63, 329.63, 392.00],
        [196.00, 246.94, 293.66, 392.00, 440.00],
    ]
    mix = np.zeros((N, 2), dtype=np.float64)
    for bar, chord in enumerate(chords):
        start = bar * 60.0
        for j, f in enumerate(chord):
            mix += note(f, start, 62.0, 0.025 if j else 0.035, pan=(-0.28 + j*0.14), harmonics=5)
            mix += note(f * 0.5, start + 1.5, 59.0, 0.012, pan=(0.25 - j*0.1), harmonics=3)
    # Sparse, soft bell/piano-like notes add movement without a repetitive short loop.
    melody = [
        (659.25, 12, 9), (587.33, 29, 8), (523.25, 47, 10),
        (493.88, 72, 9), (440.00, 91, 8), (392.00, 111, 10),
        (440.00, 132, 9), (523.25, 151, 8), (587.33, 171, 10),
        (659.25, 192, 9), (587.33, 211, 8), (523.25, 229, 8),
    ]
    for idx, (f, start, length) in enumerate(melody):
        mix += note(f, start, length, 0.028, pan=(-0.35 if idx % 2 else 0.35), harmonics=7)
    # A quiet, slowly moving sub layer gives warmth without percussion or nature effects.
    t = np.arange(N) / SR
    sub = 0.018 * np.sin(2*np.pi*65.41*t) * (0.8 + 0.2*np.sin(2*np.pi*t/83))
    mix[:, 0] += sub
    mix[:, 1] += sub
    # Crossfade the four-minute composition's endpoints to make the long-form loop unobtrusive.
    k = 8 * SR
    fade = np.linspace(0.0, 1.0, k)[:, None]
    seam = (1.0 - fade) * mix[-k:] + fade * mix[:k]
    mix[:k] = seam
    mix[-k:] = seam
    mix -= np.mean(mix, axis=0, keepdims=True)
    mix *= 0.78 / (np.max(np.abs(mix)) + 1e-12)
    write(OUT, SR, np.int16(np.clip(mix, -1, 1) * 32767))
    mp3 = ROOT / "original_deep_sleep_ambient.mp3"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(OUT), "-codec:a", "libmp3lame", "-b:a", "192k",
                    str(mp3)], check=True)
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest["original_music"] = {
        "file": mp3.name,
        "creator": "TV OFF — original procedural composition",
        "source_url": "https://github.com/Rsychs/TV-OFF-AutoPublisher/blob/main/generate_original_music.py",
        "license": "Original composition synthesized for TV OFF; no third-party samples, recordings, or melodies used.",
        "downloaded_at": datetime.now(timezone.utc).isoformat()
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Generated original 4-minute Deep Sleep Ambient master: {mp3}")

if __name__ == "__main__":
    main()
