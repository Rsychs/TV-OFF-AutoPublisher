#!/usr/bin/env python3
"""Assemble distinct, verified ACE-Step sections; never loop or time-stretch."""
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path

HOURS = (1, 3, 8, 10)
XFADE = 2.0

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def duration(path):
    p = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",str(path)],
        check=True,capture_output=True,text=True,timeout=60)
    return float(p.stdout.strip())

def read_sections(root):
    result=[]
    for mp in sorted(root.glob("section-*/ace_step_smoke_result.json")):
        m=json.loads(mp.read_text(encoding="utf-8"))
        if m.get("status")!="ok" or m.get("provider")!="ACE-Step-1.5" or m.get("publishing_enabled") is not True or m.get("instrumental") is not True:
            raise RuntimeError(f"Unapproved/non-ACE-Step section: {mp}")
        audio=(mp.parent/str(m.get("audio_file",""))).resolve()
        if not audio.is_relative_to(root.resolve()) or not audio.is_file():
            raise RuntimeError(f"Missing/out-of-root audio: {mp}")
        sha=digest(audio); dur=duration(audio)
        if sha!=m.get("sha256") or abs(dur-float(m.get("duration_seconds",0)))>1:
            raise RuntimeError(f"Hash or duration mismatch: {audio}")
        if not m.get("seed"): raise RuntimeError(f"Missing generation seed: {mp}")
        result.append({"manifest":mp,"audio":audio,"sha":sha,"seed":str(m["seed"]),
            "duration":dur,"title":str(m.get("title","")),"style":str(m.get("style",""))})
    if len(result)<2: raise RuntimeError("At least two independent ACE-Step sections are required.")
    if len({s["sha"] for s in result})!=len(result): raise RuntimeError("Duplicate section audio hash.")
    if len({s["seed"] for s in result})!=len(result): raise RuntimeError("Repeated ACE-Step seed.")
    return result

def assemble(root, output, hours):
    if hours not in HOURS: raise ValueError(f"Hours must be one of {HOURS}")
    ffmpeg=shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"): raise RuntimeError("ffmpeg and ffprobe required")
    sections=read_sections(root); target=hours*3600.0
    available=sum(s["duration"] for s in sections)-XFADE*(len(sections)-1)
    if available<target:
        raise RuntimeError(f"Only {available:.1f}s of unique audio for {target:.1f}s; generate more sections, no looping.")
    output.parent.mkdir(parents=True,exist_ok=True)
    cmd=[ffmpeg,"-y","-hide_banner","-loglevel","error"]
    for s in sections: cmd += ["-i",str(s["audio"])]
    filters=[]; previous="[0:a]"
    for i in range(1,len(sections)):
        label=f"[mix{i}]"
        filters.append(f"{previous}[{i}:a]acrossfade=d={XFADE}:c1=tri:c2=tri{label}")
        previous=label
    filters.append(f"{previous}atrim=duration={target:.3f},asetpts=PTS-STARTPTS[out]")
    cmd += ["-filter_complex",";".join(filters),"-map","[out]","-c:a","aac","-b:a","192k",
        "-ar","48000","-ac","2",str(output)]
    subprocess.run(cmd,check=True,timeout=max(1800,hours*1800))
    actual=duration(output)
    if abs(actual-target)>1: raise RuntimeError(f"Duration mismatch: {actual:.2f}s vs {target:.2f}s")
    report={"status":"dry_run_assembled","published":False,"provider":"ACE-Step-1.5",
        "duration_hours":hours,"duration_seconds":round(actual,3),"audio_file":output.name,
        "audio_sha256":digest(output),"crossfade_seconds":XFADE,"unique_section_count":len(sections),
        "sections":[{"file":s["audio"].name,"sha256":s["sha"],"seed":s["seed"],
            "duration_seconds":round(s["duration"],3),"title":s["title"],"style":s["style"]} for s in sections]}
    output.with_suffix(output.suffix+".manifest.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--sections-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--hours",type=int,choices=HOURS,required=True)
    a=p.parse_args()
    print(json.dumps(assemble(a.sections_root,a.output,a.hours),indent=2))
