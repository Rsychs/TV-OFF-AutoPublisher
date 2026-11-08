import json, os, re, subprocess, time, hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://commons.wikimedia.org/w/api.php"
ROOT = Path(os.environ.get("SOURCE_AUDIO_DIR", "generated-audio"))
ROOT.mkdir(parents=True, exist_ok=True)
UA = "TV-OFF-AutoPublisher/1.0 (licensed ambience downloader)"
QUERIES = {
 "ocean": ["ocean waves field recording", "sea waves beach ambience", "waves shore recording"],
 "forest": ["forest birds dawn ambience", "woodland birds field recording", "birds forest soundscape"],
 "river": ["flowing river stream water field recording", "forest stream water ambience", "river rapids recording"],
 "fireplace": ["fireplace crackling wood fire recording", "wood fire crackling ambience", "campfire crackling sound"],
}
APPROVED = ("public domain", "cc0", "cc-zero", "cc zero")

def api(params):
 params = {"format":"json", "maxlag":5, **params}
 req=Request(API+"?"+urlencode(params),headers={"User-Agent":UA})
 with urlopen(req,timeout=60) as r: return json.load(r)

def clean(s): return re.sub(r"<[^>]+>","",s or "").strip()

def duration(path):
 p=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)],capture_output=True,text=True,check=True)
 return float(p.stdout.strip())

def main():
 manifest={}
 for kind, queries in QUERIES.items():
  selected=None; seen=set()
  seeded = []
  for q in (["__seed__"] + queries):
   data=({"query":{"search":[{"title":t} for t in seeded]}} if q == "__seed__" else api({"action":"query","list":"search","srnamespace":6,"srsearch":q,"srlimit":50}))
   titles=[x["title"] for x in data.get("query",{}).get("search",[]) if x["title"] not in seen]
   seen.update(titles)
   print(f"SEARCH {kind}: {q} -> {len(titles)} unique candidates")
   if not titles: continue
   pages=api({"action":"query","titles":"|".join(titles),"prop":"imageinfo","iiprop":"url|mime|extmetadata"}).get("query",{}).get("pages",{})
   for page in pages.values():
    info=(page.get("imageinfo") or [{}])[0]
    if not (info.get("mime","").startswith("audio/") or info.get("mime") == "application/ogg"): continue
    meta=info.get("extmetadata",{})
    lic=clean(meta.get("LicenseShortName",{}).get("value"))
    usage=clean(meta.get("UsageTerms",{}).get("value"))
    if not any(x in (lic+" "+usage).lower() for x in APPROVED): continue
    url=info.get("url")
    if not url: continue
    ext=Path(url.split("?")[0]).suffix.lower() or ".audio"
    target=ROOT/f"{kind}_source{ext}"
    try:
     req=Request(url,headers={"User-Agent":UA})
     with urlopen(req,timeout=180) as src, open(target,"wb") as dst:
      while True:
       chunk=src.read(1024*1024)
       if not chunk: break
       dst.write(chunk)
     seconds=duration(target)
     if seconds<30: target.unlink(missing_ok=True); continue
    except Exception as e:
     print(f"SKIP {page.get('title')}: {e}"); target.unlink(missing_ok=True); continue
    title=page.get("title","")
    artist=clean(meta.get("Artist",{}).get("value")) or clean(meta.get("Credit",{}).get("value")) or "Not credited"
    selected={"file":target.name,"creator":artist,"source_url":"https://commons.wikimedia.org/wiki/"+title.replace(" ","_"),"license":lic or usage,"title":title,"duration_seconds":round(seconds,2),"sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"downloaded_at":datetime.now(timezone.utc).isoformat()}
    print(f"SELECTED {kind}: {title} | {seconds:.1f}s | {lic}")
    break
   if selected: break
   time.sleep(3)
  if not selected: raise RuntimeError(f"No suitable 30s+ Public Domain/CC0 recording found for {kind}; refusing synthetic fallback.")
  manifest[kind]=selected
 (ROOT/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
 print("Downloaded licensed field recordings and wrote manifest.")

if __name__=="__main__": main()
