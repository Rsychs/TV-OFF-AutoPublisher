from pathlib import Path
import csv
import math
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "thumbnails"
W, H = 1280, 720

# TV OFF visual identity: almost-black, quiet, typographic, consistent.
ACCENTS = {
    "fireplace": (166, 112, 72),
    "rain": (105, 145, 165),
    "thunderstorm": (124, 133, 158),
    "wind": (132, 151, 151),
    "ocean": (78, 139, 171),
    "forest": (103, 143, 104),
    "river": (82, 153, 164),
}

def font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size)

def detect_kind(filename, title):
    text = (filename + " " + title).lower()
    if "fire" in text:
        return "fireplace"
    if "ocean" in text or "wave" in text or "sea" in text:
        return "ocean"
    if "forest" in text or "bird" in text or "woodland" in text:
        return "forest"
    if "river" in text or "stream" in text:
        return "river"
    if "rain" in text:
        return "rain"
    if "thunder" in text or "storm" in text:
        return "thunderstorm"
    return "wind"

def make_thumbnail(row):
    filename = row["filename"].strip()
    stem = Path(filename).stem
    title = (row.get("thumbnail_title") or row.get("title") or stem).split("|")[0].strip()
    title = re.sub(r"[_-]+", " ", title)
    kind = detect_kind(stem, title)
    accent = ACCENTS[kind]

    # Deep black background with a very restrained central glow.
    im = Image.new("RGB", (W, H), (3, 4, 5))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((310, 80, 970, 740), fill=(*accent, 22))
    glow = glow.filter(ImageFilter.GaussianBlur(130))
    im = Image.alpha_composite(im.convert("RGBA"), glow)
    d = ImageDraw.Draw(im, "RGBA")

    # Quiet sound-wave mark: identical construction on every video.
    center_x, center_y = 640, 215
    for i, height in enumerate([18, 30, 46, 62, 46, 30, 18]):
        x = center_x - 66 + i * 22
        d.rounded_rectangle(
            (x, center_y - height // 2, x + 5, center_y + height // 2),
            radius=3, fill=(*accent, 190)
        )

    # Wordmark and title hierarchy remain fixed across the whole series.
    wordmark = "TV OFF"
    bbox = d.textbbox((0, 0), wordmark, font=font(34, True))
    d.text((640 - (bbox[2] - bbox[0]) / 2, 292), wordmark,
           font=font(34, True), fill=(238, 240, 239, 255))

    display_title = title.upper()
    title_font = font(58, True)
    while d.textbbox((0, 0), display_title, font=title_font)[2] > 1080 and len(display_title) > 12:
        display_title = display_title[:-4].rstrip() + "…"
    bbox = d.textbbox((0, 0), display_title, font=title_font)
    d.text((640 - (bbox[2] - bbox[0]) / 2, 374), display_title,
           font=title_font, fill=(248, 248, 245, 255))

    # Thin accent rule and identical descriptor on every thumbnail.
    d.rounded_rectangle((560, 474, 720, 478), radius=2, fill=(*accent, 210))
    descriptor = (row.get("thumbnail_descriptor") or "10 HOURS  •  BLACK SCREEN")
    bbox = d.textbbox((0, 0), descriptor, font=font(25))
    d.text((640 - (bbox[2] - bbox[0]) / 2, 516), descriptor,
           font=font(25), fill=(164, 171, 172, 255))

    tagline = "SOUND TO SWITCH OFF TO"
    bbox = d.textbbox((0, 0), tagline, font=font(17, True))
    d.text((640 - (bbox[2] - bbox[0]) / 2, 640), tagline,
           font=font(17, True), fill=(102, 111, 113, 255))

    OUT.mkdir(exist_ok=True)
    target = OUT / (stem + ".jpg")
    im.convert("RGB").save(target, quality=94, optimize=True)
    print(f"Thumbnail ready: {target}")

def main():
    schedule_path = Path(__import__("os").environ.get("SCHEDULE_FILE", ROOT / "schedule.csv"))
    with schedule_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            make_thumbnail(row)

if __name__ == "__main__":
    main()
