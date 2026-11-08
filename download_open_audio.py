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

API = "https://commons.wikimedia.org/w/api.php"
ROOT = Path(os.environ.get("SOURCE_AUDIO_DIR", "generated-audio"))
ROOT.mkdir(parents=True, exist_ok=True)
HISTORY = Path(os.environ.get("USED_SOURCES_FILE", "used_sources.json"))
SCHEDULE = Path(os.environ.get("SCHEDULE_FILE", "schedule.csv"))
UA = "TV-OFF-AutoPublisher/2.0 (licensed ambience downloader)"
QUERIES = {
    "ocean": ["ocean waves field recording", "sea waves beach ambience", "waves shore recording"],
    "forest": ["forest birds dawn ambience", "woodland birds field recording", "birds forest sound recording"],
    "river": ["flowing river stream water field recording", "forest stream water ambience", "river rapids recording"],
    "fireplace": ["fireplace crackling wood fire recording", "wood fire crackling ambience", "campfire crackling sound"],
    "rain": ["rain field recording", "rainfall outdoor ambience", "rain on pavement recording"],
    "thunderstorm": ["thunderstorm field recording", "distant thunder and rain recording", "storm ambience field recording"],
    "wind": ["wind in trees field recording", "wind through forest recording", "strong wind nature ambience"],
}
APPROVED = ("public domain", "cc0", "cc-zero", "cc zero")

def api(params):
    params = {"format": "json", "maxlag": 5, **params}
    req = Request(API + "?" + urlencode(params), headers={"User-Agent": UA})
    with urlopen(req, timeout=60) as response:
        return json.load(response)

def clean(value):
    return re.sub(r"<[^>]+>", "", value or "").strip()

def duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    return float(result.stdout.strip())

def main():
    import csv
    with SCHEDULE.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one daily schedule row, found {len(rows)}")
    kind = rows[0]["soundscape"]
    if kind not in QUERIES:
        raise RuntimeError(f"Unsupported soundscape: {kind}")

    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {"used": []}
    used = set(history.get("used", []))
    selected = None
    seen = set()

    for query in QUERIES[kind]:
        data = api({"action": "query", "list": "search", "srnamespace": 6,
                    "srsearch": query, "srlimit": 50})
        titles = [item["title"] for item in data.get("query", {}).get("search", [])
                  if item["title"] not in seen and item["title"] not in used]
        seen.update(titles)
        print(f"SEARCH {kind}: {query} -> {len(titles)} unused candidates")
        if not titles:
            continue

        for offset in range(0, len(titles), 40):
            batch = titles[offset:offset + 40]
            pages = api({"action": "query", "titles": "|".join(batch),
                         "prop": "imageinfo", "iiprop": "url|mime|extmetadata"}).get("query", {}).get("pages", {})
            for page in pages.values():
                info = (page.get("imageinfo") or [{}])[0]
                mime = info.get("mime", "")
                if not (mime.startswith("audio/") or mime == "application/ogg"):
                    continue
                metadata = info.get("extmetadata", {})
                license_name = clean(metadata.get("LicenseShortName", {}).get("value"))
                usage = clean(metadata.get("UsageTerms", {}).get("value"))
                if not any(term in (license_name + " " + usage).lower() for term in APPROVED):
                    continue
                url = info.get("url")
                if not url:
                    continue
                ext = Path(url.split("?")[0]).suffix.lower() or ".audio"
                target = ROOT / f"{kind}_source{ext}"
                try:
                    request = Request(url, headers={"User-Agent": UA})
                    with urlopen(request, timeout=180) as source, target.open("wb") as output:
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            output.write(chunk)
                    seconds = duration(target)
                    if seconds < 30:
                        target.unlink(missing_ok=True)
                        continue
                except Exception as error:
                    print(f"SKIP {page.get('title')}: {error}")
                    target.unlink(missing_ok=True)
                    continue

                title = page.get("title", "")
                creator = (clean(metadata.get("Artist", {}).get("value"))
                           or clean(metadata.get("Credit", {}).get("value"))
                           or "Not credited")
                selected = {
                    "file": target.name, "creator": creator,
                    "source_url": "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_"),
                    "license": license_name or usage, "title": title,
                    "duration_seconds": round(seconds, 2),
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "downloaded_at": datetime.now(timezone.utc).isoformat()
                }
                print(f"SELECTED {kind}: {title} | {seconds:.1f}s | {license_name}")
                break
            if selected:
                break
        if selected:
            break
        time.sleep(2)

    if not selected:
        raise RuntimeError(f"No unused 30s+ Public Domain/CC0 recording found for {kind}; refusing synthetic or repeated fallback.")

    (ROOT / "manifest.json").write_text(
        json.dumps({kind: selected}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    history.setdefault("used", []).append(selected["title"])
    HISTORY.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"LICENSED SOURCE READY: {selected['source_url']}")

if __name__ == "__main__":
    main()
