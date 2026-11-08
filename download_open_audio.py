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
USER_AGENT = "TV-OFF-AutoPublisher/1.0 (licensed ambience downloader)"
QUERIES = {
    "rain": ["rain field recording", "rain falling nature sound", "rainstorm sound recording"],
    "fireplace": ["fire crackling recording", "wood fire burning sound"],
    "thunderstorm": ["thunderstorm rain field recording", "thunder rumble recording"],
    "wind": ["wind blowing trees field recording", "wind nature sound recording"],
}

def get_json(params):
    url = API + "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=45) as response:
        return json.load(response)

def duration(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True, check=True)
    return float(p.stdout.strip())

def clean(value):
    return re.sub(r"<[^>]+>", "", value or "").strip()

def candidates(query):
    data = get_json({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query + " filetype:audio",
        "gsrnamespace": 6, "gsrlimit": 30,
        "prop": "imageinfo", "iiprop": "url|extmetadata"
    })
    pages = data.get("query", {}).get("pages", {})
    return list(pages.values())

def main():
    manifest = {}
    for kind, queries in QUERIES.items():
        selected = None
        for query in queries:
            for page in candidates(query):
                info = (page.get("imageinfo") or [{}])[0]
                meta = info.get("extmetadata", {})
                license_name = clean(meta.get("LicenseShortName", {}).get("value"))
                usage = clean(meta.get("UsageTerms", {}).get("value"))
                if not any(x in (license_name + " " + usage).lower()
                           for x in ("public domain", "cc0", "cc zero")):
                    continue
                url = info.get("url")
                if not url or not url.lower().endswith((".ogg", ".oga", ".wav", ".mp3", ".flac", ".opus")):
                    continue
                title = page.get("title", "Wikimedia Commons audio")
                target = ROOT / f"{kind}_source{Path(url).suffix.lower()}"
                try:
                    req = Request(url, headers={"User-Agent": USER_AGENT})
                    with urlopen(req, timeout=120) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    seconds = duration(target)
                    if seconds < 30:
                        target.unlink(missing_ok=True)
                        continue
                except Exception:
                    target.unlink(missing_ok=True)
                    continue
                selected = {
                    "file": target.name, "creator": clean(meta.get("Artist", {}).get("value")) or "Author credited on Wikimedia Commons",
                    "source_url": "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_"),
                    "license": license_name or usage,
                    "title": title, "duration_seconds": round(seconds, 2),
                    "downloaded_at": datetime.now(timezone.utc).isoformat()
                }
                print(f"SELECTED {kind}: {title} | {seconds:.1f}s | {license_name}")
                break
            if selected:
                break
            time.sleep(1)
        if not selected:
            raise RuntimeError(f"No suitable 30s+ Public Domain/CC0 recording found for {kind}; refusing synthetic fallback.")
        manifest[kind] = selected
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Downloaded licensed real-world recordings and wrote manifest.")

if __name__ == "__main__":
    main()
