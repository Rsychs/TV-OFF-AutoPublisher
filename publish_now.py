import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

ROOT = Path(__file__).resolve().parent
STATE_FILE = Path(os.environ.get("STATE_FILE", ROOT / "production_state.json"))
VIDEO_KEY = "TV-OFF_Rain_FieldRecording_10-Hours.mp4"
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def main():
    if not STATE_FILE.is_file():
        raise RuntimeError(f"Upload state file not found: {STATE_FILE}")
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    video_id = state.get(VIDEO_KEY)
    if not video_id:
        raise RuntimeError(f"No uploaded video ID recorded for {VIDEO_KEY}")

    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)
    result = youtube.videos().update(
        part="status",
        body={"id": video_id, "status": {"privacyStatus": "public"}},
    ).execute()
    privacy = result.get("status", {}).get("privacyStatus")
    if privacy != "public":
        raise RuntimeError(f"YouTube did not confirm public status: {privacy}")
    print(f"NOW PUBLIC: https://youtu.be/{video_id}")

if __name__ == "__main__":
    main()
