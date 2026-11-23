# TV OFF Long-form Production Pipeline

Status: implementation scaffold / production disabled.

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
3. Run ACE-Step 1.5 for a sequence of independently generated musical sections. Each section must have a distinct generation seed and composition metadata. Do not treat one short output as a complete long-form master.
4. Package all section audio and manifests; verify hashes and that section sources are distinct.
5. Assemble the requested duration (approved experiment: 1, 3, 8, 10 hours) with musically safe transitions/crossfades. No time-stretching a short track to hours and no single-source loop.
6. Generate and validate a native 1920x1080 SDXL visual for the specific release.
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

## Required workflow entry points

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

The currently active unified notebook and music publisher are designed around one short ACE-Step generation paired with a 30-second Short and a short full-track companion. Merely enabling the long-form command would not create the multi-section hour-scale output described above. Production therefore remains disabled until the real multi-section builder and independent workflow pass the acceptance tests.
