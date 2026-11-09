import csv
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://freesound.org/apiv2"
TOKEN = os.environ.get("FREESOUND_API_KEY", "").strip()
KIND = os.environ.get("SOUNDSCAPE", "thunderstorm").strip().lower()
PREFERRED_SOUND_ID = os.environ.get("PREFERRED_FREESOUND_ID", "737690").strip()
ROOT = Path(os.environ.get("SOURCE_AUDIO_DIR", "generated-audio"))
ROOT.mkdir(parents=True, exist_ok=True)
HISTORY = Path(os.environ.get("USED_SOURCES_FILE", "used_sources.json"))
MIN_SOURCE_SECONDS = 90
MIN_PREVIEW_SECONDS = 20
MAX_DOWNLOAD_ATTEMPTS = 6
QUERIES = {
    "fireplace": [
        "fireplace crackling burning wood close up field recording",
        "wood fire crackling in fireplace continuous ambience",
        "cozy indoor fireplace fire burning and crackling",
    ],
    "rain": [
        "steady rain falling outdoors field recording",
        "rain on window or roof continuous field recording",
        "heavy rainfall nature ambience",
    ],
    "thunderstorm": [
        # Shorter fallback phrases avoid over-constraining Freesound's full-text search.
        "thunderstorm rain field recording",
        "rain and thunder field recording",
        "distant rolling thunder",
        "thunderstorm ambience",
        "thunderstorm",
        "thunder rain",
        "rain thunder",
    ],
    "ocean": ["ocean waves shore field recording", "gentle sea waves beach ambience", "rolling ocean surf no speech"],
    "forest": ["forest birds dawn field recording", "woodland birds ambience no speech", "night forest insects nature ambience"],
    "river": ["flowing river stream field recording", "forest stream water ambience", "river rapids nature sound"],
    "wind": ["wind in trees field recording", "wind through forest ambience", "strong wind nature recording"],
}
CC0_MARKERS = ("creativecommons.org/publicdomain/zero", "cc0", "public domain")
SYNTHETIC_NOISE = {"white_noise": "white", "brown_noise": "brown"}

def api_json(path, params):
    url = f"{API}/{path.lstrip('/')}?{urlencode(params)}"
    req = Request(url, headers={"Authorization": f"Token {TOKEN}", "User-Agent": "TV-OFF-AutoPublisher/4.0"})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=18) as response:
                return json.load(response)
        except Exception as exc:
            if attempt == 2:
                raise
            delay = (4, 10)[attempt]
            print(f"API retry {attempt + 1}/3 in {delay}s: {exc}", flush=True)
            time.sleep(delay)

def freesound_id_from_source(value):
    text = str(value or "").strip().split("?", 1)[0].rstrip("/")
    if text.isdigit():
        return text
    match = re.search(r"(?:^|/)sounds/(\\d+)$", text)
    return match.group(1) if match else None

def is_cc0(value):
    text = str(value or "").lower()
    return any(marker in text for marker in CC0_MARKERS)

def probe_seconds(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True, timeout=30
    )
    return float(result.stdout.strip())

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def download_preview(previews, target):
    url = (previews or {}).get("preview-hq-mp3") or (previews or {}).get("preview-hq-ogg")
    if not url:
        raise RuntimeError("Freesound returned no high-quality preview URL")
    req = Request(url, headers={"User-Agent": "TV-OFF-AutoPublisher/4.0"})
    with urlopen(req, timeout=20) as response, target.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)


