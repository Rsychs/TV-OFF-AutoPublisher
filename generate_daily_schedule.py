import csv
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get("SCHEDULE_FILE", ROOT / "daily_schedule.csv"))
TZ = ZoneInfo("Europe/Riga")

# White and brown noise are mandatory first-priority releases until each is published.
WHITE_NOISE_VARIANTS = [
    ("White Noise for Sleep, Study & Focus", "white noise for sleep;white noise for focus;WhiteNoise;SleepSounds;FocusSounds", "A steady, even white-noise sound bed for sleep, study and focused listening. 10 uninterrupted hours with a completely black screen."),
    ("Soft White Noise for Newborn Sleep", "newborn white noise;white noise for newborns;newborn sleep sounds;WhiteNoise;BabySleepSounds", "A continuous, gentle white-noise background for a calm sleep environment. 10 uninterrupted hours with a completely black screen. For infant use, keep playback at a low volume and place the device well away from the baby's head and sleep space. Follow current safe-sleep guidance from your healthcare professional."),
    ("Gentle White Noise for Baby Sleep", "white noise for baby sleep;white noise for babies;baby sleep sounds;WhiteNoise;BabySleepSounds", "A steady white-noise background for quiet listening during a baby's rest time. 10 uninterrupted hours with a completely black screen. For infant use, keep playback at a low volume and place the device well away from the baby's head and sleep space. Follow current safe-sleep guidance from your healthcare professional."),
    ("White Noise for Newborns | Soft, Steady Background Sound", "white noise for newborns;newborn white noise;soft white noise;WhiteNoise;BabySleepSounds", "Soft, consistent white noise for a quiet listening environment. 10 uninterrupted hours with a completely black screen. For infant use, keep playback at a low volume and place the device well away from the baby's head and sleep space. Follow current safe-sleep guidance from your healthcare professional."),
]
WHITE_NOISE = ("white_noise", WHITE_NOISE_VARIANTS[0][0], WHITE_NOISE_VARIANTS[0][1])
BROWN_NOISE_VARIANTS = [
    ("Deep Brown Noise for Sleep & Overnight Relaxation", "brown noise for deep sleep;brown noise overnight;deep sleep sounds;BrownNoise;SleepSounds", "A steady, deep brown-noise sound bed for calm nighttime listening. 10 uninterrupted hours with a completely black screen."),
    ("Brown Noise for Focus, Work & Blocking Distractions", "brown noise for focus;brown noise for concentration;study sounds;work sounds;BrownNoise;FocusSounds", "A consistent low-frequency brown-noise background for focused work, reading and concentration. 10 uninterrupted hours with a completely black screen."),
    ("Deep Brown Noise for Studying, Reading & Focus", "deep brown noise for studying;brown noise for reading;study ambience;concentration sounds;BrownNoise;StudySounds", "Deep, even brown noise for study sessions, reading and quiet background listening. 10 uninterrupted hours with a completely black screen."),
    ("Smooth Brown Noise for Relaxation & Unwinding", "brown noise for relaxation;calming brown noise;unwind sounds;relaxing background noise;BrownNoise;RelaxationSounds", "A smooth brown-noise sound bed for slowing down and unwinding. 10 uninterrupted hours with a completely black screen."),
    ("Brown Noise to Block Distractions & Background Noise", "brown noise to block distractions;background noise for focus;steady noise;BrownNoise;FocusSounds", "Steady brown noise as a consistent background layer when you want fewer interruptions from everyday environmental sounds. 10 uninterrupted hours with a completely black screen."),
    ("Deep Low-Frequency Brown Noise for a Quiet Night", "low frequency brown noise;deep brown noise at night;night sounds;BrownNoise;SleepSounds", "A deep, steady brown-noise ambience for quiet evenings and nighttime listening. 10 uninterrupted hours with a completely black screen."),
    ("Brown Noise for Deep Work & a Quiet Home Office", "brown noise for deep work;home office background noise;focus ambience;BrownNoise;WorkSounds", "A continuous brown-noise background for deep-work blocks and home-office tasks. 10 uninterrupted hours with a completely black screen."),
    ("Brown Noise for Sleep & a Peaceful Night", "brown noise for sleep;brown noise for rest;peaceful night sounds;BrownNoise;SleepSounds", "A steady brown-noise soundscape for rest and peaceful nighttime listening. 10 uninterrupted hours with a completely black screen."),
]
BROWN_NOISE = ("brown_noise", BROWN_NOISE_VARIANTS[0][0], BROWN_NOISE_VARIANTS[0][1])
# Three-category rotation: white noise, brown noise, and original music only.
STANDARD_SOUNDS = [
    ("brown_noise", None, None),
    ("white_noise", None, None),
    ("original_music", "Deep Sleep Ambient Music | Soft, Slow & Instrumental", "deep sleep ambient music;relaxing ambient music;sleep music;calming instrumental;TV OFF"),
    ("brown_noise", None, None),
    ("white_noise", None, None),
    ("original_music", "Soft Ambient Music for Deep Rest & Nighttime Relaxation", "soft ambient music;music for deep sleep;peaceful instrumental;relaxation music;TV OFF"),
]
def published_soundscapes():
    state_path = ROOT / "state.json"
    if not state_path.is_file():
        raise RuntimeError("state.json is missing; refusing to assume priority videos were published")
    import json
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise RuntimeError("state.json is not a JSON object")
    # Normalize filenames because Python's str.title() writes "Whitenoise"/"Brownnoise",
    # while older releases may use "WhiteNoise"/"BrownNoise". Matching is case-insensitive
    # and separator-insensitive so priority releases cannot get stuck in a repeat loop.
    published = {"white_noise": False, "brown_noise": False}
    for name, video_id in state.items():
        # A filename alone is not proof of publication: require a real YouTube ID.
        if not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id.strip()):
            continue
        normalized_name = re.sub(r"[^a-z0-9]", "", str(name).lower())
        if "whitenoise" in normalized_name:
            published["white_noise"] = True
        if "brownnoise" in normalized_name:
            published["brown_noise"] = True
    return published

