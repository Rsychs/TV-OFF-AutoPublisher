#!/usr/bin/env python3
"""One-time local Google sign-in bootstrap for TV OFF analytics.

This opens a dedicated local Chrome profile. No password, cookies, or browser
storage are uploaded, printed, or copied to GitHub/Dropbox.
"""
from pathlib import Path
import os
from playwright.sync_api import sync_playwright

PROFILE = Path(os.environ.get(
    "TV_OFF_BROWSER_PROFILE",
    str(Path.home() / ".tv-off-analytics" / "chrome-profile")
)).expanduser().resolve()

def main():
    PROFILE.mkdir(parents=True, exist_ok=True)
    print("Opening a dedicated local Chrome profile.")
    print("Sign in to YouTube Studio manually in the browser window.")
    print("Do not send passwords or cookies to anyone.")
    print(f"Local profile: {PROFILE}")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            channel="chrome",
            headless=False,
            accept_downloads=False,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://studio.youtube.com/", wait_until="domcontentloaded")
        input("After YouTube Studio is fully open and signed in, return here and press Enter. ")
        context.close()
    print("Local profile saved. Keep this directory private and on this computer only.")

if __name__ == "__main__":
    main()
