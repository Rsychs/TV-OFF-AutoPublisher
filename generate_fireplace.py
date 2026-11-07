import json
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "videos" / "TV-OFF_Fireplace_1-Hour.mp4"
STATE = ROOT / "state.json"
KEY = OUT.name
DURATION = 3600
RATE = 16000


def run():
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    if KEY in state:
        print(f"Already uploaded: {state[KEY]}; generation skipped.")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wav_path = ROOT / "fireplace_temp.wav"
    rng = np.random.default_rng(20261108)
    chunk_seconds = 10
    previous = 0.0

    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        for _ in range(DURATION // chunk_seconds):
            count = RATE * chunk_seconds
            white = rng.normal(0, 1, count).astype(np.float32)
            # Soft, filtered fire-bed with a warm low-frequency body.
            smooth = np.empty_like(white)
            smooth[0] = previous
            for i in range(1, count):
                smooth[i] = 0.985 * smooth[i - 1] + 0.015 * white[i]
            previous = float(smooth[-1])
            bed = 0.12 * white + 0.34 * smooth
            # Irregular short crackles with natural exponential tails.
            crackles = np.zeros(count, dtype=np.float32)
            events = rng.poisson(2.8 * chunk_seconds)
            for pos in rng.integers(0, count, size=events):
                length = min(int(rng.uniform(0.025, 0.16) * RATE), count - pos)
                if length > 0:
                    amp = rng.uniform(0.35, 1.0) * rng.choice([-1.0, 1.0])
                    decay = np.exp(-np.arange(length, dtype=np.float32) / (RATE * rng.uniform(0.008, 0.035)))
                    crackles[pos:pos + length] += amp * decay
            # Gentle slow variation avoids a static, loop-like texture.
            t = np.arange(count, dtype=np.float32) / RATE
            warmth = 0.82 + 0.12 * np.sin(2 * np.pi * 0.07 * t + rng.uniform(0, 6.28))
            signal = (bed * warmth + 0.20 * crackles) * 0.22
            signal = np.tanh(signal * 1.8) * 0.72
            pcm = np.clip(signal * 32767, -32768, 32767).astype("<i2")
            wav.writeframes(pcm.tobytes())

    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=1:d=3600",
        "-i", str(wav_path), "-map", "0:v:0", "-map", "1:a:0",
        "-t", "3600", "-c:v", "libx264", "-preset", "ultrafast",
        "-tune", "stillimage", "-crf", "35", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "64k", "-ar", "16000",
        "-movflags", "+faststart", str(OUT)
    ], check=True)
    wav_path.unlink(missing_ok=True)
    print(f"Generated {OUT} ({OUT.stat().st_size} bytes, 3600 seconds).")


if __name__ == "__main__":
    run()
