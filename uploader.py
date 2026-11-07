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
STATE_FILE = ROOT / "state.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def load_credentials():
    token_raw = os.environ["YT_TOKEN_JSON"]
    token = json.loads(token_raw)
    creds = Credentials.from_authorized_user_info(token, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds.valid:
        raise RuntimeError("OAuth token is invalid; repeat get_token.py and update YT_TOKEN_JSON.")
    return creds

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}

def main():
    creds = load_credentials()
    youtube = build("youtube", "v3", credentials=creds)
    state = load_state()
    now = datetime.now(timezone.utc)
    with (ROOT / "schedule.csv").open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        filename = (ROOT / row["filename"]).resolve()
        key = row["filename"]
        if key in state:
            print(f"SKIP already uploaded: {key} -> {state[key]}")
            continue
        if not filename.is_file():
            print(f"WAIT missing file: {key}")
            continue
        publish_at = datetime.fromisoformat(row["publish_at"])
        if publish_at.tzinfo is None:
            raise ValueError(f"{key}: publish_at must include a timezone offset")
        future_publish = publish_at.astimezone(timezone.utc) > now

        body = {
            "snippet": {
                "title": row["title"][:100],
                "description": row.get("description", ""),
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
        print(f"UPLOADED {key}: https://youtu.be/{video_id}")

if __name__ == "__main__":
    main()
