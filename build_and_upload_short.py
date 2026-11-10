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
    if len(manifest) != 1:
        raise RuntimeError("Expected exactly one selected sound in the manifest; refusing ambiguous Short metadata.")
    kind = next(iter(manifest))
    if kind not in {"white_noise", "brown_noise", "original_music"}:
        raise RuntimeError(f"Disallowed TV OFF category for Shorts: {kind}; nature and field recordings are retired.")
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
    # Category-led vertical visual: a soft luminous frame, animated waveform and a timed end-card CTA.
    themes = {
        "white_noise": ("0xA9D8FF", "WHITE NOISE", "A LITTLE MORE QUIET"),
        "brown_noise": ("0xC99563", "BROWN NOISE", "LET THE WORLD FADE OUT"),
        "original_music": ("0xB7A6E5", "DEEP SLEEP AMBIENT", "SLOW DOWN AND LET GO"),
        "ocean": ("0x55C6D8", "OCEAN SOUNDS", "TAKE A SLOW BREATH"),
        "rain": ("0x8CB7D8", "RAIN SOUNDS", "SETTLE INTO THE MOMENT"),
        "thunderstorm": ("0x9B9BCB", "STORM SOUNDS", "LET THE NOISE FADE"),
        "forest": ("0x8DBB91", "FOREST SOUNDS", "FIND A QUIETER PLACE"),
        "river": ("0x65BFAF", "RIVER SOUNDS", "PAUSE AND UNWIND"),
        "fireplace": ("0xE6A064", "FIREPLACE SOUNDS", "WARM UP AND SLOW DOWN"),
        "wind": ("0xA8B7C8", "WIND SOUNDS", "BREATHE AND LET GO"),
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

    def sha256_file(path):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    # Content-level deduplication: slot uniqueness alone is not enough.
    audio_sha256 = sha256_file(source)
    video_sha256 = sha256_file(target)
    used_audio_hashes = set(state.get("_published_audio_sha256", []))
    used_video_hashes = set(state.get("_published_video_sha256", []))
    if audio_sha256 in used_audio_hashes:
        raise RuntimeError(
            f"Duplicate audio detected (sha256={audio_sha256}); refusing to upload this Short."
        )
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
    if not synthetic:
        raise RuntimeError("TV OFF Shorts may only use locally generated White Noise, Brown Noise or Original Music.")
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
        str(title).strip().casefold()
        for title in state.get("_published_titles", [])
        if isinstance(title, str)
    }
    variants = short_title_variants[kind]
    title_start = int(audio_sha256[:8], 16) % len(variants)
    short_title_base = next(
        (
            variants[(title_start + offset) % len(variants)]
            for offset in range(len(variants))
            if variants[(title_start + offset) % len(variants)].casefold() not in used_titles
        ),
        None,
    )
    if short_title_base is None:
        # Exhaustion is a hard stop: do not publish a repeated title.
        raise RuntimeError(
            f"All approved unique titles are exhausted for {kind}; refusing duplicate metadata."
        )
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
