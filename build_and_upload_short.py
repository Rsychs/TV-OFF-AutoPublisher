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
    last = state.get("_last_published_at")
    if last:
        elapsed = (now - datetime.fromisoformat(last)).total_seconds()
        if elapsed < 7200:
            print(f"Two-hour cooldown active; next Short in {int(7200 - elapsed)} seconds.")
            return

    # Shorts stay gated until the main 10-hour video has actually been uploaded.
    main_state = json.loads((ROOT / "state.json").read_text(encoding="utf-8"))
    long_video = next((v for k, v in main_state.items()
                       if k.startswith("TV-OFF_Thunderstorm_") and "_10-Hours.mp4" in k), None)
    if not long_video:
        raise RuntimeError("The current 10-hour thunderstorm video is not recorded as uploaded; Shorts are gated.")

    manifest_path = AUDIO_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    kind = next(iter(manifest))
    info = manifest[kind]
    source = AUDIO_DIR / info["file"]
    if not source.is_file():
        raise RuntimeError(f"Thunderstorm audio is missing: {source}")

    OUT.mkdir(exist_ok=True)
    filename = f"TV-OFF_{kind.title()}_Short_{slot}.mp4"
    target = OUT / filename
    # A minimal vertical TV OFF visual: black canvas, restrained blue-grey animated waveform.
    graph = (
        "[1:a]showwaves=s=820x180:mode=line:rate=30:colors=0x7C859E,format=rgba[w];"
        "[0:v][w]overlay=(W-w)/2:820:shortest=1,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='TV OFF':fontcolor=white:fontsize=76:x=(w-text_w)/2:y=590,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        "text='NATURE SOUNDS  /  TV OFF':fontcolor=0xAAB2C4:fontsize=30:"
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
    info = manifest["thunderstorm"]
    description = (
        f"27 seconds of {kind} ambience from a verified CC0 field recording. "
        "TV OFF — sound to switch off to.\n\n"
        f"Original recording: {info.get('creator', 'Not credited')}\n"
        f"Source: {info.get('source_url', '')}\n"
        f"License: {info.get('license', 'CC0')}\n\n"
        "#Shorts #Thunderstorm #RainSounds #TVOff #AmbientSounds"
    )
    body = {
        "snippet": {
            "title": f"{kind.title()} Nature Sounds | TV OFF #Shorts",
            "description": description,
            "tags": ["Shorts", kind.title(), "Nature Sounds", "TV OFF", "Ambient Sounds"],
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
    print(f"SHORT PUBLISHED: https://youtu.be/{video_id} | slot={slot}")

if __name__ == "__main__":
    main()
