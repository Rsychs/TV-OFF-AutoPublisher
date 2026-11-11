#!/usr/bin/env python3
"""Render a continuous real-footage TV OFF Short with original synthesized music."""
from __future__ import annotations
import json, os, re, subprocess, tempfile
from pathlib import Path
from urllib.parse import urlparse
import numpy as np
import requests
from scipy.io.wavfile import write

OUT = Path("output"); OUT.mkdir(exist_ok=True)
VIDEO = OUT / "TV_OFF_Midnight_Blue.mp4"
AUDIO = OUT / "original_ambient.wav"
SOURCE = Path(tempfile.gettempdir()) / "tv_off_source.mp4"
DEFAULT_PAGE = "https://commons.wikimedia.org/wiki/File:Radevormwald_-_Raindrops_on_a_window_04_(oT)_ies.ogv"

def safe_page(value: str) -> str:
    p = urlparse(value)
    if p.scheme != "https" or p.hostname not in {"commons.wikimedia.org", "www.pexels.com", "pexels.com"}:
        raise SystemExit("Only HTTPS Wikimedia Commons or Pexels source pages are accepted")
    return value

def resolve_source_page(page: str) -> tuple[str, str, str]:
    host = urlparse(page).hostname
    if host == "commons.wikimedia.org":
        title = page.split("/wiki/", 1)[-1]
        if not title.startswith("File:"):
            raise SystemExit("Wikimedia URL must identify a File page")
        api = "https://commons.wikimedia.org/w/api.php"
        r = requests.get(api, params={"action":"query","titles":title,"prop":"imageinfo","iiprop":"url|extmetadata","format":"json"}, headers={"User-Agent":"TV-OFF-CloudStudio/1.0 (video production)"}, timeout=(20,45))
        r.raise_for_status()
        pages = r.json().get("query",{}).get("pages",{})
        item = next(iter(pages.values()), {})
        info = (item.get("imageinfo") or [{}])[0]
        url = info.get("url","")
        if not url.startswith("https://upload.wikimedia.org/"):
            raise SystemExit("Wikimedia API did not return an approved direct media URL")
        meta = info.get("extmetadata",{})
        creator = re.sub("<[^>]+>", "", meta.get("Artist",{}).get("value","Wikimedia Commons contributor"))[:160]
        license_name = re.sub("<[^>]+>", "", meta.get("LicenseShortName",{}).get("value","CC BY-SA 3.0"))[:100]
        return url, creator, license_name
    r = requests.get(page, timeout=(20,45), headers={"User-Agent":"Mozilla/5.0 TVOFFCloudStudio/1.0"})
    r.raise_for_status()
    if urlparse(r.url).hostname not in {"pexels.com", "www.pexels.com"}:
        raise SystemExit("Pexels page redirected to an unexpected host")
    html = r.text
    candidates = re.findall(r'https?:\\?/\\?/videos\\.pexels\\.com\\/video-files\\/[^"\\\\ ]+?\\.mp4(?:\\?[^"\\\\ ]*)?', html)
    candidates += re.findall(r'https://videos\\.pexels\\.com/video-files/[^"\\\\ ]+?\\.mp4(?:\\?[^"\\\\ ]*)?', html)
    cleaned=[]
    for u in candidates:
        u=u.replace("\\/", "/").replace("&amp;", "&")
        if u.startswith("https://videos.pexels.com/") and u not in cleaned: cleaned.append(u)
    if not cleaned:
        raise SystemExit("Pexels page did not expose a direct MP4 variant")
    creator="Pexels creator"
    m=re.search(r"<meta[^>]+name=['\\\"]author['\\\"][^>]+content=['\\\"]([^'\\\"]+)",html,re.I)
    if m: creator=m.group(1)[:120]
    return cleaned[0], creator, "Pexels License"


