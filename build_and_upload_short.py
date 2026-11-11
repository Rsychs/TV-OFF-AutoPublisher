import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "shorts_state.json"
AUDIO_DIR = Path(os.environ.get("SOURCE_AUDIO_DIR", ROOT / "generated-audio"))
OUT = ROOT / "shorts"
DURATION = 18

def run(args):
    subprocess.run(args, check=True, timeout=900)

def main():
    now = datetime.now(timezone.utc)
    target_slot = os.environ.get("TARGET_SLOT", "").strip()
    if len(target_slot) != 10 or not target_slot.isdigit():
        raise RuntimeError("TARGET_SLOT is missing or invalid; refusing to publish without a pinned UTC slot.")
    current_slot = now.strftime("%Y%m%d%H")
    if current_slot != target_slot:
        raise RuntimeError(
            f"UTC slot changed before Short build: target={target_slot}, current={current_slot}; refusing rollover."
        )
    slot = target_slot
    slot_start = datetime.strptime(slot, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    slot_end = slot_start + timedelta(hours=1)
    try:
        production_started_epoch = int(os.environ.get("PRODUCTION_STARTED_EPOCH", "0"))
    except ValueError as exc:
        raise RuntimeError("Invalid PRODUCTION_STARTED_EPOCH; refusing to publish.") from exc
    if production_started_epoch <= 0:
        raise RuntimeError("PRODUCTION_STARTED_EPOCH is missing; refusing to publish without runtime tracking.")
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
        if elapsed < 2400:
            remaining = int(2400 - elapsed + 0.999)
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
    if len(manifest) != 1:
        raise RuntimeError("Expected exactly one selected sound in the manifest; refusing ambiguous Short metadata.")
    kind = next(iter(manifest))
    if kind not in {"white_noise", "brown_noise", "original_music"}:
        raise RuntimeError(f"Disallowed TV OFF category for Shorts: {kind}; nature and field recordings are retired.")
    info = manifest[kind]
    display_kind = kind.replace("_", " ").title()
    file_kind = kind.replace("_", "").title()
    expected_platforms = {
        "white_noise": "TV OFF / FFmpeg",
        "brown_noise": "TV OFF / FFmpeg",
        "original_music": "TV OFF / local synthesis",
    }
    if info.get("audio_type") != "synthetic" or info.get("platform") != expected_platforms[kind]:
        raise RuntimeError(f"{kind}: only the approved local synthetic generator is allowed.")
    source = (AUDIO_DIR / info["file"]).resolve()
    if not source.is_relative_to(AUDIO_DIR.resolve()) or not source.is_file():
        raise RuntimeError(f"Selected {kind} audio is missing or outside the local audio directory.")

    # Require a standalone sha256sum-compatible sidecar generated alongside this exact audio.
    sidecar_path = AUDIO_DIR / "manifest.sha256"
    if not sidecar_path.is_file():
        raise RuntimeError("Required generated-audio/manifest.sha256 is missing; refusing to build or upload.")
    sidecar_lines = sidecar_path.read_text(encoding="utf-8").splitlines()
    if len(sidecar_lines) != 1:
        raise RuntimeError("manifest.sha256 must contain exactly one checksum entry.")
    sidecar_parts = sidecar_lines[0].strip().split()
    if len(sidecar_parts) != 2 or sidecar_parts[1].lstrip("*") != source.name:
        raise RuntimeError("manifest.sha256 must contain the checksum and exact selected audio filename.")
    sidecar_sha256 = sidecar_parts[0].lower()
    if len(sidecar_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sidecar_sha256):
        raise RuntimeError("manifest.sha256 contains an invalid SHA-256 digest.")

    def sha256_file(path):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    audio_sha256 = sha256_file(source)
    if sidecar_sha256 != audio_sha256:
        raise RuntimeError("manifest.sha256 does not match the actual selected audio file.")
    if info.get("sha256") != audio_sha256:
        raise RuntimeError(f"manifest.json SHA-256 does not match generated {kind} audio.")

    used_audio_hashes = set(state.get("_published_audio_sha256", [])) | set(main_state.get("_published_audio_sha256", []))
    if audio_sha256 in used_audio_hashes:
        raise RuntimeError(f"Duplicate audio detected (sha256={audio_sha256}); refusing to build or upload this Short.")

    OUT.mkdir(exist_ok=True)
    filename = f"TV-OFF_{file_kind}_Short_{slot}.mp4"
    target = OUT / filename
    # Category-led vertical visual: a soft luminous frame, animated waveform and a timed end-card CTA.
    themes = {
        "white_noise": ("0xA9D8FF", "WHITE NOISE", "A LITTLE MORE QUIET"),
        "brown_noise": ("0xC99563", "BROWN NOISE", "LET THE WORLD FADE OUT"),
        "original_music": ("0xB7A6E5", "DEEP SLEEP AMBIENT", "SLOW DOWN AND LET GO"),
    }
    accent, headline, tagline = themes.get(
        kind, ("0xA9C7E8", display_kind.upper(), "SOUND TO SWITCH OFF TO")
    )
    # Three distinct Brown Noise hooks, rotated across Brown Noise slots.
    slot_hour_utc = int(slot[-2:])
    variant_index = (slot_hour_utc + slot_hour_utc // 6) % 3
    brown_hooks = [
        ("SLOW DOWN. BREATHE.", "A DEEPER SOUND FOR REST"),
        ("LET YOUR MIND UNWIND", "A QUIETER MOMENT STARTS HERE"),
        ("FIND YOUR QUIET FOCUS", "STAY WITH THE TASK"),
    ]
    if kind == "brown_noise":
        hook, tagline = brown_hooks[variant_index]
        accent = ["0xC99563", "0xD6AE82", "0xA97852"][variant_index]
    else:
        hook = "A MOMENT FOR YOU"
    graph = (
        f"[1:a]volume=3.5,showwaves=s=920x280:mode=cline:scale=sqrt:rate=30:colors={accent},format=rgba[w];"
        "[0:v]format=rgba,"
        f"drawbox=x=54:y=260:w=972:h=1390:color={accent}@0.075:t=fill,"
        f"drawbox=x=82:y=288:w=916:h=1334:color={accent}@0.45:t=3,"
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='{hook}':fontcolor=0xDCE5F2:fontsize=27:"
        "x=(w-text_w)/2:y=390,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"text='{headline}':fontcolor=white:fontsize=76:"
        "x=(w-text_w)/2:y=600,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"text='{tagline}':fontcolor={accent}:fontsize=30:"
        "x=(w-text_w)/2:y=735[vbase];"
        "[vbase][w]overlay=(W-w)/2:885:shortest=1,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='TV OFF':fontcolor=white:fontsize=44:"
        "x=(w-text_w)/2:y=1250,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        "text='SOUND TO SWITCH OFF TO':fontcolor=0xAAB2C4:fontsize=24:"
        "x=(w-text_w)/2:y=1320,"
        "drawbox=x=105:y=1490:w=870:h=112:color=0x172337@0.96:t=fill:"
        "enable='gte(t,11)',"
        "drawbox=x=105:y=1490:w=870:h=112:color=white@0.55:t=2:"
        "enable='gte(t,11)',"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='MORE SOUNDS ON OUR CHANNEL':fontcolor=white:fontsize=31:"
        "x=(w-text_w)/2:y=1526:alpha='if(lt(t,12),t-11,1)':enable='gte(t,11)'[v]"
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

    # Content-level deduplication: slot uniqueness alone is not enough.
    video_sha256 = sha256_file(target)
    used_video_hashes = set(state.get("_published_video_sha256", [])) | set(main_state.get("_published_video_sha256", []))
    if video_sha256 in used_video_hashes:
        raise RuntimeError(
            f"Duplicate video detected (sha256={video_sha256}); refusing to upload this Short."
        )

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
    short_copy = {
        "white_noise": (
            "Need a little quiet? Let this steady white noise create a calm background "
            "for rest, reading or focused moments. Press play and take a breather. "
        ),
        "brown_noise": (
            "A deeper, softer sound for a slower moment. Let this warm brown noise "
            "play in the background while you unwind, read or focus. "
        ),
        "original_music": (
            "Take a moment to slow down. This original ambient music is made for "
            "quiet evenings, gentle focus and a little time to yourself. "
        ),
    }
    description = (
        short_copy[kind]
        + "More peaceful sounds and original music on the TV OFF channel.\n\n"
        + f"#Shorts #{kind.replace('_', '')} #Relaxation #SleepSounds #TVOFF"
    )
    short_title_variants = {
        "white_noise": [
            "A Little White Noise for a Quieter Moment",
            "Steady White Noise to Help You Switch Off",
            "A Calm White Noise Sound for Rest and Focus",
            "Gentle White Noise for a Peaceful Break",
            "White Noise to Ease Into a Quiet Moment",
            "A Soft Bed of White Noise for Better Rest",
            "Find Your Focus with Steady White Noise",
            "White Noise for a Calmer Space",
            "A Simple Sound for Quiet and Comfort",
            "Let the Day Fade with Gentle White Noise",
            "White Noise for Reading, Rest and Reset",
            "A Steady Sound When You Need Some Quiet",
            "A Quiet Background with White Noise",
            "White Noise to Help You Settle Down",
            "Make Room for Calm with White Noise",
            "A Gentle Soundscape for Your Quiet Time",
            "Stay Focused with Smooth White Noise",
            "A Peaceful Pause with White Noise",
            "Soft White Noise for Your Next Reset",
            "A Little More Calm with White Noise",
        ],
        "brown_noise": [
            "Deep Brown Noise for a Moment of Calm",
            "A Softer, Deeper Sound to Unwind To",
            "Brown Noise for Quiet Focus and Rest",
            "Settle In with Deep Brown Noise",
            "A Warm Low Sound for a Calmer Mind",
            "Brown Noise for Reading and Deep Focus",
            "Let the Busy Day Fade with Brown Noise",
            "A Deeper Sound for Your Quiet Space",
            "Relax into a Steady Brown Noise Bed",
            "Low, Gentle Brown Noise for Rest",
            "Find Your Focus in Deep Brown Noise",
            "A Calm Moment with Rich Brown Noise",
        ],
        "original_music": [
            "A Quiet Moment with Original Ambient Music",
            "Soft Ambient Music to Slow Down To",
            "A Gentle Instrumental Moment for You",
            "Original Ambient Music for a Peaceful Pause",
            "Slow Down with This Gentle Ambient Sound",
            "A Soft Instrumental Space to Unwind",
            "Quiet Ambient Music for Rest and Reflection",
            "A Gentle Soundtrack for Your Evening",
            "Take a Breath with Original Ambient Music",
            "Soft Tones for a Slower Moment",
            "A Calm Instrumental Escape",
            "Let Your Thoughts Settle with Ambient Music",
        ],
    }
    # Select a title that has never been used on this channel. Never recycle a
    # title just because the UTC slot changed or the sound category repeats.
    used_titles = {
        str(title).strip().removesuffix(" #shorts").casefold()
        for title in state.get("_published_titles", [])
        if isinstance(title, str)
    }
    variants = list(short_title_variants[kind])

    def generate_fresh_titles(category, existing, count=24):
        # Local deterministic title generator: combines human-written phrase
        # fragments, requires the category keyword, and filters all used titles.
        recipes = {
            "white_noise": {
                "openers": ["Steady White Noise", "Gentle White Noise", "Soft White Noise", "Pure White Noise", "White Noise for", "A Calm White Noise Sound for"],
                "contexts": ["a Quieter Mind", "Deep Focus", "Restful Moments", "Reading and Relaxing", "a Peaceful Night", "Everyday Calm", "Uninterrupted Work", "a Gentle Reset", "Better Sleep", "Quiet Time"],
                "closers": ["", " | Relax and Unwind", " for Sleep and Focus", " to Help You Switch Off"],
            },
            "brown_noise": {
                "openers": ["Deep Brown Noise", "Warm Brown Noise", "Soft Brown Noise", "Rich Brown Noise", "Brown Noise for", "A Deeper Brown Noise Sound for"],
                "contexts": ["Quiet Focus", "Restful Sleep", "a Calmer Mind", "Reading and Relaxing", "a Peaceful Night", "Deep Work", "Unwinding", "a Gentle Reset", "Everyday Calm", "Quiet Time"],
                "closers": ["", " | Relax and Unwind", " for Sleep and Focus", " to Help You Switch Off"],
            },
            "original_music": {
                "openers": ["Original Ambient Music", "Soft Ambient Music", "Gentle Instrumental Music", "Peaceful Original Music", "Ambient Music for", "A Quiet Instrumental Soundtrack for"],
                "contexts": ["a Slower Moment", "Deep Focus", "Rest and Reflection", "Reading and Relaxing", "a Peaceful Night", "Quiet Evenings", "Unwinding", "a Gentle Reset", "Creative Flow", "Quiet Time"],
                "closers": ["", " | Relax and Unwind", " for Sleep and Focus", " to Help You Switch Off"],
            },
        }
        recipe = recipes[category]
        generated = []
        seen = {str(x).strip().casefold() for x in existing}
        # Stable ordering avoids random title selection and keeps reruns predictable.
        for opener in recipe["openers"]:
            for context in recipe["contexts"]:
                for closer in recipe["closers"]:
                    candidate = f"{opener} {context}{closer}".strip()
                    key = candidate.casefold()
                    if key not in seen:
                        seen.add(key)
                        generated.append(candidate)
                        if len(generated) >= count:
                            return generated
        return generated

    generated_by_category = state.setdefault("_generated_titles_by_category", {})
    generated_titles = generated_by_category.setdefault(kind, [])
    available = [
        title for title in variants + generated_titles
        if title.casefold() not in used_titles
    ]
    if len(available) <= 5:
        fresh = generate_fresh_titles(kind, used_titles | {x.casefold() for x in variants + generated_titles})
        if fresh:
            generated_titles.extend(fresh)
            generated_by_category[kind] = list(dict.fromkeys(generated_titles))
            state["_generated_titles_by_category"] = generated_by_category
            STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
            print(f"TITLE GENERATOR: {kind} had {len(available)} titles remaining; added {len(fresh)} fresh titles.")

    variants = variants + generated_titles
    available = [title for title in variants if title.casefold() not in used_titles]
    if not available:
        raise RuntimeError(
            f"Title generator produced no unused titles for {kind}; refusing duplicate metadata."
        )
    title_start = int(audio_sha256[:8], 16) % len(available)
    short_title_base = available[title_start]
    short_title = f"{short_title_base} #Shorts"
    short_tags = ["Shorts", display_kind, "Relaxation", "Sleep Sounds", "Focus", "TV OFF"]
    body = {
        "snippet": {
            "title": short_title,
            "description": description,
            "tags": short_tags,
            "categoryId": "10"
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    upload_check_time = datetime.now(timezone.utc)
    current_slot_before_upload = upload_check_time.strftime("%Y%m%d%H")
    if current_slot_before_upload != target_slot:
        raise RuntimeError(
            f"UTC slot changed before YouTube upload: target={target_slot}, "
            f"current={current_slot_before_upload}; refusing rollover."
        )
    remaining_in_slot = (slot_end - upload_check_time).total_seconds()
    if remaining_in_slot < 180:
        raise RuntimeError(
            f"Only {max(0, int(remaining_in_slot))}s remain in UTC slot {target_slot}; "
            "refusing YouTube upload with less than a 3-minute reserve."
        )
    response = youtube.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(target), mimetype="video/mp4", chunksize=-1, resumable=True)
    ).execute()
    video_id = response["id"]
    published_at = datetime.now(timezone.utc)
    state[slot] = video_id
    state["_published_titles"] = list(dict.fromkeys(
        state.get("_published_titles", []) + [short_title]
    ))
    state["_published_audio_sha256"] = list(dict.fromkeys(
        state.get("_published_audio_sha256", []) + [audio_sha256]
    ))[-500:]
    state["_published_video_sha256"] = list(dict.fromkeys(
        state.get("_published_video_sha256", []) + [video_sha256]
    ))[-500:]
    state["_last_published_at"] = published_at.isoformat()
    state["_last_production_duration_seconds"] = max(
        0, int(published_at.timestamp() - production_started_epoch)
    )
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"SHORT PUBLISHED: https://youtu.be/{video_id} | slot={slot} | soundscape={kind}")

if __name__ == "__main__":
    main()
