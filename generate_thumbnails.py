from pathlib import Path
import math
import re
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "thumbnails"
W, H = 1280, 720

def font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size)

def draw_scene(draw, kind):
    if kind == "fireplace":
        # Hearth glow, logs, and stylized flame.
        draw.ellipse((760, 110, 1190, 600), fill=(82, 34, 13))
        draw.ellipse((820, 170, 1130, 560), fill=(150, 57, 14))
        draw.ellipse((885, 230, 1080, 540), fill=(240, 123, 25))
        draw.polygon([(930, 515), (875, 380), (930, 290), (970, 385), (1020, 245), (1080, 390), (1045, 515)], fill=(255, 196, 82))
        draw.line((790, 545, 1130, 545), fill=(49, 26, 19), width=38)
        draw.line((825, 590, 1110, 500), fill=(77, 43, 27), width=30)
    elif kind == "rain":
        for x in range(720, 1240, 42):
            for y in range(110 + (x % 3) * 20, 660, 95):
                draw.line((x, y, x-28, y+74), fill=(102, 181, 211), width=7)
        draw.ellipse((820, 90, 1190, 300), fill=(46, 74, 94))
        draw.ellipse((900, 65, 1195, 280), fill=(56, 91, 111))
    elif kind in ("thunderstorm", "storm", "thunder"):
        draw.ellipse((760, 95, 1200, 340), fill=(47, 57, 77))
        draw.ellipse((860, 70, 1240, 320), fill=(35, 43, 63))
        draw.polygon([(1000, 240), (930, 405), (1015, 380), (965, 565), (1110, 340), (1025, 365)], fill=(244, 208, 104))
        for x in range(780, 1210, 75):
            draw.line((x, 440, x-30, 560), fill=(102, 153, 187), width=5)
    else:  # wind
        for i in range(5):
            y = 210 + i * 75
            pts = []
            for x in range(700, 1230, 12):
                yy = y + 26 * math.sin((x / 95) + i * 0.7)
                pts.append((x, yy))
            draw.line(pts, fill=(112, 178, 190), width=8)
        draw.ellipse((980, 80, 1160, 260), outline=(83, 132, 151), width=5)

def main():
    OUT.mkdir(exist_ok=True)
    import csv
    with (ROOT / "schedule.csv").open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        filename = row["filename"].strip()
        stem = Path(filename).stem
        label = re.sub(r"[_-]+", " ", stem)
        kind_text = (stem + " " + row.get("title", "")).lower()
        if "fire" in kind_text: kind = "fireplace"
        elif "rain" in kind_text: kind = "rain"
        elif any(k in kind_text for k in ("thunder", "storm")): kind = "thunderstorm"
        else: kind = "wind"

        im = Image.new("RGB", (W, H))
        px = im.load()
        left, right = (9, 17, 27), (18, 38, 49)
        for x in range(W):
            t = x / (W - 1)
            c = tuple(int(left[i] * (1-t) + right[i] * t) for i in range(3))
            for y in range(H):
                shade = int(8 * (1 - y / H))
                px[x, y] = tuple(min(255, v + shade) for v in c)
        d = ImageDraw.Draw(im, "RGBA")
        d.rounded_rectangle((54, 48, 1226, 672), radius=34, outline=(135, 173, 187, 95), width=3)
        draw_scene(d, kind)
        d.rounded_rectangle((78, 82, 590, 148), radius=20, fill=(5, 12, 19, 210))
        d.text((105, 96), "TV OFF  •  AMBIENT SERIES", font=font(28, True), fill=(215, 232, 238))
        title = row.get("thumbnail_title") or row.get("title") or label
        title = title.split("|")[0].strip()
        while d.textbbox((0,0), title, font=font(58, True))[2] > 690 and len(title) > 12:
            title = title[:-4].rstrip() + "…"
        d.text((92, 300), title.upper(), font=font(58, True), fill=(250, 250, 246), stroke_width=2, stroke_fill=(8, 17, 24))
        d.text((96, 390), "1 HOUR  •  BLACK SCREEN", font=font(30, True), fill=(170, 205, 216))
        d.text((96, 610), "SOUND TO SWITCH OFF TO", font=font(22, True), fill=(132, 165, 177))
        im.save(OUT / (stem + ".jpg"), quality=92, optimize=True)
        print(f"Thumbnail ready: {OUT / (stem + '.jpg')}")

if __name__ == "__main__":
    main()
