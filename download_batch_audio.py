import csv
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
IA_SEARCH = "https://archive.org/advancedsearch.php"
ROOT = Path(os.environ.get("SOURCE_AUDIO_DIR", "generated-audio"))
ROOT.mkdir(parents=True, exist_ok=True)
HISTORY = Path(os.environ.get("USED_SOURCES_FILE", "used_sources.json"))
SCHEDULE = Path(os.environ.get("SCHEDULE_FILE", "backlog_schedule.csv"))
UA = "TV-OFF-AutoPublisher/3.0 (licensed ambience downloader)"
QUERIES = {
    "ocean": ["ocean waves field recording", "sea waves beach ambience", "waves shore recording"],
    "forest": ["forest birds dawn ambience", "woodland birds field recording", "birds forest sound recording"],
    "river": ["flowing river stream water field recording", "forest stream water ambience", "river rapids recording"],
    "fireplace": ["fireplace crackling wood fire recording", "wood fire crackling ambience", "campfire crackling sound"],
    "rain": ["rain field recording", "rainfall outdoor ambience", "rain on pavement recording"],
    "thunderstorm": ["thunderstorm field recording", "distant thunder and rain recording", "storm ambience field recording"],
    "wind": ["wind in trees field recording", "wind through forest recording", "strong wind nature ambience"],
}
APPROVED = ("public domain", "publicdomain/zero", "publicdomain/zero/1.0", "cc0", "cc-zero", "cc zero", "cc0 1.0")

def fetch_json(url, params=None):
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params, doseq=True)
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=90) as response:
        return json.load(response)

def clean(value):
    return re.sub(r"<[^>]+>", "", str(value or "")).strip()

def duration(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True, check=True)
    return float(p.stdout.strip())

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def download(url, target):
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=180) as source, target.open("wb") as output:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)

def approved(text):
    value = text.lower().replace("-", " ")
    return any(term in value for term in APPROVED)

def commons_candidates(query, used):
    data = fetch_json(COMMONS_API, {"format":"json","maxlag":5,"action":"query",
        "list":"search","srnamespace":6,"srsearch":query,"srlimit":50})
    titles = [x["title"] for x in data.get("query",{}).get("search",[])
              if x["title"] not in used]
    for offset in range(0, len(titles), 40):
        pages = fetch_json(COMMONS_API, {"format":"json","maxlag":5,"action":"query",
            "titles":"|".join(titles[offset:offset+40]),"prop":"imageinfo",
            "iiprop":"url|mime|extmetadata"}).get("query",{}).get("pages",{})
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            if not (info.get("mime","").startswith("audio/") or info.get("mime")=="application/ogg"):
                continue
            meta = info.get("extmetadata",{})
            lic = clean(meta.get("LicenseShortName",{}).get("value")) or clean(meta.get("UsageTerms",{}).get("value"))
            if approved(lic) and info.get("url"):
                yield {"url":info["url"],"title":page.get("title",""),
                       "source_url":"https://commons.wikimedia.org/wiki/"+page.get("title","").replace(" ","_"),
                       "creator":clean(meta.get("Artist",{}).get("value")) or clean(meta.get("Credit",{}).get("value")) or "Not credited",
                       "license":lic,"platform":"Wikimedia Commons"}

def archive_candidates(query, used):
    terms = query.replace('"','')
    data = fetch_json(IA_SEARCH, {"q":f'mediatype:audio AND ({terms})',
        "fl[]":["identifier","title","creator","licenseurl","description"],
        "rows":50,"page":1,"output":"json"})
    for item in data.get("response",{}).get("docs",[]):
        identifier = item.get("identifier","")
        lic = item.get("licenseurl","")
        title = item.get("title",identifier)
        if not identifier or identifier in used or not approved(lic):
            continue
        try:
            meta = fetch_json("https://archive.org/metadata/"+quote(identifier,safe=""))
            files = meta.get("files",[])
            candidates = []
            for f in files:
                name = f.get("name","")
                fmt = (f.get("format","")+" "+name).lower()
                if f.get("source")=="original" and (name.lower().endswith((".wav",".flac",".mp3",".ogg",".m4a"))):
                    candidates.append(f)
            candidates.sort(key=lambda f: (0 if f["name"].lower().endswith((".wav",".flac")) else 1,
                                           int(f.get("size",0) or 0)), reverse=False)
            for f in candidates:
                yield {"url":"https://archive.org/download/"+quote(identifier,safe="")+"/"+quote(f["name"],safe="/"),
                       "title":title,"source_url":"https://archive.org/details/"+identifier,
                       "creator":clean(item.get("creator")) or "Not credited",
                       "license":lic,"platform":"Internet Archive"}
        except Exception as e:
            print(f"IA metadata skip {identifier}: {e}")

def try_source(kind, candidate, used):
    suffix = Path(candidate["url"].split("?")[0]).suffix.lower()
    if suffix not in (".wav",".flac",".mp3",".ogg",".m4a"):
        suffix = ".audio"
    target = ROOT / f"{kind}_source{suffix}"
    try:
        download(candidate["url"],target)
        seconds = duration(target)
        if seconds < 30:
            target.unlink(missing_ok=True)
            return None
        return {"file":target.name,"creator":candidate["creator"],
            "source_url":candidate["source_url"],"license":candidate["license"],
            "title":candidate["title"],"platform":candidate["platform"],
            "duration_seconds":round(seconds,2),"sha256":sha256(target),
            "downloaded_at":datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        print(f"SKIP {candidate.get('title')}: {e}")
        target.unlink(missing_ok=True)
        return None

def main():
    with SCHEDULE.open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    if not rows:
        raise RuntimeError("Backlog schedule is empty")
    kinds=list(dict.fromkeys(r["soundscape"] for r in rows))
    history=json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {"used":[]}
    used=set(history.get("used",[]))
    manifest={}
    failures=[]
    for kind in kinds:
        if kind not in QUERIES:
            failures.append(f"{kind}: unsupported")
            continue
        selected=None
        for query in QUERIES[kind]:
            print(f"SEARCH {kind}: {query}")
            candidates=[]
            try:
                candidates.extend(commons_candidates(query,used))
            except Exception as e:
                print(f"Commons search unavailable: {e}")
            try:
                candidates.extend(archive_candidates(query,used))
            except Exception as e:
                print(f"Internet Archive search unavailable: {e}")
            for candidate in candidates:
                selected=try_source(kind,candidate,used)
                if selected:
                    break
            if selected:
                break
            time.sleep(1)
        if selected:
            manifest[kind]=selected
            used.add(selected["title"])
            print(f"READY {kind}: {selected['title']} | {selected['duration_seconds']}s | {selected['license']} | {selected['platform']}")
        else:
            failures.append(kind)
            print(f"NO APPROVED SOURCE FOUND: {kind}")
    if failures:
        for item in ROOT.glob("*_source.*"):
            item.unlink(missing_ok=True)
        raise RuntimeError("Batch preflight failed; no videos will be built or uploaded. Missing sources: "+", ".join(failures))
    (ROOT/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    history.setdefault("used",[])
    for item in manifest.values():
        if item["title"] not in history["used"]:
            history["used"].append(item["title"])
    HISTORY.write_text(json.dumps(history,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"ALL {len(manifest)} LICENSED SOURCES READY. Manifest written.")

if __name__=="__main__":
    main()
