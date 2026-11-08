import csv
import hashlib
import json
import os
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
        "heavy rain thunderstorm continuous field recording distant rolling thunder",
        "heavy rain and rolling thunder ambience no speech",
        "steady rain with distant thunderstorm field recording",
    ],
}
CC0_MARKERS = ("creativecommons.org/publicdomain/zero", "cc0", "public domain")

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

def main():
    if not TOKEN:
        raise RuntimeError("FREESOUND_API_KEY is missing. Stop before searching.")
    if KIND not in QUERIES:
        raise RuntimeError(f"Unsupported soundscape: {KIND}")

    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {"used": []}
    used = set(history.get("used", []))
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
        if preferred_sound is not None:
            # Try the explicitly selected recording immediately; do not wait for search first.
            sounds = [preferred_sound]
            preferred_sound = None
        else:
            result = api_json("search/text/", {
                "query": query,
                "filter": 'license:"Creative Commons 0" duration:[90 TO *]',
                "sort": "rating_desc",
                "page_size": 15,
                "fields": "id,name,username,duration,license,url,avg_rating,num_downloads,previews",
            })
            sounds = result.get("results", [])
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
            if source_url in used:
                print(f"SKIP {sid}: source already used", flush=True)
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
    history.setdefault("used", [])
    history["used"].append(selected["source_url"])
    HISTORY.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    print("AUDIO PREFLIGHT PASSED: exactly one source is ready.", flush=True)

if __name__ == "__main__":
    main()