def generate_synthetic_noise():
    color = SYNTHETIC_NOISE[KIND]
    duration = 600
    target = ROOT / f"{KIND}_original.mp3"
    print(
        f"GENERATE ORIGINAL SYNTHETIC AUDIO: {KIND} | FFmpeg anoisesrc color={color} | {duration}s",
        flush=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-f", "lavfi", "-i",
            f"anoisesrc=color={color}:amplitude=0.12:sample_rate=48000:duration={duration}",
            "-ac", "2", "-c:a", "libmp3lame", "-b:a", "192k", str(target),
        ],
        check=True, timeout=180,
    )
    actual_duration = probe_seconds(target)
    if actual_duration < duration - 1:
        target.unlink(missing_ok=True)
        raise RuntimeError(
            f"Synthetic {KIND} audio is too short: {actual_duration:.1f}s"
        )
    selected = {
        "file": target.name,
        "creator": "TV OFF (original synthetic audio)",
        "source_url": "Original audio generated locally by TV OFF; no external recording.",
        "license": "Original synthetic audio generated by TV OFF with FFmpeg; no third-party sample used (CC0 not applicable).",
        "title": f"Original {KIND.replace('_', ' ').title()}",
        "platform": "TV OFF / FFmpeg",
        "audio_type": "synthetic",
        "duration_seconds": round(actual_duration, 2),
        "sha256": digest(target),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
    (ROOT / "manifest.json").write_text(
        json.dumps({KIND: selected}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        f"SYNTHETIC AUDIO PREFLIGHT PASSED: {KIND} | {actual_duration:.1f}s | no external source",
        flush=True,
    )

def main():
    if KIND in SYNTHETIC_NOISE:
        generate_synthetic_noise()
        return
    if not TOKEN:
        raise RuntimeError("FREESOUND_API_KEY is missing. Stop before searching.")
    if KIND not in QUERIES:
        raise RuntimeError(f"Unsupported soundscape: {KIND}")

    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {"used": []}
    used = set(history.get("used", []))

    # Keep one shared no-repeat pool across long videos and Shorts.
    repository_root = Path(__file__).resolve().parent
    other_history_files = (
        repository_root / "used_sources.json",
        repository_root / "shorts_used_sources.json",
    )
    for other_history_path in other_history_files:
        if other_history_path.resolve() == HISTORY.resolve() or not other_history_path.is_file():
            continue
        try:
            other_history = json.loads(other_history_path.read_text(encoding="utf-8"))
            other_used = other_history.get("used", [])
            if not isinstance(other_used, list):
                raise ValueError("the 'used' field is not a list")
            used.update(source for source in other_used if isinstance(source, str))
        except Exception as exc:
            raise RuntimeError(
                f"Cannot safely read cross-format Freesound history "
                f"{other_history_path}: {exc}"
            ) from exc
    used_ids = {
        source_id
        for source in used
        if (source_id := freesound_id_from_source(source))
    }
    print(
        f"CROSS-FORMAT SOURCE DEDUPLICATION: {len(used)} history entries and "
        f"{len(used_ids)} normalized Freesound ID(s) loaded.",
        flush=True,
    )
    seen = set()
    selected = None
    download_attempts = 0
    preferred_sound = None
    if KIND == "thunderstorm" and PREFERRED_SOUND_ID:
        try:
            preferred_sound = api_json(f"sounds/{PREFERRED_SOUND_ID}/", {
                "fields": "id,name,username,duration,license,url,avg_rating,num_downloads,previews",
            })
            print(f"PREFERRED FREESOUND SOURCE FOUND: {PREFERRED_SOUND_ID}", flush=True)
        except Exception as exc:
            print(f"PREFERRED SOURCE LOOKUP FAILED; falling back to CC0 search: {exc}", flush=True)

    for query in QUERIES[KIND]:
        print(f"FREESOUND SEARCH: {query}", flush=True)
        result = api_json("search/text/", {
            "query": query,
            "filter": 'license:"Creative Commons 0" duration:[90 TO *]',
            "sort": "rating_desc",
            "page_size": 25,
            "fields": "id,name,username,duration,license,url,avg_rating,num_downloads,previews",
        })
        sounds = result.get("results", [])
        if preferred_sound is not None:
            # Add the preferred source as an extra candidate without replacing search results.
            sounds = [preferred_sound] + sounds
            preferred_sound = None
        print(f"FREESOUND RESULTS: {len(sounds)} (including preferred source when available)", flush=True)
        for sound in sounds:
            sid = sound.get("id")
            source_url = f"https://freesound.org/sounds/{sid}/"
            if not sid or sid in seen:
                continue
            seen.add(sid)
            if not is_cc0(sound.get("license")):
                print(f"SKIP {sid}: license not verified as CC0", flush=True)
                continue
            if source_url in used or str(sid) in used_ids:
                print(f"SKIP {sid}: source already used (normalized Freesound ID)", flush=True)
                continue
            original_duration = float(sound.get("duration") or 0)
            if original_duration < MIN_SOURCE_SECONDS:
                continue

            download_attempts += 1
            if download_attempts > MAX_DOWNLOAD_ATTEMPTS:
                break
            target = ROOT / f"{KIND}_source_{sid}.mp3"
            try:
                print(f"DOWNLOAD HIGH-QUALITY PREVIEW: {sid} | {sound.get('name')} | {original_duration:.1f}s", flush=True)
                download_preview(sound.get("previews"), target)
                actual_duration = probe_seconds(target)
                if actual_duration < MIN_PREVIEW_SECONDS:
                    raise RuntimeError(f"Downloaded preview too short: {actual_duration:.1f}s")
                selected = {
                    "file": target.name,
                    "creator": sound.get("username") or "Not credited",
                    "source_url": source_url,
                    "license": "CC0 1.0 (verified by Freesound API; high-quality Freesound preview)",
                    "title": sound.get("name") or f"Freesound {sid}",
                    "platform": "Freesound",
                    "freesound_id": sid,
                    "duration_seconds": round(actual_duration, 2),
                    "sha256": digest(target),
                    "downloaded_at": datetime.now(timezone.utc).isoformat(),
                }
                print(f"SELECTED: {selected['title']} | {actual_duration:.1f}s | CC0 high-quality preview", flush=True)
                break
            except Exception as exc:
                target.unlink(missing_ok=True)
                print(f"REJECT {sid}: {exc}", flush=True)

        if selected:
            break

    if not selected:
        raise RuntimeError(f"No usable CC0 {KIND} recording found after {len(QUERIES[KIND])} focused Freesound searches.")

    manifest = {KIND: selected}
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    # A source is marked used only after YouTube confirms a publication.
    print("AUDIO PREFLIGHT PASSED: exactly one source is ready.", flush=True)

if __name__ == "__main__":
    main()
