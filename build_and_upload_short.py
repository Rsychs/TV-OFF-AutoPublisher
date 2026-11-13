import hashlib
import json
import os
import re
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
DURATION = 30

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
    if kind == "original_music":
        try:
            music_duration = int(info.get("duration_seconds", -1))
            music_bar_seconds = float(info.get("bar_seconds", -1))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Original Music Shorts manifest has invalid duration/bar_seconds.") from exc
        if (
            info.get("composition_mode") != "short_form_fast_harmonic_movement"
            or music_duration != 36
            or abs(music_bar_seconds - 4.5) > 1e-9
            or not str(info.get("music_style", "")).strip()
            or not str(info.get("sound_profile", "")).strip()
        ):
            raise RuntimeError(
                "Original Music Short requires manifest composition_mode=short_form_fast_harmonic_movement, "
                "duration_seconds=36, bar_seconds=4.5, music_style and sound_profile."
            )
        if not isinstance(state.get("_published_music_metadata", []), list):
            raise RuntimeError("Invalid _published_music_metadata ledger; refusing Original Music Short upload.")
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
    # Every Short receives a newly rendered, slot-selected 3D environment.
    themes = {
        "white_noise": ("0xA9D8FF", "WHITE NOISE", "A LITTLE MORE QUIET"),
        "brown_noise": ("0xC99563", "BROWN NOISE", "LET THE WORLD FADE OUT"),
        "original_music": ("0xB7A6E5", "ORIGINAL AMBIENT MUSIC", "SLOW DOWN AND LET GO"),
    }
    accent, headline, tagline = themes[kind]
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

    scene_png = OUT / f"scene_{slot}_{kind}.png"
    scene_script = ROOT / "scripts" / "render_tv_off_short_scene.py"
    if not scene_script.is_file():
        raise RuntimeError(f"Required 3D scene renderer is missing: {scene_script}")
    subprocess.run([
        os.sys.executable, str(scene_script),
        "--out", str(scene_png), "--kind", kind, "--slot", slot
    ], check=True, timeout=1500)
    if not scene_png.is_file() or scene_png.stat().st_size < 100000:
        raise RuntimeError("The cinematic 3D scene render is missing or unexpectedly small.")

    graph = (
        "[0:v]zoompan=z='min(1.085,1+0.000095*on)':"
        "x='iw/2-(iw/zoom/2)+2*sin(on/115)':"
        "y='ih/2-(ih/zoom/2)+3*cos(on/145)':d=1:s=1080x1920:fps=30,"
        "eq=contrast=1.035:saturation=1.06,format=yuv420p[bg];"
        f"[1:a]showwaves=s=900x150:mode=cline:scale=sqrt:rate=30:colors={accent},"
        "format=rgba,colorchannelmixer=aa=0.78[w];"
        "[bg][w]overlay=(W-w)/2:1450:shortest=1,"
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"text='{hook}':fontcolor=0xF1F4FA:fontsize=34:"
        "x=(w-text_w)/2:y=250:shadowcolor=black@0.45:shadowx=2:shadowy=3,"
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"text='{headline}':fontcolor=white:fontsize=66:"
        "x=(w-text_w)/2:y=355:shadowcolor=black@0.55:shadowx=2:shadowy=3,"
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"text='{tagline}':fontcolor={accent}:fontsize=28:"
        "x=(w-text_w)/2:y=445:shadowcolor=black@0.45:shadowx=2:shadowy=3,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='TV OFF':fontcolor=white:fontsize=38:"
        "x=(w-text_w)/2:y=1665,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        "text='MORE SOUNDS ON OUR CHANNEL':fontcolor=white:fontsize=27:"
        "x=(w-text_w)/2:y=1775:alpha='if(lt(t,26),0, min(1,(t-26)))':enable='gte(t,26)'[v]"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-loop", "1", "-framerate", "30",
        "-i", str(scene_png), "-i", str(source),
        "-filter_complex", graph, "-map", "[v]", "-map", "1:a:0",
        "-t", str(DURATION), "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "19", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "160k",
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
    def normalize_title(value):
        # One normalization rule for published, base and generated titles.
        title = " ".join(str(value).strip().split())
        title = re.sub(r"\s+#shorts\s*$", "", title, flags=re.IGNORECASE)
        return title.casefold()

    def unique_titles(values):
        result = []
        seen = set()
        for value in values:
            key = normalize_title(value)
            if key and key not in seen:
                seen.add(key)
                result.append(" ".join(str(value).strip().split()))
        return result

    used_titles = {
        normalize_title(title)
        for title in state.get("_published_titles", [])
        if isinstance(title, str)
    }
    variants = unique_titles(short_title_variants[kind])

    def generate_fresh_titles(category, existing, count=24):
        # Local deterministic title generator: combines human-written phrase
        # fragments, requires the category keyword, and filters all used titles.
        recipes = {
            "white_noise": {
                "openers": ["Steady White Noise for", "Gentle White Noise for", "Soft White Noise for", "Pure White Noise for", "White Noise for", "A Calm White Noise Sound for"],
                "contexts": ["a Quieter Mind", "Deep Focus", "Restful Moments", "Reading and Relaxing", "a Peaceful Night", "Everyday Calm", "Uninterrupted Work", "a Gentle Reset", "Better Sleep", "Quiet Time"],
                "closers": ["", " | TV OFF", " to Help You Switch Off", " — Relax and Unwind"],
            },
            "brown_noise": {
                "openers": ["Deep Brown Noise for", "Warm Brown Noise for", "Soft Brown Noise for", "Rich Brown Noise for", "Brown Noise for", "A Deeper Brown Noise Sound for"],
                "contexts": ["Quiet Focus", "Restful Sleep", "a Calmer Mind", "Reading and Relaxing", "a Peaceful Night", "Deep Work", "Unwinding", "a Gentle Reset", "Everyday Calm", "Quiet Time"],
                "closers": ["", " | TV OFF", " to Help You Switch Off", " — Relax and Unwind"],
            },
            "original_music": {
                "openers": ["Original Ambient Music for", "Soft Ambient Music for", "Gentle Instrumental Music for", "Peaceful Original Music for", "Ambient Music for", "A Quiet Instrumental Soundtrack for"],
                "contexts": ["a Slower Moment", "Deep Focus", "Rest and Reflection", "Reading and Relaxing", "a Peaceful Night", "Quiet Evenings", "Unwinding", "a Gentle Reset", "Creative Flow", "Quiet Time"],
                "closers": ["", " | TV OFF", " to Help You Switch Off", " — Relax and Unwind"],
            },
        }
        recipe = recipes[category]
        generated = []
        seen = {normalize_title(x) for x in existing}
        # Stable ordering avoids random title selection and keeps reruns predictable.
        for opener in recipe["openers"]:
            for context in recipe["contexts"]:
                for closer in recipe["closers"]:
                    candidate = f"{opener} {context}{closer}".strip()
                    key = normalize_title(candidate)
                    if key not in seen:
                        seen.add(key)
                        generated.append(candidate)
                        if len(generated) >= count:
                            return generated
        return generated

    generated_by_category = state.setdefault("_generated_titles_by_category", {})
    generated_titles = unique_titles(generated_by_category.setdefault(kind, []))
    generated_by_category[kind] = generated_titles
    available = unique_titles([
        title for title in variants + generated_titles
        if normalize_title(title) not in used_titles
    ])
    if len(available) <= 5:
        existing_titles = used_titles | {
            normalize_title(x) for x in variants + generated_titles
        }
        fresh = unique_titles(generate_fresh_titles(kind, existing_titles, count=24))
        if len(fresh) < 24:
            raise RuntimeError(
                f"Title generator produced only {len(fresh)} unique fresh titles for {kind}; "
                "refusing upload before the title pool is replenished."
            )
        generated_titles = unique_titles(generated_titles + fresh)
        generated_by_category[kind] = generated_titles
        state["_generated_titles_by_category"] = generated_by_category
        STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print(f"TITLE GENERATOR: {kind} had {len(available)} unique titles remaining; added {len(fresh)} fresh titles.")

    variants = unique_titles(variants + generated_titles)
    available = unique_titles(
        title for title in variants if normalize_title(title) not in used_titles
    )
    if not available:
        raise RuntimeError(
            f"Title generator produced no unused titles for {kind}; refusing duplicate metadata."
        )
    title_start = int(audio_sha256[:8], 16) % len(available)
    short_title_base = available[title_start]
    short_title = f"{short_title_base} #Shorts"
    if normalize_title(short_title) in used_titles:
        raise RuntimeError("Selected Shorts title is already published; refusing duplicate metadata.")
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
    if kind == "original_music":
        music_records = state.setdefault("_published_music_metadata", [])
        if not any(item.get("video_id") == video_id for item in music_records if isinstance(item, dict)):
            music_records.append({
                "video_id": video_id,
                "published_at": published_at.isoformat(),
                "title": short_title,
                "music_style": info["music_style"],
                "sound_profile": info["sound_profile"],
                "musical_mode": info.get("musical_mode"),
                "composition_mode": info["composition_mode"],
                "duration_seconds": info["duration_seconds"],
                "bar_seconds": info["bar_seconds"],
                "audio_sha256": audio_sha256,
            })
            state["_published_music_metadata"] = music_records[-100:]
    state["_last_published_at"] = published_at.isoformat()
    state["_last_production_duration_seconds"] = max(
        0, int(published_at.timestamp() - production_started_epoch)
    )
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"SHORT PUBLISHED: https://youtu.be/{video_id} | slot={slot} | soundscape={kind}")

if __name__ == "__main__":
    main()
