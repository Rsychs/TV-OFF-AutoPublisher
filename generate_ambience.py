import csv
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
VIDEO_DIR = ROOT / "videos"
STATE = ROOT / "state.json"
RATE = 16000
DURATION = 3600
CHUNK = 10

def smooth_noise(rng, n, control_points=180):
    control = rng.normal(0, 1, control_points).astype(np.float32)
    return np.interp(
        np.arange(n, dtype=np.float32),
        np.linspace(0, n - 1, control_points, dtype=np.float32),
        control
    ).astype(np.float32)

def make_signal(kind, rng, n, offset):
    t = (np.arange(n, dtype=np.float32) + offset) / RATE
    white = rng.normal(0, 1, n).astype(np.float32)
    slow = smooth_noise(rng, n, 90)
    mid = smooth_noise(rng, n, 500)
    if kind == "rain":
        # Dense fine droplets over a soft filtered rain bed.
        bed = 0.22 * white + 0.48 * mid + 0.20 * slow
        drops = np.zeros(n, dtype=np.float32)
        count = rng.poisson(18 * CHUNK)
        for p in rng.integers(0, n, size=count):
            length = min(int(rng.uniform(0.006, 0.045) * RATE), n - p)
            if length > 0:
                decay = np.exp(-np.arange(length, dtype=np.float32) / (RATE * 0.006))
                drops[p:p+length] += rng.uniform(0.12, 0.45) * decay * rng.choice([-1, 1])
        signal = 0.34 * bed + 0.18 * drops
        signal *= 0.92 + 0.06 * np.sin(2*np.pi*0.025*t)
    elif kind == "wind":
        # Broad, filtered gusts with slowly evolving intensity.
        gust = 0.58 + 0.22 * np.sin(2*np.pi*0.018*t + 0.7) + 0.12 * slow
        gust = np.clip(gust, 0.18, 1.0)
        signal = (0.36 * slow + 0.24 * mid + 0.08 * white) * gust
    elif kind == "thunderstorm":
        # Rain bed plus occasional low-frequency thunder-like rumbles.
        rain = 0.18 * white + 0.38 * mid + 0.24 * slow
        signal = 0.24 * rain
        # Deterministic event schedule per chunk; rumbles have long soft envelopes.
        events = rng.poisson(0.22 * CHUNK)
        for p in rng.integers(0, n, size=events):
            length = min(int(rng.uniform(2.5, 7.0) * RATE), n - p)
            if length > 0:
                local_t = np.arange(length, dtype=np.float32) / RATE
                freq = rng.uniform(34, 72)
                rumble = np.sin(2*np.pi*freq*local_t + rng.uniform(0, 6.28))
                rumble += 0.35*np.sin(2*np.pi*(freq*0.53)*local_t)
                attack = np.minimum(local_t / 0.7, 1.0)
                decay = np.exp(-local_t / rng.uniform(2.0, 4.0))
                envelope = attack * decay
                signal[p:p+length] += rng.uniform(0.12, 0.28) * rumble * envelope
    else:
        raise ValueError(kind)
    # Gentle saturation and headroom; no hard clipping.
    signal = np.tanh(signal * 1.7) * 0.62
    return np.clip(signal, -0.95, 0.95)

def render(kind, filename, seed):
    out = VIDEO_DIR / filename
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    if filename in state:
        print(f"Already uploaded: {filename}; generation skipped.")
        return
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    wav_path = ROOT / f"{kind}_temp.wav"
    rng = np.random.default_rng(seed)
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        for chunk_index in range(DURATION // CHUNK):
            samples = make_signal(kind, rng, RATE * CHUNK, chunk_index * RATE * CHUNK)
            pcm = np.clip(samples * 32767, -32768, 32767).astype("<i2")
            wav.writeframes(pcm.tobytes())
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=1:d=3600",
        "-i", str(wav_path), "-map", "0:v:0", "-map", "1:a:0",
        "-t", "3600", "-c:v", "libx264", "-preset", "ultrafast",
        "-tune", "stillimage", "-crf", "35", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-ar", str(RATE),
        "-movflags", "+faststart", str(out)
    ], check=True)
    wav_path.unlink(missing_ok=True)
    print(f"Generated {out} ({out.stat().st_size} bytes, 3600 seconds).")

def main():
    configs = {
        "rain": ("TV-OFF_Rain_1-Hour.mp4", 20261109),
        "thunderstorm": ("TV-OFF_Thunderstorm_1-Hour.mp4", 20261110),
        "wind": ("TV-OFF_Wind_1-Hour.mp4", 20261111),
    }
    with (ROOT / "schedule.csv").open(newline="", encoding="utf-8-sig") as f:
        scheduled = {Path(row["filename"].strip()).name for row in csv.DictReader(f)}
    for kind, (filename, seed) in configs.items():
        if filename in scheduled:
            render(kind, filename, seed)

if __name__ == "__main__":
    main()
