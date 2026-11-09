import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

ROOT = Path(__file__).resolve().parent
STATE_FILE = Path(os.environ.get("STATE_FILE", ROOT / "state.json"))
MEDIA_DIR = Path(os.environ.get("MEDIA_DIR", ROOT / "videos")).resolve()
THUMB_DIR = ROOT / "thumbnails"
SOURCE_AUDIO_DIR = Path(os.environ.get("SOURCE_AUDIO_DIR", ROOT / "audio"))
MANIFEST_FILE = SOURCE_AUDIO_DIR / "manifest.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def load_credentials():
    required = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Missing GitHub Actions secrets: " + ", ".join(missing))
    creds = Credentials(
        token=None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds

def main():
    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    schedule_path = Path(os.environ.get("SCHEDULE_FILE", ROOT / "schedule.csv"))
    with schedule_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError("Schedule contains no upload rows")
    youtube = build("youtube", "v3", credentials=load_credentials())
    now = datetime.now(timezone.utc)
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8")) if MANIFEST_FILE.is_file() else {}

    for row in rows:
        key = row["filename"].strip()
        video_id = state.get(key)
        thumbnail = THUMB_DIR / (Path(key).stem + ".jpg")

        if video_id:
            print(
                f"ALREADY PUBLISHED {key}: https://youtu.be/{video_id}; "
                "skipping without modifying the existing YouTube video."
            )
            continue

        filename = (MEDIA_DIR / key).resolve()
        if not filename.is_relative_to(MEDIA_DIR) or not filename.is_file():
            raise RuntimeError(f"Video file missing or outside media directory: {key}")
        if not thumbnail.is_file():
            raise RuntimeError(f"Missing thumbnail: {thumbnail}")

        publish_at = datetime.fromisoformat(row["publish_at"])
        if publish_at.tzinfo is None:
            raise ValueError(f"{key}: publish_at must include a timezone offset")
        future_publish = publish_at.astimezone(timezone.utc) > now
        source = manifest.get(row.get("soundscape", ""), {})
        description = row.get("description", "")
        for field in ("creator", "source_url", "license"):
            description = description.replace("{" + field + "}", str(source.get(field, "Not provided")))
        body = {
            "snippet": {
                "title": row["title"][:100],
                "description": description,
                "tags": [x.strip() for x in row.get("tags", "").split(";") if x.strip()],
                "categoryId": "10"
            },
            "status": {
                "privacyStatus": "private" if future_publish else "public",
                **({"publishAt": publish_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")} if future_publish else {}),
                "selfDeclaredMadeForKids": False
            }
        }
        media = MediaFileUpload(str(filename), mimetype="video/mp4", chunksize=-1, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = request.next_chunk()
        video_id = response["id"]
        state[key] = video_id
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail), mimetype="image/jpeg")
        ).execute()
        print(f"UPLOADED {key}: https://youtu.be/{video_id} (thumbnail set)")

if __name__ == "__main__":
    main()
