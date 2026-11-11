#!/usr/bin/env python3
"""Upload a rendered TV OFF Short only after cooldown and content dedupe checks."""
import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT=Path(__file__).resolve().parents[2]
VIDEO=ROOT/"output"/"TV_OFF_Midnight_Blue.mp4"
MANIFEST=ROOT/"output"/"production.json"
STATE=ROOT/"cloud_studio_state.json"
SHORTS_STATE=ROOT/"shorts_state.json"

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def main():
    if not VIDEO.is_file() or not MANIFEST.is_file(): raise SystemExit("Rendered MP4 or manifest missing")
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("duration_seconds") not in (20,30,40,50,60): raise SystemExit("Invalid duration")
    digest=sha256(VIDEO)
    state=json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"published_hashes":[],"uploads":[]}
    if digest in state.get("published_hashes",[]): raise SystemExit("Duplicate Cloud Studio video hash; refusing upload")
    short_state=json.loads(SHORTS_STATE.read_text(encoding="utf-8")) if SHORTS_STATE.exists() else {}
    last=short_state.get("_last_published_at")
    if last:
        stamp=datetime.fromisoformat(str(last).replace("Z","+00:00"))
        if stamp.tzinfo is None: stamp=stamp.replace(tzinfo=timezone.utc)
        elapsed=(datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()
        if elapsed<2400: raise SystemExit(f"Shared Shorts cooldown active ({int(2400-elapsed)} seconds remain); refusing to bypass it")
    required=["YT_CLIENT_ID","YT_CLIENT_SECRET","YT_REFRESH_TOKEN"]
    missing=[k for k in required if not os.environ.get(k)]
    if missing: raise SystemExit("Missing YouTube OAuth secrets: "+", ".join(missing))
    creds=Credentials(token=None,refresh_token=os.environ["YT_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["YT_CLIENT_ID"],client_secret=os.environ["YT_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/youtube.upload"])
    creds.refresh(Request())
    youtube=build("youtube","v3",credentials=creds)
    title=str(manifest.get("title","Midnight Blue"))[:95]
    description=("Original ambient music created for TV OFF, paired with continuous licensed stock footage. "
                 "A quiet visual and sound break. More original sounds on TV OFF.\n\n"
                 "#Shorts #AmbientMusic #Relaxation #TVOFF")
    body={"snippet":{"title":title+" #Shorts","description":description,"tags":["TV OFF","ambient music","relaxation","shorts","original music"],"categoryId":"10"},"status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}}
    media=MediaFileUpload(str(VIDEO),mimetype="video/mp4",chunksize=8*1024*1024,resumable=True)
    request=youtube.videos().insert(part="snippet,status",body=body,media_body=media)
    response=None
    while response is None:
        _,response=request.next_chunk()
    video_id=response.get("id")
    if not video_id: raise SystemExit("YouTube upload returned no video ID; publication is not confirmed")
    published_at=datetime.now(timezone.utc).isoformat()
    state.setdefault("published_hashes",[]).append(digest)
    state.setdefault("uploads",[]).append({"video_id":video_id,"title":title,"sha256":digest,"published_at":published_at,"source_page":manifest.get("visual_source_page")})
    state["published_hashes"]=state["published_hashes"][-500:]
    state["uploads"]=state["uploads"][-500:]
    STATE.write_text(json.dumps(state,indent=2),encoding="utf-8")
    print(f"YOUTUBE_UPLOAD_CONFIRMED video_id={video_id} url=https://www.youtube.com/shorts/{video_id}")

if __name__=="__main__": main()
