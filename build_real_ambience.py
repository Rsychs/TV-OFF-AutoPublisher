import csv, hashlib, json, os, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = Path(os.environ.get("SOURCE_AUDIO_DIR", ROOT / "audio"))
OUTPUT_DIR = Path(os.environ.get("MEDIA_DIR", ROOT / "videos"))
MANIFEST = SOURCE_DIR / "manifest.json"
DURATION = 36000
CROSSFADE = 5

def run(args):
    subprocess.run(args, check=True)

def duration(path):
    p = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(path)],check=True,capture_output=True,text=True)
    return float(p.stdout.strip())

def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_loop(source, target):
    length = duration(source)
    if length <= CROSSFADE * 3:
        raise RuntimeError(f"{source.name}: recording must exceed {CROSSFADE*3} seconds")
    graph = (
        f"[0:a]atrim=start={CROSSFADE}:end={length-CROSSFADE},asetpts=PTS-STARTPTS[mid];"
        f"[0:a]atrim=start={length-CROSSFADE}:end={length},asetpts=PTS-STARTPTS[tail];"
        f"[0:a]atrim=start=0:end={CROSSFADE},asetpts=PTS-STARTPTS[head];"
        f"[tail][head]acrossfade=d={CROSSFADE}:c1=tri:c2=tri[x];"
        f"[mid][x]concat=n=2:v=0:a=1[out]"
    )
    run(["ffmpeg","-y","-hide_banner","-i",str(source),"-filter_complex",graph,
         "-map","[out]","-ar","48000","-ac","2","-b:a","96k",str(target)])
    if duration(target) < length - (2 * CROSSFADE) - 0.3:
        raise RuntimeError(f"{source.name}: loop preparation shortened unexpectedly")

def main():
    if not MANIFEST.is_file():
        raise SystemExit(f"STOPPED: {MANIFEST} is missing. Audio generation step did not complete.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    schedule_path = Path(os.environ.get("SCHEDULE_FILE", ROOT / "schedule.csv"))
    rows = list(csv.DictReader(schedule_path.open(newline="",encoding="utf-8-sig")))
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
    for row in rows:
        kind = row["soundscape"].strip().lower()
        expected_platforms = {
            "white_noise": "TV OFF / FFmpeg",
            "brown_noise": "TV OFF / FFmpeg",
            "original_music": "TV OFF / local synthesis",
        }
        if kind not in expected_platforms:
            raise RuntimeError(f"Disallowed TV OFF category: {kind!r}")
        item = manifest.get(kind)
        if not item:
            raise RuntimeError(f"No manifest entry for {kind}")
        for field in ("file", "creator", "source_url", "license", "downloaded_at", "sha256"):
            if not item.get(field):
                raise RuntimeError(f"{kind}: missing manifest field {field}")
        if item.get("audio_type") != "synthetic" or item.get("platform") != expected_platforms[kind]:
            raise RuntimeError(f"{kind}: only the approved local synthetic generator is allowed")
        source = (SOURCE_DIR / item["file"]).resolve()
        if not source.is_relative_to(SOURCE_DIR.resolve()) or not source.is_file():
            raise RuntimeError(f"{kind}: source audio is missing or outside the local audio directory")
        actual_sha256 = sha256_file(source)
        if actual_sha256 != item["sha256"]:
            raise RuntimeError(f"{kind}: manifest SHA-256 does not match the generated audio file")
        stem = Path(row["filename"]).stem
        loop = OUTPUT_DIR / f"{stem}_loop.m4a"
        target = OUTPUT_DIR / row["filename"]
        prepare_loop(source,loop)
        run(["ffmpeg","-y","-hide_banner","-f","lavfi","-i","color=c=black:s=1280x720:r=1",
             "-stream_loop","-1","-i",str(loop),"-t",str(int(row.get("duration_seconds") or DURATION)),"-map","0:v:0","-map","1:a:0",
             "-c:v","libx264","-preset","ultrafast","-tune","stillimage","-pix_fmt","yuv420p",
             "-r","1","-c:a","aac","-b:a","96k","-movflags","+faststart",str(target)])
        loop.unlink(missing_ok=True)
        print(f"BUILT {target} from original TV OFF generated audio ({item['license']}) | sha256={actual_sha256}")

if __name__ == "__main__":
    main()
