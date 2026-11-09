from pathlib import Path
import csv
import math
import os
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "thumbnails"
W, H = 1280, 720

# A consistent TV OFF identity with a distinct visual signature per sound family.
ACCENTS = {
    "white_noise": (205, 215, 230),
    "brown_noise": (190, 145, 105),
    "fireplace": (220, 125, 65),
    "rain": (90, 155, 205),
    "thunderstorm": (135, 145, 190),
    "wind": (130, 175, 165),
    "ocean": (55, 155, 205),
    "forest": (105, 170, 115),
    "river": (65, 175, 175),
}

LABELS = {
    "white_noise": "WHITE NOISE",
    "brown_noise": "BROWN NOISE",
    "fireplace": "FIREPLACE",
    "rain": "RAIN SOUNDS",
    "thunderstorm": "RAIN & THUNDER",
    "wind": "WIND IN TREES",
    "ocean": "OCEAN WAVES",
    "forest": "FOREST BIRDS",
    "river": "FLOWING RIVER",
}

def font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size)

def detect_kind(filename, title):
    text = (filename + " " + title).lower().replace("_", " ")
    for kind in ("white noise", "brown noise", "fireplace", "thunderstorm", "rain", "ocean", "wave", "sea", "forest", "bird", "river", "stream", "wind"):
        if kind in text:
            if kind in ("wave", "sea"):
                return "ocean"
            if kind in ("bird",):
                return "forest"
            if kind in ("stream",):
                return "river"
            if kind in ("white noise", "brown noise"):
                return kind.replace(" ", "_")
            return kind
    return "wind"

def centered_text(draw, text, y, fnt, fill):
    box = draw.textbbox((0, 0), text, font=fnt)
    draw.text(((W - (box[2] - box[0])) / 2, y), text, font=fnt, fill=fill)

def draw_signature(draw, kind, accent):
    # Large, restrained category-specific motif that remains legible on mobile.
    cx, cy = W // 2, 185
    if kind in ("white_noise", "brown_noise"):
        heights = [22, 38, 58, 82, 106, 82, 58, 38, 22]
        for i, height in enumerate(heights):
            x = cx - 108 + i * 27
            draw.rounded_rectangle((x, cy-height//2, x+7, cy+height//2), radius=3, fill=(*accent, 235))
    elif kind in ("ocean", "river", "wind"):
        for j in range(4):
            points = []
            for x in range(170, 1110, 8):
                phase = x / 82 + j * 0.75
                amp = 13 if kind == "wind" else 20
                y = cy + j * 17 + math.sin(phase) * amp
                points.append((x, int(y)))
            draw.line(points, fill=(*accent, 190 - j*22), width=4)
    elif kind in ("rain", "thunderstorm"):
        for row in range(3):
            for col in range(17):
                x = 210 + col * 52 + (row % 2) * 15
                y = 105 + row * 55
                draw.line((x, y, x-10, y+28), fill=(*accent, 165-row*25), width=4)
        if kind == "thunderstorm":
            draw.line([(670, 75), (630, 155), (680, 155), (640, 235)], fill=(*accent, 230), width=9)
    elif kind == "fireplace":
        for radius in (38, 62, 86):
            draw.arc((cx-radius, cy-radius, cx+radius, cy+radius), 205, 335, fill=(*accent, 205), width=5)
        draw.ellipse((cx-10, cy-10, cx+10, cy+10), fill=(*accent, 230))
    elif kind == "forest":
        for i, x in enumerate((cx-85, cx-30, cx+30, cx+85)):
            height = (60, 85, 72, 52)[i]
            draw.polygon([(x, cy-height), (x-28, cy+15), (x+28, cy+15)], fill=(*accent, 175-i*15))
            draw.rectangle((x-4, cy+10, x+4, cy+34), fill=(*accent, 190))

def make_thumbnail(row):
    filename = row["filename"].strip()
    stem = Path(filename).stem
    source_title = (row.get("thumbnail_title") or row.get("title") or stem).split("|")[0].strip()
    source_title = re.sub(r"[_-]+", " ", source_title)
    kind = detect_kind(stem, source_title)
    accent = ACCENTS[kind]

    im = Image.new("RGBA", (W, H), (3, 5, 8, 255))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((250, -80, 1030, 600), fill=(*accent, 27))
    glow = glow.filter(ImageFilter.GaussianBlur(125))
    im = Image.alpha_composite(im, glow)
    draw = ImageDraw.Draw(im, "RGBA")

    draw_signature(draw, kind, accent)
    centered_text(draw, "TV OFF", 285, font(30, True), (235, 240, 244, 255))

    headline = LABELS.get(kind, source_title.upper())
    headline_font = font(68, True)
    bbox = draw.textbbox((0, 0), headline, font=headline_font)
    while bbox[2] - bbox[0] > 1100 and headline_font.size > 48:
        headline_font = font(headline_font.size - 2, True)
        bbox = draw.textbbox((0, 0), headline, font=headline_font)
    centered_text(draw, headline, 365, headline_font, (250, 250, 248, 255))

    draw.rounded_rectangle((510, 465, 770, 470), radius=2, fill=(*accent, 230))
    descriptor = "10 HOURS  •  BLACK SCREEN"
    centered_text(draw, descriptor, 505, font(27, True), (185, 195, 202, 255))
    centered_text(draw, "SOUND TO SWITCH OFF TO", 642, font(17, True), (105, 117, 125, 255))

    OUT.mkdir(exist_ok=True)
    target = OUT / (stem + ".jpg")
    im.convert("RGB").save(target, quality=95, optimize=True)
    print(f"Thumbnail ready: {target} | category={kind} | headline={headline}")

def main():
    schedule_path = Path(os.environ.get("SCHEDULE_FILE", ROOT / "schedule.csv"))
    with schedule_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("Schedule contains no thumbnail rows")
    for row in rows:
        make_thumbnail(row)

if __name__ == "__main__":
    main()
