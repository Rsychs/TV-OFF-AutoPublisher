import json, subprocess, sys
from pathlib import Path

EXPECTED = 10 * 60 * 60

def probe(path):
    p=subprocess.run(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(path)],check=True,capture_output=True,text=True)
    return json.loads(p.stdout)

def validate(path):
    data=probe(path); streams=data.get("streams",[])
    audio=[s for s in streams if s.get("codec_type")=="audio"]
    video=[s for s in streams if s.get("codec_type")=="video"]
    if not audio or not video: raise RuntimeError(f"{path}: missing audio/video stream")
    duration=float(data["format"]["duration"])
    if abs(duration-EXPECTED)>3: raise RuntimeError(f"{path}: expected 10 hours, got {duration:.1f}s")
    if video[0].get("width")!=1280 or video[0].get("height")!=720: raise RuntimeError(f"{path}: expected 1280x720")
    if audio[0].get("channels",0)<1: raise RuntimeError(f"{path}: invalid audio channels")
    check=subprocess.run(["ffmpeg","-v","error","-i",str(path),"-f","null","-"],capture_output=True,text=True)
    if check.returncode: raise RuntimeError(f"{path}: audio/video decode errors: {check.stderr[-1500:]}")
    print(f"VALID: {path.name} | {duration/3600:.3f} hours | {audio[0].get('codec_name')}")

if __name__=="__main__":
    if len(sys.argv)<2: raise SystemExit("Usage: python validate_media.py video.mp4 [...]")
    for item in sys.argv[1:]: validate(Path(item))
