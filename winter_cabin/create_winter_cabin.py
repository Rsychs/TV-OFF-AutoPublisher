#!/usr/bin/env python3
"""Create original TV OFF Winter Cabin + Lo-Fi ambience assets.

The soundtrack is synthesized locally from original waveforms; no third-party
recordings, samples, soundfonts, or generative-music APIs are used.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "winter_cabin"
AUDIO = WORK / "audio"
VIDEO = WORK / "videos"
THUMB = ROOT / "thumbnails"
WIDTH, HEIGHT = 1280, 720
SR = 22050
BPM = 80
BEAT = 60.0 / BPM
BAR = 4 * BEAT
FILENAME = "TV-OFF_Winter_Cabin_Cozy_LoFi_10-Hours.mp4"
TITLE = "Winter Cabin — Cozy Lo-Fi Music for Relaxing, Studying & Sleeping"

def run(args):
    subprocess.run(args, check=True)

def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def cabin_background(path):
    im = Image.new("RGB", (WIDTH, HEIGHT), (24, 20, 18))
    px = im.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            glow = max(0.0, 1.0 - math.sqrt(((x-330)/900)**2 + ((y-600)/700)**2))
            px[x, y] = (int(25+44*glow), int(20+27*glow), int(17+13*glow))
    d = ImageDraw.Draw(im, "RGBA")
    # Timber cabin wall and ceiling beams.
    d.polygon([(0,0),(1280,0),(1280,80),(0,180)], fill=(52,35,27,255))
    for y in (110, 660):
        d.line((0,y,1280,y-65), fill=(104,70,48,130), width=8)
    # Large frosted window with a blue winter night.
    d.rounded_rectangle((650,95,1190,485), radius=12, fill=(28,39,53,255), outline=(116,81,54,255), width=22)
    d.rectangle((675,120,1165,460), fill=(31,52,72,255))
    # Distant snowy hills and pine silhouettes.
    d.polygon([(675,360),(760,280),(835,345),(930,245),(1025,340),(1165,265),(1165,460),(675,460)], fill=(76,94,105,255))
    d.polygon([(675,390),(790,325),(880,385),(990,300),(1080,390),(1165,335),(1165,460),(675,460)], fill=(177,190,194,255))
    for x,y,s in [(720,285,1),(805,250,.8),(915,290,1),(1065,260,.9),(1130,300,.7),(755,355,.6),(1010,360,.7)]:
        top=y-72*s
        d.polygon([(x,top),(x-30*s,y+30*s),(x+30*s,y+30*s)], fill=(22,47,49,255))
        d.polygon([(x,top+24*s),(x-38*s,y+55*s),(x+38*s,y+55*s)], fill=(27,57,55,255))
    # Snow outside the window, stationary background specks.
    rng=np.random.default_rng(91)
    for _ in range(120):
        x=int(rng.integers(680,1160)); y=int(rng.integers(125,455)); r=int(rng.integers(1,4))
        d.ellipse((x-r,y-r,x+r,y+r), fill=(230,239,245,int(rng.integers(80,190))))
    # Window frame.
    d.rectangle((905,105,925,475), fill=(93,61,42,255))
    d.rectangle((660,275,1180,295), fill=(93,61,42,255))
    # Fireplace stone surround, firebox and logs.
    d.rounded_rectangle((90,260,505,650), radius=20, fill=(91,66,50,255), outline=(139,103,72,255), width=10)
    d.rounded_rectangle((145,335,450,615), radius=12, fill=(12,12,13,255), outline=(48,36,29,255), width=12)
    d.rectangle((190,560,405,585), fill=(73,43,29,255))
    d.line((215,560,370,530), fill=(101,61,37,255), width=20)
    d.line((245,585,390,550), fill=(120,73,40,255), width=14)
    # Soft stylized flames; the animated ember overlay adds movement.
    d.polygon([(250,560),(220,505),(250,465),(270,515),(300,440),(325,515),(355,480),(370,560)], fill=(213,91,34,230))
    d.polygon([(270,560),(265,510),(295,480),(310,535),(335,500),(345,560)], fill=(255,177,69,245))
    d.polygon([(300,560),(300,520),(320,500),(330,560)], fill=(255,224,143,240))
    # Rug, chair and side table.
    d.ellipse((80,620,590,800), fill=(105,65,44,100))
    d.rounded_rectangle((900,520,1160,700), radius=35, fill=(76,48,35,255), outline=(128,82,54,255), width=8)
    d.rounded_rectangle((945,445,1120,600), radius=45, fill=(105,68,48,255))
    d.rectangle((1035,585,1055,705), fill=(57,38,29,255))
    d.rounded_rectangle((530,590,700,680), radius=14, fill=(80,52,37,255))
    d.line((550,675,540,715), fill=(46,32,26,255), width=12)
    d.line((680,675,690,715), fill=(46,32,26,255), width=12)
    # Warm lamp glow and lamp.
    glow=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    gd=ImageDraw.Draw(glow)
    gd.ellipse((460,170,660,390), fill=(255,176,88,36))
    glow=glow.filter(ImageFilter.GaussianBlur(50))
    im=Image.alpha_composite(im.convert("RGBA"),glow)
    d=ImageDraw.Draw(im,"RGBA")
    d.line((560,175,560,290), fill=(43,33,27,255), width=8)
    d.polygon([(505,230),(615,230),(645,310),(475,310)], fill=(218,166,103,230))
    d.ellipse((520,285,600,330), fill=(255,197,111,85))
    im.convert("RGB").save(path, quality=95)
    return im.convert("RGB")

def make_fx(path, seed, seconds=20, fps=8):
    frames=seconds*fps
    rng=np.random.default_rng(seed)
    snow=[(float(rng.uniform(0,WIDTH)),float(rng.uniform(0,HEIGHT)),float(rng.uniform(1.0,3.4)),float(rng.uniform(14,42)),float(rng.uniform(0,6.28))) for _ in range(170)]
    embers=[(float(rng.uniform(210,420)),float(rng.uniform(460,600)),float(rng.uniform(0.7,2.0)),float(rng.uniform(8,24)),float(rng.uniform(0,6.28))) for _ in range(34)]
    frame_dir=WORK/"fx_frames"
    frame_dir.mkdir(parents=True,exist_ok=True)
    for i in range(frames):
        t=i/fps
        im=Image.new("RGB",(WIDTH,HEIGHT),(0,0,0))
        d=ImageDraw.Draw(im)
        for x,y,r,speed,phase in snow:
            yy=(y+speed*t)%HEIGHT
            xx=(x+math.sin(t*0.55+phase)*10)%WIDTH
            d.ellipse((xx-r,yy-r,xx+r,yy+r), fill=(205,222,235))
        for x,y,r,speed,phase in embers:
            yy=y-speed*t%90
            xx=x+math.sin(t*1.1+phase)*12
            pulse=0.55+0.45*math.sin(t*3+phase)
            c=(int(220*pulse),int(94*pulse),int(28*pulse))
            d.ellipse((xx-r,yy-r,xx+r,yy+r), fill=c)
        im.save(frame_dir/f"{i:04d}.png")
    run(["ffmpeg","-y","-hide_banner","-loglevel","error","-framerate",str(fps),
         "-i",str(frame_dir/"%04d.png"),"-c:v","libx264","-preset","ultrafast",
         "-pix_fmt","yuv420p","-crf","24","-movflags","+faststart",str(path)])
    for p in frame_dir.glob("*.png"):
        p.unlink()
    frame_dir.rmdir()

def note_wave(freq, t, phase=0.0):
    # A soft, rounded electric-piano timbre with a gentle second harmonic.
    return (np.sin(2*np.pi*freq*t+phase)+0.22*np.sin(4*np.pi*freq*t+phase*0.7)+0.06*np.sin(6*np.pi*freq*t))*0.72

def make_music(path, seconds, seed):
    rng=np.random.default_rng(seed)
    bar_samples=int(round(SR*BAR))
    bars=int(math.ceil(seconds/BAR))
    # C-major/A-minor family, with warm extensions; generated progression varies by section.
    progressions=[
        [(0,4,7,11),(9,0,4,7),(5,9,0,4),(7,11,2,5)],
        [(2,5,9,0),(7,11,2,5),(0,4,7,11),(9,0,4,7)],
        [(5,9,0,4),(0,4,7,11),(2,5,9,0),(7,11,2,5)],
    ]
    scale=[0,2,4,5,7,9,11,12,14,16,17,19,21,23,24]
    with wave.open(str(path),"wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        for bar_index in range(bars):
            section=(bar_index//16)%len(progressions)
            chord=progressions[section][(bar_index//4)%4]
            t=np.arange(bar_samples,dtype=np.float32)/SR
            beat_phase=(bar_index%4)*0.19
            mix=np.zeros(bar_samples,dtype=np.float32)
            # Warm sustained chord, gently detuned and filtered by a slow tremolo.
            for n,semitone in enumerate(chord):
                freq=220.0*2**((semitone-9)/12)
                tone=note_wave(freq,t,phase=n*0.17)
                tone+=0.16*np.sin(2*np.pi*freq*0.5*t+n*0.4)
                mix+=tone*(0.040+0.008*math.sin(bar_index*0.13+n))* (0.82+0.18*np.sin(2*np.pi*0.17*t+beat_phase))
            # Soft bass on alternating beats.
            bass_note=chord[0]-12
            bass_freq=220.0*2**((bass_note-9)/12)
            bass=np.sin(2*np.pi*bass_freq*t)*0.10
            bass*=0.65+0.35*np.sin(2*np.pi*0.25*t)
            mix+=bass
            # Sparse original bell-like melody; note selection changes every bar.
            melody_notes=rng.choice(scale,size=4,replace=True)
            for beat,note in enumerate(melody_notes):
                start=int(beat*BEAT*SR+int(rng.uniform(0,0.10)*SR))
                length=min(int(0.48*SR),bar_samples-start)
                if length<=0: continue
                tt=np.arange(length,dtype=np.float32)/SR
                freq=440.0*2**((int(note)-9)/12)
                env=np.exp(-tt*5.5)*(1-np.exp(-tt*45))
                pluck=note_wave(freq,tt,phase=float(rng.uniform(0,1)))*env*0.12
                mix[start:start+length]+=pluck.astype(np.float32)
            # Dusty boom-bap drums: soft kick, brushed snare and low-level hats.
            for beat in (0,2):
                start=int(beat*BEAT*SR)
                length=min(int(0.30*SR),bar_samples-start)
                tt=np.arange(length,dtype=np.float32)/SR
                freq=88*np.exp(-tt*13)+42
                kick=np.sin(2*np.pi*freq*tt)*np.exp(-tt*12)*0.20
                mix[start:start+length]+=kick.astype(np.float32)
            for beat in (1,3):
                start=int(beat*BEAT*SR)
                length=min(int(0.20*SR),bar_samples-start)
                tt=np.arange(length,dtype=np.float32)/SR
                noise=rng.normal(0,1,length).astype(np.float32)
                snare=noise*np.exp(-tt*22)*0.055
                mix[start:start+length]+=snare
            for beat in range(4):
                start=int(beat*BEAT*SR+0.5*BEAT*SR)
                if start>=bar_samples: continue
                length=min(int(0.055*SR),bar_samples-start)
                tt=np.arange(length,dtype=np.float32)/SR
                hat=rng.normal(0,1,length).astype(np.float32)*np.exp(-tt*75)*0.014
                mix[start:start+length]+=hat
            # Quiet vinyl texture and gentle saturation, never loud enough to mask the music.
            vinyl=rng.normal(0,1,bar_samples).astype(np.float32)*0.003
            mix+=vinyl
            mix=np.tanh(mix*1.45)*0.78
            pcm=np.clip(mix*32767,-32768,32767).astype("<i2")
            wf.writeframes(pcm.tobytes())
            if (bar_index+1)%200==0:
                print(f"Music composition: {bar_index+1}/{bars} bars",flush=True)

def make_thumbnail(base_path):
    im=Image.open(base_path).convert("RGB")
    d=ImageDraw.Draw(im,"RGBA")
    d.rectangle((0,0,WIDTH,150),fill=(0,0,0,85))
    d.rounded_rectangle((52,42,225,96),radius=24,fill=(12,18,24,185),outline=(232,177,111,230),width=2)
    d.text((82,53),"TV OFF",font=font(27,True),fill=(255,245,230,255))
    headline="WINTER CABIN"
    f=font(76,True)
    box=d.textbbox((0,0),headline,font=f)
    d.text(((WIDTH-(box[2]-box[0]))/2,480),headline,font=f,fill=(255,248,236,255),stroke_width=2,stroke_fill=(24,18,14,180))
    sub="COZY LO-FI  •  10 HOURS"
    f2=font(28,True); box=d.textbbox((0,0),sub,font=f2)
    d.text(((WIDTH-(box[2]-box[0]))/2,580),sub,font=f2,fill=(244,196,133,255))
    THUMB.mkdir(parents=True,exist_ok=True)
    im.save(THUMB/(Path(FILENAME).stem+".jpg"),quality=94,optimize=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=["preview","full"],required=True)
    parser.add_argument("--test-id",required=True)
    args=parser.parse_args()
    if not args.test_id or len(args.test_id)>32 or not all(c.isalnum() or c in "_-" for c in args.test_id):
        raise SystemExit("test-id must contain only letters, digits, underscore or hyphen (max 32 chars)")
    AUDIO.mkdir(parents=True,exist_ok=True); VIDEO.mkdir(parents=True,exist_ok=True)
    seed=int(hashlib.sha256(args.test_id.encode()).hexdigest()[:8],16)
    base=AUDIO/"winter_cabin_scene.jpg"
    fx=AUDIO/"winter_cabin_fx.mp4"
    cabin_background(base)
    make_fx(fx,seed)
    duration=180 if args.mode=="preview" else 36000
    music_seconds=180 if args.mode=="preview" else 3600
    wav=AUDIO/"winter_cabin_lofi.wav"
    audio=AUDIO/"winter_cabin_lofi.m4a"
    print(f"Generating original Lo-Fi composition: {music_seconds} seconds")
    make_music(wav,music_seconds,seed)
    run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(wav),"-c:a","aac","-b:a","128k","-ar","44100",str(audio)])
    wav.unlink(missing_ok=True)
    if args.mode=="preview":
        filename=f"TV-OFF_Winter_Cabin_Preview_{args.test_id}.mp4"
        target=VIDEO/filename
    else:
        filename=FILENAME
        target=VIDEO/filename
    run(["ffmpeg","-y","-hide_banner","-loglevel","error",
         "-loop","1","-framerate","8","-i",str(base),
         "-stream_loop","-1","-i",str(fx),
         "-stream_loop","-1","-i",str(audio),
         "-filter_complex","[0:v][1:v]blend=all_mode=screen:shortest=1,format=yuv420p[v]",
         "-map","[v]","-map","2:a:0","-t",str(duration),
         "-r","8","-c:v","libx264","-preset","veryfast","-tune","stillimage",
         "-crf","25","-pix_fmt","yuv420p","-c:a","aac","-b:a","128k",
         "-ar","44100","-movflags","+faststart",str(target)])
    if args.mode=="preview":
        print(f"PREVIEW_READY {target} ({duration}s); not uploaded.")
        return
    make_thumbnail(base)
    schedule=WORK/"schedule.csv"
    description=(
        "Settle into a quiet winter cabin with warm, original lo-fi music, a softly glowing fireplace "
        "and snow drifting beyond the window. A long, gentle soundscape for relaxing, studying, reading "
        "or winding down. No voice, no abrupt transitions.\\n\\n"
        "Music: original TV OFF composition, synthesized for this video. No third-party recordings or samples.\\n"
        "Visuals: original TV OFF artwork and animation.\\n\\n"
        "🎧 Keep the volume comfortable.\\n"
        "🪵 10 hours • Cozy winter cabin • Original Lo-Fi\\n\\n"
        "Subscribe to TV OFF for more long-form soundscapes.\\n\\n"
        "#LoFi #WinterCabin #CozyAmbience #StudyMusic #RelaxingMusic"
    )
    with schedule.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=["filename","soundscape","title","description","tags","publish_at"])
        writer.writeheader()
        from datetime import datetime,timezone
        writer.writerow({"filename":FILENAME,"soundscape":"winter_cabin","title":TITLE,
                         "description":description,"tags":"winter cabin;cozy lofi;lofi music;study music;relaxing music;fireplace ambience;snow ambience;TV OFF",
                         "publish_at":datetime.now(timezone.utc).isoformat()})
    manifest={"winter_cabin":{"file":"winter_cabin_lofi.m4a","creator":"TV OFF — original synthesized Lo-Fi music",
        "source_url":"https://github.com/Rsychs/TV-OFF-AutoPublisher/tree/main/winter_cabin",
        "license":"Original TV OFF composition and artwork; no third-party samples or recordings."}}
    (AUDIO/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(f"FULL_VIDEO_READY {target} ({duration}s); awaiting validated uploader step.")

if __name__=="__main__":
    main()