def download_source(url: str) -> None:
    p=urlparse(url)
    if p.scheme!="https" or p.hostname not in {"videos.pexels.com", "upload.wikimedia.org"}:
        raise SystemExit("Resolved source is not on an approved Pexels or Wikimedia media host")
    # Wikimedia imageinfo URLs may carry tracking query parameters that trigger CDN denials.
    clean_url = url.split("?", 1)[0] if p.hostname == "upload.wikimedia.org" else url
    headers = {"User-Agent": "Mozilla/5.0 (compatible; TV-OFF-CloudStudio/1.0)", "Accept": "video/*,application/octet-stream,*/*"}
    if p.hostname == "upload.wikimedia.org":
        headers["Referer"] = "https://commons.wikimedia.org/"
    with requests.get(clean_url,headers=headers,stream=True,timeout=(20,90)) as response:
        response.raise_for_status()
        if urlparse(response.url).hostname not in {"videos.pexels.com", "upload.wikimedia.org"}:
            raise SystemExit("Video download redirected away from approved media hosts")
        total=0
        with SOURCE.open("wb") as target:
            for chunk in response.iter_content(1024*1024):
                if not chunk: continue
                total+=len(chunk)
                if total>500*1024*1024: raise SystemExit("Source exceeds 500 MB")
                target.write(chunk)
    if SOURCE.stat().st_size<100_000: raise SystemExit("Downloaded source is unexpectedly small")

def create_original_ambient(duration: int) -> None:
    sr=48000; t=np.arange(sr*duration,dtype=np.float64)/sr; audio=np.zeros_like(t)
    chords=[[146.83,174.61,220.00,293.66],[116.54,146.83,174.61,233.08],[174.61,220.00,261.63,349.23],[130.81,164.81,196.00,261.63]]
    segment=duration/len(chords)
    for i,freqs in enumerate(chords):
        start,end=i*segment,(i+1)*segment; mask=(t>=start)&(t<end); local=t[mask]-start
        fade=np.minimum(1,local/2.5)*np.minimum(1,(segment-local)/2.5); pad=np.zeros_like(local)
        for v,hz in enumerate(freqs):
            pad+=np.sin(2*np.pi*hz*local+v*.31)/(v+1)
            pad+=.12*np.sin(2*np.pi*hz*2.002*local+v*.17)/(v+1)
        audio[mask]+=.12*pad*fade
    audio+=.008*np.sin(2*np.pi*523.25*t+.15*np.sin(2*np.pi*.045*t))
    audio*=np.minimum(1,t/2)*np.minimum(1,(duration-t)/3)
    audio=(audio/max(float(np.max(np.abs(audio))),1e-9)*.68).astype(np.float32)
    write(str(AUDIO),sr,(np.column_stack((audio,np.roll(audio,700)))*32767).astype(np.int16))

def main():
    page=safe_page(os.environ.get("SOURCE_PAGE_URL",DEFAULT_PAGE).strip())
    title=os.environ.get("VIDEO_TITLE","Midnight Blue").strip()[:80] or "Midnight Blue"
    duration=int(os.environ.get("DURATION_SECONDS","30"))
    if duration not in (20,30,40,50,60): raise SystemExit("Duration must be 20–60 seconds")
    source_url,creator,license_name=resolve_source_page(page)
    download_source(source_url)
    create_original_ambient(duration)
    probe=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(SOURCE)],check=True,capture_output=True,text=True)
    source_duration=float(probe.stdout.strip())
    if source_duration<duration: raise SystemExit(f"Source is only {source_duration:.1f}s; requested {duration}s")
    vf="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,eq=contrast=1.06:saturation=1.08:brightness=-0.015,unsharp=5:5:0.35:3:3:0.0,format=yuv420p"
    cmd=["ffmpeg","-y","-i",str(SOURCE),"-i",str(AUDIO),"-t",str(duration),"-vf",vf,"-af",f"afade=t=in:st=0:d=1.8,afade=t=out:st={max(0,duration-2.8)}:d=2.8","-map","0:v:0","-map","1:a:0","-c:v","libx264","-preset","medium","-crf","19","-profile:v","high","-pix_fmt","yuv420p","-r","30","-c:a","aac","-b:a","192k","-movflags","+faststart",str(VIDEO)]
    subprocess.run(cmd,check=True)
    outprobe=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(VIDEO)],check=True,capture_output=True,text=True)
    actual=float(outprobe.stdout.strip())
    if abs(actual-duration)>.5: raise SystemExit(f"Duration mismatch: {actual}")
    manifest={"title":title,"duration_seconds":duration,"format":"MP4 / H.264 / AAC","resolution":"1080x1920","fps":30,"visual_source_page":page,"visual_creator":creator,"music":"Original TV OFF ambient synthesis; no samples or third-party recordings","license":license_name,"required_attribution":creator,"source_page_retained":page,"published":False}
    (OUT/"production.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(f"Rendered and validated {VIDEO} ({actual:.2f}s)")

if __name__=="__main__": main()
