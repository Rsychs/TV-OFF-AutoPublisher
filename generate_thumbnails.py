from pathlib import Path
import csv, hashlib, math, os, re, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "thumbnails"
W, H = 1280, 720
PALETTES = {
    "white_noise": {"accent": (174, 211, 255), "bright": (242, 248, 255), "bg": (4, 13, 31), "label": "WHITE NOISE"},
    "brown_noise": {"accent": (255, 174, 72), "bright": (255, 224, 166), "bg": (22, 10, 4), "label": "BROWN NOISE"},
    "original_music": {"accent": (174, 112, 255), "bright": (255, 199, 112), "bg": (8, 7, 28), "label": "ORIGINAL MUSIC"},
}

def get_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def detect_kind(filename, title=""):
    s = (filename + " " + title).lower().replace("_", " ").replace("-", " ")
    if "brown" in s: return "brown_noise"
    if "white" in s: return "white_noise"
    if "music" in s or "ambient" in s or "lofi" in s: return "original_music"
    raise RuntimeError(f"Cannot identify TV OFF thumbnail category: {filename}")

def center(draw, text, y, fnt, fill, stroke_width=0, stroke_fill=(0,0,0,255)):
    box = draw.textbbox((0,0), text, font=fnt, stroke_width=stroke_width)
    draw.text(((W-(box[2]-box[0]))/2, y), text, font=fnt, fill=fill,
              stroke_width=stroke_width, stroke_fill=stroke_fill)

