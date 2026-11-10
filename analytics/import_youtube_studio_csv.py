#!/usr/bin/env python3
"""Normalize a YouTube Studio video-level CSV without calling YouTube APIs.

Writes analytics JSON only to a caller-selected output directory. It never copies
or retains the source CSV. Missing metrics stay null.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path

ALIASES = {
    "video_id": ["video id", "content id", "id"],
    "title": ["video title", "title", "content"],
    "publish_date": ["video publish time", "publish date", "published at", "publish time"],
    "duration": ["duration", "video duration"],
    "views": ["views"],
    "watch_time_hours": ["watch time (hours)", "watch time hours", "watch time"],
    "average_view_duration": ["average view duration", "avg view duration"],
    "average_percentage_viewed": ["average percentage viewed (%)", "average percentage viewed", "avg percentage viewed"],
    "subscribers_gained": ["subscribers gained"],
    "subscribers_lost": ["subscribers lost"],
    "likes": ["likes"],
    "comments": ["comments"],
    "shares": ["shares"],
    "impressions": ["impressions"],
    "impressions_ctr": ["impressions click-through rate (%)", "impressions ctr", "click-through rate"],
    "shown_in_feed": ["shown in feed", "times shown in feed"],
    "viewed_vs_swiped_away": ["viewed vs swiped away (%)", "viewed vs swiped away"],
    "format": ["video type", "format"],
    "category": ["category"],
}
NUMERIC = {
    "views", "watch_time_hours", "average_percentage_viewed", "subscribers_gained",
    "subscribers_lost", "likes", "comments", "shares", "impressions",
    "impressions_ctr", "shown_in_feed", "viewed_vs_swiped_away"
}

def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9%]+", " ", (s or "").strip().lower()).strip()

def parse_number(value):
    if value is None or not str(value).strip():
        return None
    s = str(value).strip().replace(",", "").replace("%", "")
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None

def parse_duration_seconds(value):
    if not value:
        return None
    s = str(value).strip()
    parts = s.split(":")
    try:
        nums = [int(x) for x in parts]
        if len(nums) == 3: return nums[0]*3600 + nums[1]*60 + nums[2]
        if len(nums) == 2: return nums[0]*60 + nums[1]
        return int(s)
    except ValueError:
        return None

def parse_date(value):
    if not value: return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%Y-%m-%d %H:%M:%S"):
        try: return datetime.strptime(s, fmt).date().isoformat()
        except ValueError: pass
    return s

def detect_format(row):
    raw = (row.get("format") or "").strip().lower()
    if "short" in raw: return "shorts"
    if "long" in raw: return "long_form"
    sec = parse_duration_seconds(row.get("duration"))
    if sec is not None: return "shorts" if sec <= 180 else "long_form"
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_file", type=Path)
    ap.add_argument("--out-dir", required=True, type=Path,
                    help="Private/local directory outside this public repository")
    args = ap.parse_args()
    raw = args.csv_file.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise SystemExit("CSV has no header row")
    header_map = {norm(h): h for h in reader.fieldnames}
    field_map = {}
    for key, aliases in ALIASES.items():
        for alias in aliases:
            if norm(alias) in header_map:
                field_map[key] = header_map[norm(alias)]
                break
    if not field_map.get("title") and not field_map.get("video_id"):
        raise SystemExit("Unrecognized export: expected a video title or video ID column")
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for source in reader:
        item = {k: None for k in ALIASES}
        for key, source_col in field_map.items():
            val = source.get(source_col)
            if key in NUMERIC: item[key] = parse_number(val)
            elif key == "publish_date": item[key] = parse_date(val)
            else: item[key] = (val.strip() if isinstance(val, str) and val.strip() else None)
        item["duration_seconds"] = parse_duration_seconds(item.get("duration"))
        item["format"] = detect_format(item)
        item["source_export_hash"] = digest
        item["imported_at"] = now
        item["snapshot_key"] = "|".join([
            str(item.get("video_id") or item.get("title") or ""),
            str(item.get("publish_date") or ""),
            digest
        ])
        rows.append(item)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    snapshots_path = out / "video_snapshots.jsonl"
    existing = set()
    if snapshots_path.exists():
        for line in snapshots_path.read_text(encoding="utf-8").splitlines():
            try: existing.add(json.loads(line).get("snapshot_key"))
            except json.JSONDecodeError: continue
    fresh = [r for r in rows if r["snapshot_key"] not in existing]
    with snapshots_path.open("a", encoding="utf-8") as f:
        for r in fresh: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    registry_path = out / "videos.json"
    registry = {}
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for r in rows:
        key = r.get("video_id") or r.get("title")
        if key:
            prior = registry.get(key, {})
            registry[key] = {**prior, "video_id": r.get("video_id"),
                "title": r.get("title"), "publish_date": r.get("publish_date"),
                "format": r.get("format"), "category": r.get("category")}
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"source_export_hash": digest, "rows_read": len(rows),
        "new_snapshots": len(fresh), "duplicate_snapshots_skipped": len(rows)-len(fresh),
        "fields_detected": sorted(field_map), "imported_at": now}
    (out / "last_import.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
