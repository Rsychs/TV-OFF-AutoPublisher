import json, os, re
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from generate_thumbnails import make_thumbnail, OUT

ROOT = Path(__file__).resolve().parent
STATE_FILE = Path(os.environ.get("STATE_FILE", ROOT / "state.json"))

def main():
    required = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]
    missing = [x for x in required if not os.environ.get(x)]
    if missing:
        raise RuntimeError("Missing YouTube credentials: " + ", ".join(missing))
    if not STATE_FILE.is_file():
        raise RuntimeError("state.json missing; refusing an ungrounded thumbnail refresh.")
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise RuntimeError("Invalid state.json; refusing thumbnail refresh.")

    creds = Credentials(
        token=None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)

    entries = []
    for filename, video_id in state.items():
        if filename.startswith("_") or not isinstance(video_id, str):
            continue
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id.strip()):
            continue
        if not filename.lower().endswith(".mp4"):
            continue
        kind = None
        lower = filename.lower()
        if "white" in lower: kind = "white_noise"
        elif "brown" in lower: kind = "brown_noise"
        elif "music" in lower or "ambient" in lower or "lofi" in lower: kind = "original_music"
        if not kind:
            print(f"SKIP unsupported/legacy category: {filename}")
            continue
        entries.append((filename, video_id, kind))

    if not entries:
        raise RuntimeError("No confirmed published long-form videos with supported categories found.")

    success = 0
    for filename, video_id, kind in entries:
        row = {"filename": filename, "soundscape": kind, "title": Path(filename).stem}
        make_thumbnail(row)
        image_path = OUT / (Path(filename).stem + ".jpg")
        if not image_path.is_file():
            raise RuntimeError(f"Generated thumbnail missing: {image_path}")
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(image_path), mimetype="image/jpeg"),
        ).execute()
        success += 1
        print(f"THUMBNAIL UPDATED: {filename} -> https://youtu.be/{video_id}")

    print(f"COMPLETE: updated {success}/{len(entries)} published long-form thumbnails.")

if __name__ == "__main__":
    main()