def make_thumbnail(row):
    filename = str(row.get("filename", "")).strip()
    if not filename: raise RuntimeError("Thumbnail row has no filename")
    stem = Path(filename).stem
    title = str(row.get("thumbnail_title") or row.get("title") or row.get("thumbnail_descriptor") or stem).split("|")[0].strip()
    kind = str(row.get("soundscape") or "").strip().lower() or detect_kind(filename, title)
    if kind not in PALETTES: raise RuntimeError(f"Disallowed TV OFF thumbnail category: {kind}")
    p = PALETTES[kind]
    seed = int(hashlib.sha256((filename + "|" + title).encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    accent, bright, bg = p["accent"], p["bright"], p["bg"]

    # Deep cinematic gradient and soft category-colored atmospheric glow.
    im = Image.new("RGB", (W,H))
    pix = im.load()
    gx, gy = W*(0.50 + rng.uniform(-.035,.035)), H*.44
    for y in range(H):
        for x in range(W):
            d = math.sqrt(((x-gx)/(W*.78))**2 + ((y-gy)/(H*.92))**2)
            glow = max(0, 1-d)**2
            vignette = max(.48, 1 - .34*((x-W/2)/(W/2))**2 - .25*((y-H/2)/(H/2))**2)
            pix[x,y] = tuple(max(0,min(255,int((bg[i] + accent[i]*.23*glow)*vignette))) for i in range(3))

    # Atmospheric haze and layered luminous particle-wave mesh.
    haze = Image.new("RGBA",(W,H),(0,0,0,0)); hd = ImageDraw.Draw(haze)
    for j in range(7):
        yy = 430 + j*25
        hd.ellipse((-240, yy-150, 1520, yy+170), fill=(*accent, 8+j*2))
    haze = haze.filter(ImageFilter.GaussianBlur(75))
    im = Image.alpha_composite(im.convert("RGBA"), haze)
    glow_layer = Image.new("RGBA",(W,H),(0,0,0,0)); gd = ImageDraw.Draw(glow_layer)
    line_layer = Image.new("RGBA",(W,H),(0,0,0,0)); ld = ImageDraw.Draw(line_layer)

    phase0 = rng.uniform(0, math.tau)
    for layer in range(5):
        pts=[]
        for x in range(-30,W+31,5):
            t=x/W
            y=520 + layer*27 + math.sin(t*math.tau*1.35 + phase0 + layer*.48)* (75+layer*7) + math.sin(t*math.tau*2.2+layer)*17
            pts.append((x,int(y)))
        gd.line(pts, fill=(*accent, 70), width=17)
        ld.line(pts, fill=(*bright, max(48,145-layer*18)), width=2 if layer else 3)
        for idx in range(0,len(pts),3):
            x,y=pts[idx]
            radius=1.5 if layer>1 else 2.2
            gd.ellipse((x-radius*3,y-radius*3,x+radius*3,y+radius*3),fill=(*accent,70))
            ld.ellipse((x-radius,y-radius,x+radius,y+radius),fill=(*bright,210-layer*20))
    for _ in range(950):
        x=rng.randrange(W); y=int(350 + rng.random()*340)
        r=rng.choice([1,1,1,2])
        alpha=rng.randrange(45,180)
        ld.ellipse((x-r,y-r,x+r,y+r), fill=(*bright,alpha))
    glow_layer=glow_layer.filter(ImageFilter.GaussianBlur(23))
    im=Image.alpha_composite(im,glow_layer)
    im=Image.alpha_composite(im,line_layer)
    d=ImageDraw.Draw(im,"RGBA")

    # Music receives a recognizable keyboard silhouette; noise categories keep abstract waves.
    if kind=="original_music":
        for i in range(22):
            x=250+i*37
            d.polygon([(x,590),(x+35,590),(x+61,670),(x+25,670)],fill=(15,18,40,235),outline=(210,190,255,100))
        for i in range(15):
            x=275+i*52
            if i%7 not in (2,6):
                d.polygon([(x,590),(x+22,590),(x+37,636),(x+15,636)],fill=(2,3,12,255),outline=(255,205,135,180))

    # Brand lockup.
    d.line((330,78,505,78),fill=(*accent,180),width=2)
    d.line((775,78,950,78),fill=(*accent,180),width=2)
    d.ellipse((601,35,679,113),outline=(*accent,170),width=3)
    d.arc((607,29,673,95),195,345,fill=(*bright,255),width=4)
    d.rounded_rectangle((625,37,655,85),radius=13,fill=(*bg,255))
    d.line((640,38,640,65),fill=(*bright,255),width=5)
    brand=get_font(34,True)
    d.text((W/2-105,47),"TV OFF",font=brand,fill=(250,251,255,255),stroke_width=1,stroke_fill=(*bg,255))

    headline=p["label"]
    size=92 if len(headline)<13 else 78
    f=get_font(size,True)
    bb=d.textbbox((0,0),headline,font=f)
    while bb[2]-bb[0]>1120 and size>54:
        size-=2; f=get_font(size,True); bb=d.textbbox((0,0),headline,font=f)
    # Subtle dark plate behind headline for legibility at mobile size.
    d.rounded_rectangle((95,180,1185,330),radius=30,fill=(0,0,0,65),outline=(*accent,55),width=1)
    center(d,headline,207,f,(255,255,255,255),2,(15,20,34,210))

    duration=int(row.get("duration_seconds") or 0)
    if duration not in {3600,10800,28800,36000}:
        # Existing videos may not carry duration in their reconstructed row; infer from filename.
        m=re.search(r"_(1|3|8|10)-Hours",filename,re.I)
        duration=int(m.group(1))*3600 if m else 0
    duration_label=(f"{duration//3600} HOUR"+("S" if duration//3600!=1 else "")) if duration else "LONG PLAY"
    badge_text=f"{duration_label}  •  BLACK SCREEN"
    d.rounded_rectangle((390,355,890,420),radius=30,fill=(*accent,235),outline=(*bright,210),width=2)
    bf=get_font(23,True); bb=d.textbbox((0,0),badge_text,font=bf)
    d.text(((W-(bb[2]-bb[0]))/2,374),badge_text,font=bf,fill=(8,12,22,255))
    sub=title.upper()
    sub=re.sub(r"[_-]+"," ",sub)
    if len(sub)>64: sub=sub[:61].rstrip()+"..."
    sf=get_font(19,True); bb=d.textbbox((0,0),sub,font=sf)
    d.text(((W-(bb[2]-bb[0]))/2,665),sub,font=sf,fill=(205,216,233,230))

    OUT.mkdir(exist_ok=True)
    target=OUT/(stem+".jpg")
    im.convert("RGB").save(target,quality=96,optimize=True)
    print(f"Thumbnail ready: {target} | {kind} | {duration_label}")

def main():
    schedule=Path(os.environ.get("SCHEDULE_FILE",ROOT/"schedule.csv"))
    with schedule.open(newline="",encoding="utf-8-sig") as f: rows=list(csv.DictReader(f))
    if not rows: raise RuntimeError("Schedule contains no thumbnail rows")
    for row in rows: make_thumbnail(row)

if __name__=="__main__": main()
