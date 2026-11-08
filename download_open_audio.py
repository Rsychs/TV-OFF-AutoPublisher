import json
import os
import re
import subprocess
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://commons.wikimedia.org/w/api.php"
ROOT = Path(os.environ.get("SOURCE_AUDIO_DIR", "generated-audio"))
ROOT.mkdir(parents=True, exist_ok=True)
USER_AGENT = "TV-OFF-AutoPublisher/1.0 (licensed ambience downloader)"
QUERIES = {
    "rain": ["rain filetype:audio", "rainfall filetype:audio", "rain storm sound filetype:audio"],
    "fireplace": ["fire crackling filetype:audio", "fireplace sound filetype:audio"],
    "thunderstorm": ["thunderstorm filetype:audio", "thunder rumble filetype:audio"],
    "wind": ["wind in trees filetype:audio", "wind blowing filetype:audio"],
}
APPROVED = ("public domain", "cc0", "cc-zero", "cc zero")

def api(params):
    params = {"format": "json", "maxlag": 5, **params}
    req = Request(API + "?" + urlencode(params), headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=45) as response:
        return json.load(response)

def duration(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True, check=True)
    return float(p.stdout.strip())

def clean(value):
    return re.sub(r"<[^>]+>", "", value or "").strip()

def search_titles(query):
    data = api({"action": "query", "list": "search", "srnamespace": 6,
                "srsearch": query, "srlimit": 50})
    return [x["title"] for x in data.get("query", {}).get("search", [])]

def get_page(title):
    data = api({"action": "query", "titles": title, "prop": "imageinfo",
                "iiprop": "url|mime|size|extmetadata", "iiextmetadatafilter":
                "LicenseShortName|UsageTerms|Artist|Credit"})
    pages = data.get("query", {}).get("pages", {})
    return next(iter(pages.values()), {})

def main():
    manifest = {}
    for kind, queries in QUERIES.items():
        selected = None
        seen = set()
        for query in queries:
            titles = search_titles(query)
            print(f"SEARCH {kind}: {query} -> {len(titles)} results")
            for title in titles:
                if title in seen:
                    continue
                seen.add(title)
                page = get_page(title)
                info = (page.get("imageinfo") or [{}])[0]
                if not info.get("mime", "").startswith("audio/"):
                    continue
                meta = info.get("extmetadata", {})
                license_name = clean(meta.get("LicenseShortName", {}).get("value"))
                usage = clean(meta.get("UsageTerms", {}).get("value"))
                license_text = (license_name + " " + usage).lower()
                if not any(x in license_text for x in APPROVED):
                    continue
                url = info.get("url")
                if not url:
                    continue
                ext = Path(url.split("?")[0]).suffix.lower() or ".audio"
                target = ROOT / f"{kind}_source{ext}"
                try:
                    req = Request(url, headers={"User-Agent": USER_AGENT})
                    with urlopen(req, timeout=180) as src, open(target, "wb") as dst:
                        while True:
                            chunk = src.read(1024 * 1024)
                            if not chunk:
                                break
                            dst.write(chunk)
                    seconds = duration(target)
                    if seconds < 30:
                        target.unlink(missing_ok=True)
                        continue
                except Exception as exc:
                    print(f"SKIP {title}: {exc}")
                    target.unlink(missing_ok=True)
                    continue
                artist = clean(meta.get("Artist", {}).get("value")) or clean(meta.get("Credit", {}).get("value")) or "Not credited"
                selected = {
                    "file": target.name, "creator": artist,
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
            time.sleep(1)
        if not selected:
            raise RuntimeError(f"No suitable 30s+ Public Domain/CC0 recording found for {kind}; refusing synthetic fallback.")
        manifest[kind] = selected
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Downloaded licensed real-world recordings and wrote manifest.")

if __name__ == "__main__":
    main()
