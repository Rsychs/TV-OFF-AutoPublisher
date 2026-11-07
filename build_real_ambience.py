import csv, json, os, subprocess
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
    if duration(target) < length - 0.3:
        raise RuntimeError(f"{source.name}: loop preparation shortened unexpectedly")

def main():
    if not MANIFEST.is_file():
        raise SystemExit(f"STOPPED: {MANIFEST} is missing. Audio generation step did not complete.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = list(csv.DictReader((ROOT/"schedule.csv").open(newline="",encoding="utf-8-sig")))
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
    for row in rows:
        item = manifest.get(row["soundscape"])
        if not item:
            raise RuntimeError(f"No manifest entry for {row['soundscape']}")
        for field in ("file","creator","source_url","license","downloaded_at"):
            if not item.get(field):
                raise RuntimeError(f"{row['soundscape']}: missing manifest field {field}")
        source = SOURCE_DIR / item["file"]
        if not source.is_file():
            raise RuntimeError(f"Source audio not found: {source}")
        stem = Path(row["filename"]).stem
        loop = OUTPUT_DIR / f"{stem}_loop.m4a"
        target = OUTPUT_DIR / row["filename"]
        prepare_loop(source,loop)
        run(["ffmpeg","-y","-hide_banner","-f","lavfi","-i","color=c=black:s=1280x720:r=1",
             "-stream_loop","-1","-i",str(loop),"-t",str(DURATION),"-map","0:v:0","-map","1:a:0",
             "-c:v","libx264","-preset","ultrafast","-tune","stillimage","-pix_fmt","yuv420p",
             "-r","1","-c:a","aac","-b:a","96k","-movflags","+faststart",str(target)])
        loop.unlink(missing_ok=True)
        print(f"BUILT {target} from original TV OFF generated audio ({item['license']})")

if __name__ == "__main__":
    main()