def main():
    now = datetime.now(TZ)
    slot_hour = (now.hour // 3) * 3
    slot_start = now.replace(hour=slot_hour, minute=0, second=0, microsecond=0)
    date_key = slot_start.strftime("%Y%m%d")
    slot_key = slot_start.strftime("%H")
    published = published_soundscapes()
    brown_description = None
    white_description = None
    slot_number = int(slot_start.timestamp() // (3 * 3600))
    if not published["brown_noise"]:
        kind = "brown_noise"
        title, tags, brown_description = BROWN_NOISE_VARIANTS[slot_number % len(BROWN_NOISE_VARIANTS)]
        print("PRIORITY QUEUE: brown noise is not yet published; selecting Brown Noise before all other long-form topics.")
    elif not published["white_noise"]:
        kind = "white_noise"
        title, tags, white_description = WHITE_NOISE_VARIANTS[slot_number % len(WHITE_NOISE_VARIANTS)]
        print("PRIORITY QUEUE: brown noise is published; white noise is still missing, so selecting a natural title variant.")
    else:
        slot_number = int(slot_start.timestamp() // (3 * 3600))
        kind, title, tags = STANDARD_SOUNDS[slot_number % len(STANDARD_SOUNDS)]
        if kind == "brown_noise":
            title, tags, brown_description = BROWN_NOISE_VARIANTS[(slot_number // len(STANDARD_SOUNDS)) % len(BROWN_NOISE_VARIANTS)]
        elif kind == "white_noise":
            title, tags, white_description = WHITE_NOISE_VARIANTS[(slot_number // len(STANDARD_SOUNDS)) % len(WHITE_NOISE_VARIANTS)]
        print("PRIORITY QUEUE COMPLETE: both white and brown noise are published; using expanded standard rotation.")
    file_kind = kind.replace("_", "").title()
    display_kind = kind.replace("_", " ").title()
    filename = f"TV-OFF_{file_kind}_{date_key}_{slot_key}_10-Hours.mp4"

    if kind in {"white_noise", "brown_noise"}:
        description_intro = (
            brown_description or white_description or (
                f"10 hours of steady, original {display_kind.lower()} sound for sleep, relaxation and focus. "
                "A continuous sound bed with a completely black screen for overnight listening."
            )
        )
        noise_hashtag = "#WhiteNoise" if kind == "white_noise" else "#BrownNoise"
        audience_hashtag = " #BabySleep" if kind == "white_noise" and white_description and ("newborn" in title.lower() or "baby" in title.lower()) else ""
        hashtags = f"{noise_hashtag} #SleepSounds #FocusSounds{audience_hashtag} #BlackScreen #TVOff"
        thumbnail_descriptor = f"{display_kind.upper()} • 10 HOURS"
    elif kind == "original_music":
        description_intro = (
            "10 hours of original, slow-evolving ambient instrumental music for deep rest, sleep and relaxation. "
            "Composed and synthesized specifically for TV OFF with no third-party recordings, samples or borrowed melodies. "
            "The music is carefully crossfaded for uninterrupted listening; the screen remains completely black."
        )
        hashtags = "#AmbientMusic #SleepMusic #RelaxingMusic #BlackScreen #TVOff"
        thumbnail_descriptor = "AMBIENT MUSIC • 10 HOURS"
    else:
        raise RuntimeError(f"Unsupported sound category: {kind}")

    source_label = "Original composition" if kind == "original_music" else "Original audio"
    description = (
        description_intro + "\n\n"
        f"{source_label}: {{creator}}\nSource: {{source_url}}\nLicense: {{license}}\n\n"
        "🎧 Keep the volume comfortable.\n🖤 10 hours • Black screen • No visuals\n\n"
        "Subscribe to TV OFF for more long-form ambient soundscapes.\n\n"
        + hashtags
    )
    publish_at = now.isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "filename", "soundscape", "title", "description", "tags",
            "publish_at", "thumbnail_descriptor"
        ])
        writer.writeheader()
        writer.writerow({
            "filename": filename,
            "soundscape": kind,
            "title": f"{title} | 10 Hours, Black Screen — TV OFF",
            "description": description,
            "tags": ";".join([x.strip() for x in tags.split(";")] + [
                "10 hours", "black screen", "TV OFF"
            ]),
            "publish_at": publish_at,
            "thumbnail_descriptor": thumbnail_descriptor
        })
    print(f"3-HOUR SLOT: {slot_start.isoformat()} | {kind} | {filename} | {publish_at}")

if __name__ == "__main__":
    main()
