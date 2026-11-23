# TV OFF Long-form Production Pipeline

Status: independent ACE-Step section generator, 16:9 SDXL dry-run notebook, audio assembler, and isolated dry-run workflow implemented on the feature branch; production disabled pending CI and real Colab dry-run.

## Objective

Run long-form music video production as an independent stream alongside the existing Shorts + track stream. The long-form queue has its own schedule, run ledger, publication IDs and retry state. It must not mutate the Shorts/music publication state.

## Resource model

- The existing unified ACE-Step 1.5 + SDXL Colab T4 remains the only approved GPU path.
- Long-form and Shorts/music are separate workflow entry points.
- Colab allocation is serialized by one shared resource lease/session check. A queued long-form job waits for an active Shorts/music T4 session to close; it must not allocate a second session.
- Keep the existing Shorts/music UTC-slot deduplication and 60-minute cooldown unchanged. Long-form has independent slot deduplication and must not consume a Shorts slot.
- Do not use Dropbox, Kaggle, or legacy generators.

## Production stages

1. Validate owner command, Riga slot, long-form state and existing YouTube IDs.
2. Acquire the shared Colab resource lease; verify no TV OFF session is already active.
3. Run the dedicated `longform/generate_sections_colab.py` on the Colab T4. It reuses one initialized ACE-Step 1.5 handler and sequentially generates distinct 204-second sections with unique seeds, genre prompts, titles, hashes and per-section manifests. A one-hour test currently requires 18 independent sections. Each section must have a distinct generation seed and composition metadata. Do not treat one short output as a complete long-form master.
4. Package all section audio and manifests; verify hashes and that section sources are distinct.
5. Assemble the requested duration (approved experiment: 1, 3, 8, 10 hours) with musically safe transitions/crossfades. No time-stretching a short track to hours and no single-source loop.
6. Generate and validate one native 1920x1080 SDXL Turbo visual in `longform/longform_colab_dry_run.ipynb`.
7. Render MP4 and validate exact duration, audio/video streams, finite samples, loudness, true peak/clipping, and file integrity.
8. Generate a unique genre-specific English title, description and tags. Avoid boilerplate title prefixes.
9. Upload using the existing YouTube OAuth secrets only after every validation passes.
10. Verify the returned YouTube video ID and persist it in the independent long-form ledger. Mark published only after verification.
11. Release the Colab session in an always-run cleanup step and record artifacts/logs.

## Required independent state

Suggested `longform_state.json` fields:
- `_processed_utc_slots`
- `_published_audio_sha256`
- `_published_video_sha256`
- `published_releases[]` with slot, duration, genre, title, source manifests/hashes, YouTube ID, upload status and workflow run ID
- `pending_release` for safe recovery without duplicate uploads

## Implemented dry-run path\n\n- `longform/longform_colab_dry_run.ipynb` installs the supported ACE-Step Python 3.12 environment, runs the sequential section generator, creates a native 16:9 SDXL visual, and packages hash-verified source assets.\n- `.github/workflows/tv-off-longform-dry-run.yml` uses the same `tv-off-single-video` GitHub Actions concurrency group as existing production, checks for an active `tv-off-prod` / `tv-off-unified` Colab session, runs the notebook, downloads assets before stopping Colab, assembles and renders a local dry-run MP4, and uploads an artifact. It has no YouTube upload step.\n- The first GPU dry-run is fixed to one hour for the issue-command route; workflow dispatch supports 1/3/8/10 hours.\n\n## Required workflow entry points

- Separate issue command: `/tv-off-longform YYYYMMDD-HH`
- Separate scheduled workflow at its own cadence.
- The existing `/tv-off-music` trigger remains unchanged.
- Invalid, stale, duplicate or unauthorized commands must stop before GPU allocation.

## Acceptance tests before production

- Workflow syntax and Python compilation.
- Unit tests for duration selection, slot deduplication and independent state.
- Dry-run with multiple independently generated audio sections and SDXL visual; no YouTube API call.
- Media validation confirms requested duration and distinct source hashes.
- Shared T4 lock/session reconciliation tested against an active Shorts/music run.
- Upload test only after dry-run passes; production status requires a confirmed YouTube ID.

## Current known limitation

The existing Shorts + Track workflow remains separate and unchanged. The new Long-form workflow is dry-run only; it must pass CI and a real one-hour Colab generation/render before a separate publication workflow or independent schedule is enabled.
