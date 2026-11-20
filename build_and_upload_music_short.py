import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent
AUDIO_DIR = Path(os.environ.get("SOURCE_AUDIO_DIR", ROOT / "artifacts"))
OUT = ROOT / "music-shorts"
STATE = ROOT / "music_shorts_state.json"
DURATION = 30
COOLDOWN_SECONDS = 3600

def run(args):
    subprocess.run(args, check=True, timeout=1800)

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    manifests = list(AUDIO_DIR.rglob("ace_step_smoke_result.json"))
    if len(manifests) != 1:
        raise RuntimeError(f"Expected exactly one ACE-Step manifest, found {len(manifests)}")
    manifest_path = manifests[0]
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    if m.get("status") != "ok" or m.get("publishing_enabled") is not False:
        raise RuntimeError("ACE-Step manifest is not a verified non-publishing generation result")
    if not m.get("title") or not m.get("style") or not m.get("prompt"):
        raise RuntimeError("ACE-Step manifest is missing title/style/prompt")
    audio = (manifest_path.parent / m["audio_file"]).resolve()
    if not audio.is_relative_to(AUDIO_DIR.resolve()) or not audio.is_file():
        raise RuntimeError("Manifest audio file is missing or outside the downloaded artifact")
    audio_hash = sha256(audio)
    if audio_hash != m.get("sha256"):
        raise RuntimeError("Audio SHA-256 does not match ACE-Step manifest")
    duration = float(m.get("duration_seconds", 0))
    if duration < DURATION:
        raise RuntimeError(f"Track is too short for a {DURATION}-second Short: {duration:.1f}s")

    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    if not isinstance(state, dict):
        raise RuntimeError("music_shorts_state.json is invalid")
    if audio_hash in state.get("_published_audio_sha256", []):
        print(f"TRACK ALREADY PUBLISHED AS SHORT: {audio_hash}")
        return
    started = time.time()
    last = state.get("_last_published_at")
    if last:
        last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        wait = COOLDOWN_SECONDS - (datetime.now(timezone.utc) - last_dt.astimezone(timezone.utc)).total_seconds()
        if wait > 0:
            print(f"60-minute shared music Shorts cooldown active; waiting {int(wait)} seconds")
            time.sleep(wait)

    # Deterministic source segment, with a gentle in/out fade. Every Short uses this exact track.
    clip_start = max(0.0, min(duration - DURATION, duration * 0.18))
    OUT.mkdir(exist_ok=True)
    slot = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    scene = OUT / f"scene_{slot}.png"
    video = OUT / f"TV-OFF_Original-Music_Short_{slot}.mp4"
    title = re.sub(r"\s+", " ", str(m["title"])).strip()
    safe_title = title.replace("'", "").replace(":", " —")
    subprocess.run([
        os.sys.executable, str(ROOT / "scripts" / "render_tv_off_short_scene.py"),
        "--out", str(scene), "--kind", "original_music", "--slot", slot[:10], "--style", str(m["style"])
    ], check=True, timeout=1800)
    if not scene.is_file() or scene.stat().st_size < 100000:
        raise RuntimeError("Music-specific 3D scene render failed")

    # Fixed still background = locked camera. Only waveform and typography animate.
    graph = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,"
        "eq=contrast=1.04:saturation=1.08,format=yuv420p[bg];"
        "[1:a]showwaves=s=920x150:mode=cline:scale=sqrt:rate=30:colors=0xC5A6FF,"
        "format=rgba,colorchannelmixer=aa=0.82[w];"
        "[bg][w]overlay=(W-w)/2:1430:shortest=1,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='ORIGINAL MUSIC':fontcolor=white:fontsize=54:x=(w-text_w)/2:y=250:"
        "shadowcolor=black@0.55:shadowx=2:shadowy=3,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"text='{safe_title[:52]}':fontcolor=0xE7DFFF:fontsize=32:x=(w-text_w)/2:y=340:"
        "shadowcolor=black@0.55:shadowx=2:shadowy=3,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='TV OFF':fontcolor=white:fontsize=42:x=(w-text_w)/2:y=1660,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        "text='FULL TRACK ON OUR CHANNEL':fontcolor=white:fontsize=27:"
        "x=(w-text_w)/2:y=1775:alpha='if(lt(t,22),0,min(1,(t-22)))':enable='gte(t,22)'[v]"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-loop", "1", "-framerate", "30", "-i", str(scene),
        "-ss", f"{clip_start:.3f}", "-i", str(audio), "-filter_complex", graph,
        "-map", "[v]", "-map", "1:a:0", "-t", str(DURATION),
        "-af", "afade=t=in:st=0:d=0.35,afade=t=out:st=28.8:d=1.2,loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
        "-r", "30", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(video)
    ])
    if not video.is_file() or video.stat().st_size < 100000:
        raise RuntimeError("Rendered music Short is missing or unexpectedly small")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
                           capture_output=True, text=True, check=True)
    if abs(float(probe.stdout.strip()) - DURATION) > 0.15:
        raise RuntimeError(f"Rendered Short duration is not {DURATION} seconds")
    video_hash = sha256(video)
    if video_hash in state.get("_published_video_sha256", []):
        raise RuntimeError("Duplicate rendered video detected; refusing upload")

    required = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError("Missing YouTube upload secrets: " + ", ".join(missing))
    creds = Credentials(
        token=None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)
    short_title = f"{title[:75]} | Original Music #Shorts"
    description = (
        f"A 30-second excerpt from {title}, an original {m['style']} composition created for TV OFF.\n\n"
        "Listen to the full original track on the TV OFF channel.\n\n"
        "#Shorts #OriginalMusic #InstrumentalMusic #TVOFF"
    )
    response = youtube.videos().insert(
        part="snippet,status",
        body={"snippet": {"title": short_title[:100], "description": description,
                          "tags": ["Shorts", "Original Music", "Instrumental", str(m["style"]), "TV OFF"],
                          "categoryId": "10"},
              "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}},
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", chunksize=-1, resumable=True)
    ).execute()
    video_id = response["id"]
    published = datetime.now(timezone.utc).isoformat()
    state.setdefault("_published_audio_sha256", []).append(audio_hash)
    state["_published_audio_sha256"] = state["_published_audio_sha256"][-500:]
    state.setdefault("_published_video_sha256", []).append(video_hash)
    state["_published_video_sha256"] = state["_published_video_sha256"][-500:]
    state.setdefault("published_tracks", []).append({
        "video_id": video_id, "youtube_url": f"https://youtu.be/{video_id}",
        "track_title": title, "style": m["style"], "audio_sha256": audio_hash,
        "video_sha256": video_hash, "published_at": published,
        "clip_start_seconds": clip_start, "duration_seconds": DURATION
    })
    state["published_tracks"] = state["published_tracks"][-500:]
    state["_last_published_at"] = published
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"MUSIC SHORT PUBLISHED: https://youtu.be/{video_id} | track={title} | duration={DURATION}s")

if __name__ == "__main__":
    main()
