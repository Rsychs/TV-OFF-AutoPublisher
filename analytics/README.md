# TV OFF Analytics — CSV-first, autonomous mode

This module is intentionally isolated from the publishing workflows.

## Hard constraints
- Do not enable, dispatch, or add a trigger for the `youtube-analytics` workflow.
- Do not request or use `YT_ANALYTICS_REFRESH_TOKEN`, YouTube Analytics API, or YouTube Data API for metric collection.
- Publishing workflows, issue #15 commands, schedule, shared lock, cooldown, slot deduplication, and upload state are out of scope.
- Never commit channel analytics, raw CSV exports, OAuth tokens, or private reports to this public repository.
- Never turn missing metrics into zero. Missing values remain null.
- Compare Shorts only with Shorts and long-form only with long-form.
- New content categories are limited to White Noise, Brown Noise, and Original Music.

## Import contract
Run the local importer against a YouTube Studio CSV export. Output is written to a directory outside the repository (or a user-selected private location). The source CSV is not copied or retained by the importer.

The importer:
1. Reads a video-level CSV export.
2. Normalizes known YouTube Studio column names and common variants.
3. Preserves unknown/missing metrics as null.
4. Derives format only when it can be grounded in the video duration or an explicit format field; otherwise marks it unknown.
5. Writes normalized JSON snapshots and a video registry.
6. Deduplicates identical imports by content hash and snapshot key.

## Metrics model
Common fields: video_id, title, publish_date, format, category, views, watch_time_hours, average_view_duration_seconds, average_percentage_viewed, subscribers_gained, likes, comments, shares, impressions, impressions_ctr, shown_in_feed, viewed_vs_swiped_away, source_export_hash, imported_at.

YouTube Studio exports do not always contain every field in one report. The importer must not fabricate unavailable fields. In particular, feed metrics and impressions/CTR may require separate Studio exports.

## Autonomy policy
Autonomous changes are constrained to reversible packaging and production experiments:
- Titles/descriptions/tags and thumbnail variants can be tested in a logged experiment.
- Do not alter published video files, delete videos, or claim that a thumbnail/title change caused an improvement without a comparable cohort.
- Do not change category strategy, publishing cadence, duration, or channel-wide format based on a single video.
- Use a minimum cohort of 5 comparable videos per variant where possible; otherwise report low confidence and gather more data.
- Change one major variable per experiment.
- Keep a complete before/after record and rollback value for every automated change.
- Roll back a change when the post-change cohort materially underperforms its baseline after the minimum observation window.

## Storage and security
The repository is public. Only code and non-sensitive schemas belong here. Metrics, raw exports, per-video reports, experiment history, and recommendation history must live in private storage. Until a private persistent store is configured, import/report runs must be manual and local; do not pretend that autonomous persistence is active.

## Current rollout status
- CSV parser: scaffold in progress.
- Persistent private metrics store: not configured.
- Scheduled report/decision runner: not enabled.
- Automated edits: disabled until data persistence and rollback execution are validated.


## Browser-based Studio export (experimental, opt-in)

The separate workflow `.github/workflows/studio-csv-export.yml` uses Playwright on a
self-hosted runner. It is deliberately **not** scheduled and is not connected to
publishing triggers. It can only be started manually with `workflow_dispatch`.

### Security design

- Never store a Google password, OAuth refresh token, browser cookies, or Playwright
  storage-state file in GitHub Secrets, repository files, workflow artifacts, or Dropbox.
- A dedicated Chrome profile is created locally at
  `~/.tv-off-analytics/chrome-profile` (override with `TV_OFF_BROWSER_PROFILE`).
- Run `python analytics/bootstrap_studio_profile.py` once on the runner machine.
  Complete Google sign-in manually in the visible Chrome window. This is a one-time
  human bootstrap; no credentials are entered into scripts.
- The profile remains on the self-hosted runner's disk and must be protected by the
  computer's OS account and disk encryption. Do not sync this profile to Dropbox.
- Configure runner environment variables locally:
  - `TV_OFF_BROWSER_PROFILE`: absolute path to the dedicated Chrome profile.
  - `TV_OFF_STUDIO_REPORT_URL`: saved Advanced Mode report URL, beginning
    `https://studio.youtube.com/`.
  - `TV_OFF_ANALYTICS_DROPBOX_DIR`: local Dropbox Desktop sync path for the
    already-created `TV OFF Analytics` folder.
- The runner must have Google Chrome, Python 3.10+, Playwright's Chromium/Chrome
  support, and Dropbox Desktop sync configured. The workflow uses the installed
  Chrome channel and does not install or launch a hosted cloud browser.
- Install Playwright once before first use:
  `python -m pip install playwright==1.55.0`.
- The workflow only runs on runner labels `self-hosted,tv-off-analytics`.
  It does not run on GitHub-hosted machines, and no GitHub cron is added.

### Export behavior

The report URL must point to a saved YouTube Studio Advanced Mode report. The
exporter opens that report, clicks **Export current view**, selects CSV, validates
the download, stores it in the local Dropbox-synced folder, then runs the CSV
normalizer. It never prints report rows or metric values. If Google redirects to
sign-in, the UI changes, export is unavailable, or the CSV fails validation, the
job fails closed; it does not attempt CAPTCHA/2FA bypass or session repair.

YouTube Studio's official documented path is Analytics → Advanced Mode/See more →
Export current view → choose CSV. Studio exports are limited to 500 rows per
download. See https://support.google.com/youtube/answer/9717005.

### Limitations and risk assessment

- **Session expiry / re-authentication:** Google may expire the local session or
  require a challenge. A person must sign in again locally; the workflow will stop.
- **UI drift:** YouTube can rename controls, change menus, or alter the report URL.
  Selectors are intentionally narrow; failures require maintenance rather than
  broad clicking.
- **Automation detection:** Google may challenge or block automated browser
  sessions. The workflow does not disguise identity, evade challenges, or bypass
  access controls.
- **Runner availability:** The computer must be powered on, connected, and the
  GitHub self-hosted runner service and Dropbox sync client must be running.
- **Local compromise:** Anyone with access to the runner account/profile may be
  able to use the authenticated session. Use a dedicated OS account and disk
  encryption; revoke the session and delete the local profile if compromised.
- **CSV scope:** One saved report exports only the selected view. Shorts feed
  metrics, long-form impressions/CTR, retention, and traffic-source reports may
  require separate saved views and separate runs. Do not treat absent columns as
  zero.

### Rollout status

This is an experimental, opt-in implementation on the `analytics/csv-autonomy`
branch. It is not active in production, no workflow has been run, no runner has
been registered, and no local browser profile or report URL has been configured.
The first run cannot succeed until the one-time local setup is completed.
