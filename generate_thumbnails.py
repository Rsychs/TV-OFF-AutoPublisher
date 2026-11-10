from pathlib import Path
import csv
import hashlib
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
    "original_music": (161, 143, 214),
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
    "original_music": "DEEP SLEEP AMBIENT",
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
    for kind in ("original music", "ambient music", "deep sleep ambient", "white noise", "brown noise", "fireplace", "thunderstorm", "rain", "ocean", "wave", "sea", "forest", "bird", "river", "stream", "wind"):
        if kind in text:
            if kind in ("original music", "ambient music", "deep sleep ambient"):
                return "original_music"
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

def draw_signature(draw, kind, accent, variation):
    # Keep the channel identity while varying each release's motif deterministically.
    cx = W // 2 + (variation % 61) - 30
    cy = 185 + ((variation >> 6) % 31) - 15
    if kind in ("white_noise", "brown_noise"):
        heights = [22, 38, 58, 82, 106, 82, 58, 38, 22]
        for i, base_height in enumerate(heights):
            scale = 0.82 + (((variation >> ((i % 8) * 3)) & 7) / 25)
            height = int(base_height * scale)
            x = cx - 108 + i * 27 + ((variation >> 12) % 5 - 2)
            draw.rounded_rectangle((x, cy-height//2, x+7, cy+height//2), radius=3, fill=(*accent, 235))
    elif kind in ("ocean", "river", "wind"):
        for j in range(4):
            points = []
            for x in range(170, 1110, 8):
                phase = x / (74 + variation % 21) + j * 0.75 + ((variation >> 5) % 31) / 10
                amp = (13 if kind == "wind" else 20) + ((variation >> (j * 4)) & 3)
                y = cy + j * 17 + math.sin(phase) * amp
                points.append((x, int(y)))
            draw.line(points, fill=(*accent, 190 - j*22), width=4)
    elif kind == "original_music":
        for layer in range(4):
            points = []
            for x in range(180, 1110, 7):
                phase = x / (112 + layer * 13) + layer * 0.85 + ((variation >> 5) % 37) / 12
                y = cy + layer * 13 + math.sin(phase) * (12 + layer * 3)
                points.append((x, int(y)))
            draw.line(points, fill=(*accent, 200 - layer * 24), width=4)
        for x, offset in ((cx-78, -12), (cx+12, 8)):
            draw.ellipse((x-9, cy+offset, x+9, cy+offset+13), fill=(*accent, 220))
            draw.line((x+7, cy+offset+5, x+7, cy-65+offset), fill=(*accent, 220), width=5)
    elif kind in ("rain", "thunderstorm"):
        for row in range(3):
            for col in range(17):
                x = 210 + col * 52 + (row % 2) * 15 + ((variation >> 8) % 13 - 6)
                y = 105 + row * 55 + ((variation >> 16) % 9 - 4)
                draw.line((x, y, x-10, y+28), fill=(*accent, 165-row*25), width=4)
        if kind == "thunderstorm":
            draw.line([(670, 75), (630, 155), (680, 155), (640, 235)], fill=(*accent, 230), width=9)
    elif kind == "fireplace":
        radius_shift = (variation % 9) - 4
        for radius in (38 + radius_shift, 62 + radius_shift, 86 + radius_shift):
            draw.arc((cx-radius, cy-radius, cx+radius, cy+radius), 205, 335, fill=(*accent, 205), width=5)
        draw.ellipse((cx-10, cy-10, cx+10, cy+10), fill=(*accent, 230))
    elif kind == "forest":
        for i, x in enumerate((cx-85, cx-30, cx+30, cx+85)):
            height = (60, 85, 72, 52)[i] + ((variation >> (i * 5)) % 13 - 6)
            draw.polygon([(x, cy-height), (x-28, cy+15), (x+28, cy+15)], fill=(*accent, 175-i*15))
            draw.rectangle((x-4, cy+10, x+4, cy+34), fill=(*accent, 190))

def make_thumbnail(row):
    filename = row["filename"].strip()
    stem = Path(filename).stem
    source_title = (row.get("thumbnail_title") or row.get("title") or row.get("thumbnail_descriptor") or stem).split("|")[0].strip()
    source_title = re.sub(r"[_-]+", " ", source_title)
    declared_kind = str(row.get("soundscape") or "").strip().lower()
    allowed_kinds = {"white_noise", "brown_noise", "original_music"}
    if declared_kind:
        if declared_kind not in allowed_kinds:
            raise RuntimeError(f"Disallowed TV OFF thumbnail category: {declared_kind}")
        kind = declared_kind
    else:
        kind = detect_kind(stem, source_title)
        if kind not in allowed_kinds:
            raise RuntimeError(f"Cannot safely identify an allowed TV OFF category for thumbnail: {filename}")
    accent = ACCENTS[kind]
    variation = int(hashlib.sha256(f"{filename}|{source_title}".encode("utf-8")).hexdigest()[:8], 16)

    # Cinematic dark gradient with a vivid category-colored glow and layered sound rings.
    im = Image.new("RGBA", (W, H), (4, 8, 15, 255))
    pixels = im.load()
    for y in range(H):
        for x in range(W):
            glow_x = W*0.52 + ((variation >> 3) % 41 - 20)
            glow_y = H*0.28 + ((variation >> 9) % 25 - 12)
            glow_strength = max(0.0, 1.0 - math.sqrt(((x-glow_x)/(W*0.72))**2 + ((y-glow_y)/(H*0.95))**2))
            edge = 1.0 - 0.22 * (abs(x-W/2)/(W/2))
            pixels[x, y] = (
                int(4 + accent[0] * 0.13 * glow_strength * edge),
                int(8 + accent[1] * 0.13 * glow_strength * edge),
                int(15 + accent[2] * 0.18 * glow_strength * edge),
                255
            )
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    ring_x = W//2 + (variation % 51) - 25
    ring_y = 125 + ((variation >> 7) % 31) - 15
    ring_shift = ((variation >> 14) % 17) - 8
    for radius, alpha in ((190 + ring_shift, 18), (145 + ring_shift, 22), (100 + ring_shift, 27)):
        gd.ellipse((ring_x-radius, ring_y-radius, ring_x+radius, ring_y+radius), outline=(*accent, alpha), width=5)
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    im = Image.alpha_composite(im, glow)
    draw = ImageDraw.Draw(im, "RGBA")

    # Soft luminous waveform across the upper half creates a clear visual hook at small sizes.
    draw_signature(draw, kind, accent, variation)
    draw.rounded_rectangle((48, 42, 220, 91), radius=22, fill=(255, 255, 255, 18), outline=(*accent, 150), width=2)
    draw.text((76, 51), "TV OFF", font=font(25, True), fill=(245, 248, 252, 255))

    headline = LABELS.get(kind, source_title.upper())
    headline_font = font(72, True)
    bbox = draw.textbbox((0, 0), headline, font=headline_font)
    while bbox[2] - bbox[0] > 1160 and headline_font.size > 48:
        headline_font = font(headline_font.size - 2, True)
        bbox = draw.textbbox((0, 0), headline, font=headline_font)
    centered_text(draw, headline, 345, headline_font, (255, 255, 255, 255))

    # A strong, readable duration pill helps the thumbnail communicate the format instantly.
    draw.rounded_rectangle((420, 455, 860, 520), radius=28, fill=(*accent, 235))
    centered_text(draw, "10 HOURS  •  BLACK SCREEN", 470, font(23, True), (8, 12, 19, 255))
    subtitle = source_title.upper()
    if len(subtitle) > 52:
        subtitle = subtitle[:49].rstrip() + "…"
    centered_text(draw, subtitle, 635, font(20, True), (190, 202, 216, 255))

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
