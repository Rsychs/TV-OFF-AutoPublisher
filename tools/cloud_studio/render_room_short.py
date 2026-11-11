#!/usr/bin/env python3
"""Render a continuous animated TV OFF room scene with original ambient music."""
import json, os, subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.io.wavfile import write

OUT=Path("output"); OUT.mkdir(exist_ok=True)
W,H=1080,1920
TITLE=os.environ.get("VIDEO_TITLE","Midnight Blue").strip()[:80] or "Midnight Blue"
DURATION=int(os.environ.get("DURATION_SECONDS","24"))
STYLE=os.environ.get("ROOM_STYLE","midnight_blue").strip().lower()

def lerp(a,b,t): return tuple(int(a[i]*(1-t)+b[i]*t) for i in range(3))
def make_room(path):
    im=Image.new("RGB",(W,H)); px=im.load()
    top=(10,16,38) if STYLE=="midnight_blue" else (24,18,24)
    bottom=(34,39,61) if STYLE=="midnight_blue" else (67,43,32)
    for y in range(H):
        c=lerp(top,bottom,y/H)
        for x in range(W): px[x,y]=c
    d=ImageDraw.Draw(im,"RGBA")
    # architectural wall and floor
    d.polygon([(0,0),(W,0),(W,1390),(0,1390)],fill=(13,20,42,255))
    d.polygon([(0,1330),(W,1330),(W,H),(0,H)],fill=(32,34,49,255))
    # ambient wall wash
    glow=Image.new("RGBA",(W,H),(0,0,0,0)); gd=ImageDraw.Draw(glow)
    gd.ellipse((150,250,930,1250),fill=(34,83,180,42))
    glow=glow.filter(ImageFilter.GaussianBlur(120)); im=Image.alpha_composite(im.convert("RGBA"),glow); d=ImageDraw.Draw(im,"RGBA")
    # window, skyline
    d.rounded_rectangle((55,230,345,790),radius=18,fill=(4,8,20,255),outline=(76,100,145,180),width=8)
    d.rectangle((72,250,328,770),fill=(8,17,39,255))
    for i,(x,hh) in enumerate([(85,120),(120,190),(157,145),(198,235),(240,160),(278,210),(305,130)]):
        d.rectangle((x,770-hh,x+25,770),fill=(17,29,54,255))
        for yy in range(770-hh+15,760,34):
            for xx in range(x+6,x+22,12): d.rectangle((xx,yy,xx+3,yy+8),fill=(76,115,177,150))
    d.line((200,240,200,780),fill=(90,110,150,150),width=5); d.line((65,510,335,510),fill=(90,110,150,150),width=5)
    # TV and screen (screen is composited as animated footage later)
    d.rounded_rectangle((365,390,1000,940),radius=34,fill=(2,3,8,255),outline=(83,99,130,255),width=7)
    d.rounded_rectangle((388,413,977,916),radius=12,fill=(5,12,29,255))
    d.ellipse((675,923,690,938),fill=(72,135,255,180))
    # media console
    d.rounded_rectangle((315,950,1040,1085),radius=24,fill=(20,24,37,255),outline=(72,82,108,150),width=4)
    d.rectangle((350,1080,375,1170),fill=(12,15,24,255)); d.rectangle((980,1080,1005,1170),fill=(12,15,24,255))
    d.rounded_rectangle((410,985,580,1050),radius=10,fill=(9,12,22,255))
    # couch foreground
    d.rounded_rectangle((90,1180,990,1630),radius=95,fill=(24,32,53,255),outline=(70,86,122,170),width=8)
    d.rounded_rectangle((135,1130,945,1390),radius=75,fill=(31,42,68,255))
    d.rounded_rectangle((105,1330,975,1580),radius=65,fill=(25,34,57,255))
    d.rounded_rectangle((140,1200,520,1450),radius=55,fill=(39,52,82,255))
    d.rounded_rectangle((560,1200,930,1450),radius=55,fill=(34,47,75,255))
    # cushions
    d.rounded_rectangle((190,1220,410,1390),radius=45,fill=(48,64,101,255))
    d.rounded_rectangle((690,1210,880,1390),radius=45,fill=(43,58,91,255))
    # rug, plant, floor lamp
    d.ellipse((120,1570,970,1880),fill=(12,17,30,170))
    d.line((1020,330,1020,1030),fill=(115,129,160,220),width=10)
    d.ellipse((955,270,1080,380),fill=(100,145,255,70))
    d.ellipse((950,265,1080,380),outline=(119,154,220,210),width=6)
    # small plant
    d.rectangle((45,1040,140,1190),fill=(16,20,29,255))
    for x,y in [(60,1030),(95,990),(130,1040),(75,970),(120,960)]:
        d.ellipse((x-28,y-65,x+28,y+30),fill=(30,83,75,230))
    # TV OFF wordmark discreetly on console
    d.text((690,1000),"TV OFF",fill=(117,151,220,190),stroke_width=0)
    im.convert("RGB").save(path,quality=95)

