import csv
import os
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get("SCHEDULE_FILE", ROOT / "daily_schedule.csv"))
TZ = ZoneInfo("Europe/Riga")
SOUNDS = [
    ("ocean", "Ocean Waves for Sleep & Relaxation", "OceanWaves;SeaSounds;SleepSounds"),
    ("forest", "Forest Birds at Dawn", "ForestBirds;Birdsong;NatureSounds"),
    ("river", "Flowing River Sounds for Sleep & Focus", "RiverSounds;FlowingWater;NatureSounds"),
    ("fireplace", "Fireplace Crackling for Sleep & Relaxation", "FireplaceSounds;FireCrackling;SleepSounds"),
    ("rain", "Rain Sounds for Sleep & Focus", "RainSounds;RainAmbience;SleepSounds"),
    ("thunderstorm", "Distant Thunderstorm & Rain Sounds", "Thunderstorm;RainAndThunder;StormSounds"),
    ("wind", "Wind in the Trees | Nature Sounds", "WindSounds;WindInTrees;NatureSounds"),
]

def main():
    now = datetime.now(TZ)
    publish_day = now.date()
    if now.time() >= time(18, 0):
        publish_day += timedelta(days=1)
    # Rotate predictably through all seven soundscapes: Monday=0 through Sunday=6.
    kind, title, tags = SOUNDS[publish_day.weekday()]
    date_key = publish_day.strftime("%Y%m%d")
    filename = f"TV-OFF_{kind.title()}_{date_key}_10-Hours.mp4"
    description = (
        f"10 hours of real {kind} ambience from a newly selected field recording, "
        "smoothly looped for uninterrupted listening. Completely black screen throughout.\n\n"
        "Original recording: {creator}\nSource: {source_url}\nLicense: {license}\n\n"
        "🎧 Keep the volume comfortable.\n🖤 10 hours • Black screen • No visuals\n\n"
        "Subscribe to TV OFF for more long-form ambient soundscapes.\n\n"
        "#SleepSounds #NatureSounds #BlackScreen #TVOff"
    )
    # Publish immediately after the upload completes; do not schedule for 18:00.
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
            "thumbnail_descriptor": "10 HOURS • BLACK SCREEN"
        })
    print(f"DAILY SCHEDULE: {kind} | {filename} | {publish_at}")

if __name__ == "__main__":
    main()
