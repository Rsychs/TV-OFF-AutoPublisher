# Winter Cabin + Lo-Fi (isolated TV OFF production lane)

This is an opt-in, manual-only long-form format. It does not modify the regular
Shorts or soundscape schedules and does not add a cron trigger.

## Workflow

GitHub Actions → **TV OFF — Winter Cabin Lo-Fi (manual)**

- **Preview** (default): creates a 3-minute MP4 and stores it as a short-lived
  Actions artifact. It does not upload to YouTube or modify publication state.
- **Full**: creates a 10-hour MP4, validates its duration and audio stream, then
  uploads it through the existing YouTube uploader with a separate schedule,
  media directory, source manifest and upload ledger.

The workflow shares the `tv-off-single-video` concurrency group with the regular
long-form builder, so it waits rather than cancelling a running build.

## Original content

The music is synthesized locally from original waveforms (electric-piano-like
chords, bass, soft drums and low-level vinyl texture). No third-party audio,
samples, soundfonts or external music-generation API are used. The artwork and
animated snowfall/embers are generated locally by the Python script.

The full soundtrack is a varied 60-minute composition, looped to cover the
10-hour video. The preview is a separate 3-minute composition. A successful
preview validates the render path, not the full 10-hour upload duration or
YouTube processing.

## Safety and deduplication

- Stable publication filename: `TV-OFF_Winter_Cabin_Cozy_LoFi_10-Hours.mp4`.
- The workflow checks both the shared `state.json` and
  `winter_cabin/state.json` before full production.
- After a confirmed upload, the YouTube ID is saved to both ledgers.
- The standard schedules, source history and Shorts state are not changed.
- The workflow is manual only; there is no schedule or automatic publication.

Required repository secrets for **Full** mode are the existing
`YT_CLIENT_ID`, `YT_CLIENT_SECRET` and `YT_REFRESH_TOKEN`.
