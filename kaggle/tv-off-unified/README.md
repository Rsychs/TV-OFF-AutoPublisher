# TV OFF unified ACE-Step + SDXL Turbo dry-run

This is an isolated integration prototype. It does not change `main`, does not enable YouTube publishing, and does not touch existing Shorts state.

## Pipeline

1. Pushes the existing ACE-Step 1.5 T4 smoke notebook, extended with a second SDXL Turbo stage.
2. ACE-Step generates the original instrumental WAV and validates the master.
3. The process exits before SDXL starts, so the T4 is available for image generation.
4. A deterministic Art Director maps the track style/title into an architectural interior brief. The seed is derived from the track seed and audio SHA-256.
5. SDXL Turbo generates one unique 768x1360 image, then Lanczos-upscales it to 1080x1920.
6. The manifest records audio/visual hashes, model, seed, dimensions and pipeline version.
7. GitHub Actions downloads the exact Kaggle output, renders a 30-second Short and validates duration and hashes.
8. The workflow uploads an artifact for review. It never calls the YouTube API.

## Required GitHub Actions secrets

Configure one of:
- `KAGGLE_API_TOKEN` (preferred), or
- `KAGGLE_USERNAME` and `KAGGLE_KEY`.

The Kaggle account must have GPU and internet access enabled. The private kernel slug is `TVOffset/tv-off-unified-ace-step-sdxl-turbo`.

## Run

From the GitHub Actions tab, select **TV OFF — Unified ACE-Step + SDXL Turbo (Dry Run)** and click **Run workflow** on this feature branch.

Expected artifact: `tv-off-unified-sdxl-dry-run`.

## Current scope / known limitations

- This first end-to-end pass intentionally reuses the fixed Track 010 smoke-test prompt from the existing ACE-Step notebook. It proves the ACE-Step → SDXL → FFmpeg → integrity-check path; it is not yet a rolling music-library scheduler.
- The Kaggle notebook runs sequentially on one Tesla T4. It does not assume that Kaggle has allocated a second GPU.
- The workflow is manual-dispatch only. No schedule or autonomous publication is enabled.
- YouTube OAuth secrets are not read by this workflow. `PUBLISH_MODE` defaults to `dry_run`; publication requires a separate, reviewed change.
- The existing `tv-off-single-video` concurrency group is retained with `cancel-in-progress: false`.
- Existing production workflows on `main`, analytics, published IDs, UTC deduplication and Shorts state are untouched.
