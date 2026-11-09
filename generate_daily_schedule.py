import csv
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get("SCHEDULE_FILE", ROOT / "daily_schedule.csv"))
TZ = ZoneInfo("Europe/Riga")

# Top-tier categories have 2x rotation weight; standard nature categories remain in rotation.
TOP_SOUNDS = [
    ("white_noise", "White Noise for Deep Sleep & Focus", "WhiteNoise;SleepSounds;FocusSounds"),
    ("brown_noise", "Brown Noise for Deep Sleep & Relaxation", "BrownNoise;SleepSounds;RelaxationSounds"),
]
STANDARD_SOUNDS = [
    ("ocean", "Ocean Waves for Sleep & Relaxation", "OceanWaves;SeaSounds;SleepSounds"),
    ("forest", "Forest Birds at Dawn", "ForestBirds;Birdsong;NatureSounds"),
    ("river", "Flowing River Sounds for Sleep & Focus", "RiverSounds;FlowingWater;NatureSounds"),
    ("fireplace", "Fireplace Crackling for Sleep & Relaxation", "FireplaceSounds;FireCrackling;SleepSounds"),
    ("rain", "Rain Sounds for Sleep & Focus", "RainSounds;RainAmbience;SleepSounds"),
    ("thunderstorm", "Distant Thunderstorm & Rain Sounds", "Thunderstorm;RainAndThunder;StormSounds"),
    ("wind", "Wind in the Trees | Nature Sounds", "WindSounds;WindInTrees;NatureSounds"),
]
SOUNDS = [TOP_SOUNDS[0], TOP_SOUNDS[1], TOP_SOUNDS[0], TOP_SOUNDS[1], *STANDARD_SOUNDS]

def main():
    now = datetime.now(TZ)
    slot_hour = (now.hour // 3) * 3
    slot_start = now.replace(hour=slot_hour, minute=0, second=0, microsecond=0)
    date_key = slot_start.strftime("%Y%m%d")
    slot_key = slot_start.strftime("%H")
    # Rotate through a weighted 11-slot cycle: each top-tier noise appears twice.
    slot_number = int(slot_start.timestamp() // (3 * 3600))
    kind, title, tags = SOUNDS[slot_number % len(SOUNDS)]
    file_kind = kind.replace("_", "").title()
    display_kind = kind.replace("_", " ").title()
    filename = f"TV-OFF_{file_kind}_{date_key}_{slot_key}_10-Hours.mp4"

    if kind in {"white_noise", "brown_noise"}:
        description_intro = (
            f"10 hours of original digitally generated {display_kind.lower()} "
            "for sleep, relaxation and focus. Smooth, continuous audio with a completely black screen."
        )
        noise_hashtag = "#WhiteNoise" if kind == "white_noise" else "#BrownNoise"
        hashtags = f"{noise_hashtag} #SleepSounds #FocusSounds #BlackScreen #TVOff"
        thumbnail_descriptor = f"{display_kind.upper()} • 10 HOURS"
    else:
        description_intro = (
            f"10 hours of real {kind} ambience from a newly selected field recording, "
            "smoothly looped for uninterrupted listening. Completely black screen throughout."
        )
        hashtags = "#SleepSounds #NatureSounds #BlackScreen #TVOff"
        thumbnail_descriptor = "10 HOURS • BLACK SCREEN"

    description = (
        description_intro + "\n\n"
        "Original recording: {creator}\nSource: {source_url}\nLicense: {license}\n\n"
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
