import csv
import hashlib
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
ALLOWED_PLATFORMS = {
    "white_noise": "TV OFF / FFmpeg",
    "brown_noise": "TV OFF / FFmpeg",
    "original_music": "TV OFF / local synthesis",
}

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

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
    shorts_state_path = ROOT / "shorts_state.json"
    shorts_state = json.loads(shorts_state_path.read_text(encoding="utf-8")) if shorts_state_path.exists() else {}
    if not isinstance(state, dict) or not isinstance(shorts_state, dict):
        raise RuntimeError("Invalid publication state; refusing to bypass cross-format deduplication.")
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
        duplicate_record = next(
            (
                entry for entry in state.get("_duplicate_publications", [])
                if isinstance(entry, dict) and entry.get("filename") == key
            ),
            None,
        )
        if duplicate_record and not video_id:
            duplicate_id = duplicate_record.get("video_id", "unknown")
            raise RuntimeError(
                f"REFUSING TO REPUBLISH {key}: a prior duplicate upload is already recorded "
                f"(https://youtu.be/{duplicate_id}); reconcile state before retrying."
            )

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
        requested_privacy = row.get("privacy_status", "").strip().lower()
        privacy_status = requested_privacy or ("private" if future_publish else "public")
        if privacy_status not in {"private", "public", "unlisted"}:
            raise ValueError(f"{key}: unsupported privacy_status {privacy_status!r}")
        if future_publish and privacy_status != "private":
            raise ValueError(f"{key}: publish_at in the future is only valid with private visibility")
        soundscape = row.get("soundscape", "").strip().lower()
        if soundscape not in ALLOWED_PLATFORMS:
            raise RuntimeError(f"Disallowed TV OFF category: {soundscape!r}")
        source = manifest.get(soundscape, {})
        if source.get("audio_type") != "synthetic" or source.get("platform") != ALLOWED_PLATFORMS[soundscape]:
            raise RuntimeError(f"{soundscape}: only the approved local synthetic generator is allowed.")
        for field in ("file", "sha256"):
            if not source.get(field):
                raise RuntimeError(f"{soundscape}: manifest is missing {field}.")
        source_audio = (SOURCE_AUDIO_DIR / source["file"]).resolve()
        if not source_audio.is_relative_to(SOURCE_AUDIO_DIR.resolve()) or not source_audio.is_file():
            raise RuntimeError(f"{soundscape}: generated audio is missing or outside the local audio directory.")
        audio_sha256 = sha256_file(source_audio)
        if audio_sha256 != source["sha256"]:
            raise RuntimeError(f"{soundscape}: manifest SHA-256 does not match the generated audio.")
        video_sha256 = sha256_file(filename)
        used_audio_hashes = set(state.get("_published_audio_sha256", [])) | set(shorts_state.get("_published_audio_sha256", []))
        used_video_hashes = set(state.get("_published_video_sha256", [])) | set(shorts_state.get("_published_video_sha256", []))
        if audio_sha256 in used_audio_hashes:
            raise RuntimeError(f"Cross-format duplicate audio detected (sha256={audio_sha256}); refusing upload.")
        if video_sha256 in used_video_hashes:
            raise RuntimeError(f"Cross-format duplicate video detected (sha256={video_sha256}); refusing upload.")
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
                "privacyStatus": privacy_status,
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
        state["_published_audio_sha256"] = list(dict.fromkeys(
            state.get("_published_audio_sha256", []) + [audio_sha256]
        ))[-500:]
        state["_published_video_sha256"] = list(dict.fromkeys(
            state.get("_published_video_sha256", []) + [video_sha256]
        ))[-500:]
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail), mimetype="image/jpeg")
        ).execute()
        print(f"UPLOADED {key}: https://youtu.be/{video_id} (thumbnail set)")

if __name__ == "__main__":
    main()
