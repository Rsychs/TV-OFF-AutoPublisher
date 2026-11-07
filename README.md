# TV OFF — YouTube AutoPublisher

Free, self-hosted YouTube uploader using the official YouTube Data API and GitHub Actions.

## What it does
- Reads `schedule.csv`.
- Uploads each video once and schedules future publication using its Riga-local publication time.
- Sets title, description, tags, category and `public` visibility with a scheduled `publishAt`.
- Stores upload IDs in `state.json` so reruns do not upload duplicates.
- Runs hourly through GitHub Actions.

## One-time setup required
This project cannot authorize itself into your Google/YouTube account. The channel owner must complete OAuth once and add the resulting credentials as GitHub Actions secrets.

1. Create a Google Cloud project and enable **YouTube Data API v3**.
2. Configure the OAuth consent screen and create an OAuth client of type **Desktop app**.
3. Download the OAuth client JSON as `client_secret.json` into this folder.
4. On a computer with Python, run:
   ```bash
   pip install -r requirements.txt
   python get_token.py
   ```
   Sign in with the Google account that owns/manages **TV OFF (@tvoffsounds)** and approve access. This creates `token.json`.
5. In GitHub, open the repository → Settings → Secrets and variables → Actions. Add:
   - `YT_TOKEN_JSON` — the entire contents of `token.json` (it includes the OAuth client details)
6. Make the repository private before adding videos. Then upload MP4 files into `videos/` and edit `schedule.csv`. Use ISO 8601 times with the Riga offset, e.g. `2026-11-08T20:00:00+02:00`.
7. Commit and push. The workflow checks hourly. You can also run it manually from Actions.

**Important:** Do not commit `client_secret.json`, `token.json`, or private video files to a public repository. Keep the repository private. YouTube/Google may require API project verification before videos uploaded by a newly created API project can be made public. Until that is resolved, uploads may be restricted to private visibility.

## CSV format
`filename,title,description,tags,publish_at`
- `filename`: path relative to repository root, e.g. `videos/Fireplace.mp4`
- `tags`: semicolon-separated
- `publish_at`: ISO 8601 timestamp with timezone offset

The workflow does not create or upload videos that are missing from `videos/`.
