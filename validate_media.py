import json
import re
import subprocess
import sys
from pathlib import Path

def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout

def validate(path):
    path = Path(path)
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    streams = probe.get("streams", [])
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    video = [s for s in streams if s.get("codec_type") == "video"]
    if not audio or not video:
        raise RuntimeError(f"{path.name}: missing audio or video stream")
    duration = float(probe["format"]["duration"])
    if not 3590 <= duration <= 3610:
        raise RuntimeError(f"{path.name}: expected 1 hour, got {duration:.1f}s")
    if audio[0].get("channels", 0) < 1:
        raise RuntimeError(f"{path.name}: invalid audio channel count")
    if video[0].get("width") != 1280 or video[0].get("height") != 720:
        raise RuntimeError(f"{path.name}: unexpected video dimensions")
    log = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect,silencedetect=noise=-55dB:d=10", "-f", "null", "-"],
        capture_output=True, text=True
    )
    output = log.stderr
    if log.returncode != 0:
        raise RuntimeError(f"{path.name}: FFmpeg decode check failed")
    mean = re.search(r"mean_volume: (-?[0-9.]+) dB", output)
    peak = re.search(r"max_volume: (-?[0-9.]+) dB", output)
    if not mean or not peak:
        raise RuntimeError(f"{path.name}: could not measure audio levels")
    mean_db, peak_db = float(mean.group(1)), float(peak.group(1))
    if mean_db < -42 or mean_db > -8:
        raise RuntimeError(f"{path.name}: average loudness outside safe range ({mean_db:.1f} dBFS)")
    if peak_db < -28 or peak_db > -0.5:
        raise RuntimeError(f"{path.name}: peak outside safe range ({peak_db:.1f} dBFS)")
    if "silence_start:" in output:
        raise RuntimeError(f"{path.name}: silence longer than 10 seconds detected")
    print(f"AUDIO OK: {path.name} | {duration/60:.1f} min | mean {mean_db:.1f} dBFS | peak {peak_db:.1f} dBFS")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python validate_media.py video.mp4 [...]")
    for item in sys.argv[1:]:
        validate(item)
