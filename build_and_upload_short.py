import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "shorts_state.json"
AUDIO_DIR = Path(os.environ.get("SOURCE_AUDIO_DIR", ROOT / "generated-audio"))
OUT = ROOT / "shorts"
DURATION = 27

def run(args):
    subprocess.run(args, check=True, timeout=900)

def main():
    now = datetime.now(timezone.utc)
    slot = now.strftime("%Y%m%d%H")
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    if slot in state:
        print(f"SHORT ALREADY PUBLISHED FOR SLOT {slot}: {state[slot]}")
        return
    last_published_at = state.get("_last_published_at")
    if last_published_at:
        try:
            last_at = datetime.fromisoformat(str(last_published_at).replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeError("Invalid _last_published_at in shorts_state.json; refusing to bypass cooldown.") from exc
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
        elapsed = (now - last_at.astimezone(timezone.utc)).total_seconds()
        if elapsed < 3600:
            remaining = int(3600 - elapsed + 0.999)
            print(f"SHORT COOLDOWN ACTIVE: {remaining}s remaining since {last_at.isoformat()}")
            return
    # Shorts stay gated until at least one 10-hour soundscape video is recorded as uploaded.
    main_state = json.loads((ROOT / "state.json").read_text(encoding="utf-8"))
    long_video = next((
        value for key, value in main_state.items()
        if isinstance(key, str) and key.startswith("TV-OFF_") and "_10-Hours.mp4" in key
    ), None)
    if not long_video:
        raise RuntimeError("No 10-hour soundscape video is recorded as uploaded; Shorts are gated.")

    manifest_path = AUDIO_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    kind = next(iter(manifest))
    info = manifest[kind]
    display_kind = kind.replace("_", " ").title()
    file_kind = kind.replace("_", "").title()
    synthetic = info.get("audio_type") == "synthetic"
    visual_label = f"{display_kind.upper()}  /  TV OFF" if synthetic else "NATURE SOUNDS  /  TV OFF"
    source = AUDIO_DIR / info["file"]
    if not source.is_file():
        raise RuntimeError(f"Selected {kind} audio is missing: {source}")

    OUT.mkdir(exist_ok=True)
    filename = f"TV-OFF_{file_kind}_Short_{slot}.mp4"
    target = OUT / filename
    # A minimal vertical TV OFF visual: black canvas, restrained blue-grey animated waveform.
    graph = (
        "[1:a]showwaves=s=820x180:mode=line:rate=30:colors=0x7C859E,format=rgba[w];"
        "[0:v][w]overlay=(W-w)/2:820:shortest=1,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='TV OFF':fontcolor=white:fontsize=76:x=(w-text_w)/2:y=590,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"text='{visual_label}':fontcolor=0xAAB2C4:fontsize=30:"
        "x=(w-text_w)/2:y=1110[v]"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-f", "lavfi", "-i",
        f"color=c=black:s=1080x1920:r=30:d={DURATION}",
        "-stream_loop", "-1", "-i", str(source),
        "-filter_complex", graph, "-map", "[v]", "-map", "1:a:0",
        "-t", str(DURATION), "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k",
        "-af", "loudnorm=I=-18:TP=-2:LRA=11", "-movflags", "+faststart",
        str(target)
    ])
    if not target.is_file() or target.stat().st_size < 100000:
        raise RuntimeError("Short video output is missing or unexpectedly small.")

    required = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]
    missing = [x for x in required if not os.environ.get(x)]
    if missing:
        raise RuntimeError("Missing YouTube secrets: " + ", ".join(missing))
    creds = Credentials(
        token=None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)
    if synthetic:
        description = (
            f"Short {display_kind.lower()} sound for sleep, focus and relaxation, created by TV OFF. "
            "Created locally with FFmpeg; no third-party recording or sample is used. "
            "TV OFF — sound to switch off to.\n\n"
            f"Audio type: original synthetic audio\n"
            f"Production: {info.get('creator', 'TV OFF')}\n"
            f"{info.get('license', 'Original synthetic audio; no third-party sample used.')}\n\n"
            f"#Shorts #{kind.replace('_', '')} #SleepSounds #FocusSounds #TVOff #AmbientSounds"
        )
        short_use = "Sleep & Relaxation" if kind == "brown_noise" else "Sleep & Focus"
        short_title = f"{display_kind} for {short_use} | {now.strftime('%b %d, %H:%M')} #Shorts"
        short_tags = ["Shorts", display_kind, "Sleep Sounds", "Focus Sounds", "TV OFF", "Ambient Sounds"]
    else:
        description = (
            f"{display_kind} nature sounds for relaxation, focus and quiet moments, from a verified CC0 field recording. "
            "TV OFF — sound to switch off to.\n\n"
            f"Original recording: {info.get('creator', 'Not credited')}\n"
            f"Source: {info.get('source_url', '')}\n"
            f"License: {info.get('license', 'CC0')}\n\n"
            f"#Shorts #{kind.title().replace(' ', '')} #NatureSounds #TVOff #AmbientSounds"
        )
        short_title = f"{display_kind} Nature Sounds | TV OFF #Shorts"
        short_tags = ["Shorts", display_kind, "Nature Sounds", "TV OFF", "Ambient Sounds"]
    body = {
        "snippet": {
            "title": short_title,
            "description": description,
            "tags": short_tags,
            "categoryId": "10"
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    response = youtube.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(target), mimetype="video/mp4", chunksize=-1, resumable=True)
    ).execute()
    video_id = response["id"]
    state[slot] = video_id
    state["_last_published_at"] = now.isoformat()
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    if info.get("platform") == "Freesound" and info.get("source_url"):
        history_path = ROOT / "shorts_used_sources.json"
        history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else {"used": []}
        used = history.setdefault("used", [])
        if info["source_url"] not in used:
            used.append(info["source_url"])
            history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"SHORT PUBLISHED: https://youtu.be/{video_id} | slot={slot} | soundscape={kind}")

if __name__ == "__main__":
    main()
