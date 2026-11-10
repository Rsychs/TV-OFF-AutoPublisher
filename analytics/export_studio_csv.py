#!/usr/bin/env python3
"""Export a saved YouTube Studio Advanced Mode view to a private Dropbox-synced folder.

No Google password/OAuth token is read. Uses a dedicated local Chrome profile
created by bootstrap_studio_profile.py. Fails closed on login challenges,
unexpected UI, missing CSV, or invalid output.
"""
from __future__ import annotations
import csv
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

REPORT_URL = os.environ.get("TV_OFF_STUDIO_REPORT_URL", "").strip()
PROFILE = Path(os.environ.get(
    "TV_OFF_BROWSER_PROFILE",
    str(Path.home() / ".tv-off-analytics" / "chrome-profile")
)).expanduser().resolve()
DROPBOX_RAW = os.environ.get("TV_OFF_ANALYTICS_DROPBOX_DIR", "").strip()
DROPBOX_DIR = Path(DROPBOX_RAW).expanduser().resolve() if DROPBOX_RAW else None
HEADLESS = os.environ.get("TV_OFF_HEADLESS", "true").lower() not in {"0", "false", "no"}

def fail(message: str) -> None:
    print(f"EXPORT_FAILED: {message}", file=sys.stderr)
    raise SystemExit(2)

def main() -> None:
    if not REPORT_URL.startswith("https://studio.youtube.com/"):
        fail("TV_OFF_STUDIO_REPORT_URL must be a saved YouTube Studio report URL.")
    if not PROFILE.is_dir():
        fail("Local Chrome profile missing. Run bootstrap_studio_profile.py once on this runner.")
    if DROPBOX_DIR is None or not DROPBOX_DIR.is_dir():
        fail("TV_OFF_ANALYTICS_DROPBOX_DIR must point to the already-synced Dropbox folder.")
    DROPBOX_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            channel="chrome",
            headless=HEADLESS,
            accept_downloads=True,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(REPORT_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

            current_url = page.url.lower()
            if "accounts.google.com" in current_url or "signin" in current_url:
                fail("Google sign-in required or session expired. Re-authenticate locally; no login bypass attempted.")
            if "studio.youtube.com" not in current_url:
                fail("Unexpected redirect away from YouTube Studio.")

            export_button = page.get_by_role(
                "button", name=re.compile(r"export current view", re.I)
            ).first
            export_button.click(timeout=20000)

            csv_choice = page.get_by_text(
                re.compile(r"(comma.?separated|\.csv|csv)", re.I)
            ).last
            with page.expect_download(timeout=30000) as download_info:
                csv_choice.click(timeout=15000)
            download = download_info.value
            suggested = download.suggested_filename or "studio-export.csv"
            if not suggested.lower().endswith(".csv"):
                fail(f"Studio did not return a CSV file (received {Path(suggested).suffix or 'unknown format'}).")

            target = DROPBOX_DIR / f"youtube_studio_{stamp}.csv"
            download.save_as(target)
            if not target.exists() or target.stat().st_size < 20:
                fail("Downloaded CSV is empty or too small.")

            # Validate it as CSV without logging its contents or metrics.
            try:
                with target.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.reader(handle)
                    headers = next(reader, [])
                    if len(headers) < 2:
                        fail("CSV header validation failed.")
                    row_count = sum(1 for _ in reader)
            except (UnicodeDecodeError, csv.Error, StopIteration):
                fail("CSV could not be parsed as UTF-8 CSV.")

            # Import normalized snapshots beside the source CSV. Do not print row values.
            import subprocess
            out_dir = DROPBOX_DIR / "normalized"
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("import_youtube_studio_csv.py")),
                 str(target), "--out-dir", str(out_dir)],
                check=False,
            )
            if result.returncode != 0:
                fail("CSV saved, but the normalizer rejected its structure. Raw export was retained; check importer output in the runner log.")
            print(f"EXPORT_OK file={target.name} rows={row_count} bytes={target.stat().st_size}")
        except PlaywrightTimeoutError:
            fail("Timed out waiting for the Studio export control or CSV download. UI may have changed.")
        finally:
            context.close()

if __name__ == "__main__":
    main()