def make_audio(path):
    sr=48000; t=np.arange(sr*DURATION,dtype=np.float64)/sr
    freqs=[110.0,146.83,174.61,220.0,261.63]
    a=np.zeros_like(t)
    for i,f in enumerate(freqs):
        a += (0.12/(i+1))*np.sin(2*np.pi*f*t + 0.3*np.sin(2*np.pi*(0.025+i*.007)*t))
    a += .018*np.sin(2*np.pi*55*t)
    a *= np.minimum(1,t/2)*np.minimum(1,(DURATION-t)/2.5)
    a=a/max(np.max(np.abs(a)),1e-9)*.58
    stereo=np.column_stack((a,np.roll(a,420)))
    write(str(path),sr,(stereo*32767).astype(np.int16))

def main():
    if DURATION not in (20,24,30,40,50,60): raise SystemExit("Duration must be 20, 24, 30, 40, 50 or 60 seconds")
    still=OUT/"room_scene.png"; audio=OUT/"original_ambient.wav"; video=OUT/"TV_OFF_Midnight_Blue_ROOM.mp4"
    make_room(still); make_audio(audio)
    # The TV panel is a separate animated blue visual, then the complete room receives a subtle continuous camera drift.
    cmd=["ffmpeg","-y","-loop","1","-i",str(still),"-f","lavfi","-i",f"color=c=#102a58:s=589x503:r=30:d={DURATION}","-i",str(audio),
         "-filter_complex",
         f"[1:v]noise=alls=9:allf=t,hue=h='8*sin(t*0.7)',eq=brightness='0.025+0.025*sin(t*1.8)',gblur=sigma=8[screen];"
         "[0:v][screen]overlay=388:413:shortest=1,zoompan=z='min(1.035,1+0.00035*on)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,format=yuv420p[v]",
         "-map","[v]","-map","2:a:0","-t",str(DURATION),"-c:v","libx264","-preset","veryfast","-crf","20","-r","30","-c:a","aac","-b:a","192k","-movflags","+faststart",str(video)]
    subprocess.run(cmd,check=True)
    probe=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(video)],check=True,capture_output=True,text=True)
    actual=float(probe.stdout.strip())
    if abs(actual-DURATION)>.5: raise SystemExit(f"Duration mismatch: {actual}")
    manifest={"title":TITLE,"style":"Midnight Blue","scene_type":"designed living room with television","duration_seconds":DURATION,"resolution":"1080x1920","fps":30,"video":"continuous animated room scene with subtle camera drift and animated TV screen","music":"Original synthesized ambient music; no samples or third-party recordings","preview_only":True}
    (OUT/"production.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(f"ROOM_SCENE_RENDERED {video} duration={actual:.2f}s scene=room_tv style=midnight_blue")

if __name__=="__main__": main()
