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
    ("White Noise for Sleep, Study & Focus", "white noise for sleep;white noise for focus;WhiteNoise;SleepSounds;FocusSounds", "A steady, even white-noise sound bed for sleep, study and focused listening. continuous sound with a completely black screen."),
    ("Soft White Noise for Newborn Sleep", "newborn white noise;white noise for newborns;newborn sleep sounds;WhiteNoise;BabySleepSounds", "A continuous, gentle white-noise background for a calm sleep environment. continuous sound with a completely black screen. For infant use, keep playback at a low volume and place the device well away from the baby's head and sleep space. Follow current safe-sleep guidance from your healthcare professional."),
    ("Gentle White Noise for Baby Sleep", "white noise for baby sleep;white noise for babies;baby sleep sounds;WhiteNoise;BabySleepSounds", "A steady white-noise background for quiet listening during a baby's rest time. continuous sound with a completely black screen. For infant use, keep playback at a low volume and place the device well away from the baby's head and sleep space. Follow current safe-sleep guidance from your healthcare professional."),
    ("White Noise for Newborns | Soft, Steady Background Sound", "white noise for newborns;newborn white noise;soft white noise;WhiteNoise;BabySleepSounds", "Soft, consistent white noise for a quiet listening environment. continuous sound with a completely black screen. For infant use, keep playback at a low volume and place the device well away from the baby's head and sleep space. Follow current safe-sleep guidance from your healthcare professional."),
]
WHITE_NOISE = ("white_noise", WHITE_NOISE_VARIANTS[0][0], WHITE_NOISE_VARIANTS[0][1])
BROWN_NOISE_VARIANTS = [
    ("Deep Brown Noise for Sleep & Overnight Relaxation", "brown noise for deep sleep;brown noise overnight;deep sleep sounds;BrownNoise;SleepSounds", "A steady, deep brown-noise sound bed for calm nighttime listening. continuous sound with a completely black screen."),
    ("Brown Noise for Focus, Work & Blocking Distractions", "brown noise for focus;brown noise for concentration;study sounds;work sounds;BrownNoise;FocusSounds", "A consistent low-frequency brown-noise background for focused work, reading and concentration. continuous sound with a completely black screen."),
    ("Deep Brown Noise for Studying, Reading & Focus", "deep brown noise for studying;brown noise for reading;study ambience;concentration sounds;BrownNoise;StudySounds", "Deep, even brown noise for study sessions, reading and quiet background listening. continuous sound with a completely black screen."),
    ("Smooth Brown Noise for Relaxation & Unwinding", "brown noise for relaxation;calming brown noise;unwind sounds;relaxing background noise;BrownNoise;RelaxationSounds", "A smooth brown-noise sound bed for slowing down and unwinding. continuous sound with a completely black screen."),
    ("Brown Noise to Block Distractions & Background Noise", "brown noise to block distractions;background noise for focus;steady noise;BrownNoise;FocusSounds", "Steady brown noise as a consistent background layer when you want fewer interruptions from everyday environmental sounds. continuous sound with a completely black screen."),
    ("Deep Low-Frequency Brown Noise for a Quiet Night", "low frequency brown noise;deep brown noise at night;night sounds;BrownNoise;SleepSounds", "A deep, steady brown-noise ambience for quiet evenings and nighttime listening. continuous sound with a completely black screen."),
    ("Brown Noise for Deep Work & a Quiet Home Office", "brown noise for deep work;home office background noise;focus ambience;BrownNoise;WorkSounds", "A continuous brown-noise background for deep-work blocks and home-office tasks. continuous sound with a completely black screen."),
    ("Brown Noise for Sleep & a Peaceful Night", "brown noise for sleep;brown noise for rest;peaceful night sounds;BrownNoise;SleepSounds", "A steady brown-noise soundscape for rest and peaceful nighttime listening. continuous sound with a completely black screen."),
]
BROWN_NOISE = ("brown_noise", BROWN_NOISE_VARIANTS[0][0], BROWN_NOISE_VARIANTS[0][1])
# Original Music title variants rotate independently from the three-category mix.
ORIGINAL_MUSIC_VARIANTS = [
    ("Deep Sleep Ambient Music | Soft, Slow & Instrumental", "deep sleep ambient music;relaxing ambient music;sleep music;calming instrumental;TV OFF"),
    ("Soft Ambient Music for Deep Rest & Nighttime Relaxation", "soft ambient music;music for deep sleep;peaceful instrumental;relaxation music;TV OFF"),
    ("Peaceful Ambient Music for Rest & Quiet Focus", "peaceful ambient music;quiet focus music;rest music;calming instrumental;TV OFF"),
    ("Gentle Ambient Music for a Calm Evening", "gentle ambient music;calm evening music;relaxing instrumental;TV OFF"),
    ("Slow Ambient Music for Deep Rest", "slow ambient music;deep rest music;soft instrumental;TV OFF"),
]
# Strict three-release cycle. The current sequence continues after the last
# confirmed Brown Noise release: Original Music, White Noise, Brown Noise.
STANDARD_SOUNDS = [
    ("brown_noise", None, None),
    ("original_music", None, None),
    ("white_noise", None, None),
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
        elif kind == "original_music":
            title, tags = ORIGINAL_MUSIC_VARIANTS[(slot_number // len(STANDARD_SOUNDS)) % len(ORIGINAL_MUSIC_VARIANTS)]
        print("PRIORITY QUEUE COMPLETE: both white and brown noise are published; using an equal three-category rotation.")

    if os.environ.get("FORCE_SOUND", "").strip() == "original_music":
        if not published["brown_noise"] or not published["white_noise"]:
            raise RuntimeError(
                "Original Music cannot override the mandatory White/Brown Noise priority. "
                "Publish both noise categories with real YouTube IDs first."
            )
        kind = "original_music"
        title, tags = ORIGINAL_MUSIC_VARIANTS[(slot_number // len(STANDARD_SOUNDS)) % len(ORIGINAL_MUSIC_VARIANTS)]
        print("MANUAL PRIORITY: original music selected for this confirmed production slot.")

    # Seven-day duration experiment: each confirmed 3-hour slot cycles 1h/3h/8h/10h.
    # ChatGPT owns the cadence; this script only selects the current slot's duration.
    duration_index = slot_number % 4
    duration_hours = (1, 3, 8, 10)[duration_index]
    duration_seconds = duration_hours * 3600
    file_kind = kind.replace("_", "").title()
    display_kind = kind.replace("_", " ").title()
    filename = f"TV-OFF_{file_kind}_{date_key}_{slot_key}_{duration_hours}-Hours.mp4"

    if kind == "white_noise":
        description_intro = (
            "Need a little peace and quiet? Let this gentle, steady white noise create a calm "
            "background for sleep, rest, studying or focused work. Settle in, press play and "
            "take a moment away from the noise of the day.\n\n"
            "If you're playing this for a baby, keep the volume low and place the device well "
            "away from the baby's head and sleep space. Follow current safe-sleep guidance "
            "from your healthcare professional."
        )
        hashtags = "#WhiteNoise #SleepSounds #Relaxation #Focus #TVOFF"
        thumbnail_descriptor = f"WHITE NOISE • {duration_hours} HOUR" + ("S" if duration_hours != 1 else "")
    elif kind == "brown_noise":
        description_intro = (
            "Looking for a deeper, softer sound to settle into? This steady brown noise creates "
            "a warm, low-frequency background for sleep, reading, concentration or simply "
            "unwinding after a long day. Get comfortable, press play and enjoy a quieter moment."
        )
        hashtags = "#BrownNoise #DeepSleep #Relaxation #Focus #TVOFF"
        thumbnail_descriptor = f"BROWN NOISE • {duration_hours} HOUR" + ("S" if duration_hours != 1 else "")
    elif kind == "original_music":
        description_intro = (
            "Slow down and let the day fade into the background. This original ambient music "
            "was created for quiet evenings, restful nights, meditation or gentle focus. "
            "Let it play softly while you relax, read or drift off to sleep.\n\n"
            "Made especially for TV OFF, with an uninterrupted black screen."
        )
        hashtags = "#AmbientMusic #SleepMusic #RelaxingMusic #FocusMusic #TVOFF"
        thumbnail_descriptor = f"AMBIENT MUSIC • {duration_hours} HOUR" + ("S" if duration_hours != 1 else "")
    else:
        raise RuntimeError(f"Unsupported sound category: {kind}")

    description = (
        description_intro + "\n\n"
        "🎧 Find a comfortable volume, get settled and enjoy your time away from the noise.\n"
        f"🖤 {duration_hours} hour" + ("s" if duration_hours != 1 else "") + " of sound with a completely black screen.\n\n"
        "Subscribe to TV OFF for more peaceful sounds and original music.\n\n"
        + hashtags
    )
    publish_at = now.isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "filename", "soundscape", "title", "description", "tags",
            "publish_at", "thumbnail_descriptor", "duration_seconds"
        ])
        writer.writeheader()
        writer.writerow({
            "filename": filename,
            "soundscape": kind,
            "title": f"{title} | {duration_hours} Hour" + ("s" if duration_hours != 1 else "") + ", Black Screen — TV OFF",
            "description": description,
            "tags": ";".join([x.strip() for x in tags.split(";")] + [
                f"{duration_hours} hour" + ("s" if duration_hours != 1 else ""), "black screen", "TV OFF"
            ]),
            "publish_at": publish_at,
            "thumbnail_descriptor": thumbnail_descriptor,
            "duration_seconds": duration_seconds
        })
    print(f"3-HOUR SLOT: {slot_start.isoformat()} | {kind} | {duration_hours}h | {filename} | {publish_at}")

if __name__ == "__main__":
    main()
