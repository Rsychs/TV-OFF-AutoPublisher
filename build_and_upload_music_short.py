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
AUDIO_DIR = Path(os.environ.get("SOURCE_AUDIO_DIR", ROOT / "colab-output"))
OUT = ROOT / "music-shorts"
STATE = ROOT / "music_shorts_state.json"
DURATION = 30
COOLDOWN_SECONDS = 3600
PUBLISH_MODE = os.environ.get("PUBLISH_MODE", "publish").strip().lower()
if PUBLISH_MODE not in {"dry_run", "publish"}:
    raise RuntimeError("PUBLISH_MODE must be dry_run or publish")

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
    if m.get("status") != "ok" or m.get("publishing_enabled") is not True:
        raise RuntimeError("ACE-Step manifest is not an explicitly approved production generation result")
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
    published_audio = state.get("_published_audio_sha256", [])
    if not isinstance(published_audio, list):
        raise RuntimeError("music_shorts_state.json has an invalid audio deduplication list")
    tracks = state.get("published_tracks", [])
    if not isinstance(tracks, list):
        raise RuntimeError("music_shorts_state.json has an invalid published_tracks list")
    existing_track = next(
        (item for item in reversed(tracks)
         if isinstance(item, dict) and item.get("audio_sha256") == audio_hash),
        None,
    )
    # If the Short succeeded but its companion full upload failed, resume only the
    # missing full upload. Never upload the Short a second time.
    resume_full_only = (
        PUBLISH_MODE == "publish"
        and audio_hash in published_audio
        and existing_track is not None
        and bool(existing_track.get("short_video_id"))
        and existing_track.get("full_upload_status") != "published"
    )
    if audio_hash in published_audio and not resume_full_only:
        print(f"TRACK ALREADY PUBLISHED; refusing duplicate Short: {audio_hash}")
        return
    if resume_full_only:
        print(f"SHORT ALREADY PUBLISHED; resuming missing full-track upload: {existing_track['short_video_id']}")
    # Cooldown applies to a new Short, not to completion of an already-published pair.
    # Dry-runs never wait or mutate state.
    if PUBLISH_MODE == "publish" and not resume_full_only:
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
    full_video = OUT / f"TV-OFF_Original-Music_Full_{slot}.mp4"
    title = re.sub(r"\s+", " ", str(m["title"])).strip()
    if re.search(r"\d", title):
        raise RuntimeError("Public YouTube title must not contain digits; refusing upload.")
    safe_title = title.replace("\\", "").replace("'", "").replace(":", " —").replace("%", " ").replace(",", " ").replace("[", "(").replace("]", ")")
    # Newly generated tracks must carry the exact visual rendered in the same ACE-Step run.
    bundled_visual = m.get("visual_file")
    if not bundled_visual:
        raise RuntimeError("Verified track has no bundled genre-matched visual; refusing to generate a replacement later")
    scene = (manifest_path.parent / bundled_visual).resolve()
    if not scene.is_relative_to(AUDIO_DIR.resolve()) or not scene.is_file():
        raise RuntimeError("Bundled visual is missing or outside the downloaded track artifact")
    if m.get("visual_style") != m.get("style") or m.get("visual_seed") != m.get("seed"):
        raise RuntimeError("Bundled visual metadata does not match this exact music track")
    print(f"Using music-generation visual: {scene.name} | style={m['visual_style']}")
    # Full-length upload uses a separately generated native 16:9 image.
    bundled_landscape = m.get("landscape_file")
    if not bundled_landscape:
        raise RuntimeError("Missing separately generated landscape artwork for full-track upload")
    full_scene = (manifest_path.parent / bundled_landscape).resolve()
    if not full_scene.is_relative_to(AUDIO_DIR.resolve()) or not full_scene.is_file():
        raise RuntimeError("Landscape artwork is missing or outside the downloaded track artifact")
    if full_scene.stat().st_size < 100000:
        raise RuntimeError("Landscape artwork is unexpectedly small")
    full_visual_hash = sha256(full_scene)
    if full_visual_hash != m.get("landscape_sha256"):
        raise RuntimeError("Landscape artwork SHA-256 does not match generation manifest")
    if (m.get("landscape_width"), m.get("landscape_height")) != (1920, 1080):
        raise RuntimeError("Full-track artwork must be 1920x1080 landscape")
    if not scene.is_file() or scene.stat().st_size < 100000:
        raise RuntimeError("Music-specific visual asset is missing or too small")
    visual_hash = sha256(scene)
    if m.get("visual_sha256") and visual_hash != m.get("visual_sha256"):
        raise RuntimeError("Visual SHA-256 does not match unified-generation manifest")
    if m.get("visual_width") not in (None, 1080) or m.get("visual_height") not in (None, 1920):
        raise RuntimeError("Visual dimensions are not the required 1080x1920 vertical format")

    # Pure visual Short: one still image + original music. No text, logo, waveform,
    # progress bar, overlays, or camera movement.
    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1,eq=contrast=1.04:saturation=1.08,format=yuv420p"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-loop", "1", "-framerate", "30", "-i", str(scene),
        "-ss", f"{clip_start:.3f}", "-i", str(audio), "-vf", video_filter,
        "-map", "0:v:0", "-map", "1:a:0", "-t", str(DURATION),
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
    # Full-track companion: landscape 16:9, same artwork, static frame, complete original audio.
    full_filter = (
        "scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,setsar=1,format=yuv420p"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-loop", "1", "-framerate", "1", "-i", str(full_scene),
        "-i", str(audio), "-vf", full_filter,
        "-map", "0:v:0", "-map", "1:a:0", "-t", f"{duration:.3f}",
        "-af", "afade=t=in:st=0:d=0.5,afade=t=out:st=" + f"{max(0.5, duration-2):.3f}" + ":d=2,loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-r", "1", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(full_video)
    ])
    if not full_video.is_file() or full_video.stat().st_size < 100000:
        raise RuntimeError("Rendered full-track video is missing or unexpectedly small")
    full_probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "default=noprint_wrappers=1:nokey=1", str(full_video)],
                                capture_output=True, text=True, check=True)
    if abs(float(full_probe.stdout.strip()) - duration) > 0.5:
        raise RuntimeError("Full-track video duration does not match source audio")
    full_video_hash = sha256(full_video)

    video_hash = sha256(video)
    if video_hash in state.get("_published_video_sha256", []) and not resume_full_only:
        raise RuntimeError("Duplicate rendered video detected; refusing upload")
    if full_video_hash in state.get("_published_full_video_sha256", []) and not resume_full_only:
        raise RuntimeError("Duplicate full-track video detected; refusing upload")

    # Dry-run remains available only when explicitly requested; production is the default.
    if PUBLISH_MODE == "dry_run":
        report = {
            "status": "dry_run_passed", "published": False, "title": title,
            "audio_sha256": audio_hash, "visual_sha256": visual_hash,
            "video_sha256": video_hash, "video_file": str(video),
            "full_video_sha256": full_video_hash, "full_video_file": str(full_video),
            "duration_seconds": DURATION, "visual_model": m.get("visual_model"),
            "visual_generation_seed": m.get("visual_generation_seed"),
            "pipeline_version": m.get("pipeline_version")
        }
        (OUT / "dry_run_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("DRY RUN PASSED — no YouTube API call, no public upload, no state mutation.")
        print(json.dumps(report, indent=2))
        return

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
    follow_description = (
        "Follow TV OFF for more original music and new instrumental soundscapes.\\n\\n"
        f"Original composition: {title}\\n"
        f"Style: {m['style']}\\n\\n"
        "New music. New atmospheres. Stay tuned.\\n\\n"
        "#Shorts #OriginalMusic #InstrumentalMusic #TVOFF"
    )
    full_title = f"{title[:85]} | Full Original Music"
    full_description = (
        "Listen to the complete original composition.\\n\\n"
        "Follow TV OFF for more original music and new instrumental soundscapes.\\n\\n"
        f"Composition: {title}\\n"
        f"Style: {m['style']}\\n"
        f"Duration: {int(duration // 60)}:{int(duration % 60):02d}\\n\\n"
        "#OriginalMusic #InstrumentalMusic #TVOFF"
    )
    if resume_full_only:
        short_id = str(existing_track["short_video_id"])
        short_url = str(existing_track.get("short_url") or f"https://youtu.be/{short_id}")
        # A previous attempt may have received a full-video ID but failed before
        # persisting the final state. Verify that ID before attempting another insert.
        existing_full_id = existing_track.get("full_video_id")
        if existing_full_id:
            check = youtube.videos().list(part="id,status", id=str(existing_full_id)).execute()
            if check.get("items"):
                existing_track["full_upload_status"] = "published"
                existing_track.setdefault("full_url", f"https://youtu.be/{existing_full_id}")
                existing_track.setdefault("full_published_at", datetime.now(timezone.utc).isoformat())
                state.setdefault("_published_full_video_sha256", []).append(full_video_hash)
                state["_published_full_video_sha256"] = list(dict.fromkeys(state["_published_full_video_sha256"]))[-500:]
                STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
                print(f"FULL TRACK ALREADY EXISTS: https://youtu.be/{existing_full_id}")
                print(f"PAIR PUBLISHED: Short={short_url} | Full=https://youtu.be/{existing_full_id}")
                return
            existing_track.pop("full_video_id", None)
            existing_track.pop("full_url", None)
            existing_track["full_upload_status"] = "pending"
    else:
        short_response = youtube.videos().insert(
            part="snippet,status",
            body={"snippet": {"title": short_title[:100], "description": follow_description,
                              "tags": ["Shorts", "Original Music", "Instrumental", str(m["style"]), "TV OFF"],
                              "categoryId": "10"},
                  "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}},
            media_body=MediaFileUpload(str(video), mimetype="video/mp4", chunksize=-1, resumable=True)
        ).execute()
        short_id = short_response["id"]
        short_url = f"https://youtu.be/{short_id}"
        print(f"MUSIC SHORT PUBLISHED: {short_url} | duration=30s")

        # Persist the Short ID before attempting the companion full-track upload.
        published = datetime.now(timezone.utc).isoformat()
        state.setdefault("_published_audio_sha256", []).append(audio_hash)
        state["_published_audio_sha256"] = list(dict.fromkeys(state["_published_audio_sha256"]))[-500:]
        state.setdefault("_published_video_sha256", []).append(video_hash)
        state["_published_video_sha256"] = list(dict.fromkeys(state["_published_video_sha256"]))[-500:]
        state.setdefault("published_tracks", []).append({
            "short_video_id": short_id, "short_url": short_url,
            "track_title": title, "style": m["style"], "audio_sha256": audio_hash,
            "short_video_sha256": video_hash, "full_video_sha256": full_video_hash,
            "visual_sha256": visual_hash, "duration_seconds": duration,
            "short_published_at": published, "full_upload_status": "pending"
        })
        state["published_tracks"] = state["published_tracks"][-500:]
        state["_last_published_at"] = published
        STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    full_response = youtube.videos().insert(
        part="snippet,status",
        body={"snippet": {"title": full_title[:100], "description": full_description,
                          "tags": ["Original Music", "Full Track", "Instrumental", str(m["style"]), "TV OFF"],
                          "categoryId": "10"},
              "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}},
        media_body=MediaFileUpload(str(full_video), mimetype="video/mp4", chunksize=-1, resumable=True)
    ).execute()
    full_id = full_response["id"]
    full_url = f"https://youtu.be/{full_id}"
    if resume_full_only:
        existing_track.update({
            "full_video_id": full_id, "full_url": full_url,
            "full_video_sha256": full_video_hash,
            "full_published_at": datetime.now(timezone.utc).isoformat(),
            "full_upload_status": "published"
        })
    else:
        state["published_tracks"][-1].update({
            "full_video_id": full_id, "full_url": full_url,
            "full_video_sha256": full_video_hash,
            "full_published_at": datetime.now(timezone.utc).isoformat(),
            "full_upload_status": "published"
        })
    state.setdefault("_published_full_video_sha256", []).append(full_video_hash)
    state["_published_full_video_sha256"] = list(dict.fromkeys(state["_published_full_video_sha256"]))[-500:]
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"FULL ORIGINAL AUDIO PUBLISHED: {full_url} | duration={duration:.1f}s")
    print(f"PAIR PUBLISHED: Short={short_url} | Full={full_url}")

if __name__ == "__main__":
    main()
