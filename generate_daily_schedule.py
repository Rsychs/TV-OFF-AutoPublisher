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
WHITE_NOISE = ("white_noise", "White Noise for Deep Sleep & Focus", "white noise for sleep;white noise for focus;WhiteNoise;SleepSounds;FocusSounds")
BROWN_NOISE = ("brown_noise", "Brown Noise for Deep Sleep & Relaxation", "brown noise for sleep;brown noise for relaxation;BrownNoise;SleepSounds;RelaxationSounds")
STANDARD_SOUNDS = [
    ("ocean", "Ocean Waves for Deep Sleep & Relaxation", "ocean waves for sleep;sea sounds;OceanWaves;SleepSounds"),
    ("forest", "Forest Birds for Relaxation & Focus", "forest birds;birdsong for relaxation;ForestBirds;NatureSounds"),
    ("river", "Flowing River Sounds for Sleep & Relaxation", "river sounds for sleep;flowing water sounds;RiverSounds;NatureSounds"),
    ("fireplace", "Fireplace Sounds for Sleep & Cozy Ambience", "fireplace sounds for sleep;fire crackling;FireplaceSounds;SleepSounds"),
    ("rain", "Rain Sounds for Deep Sleep & Relaxation", "rain sounds for sleep;relaxing rain;RainSounds;SleepSounds"),
    ("thunderstorm", "Thunderstorm Sounds for Sleep | Rain & Distant Thunder", "thunderstorm sounds for sleep;rain and thunder;Thunderstorm;StormSounds"),
    ("wind", "Wind Sounds in Trees for Relaxation & Focus", "wind sounds in trees;wind ambience;WindSounds;NatureSounds"),
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
    normalized_names = [
        re.sub(r"[^a-z0-9]", "", str(name).lower())
        for name in state
    ]
    return {
        "white_noise": any("whitenoise" in name for name in normalized_names),
        "brown_noise": any("brownnoise" in name for name in normalized_names),
    }

def main():
    now = datetime.now(TZ)
    slot_hour = (now.hour // 3) * 3
    slot_start = now.replace(hour=slot_hour, minute=0, second=0, microsecond=0)
    date_key = slot_start.strftime("%Y%m%d")
    slot_key = slot_start.strftime("%H")
    published = published_soundscapes()
    if not published["white_noise"]:
        kind, title, tags = WHITE_NOISE
        print("PRIORITY QUEUE: white noise is not yet published; selecting it first.")
    elif not published["brown_noise"]:
        kind, title, tags = BROWN_NOISE
        print("PRIORITY QUEUE: brown noise is not yet published; selecting it next.")
    else:
        slot_number = int(slot_start.timestamp() // (3 * 3600))
        kind, title, tags = STANDARD_SOUNDS[slot_number % len(STANDARD_SOUNDS)]
        print("PRIORITY QUEUE COMPLETE: both white and brown noise are published; using standard rotation.")
    file_kind = kind.replace("_", "").title()
    display_kind = kind.replace("_", " ").title()
    filename = f"TV-OFF_{file_kind}_{date_key}_{slot_key}_10-Hours.mp4"

    if kind in {"white_noise", "brown_noise"}:
        description_intro = (
            f"10 hours of steady, original {display_kind.lower()} sound for sleep, relaxation and focus. "
            "A continuous sound bed with a completely black screen for overnight listening."
        )
        noise_hashtag = "#WhiteNoise" if kind == "white_noise" else "#BrownNoise"
        hashtags = f"{noise_hashtag} #SleepSounds #FocusSounds #BlackScreen #TVOff"
        thumbnail_descriptor = f"{display_kind.upper()} • 10 HOURS"
    else:
        description_intro = (
            f"10 hours of {kind} nature sounds for sleep and relaxation, using a newly selected field recording. "
            "The audio is smoothly looped and the screen stays completely black throughout."
        )
        hashtags = "#SleepSounds #NatureSounds #BlackScreen #TVOff"
        thumbnail_descriptor = "10 HOURS • BLACK SCREEN"

    source_label = "Original audio" if kind in {"white_noise", "brown_noise"} else "Original recording"
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
