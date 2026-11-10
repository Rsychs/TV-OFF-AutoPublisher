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
