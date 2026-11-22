#!/usr/bin/env python3
"""TV OFF music provider router.

Stable Audio is opt-in because hosted generation consumes paid credits.
Without both STABILITY_AUDIO_ENABLED=true and STABILITY_API_KEY, the existing
local TV OFF composer remains the zero-cost fallback.
"""
import os
import subprocess
import sys


def main():
    enabled = os.environ.get("STABILITY_AUDIO_ENABLED", "").strip().lower() == "true"
    api_key = os.environ.get("STABILITY_API_KEY", "").strip()
    if enabled and api_key:
        print("MUSIC PROVIDER: Stability AI Stable Audio 3 (explicitly enabled).")
        subprocess.run([sys.executable, "generate_stable_audio.py"], check=True)
        return
    if enabled and not api_key:
        raise RuntimeError(
            "STABILITY_AUDIO_ENABLED=true but STABILITY_API_KEY is missing. "
            "Refusing a silent fallback because the configured provider is unavailable."
        )
    print("MUSIC PROVIDER: existing local TV OFF composer (no paid API call).")
    subprocess.run([sys.executable, "generate_original_music.py"], check=True)


if __name__ == "__main__":
    main()
