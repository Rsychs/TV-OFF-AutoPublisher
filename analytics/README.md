# TV OFF Analytics — Cloud OAuth

Read-only channel analytics run on GitHub-hosted Actions and are saved directly
to the private Dropbox folder `/TV OFF Analytics`. No personal computer or
browser automation is required.

## Security

- Google scopes: `youtube.readonly` and `yt-analytics.readonly` only.
- No upload/manage scope and no Google password.
- Google OAuth client secret and refresh token are stored only in GitHub Actions Secrets.
- Dropbox app key, app secret and refresh token are stored only in GitHub Actions Secrets.
- Metrics are uploaded directly to private Dropbox, never committed to this public repo
  or printed in workflow logs.
- Workflow token has `contents: read`; checkout credentials are not persisted.
- This workflow is isolated from publishing workflows, locks, state, slot guards,
  cooldowns and deduplication.
- Existing `youtube-analytics.yml` is not modified or enabled.

## Data and limitations

Collects top-video views, engagedViews, comments, likes, shares, estimated watch
minutes, average view duration/percentage, subscribers gained/lost; daily channel
views/watch time/subscriber trends; video title, publish time, duration and tags;
and audience-retention curves for up to 30 top videos.

It does **not** reproduce every Studio report. Thumbnail impressions/CTR and
Shorts shown-in-feed/viewed-vs-swiped-away are not included in this first version.
Missing metrics remain unavailable, never zero. The top-video report is paginated
in batches of 200. Daily reports can lag behind the current date.

Default reporting period starts 2020-01-01 and ends yesterday in Europe/Riga.

## Schedule

Two UTC cron entries (06:00 and 07:00 UTC) cover the Europe/Riga daylight-saving
offsets. The script checks local Riga time and only proceeds at 08:00; the other
invocation exits without fetching. Manual `workflow_dispatch` is also available.

## Google OAuth setup (one-time)

1. In Google Cloud Console create a project and enable **YouTube Analytics API**
   and **YouTube Data API v3**.
2. Configure the OAuth consent screen as External. Add the Google account that
   owns TV OFF as a test user while setting up.
3. Create OAuth Client ID → **Web application**. Add this redirect URI exactly:
   `https://developers.google.com/oauthplayground`.
4. Open Google OAuth 2.0 Playground settings and select **Use your own OAuth
   credentials**. Enter the client ID and secret from Cloud Console. Keep both private.
5. Request these scopes:
   `https://www.googleapis.com/auth/youtube.readonly`
   `https://www.googleapis.com/auth/yt-analytics.readonly`
6. Authorize the Google account that owns TV OFF. Exchange the code for tokens and
   copy the refresh token.
7. For unattended operation, set the OAuth consent app to **In production** after
   validation. An External app left in Testing can issue refresh tokens that expire
   after seven days for these scopes. Production apps may show an unverified-app
   warning or require verification for broader distribution; this setup is for the
   channel owner's own use.

## Dropbox OAuth setup (one-time)

1. In Dropbox App Console create an app with scoped access. Grant only
   `files.content.write`. Choose Full Dropbox access if the app-folder model cannot
   write to the existing root-level folder.
2. Complete Dropbox OAuth with offline access and obtain a refresh token.
3. Do not send Dropbox credentials or tokens in chat.

## GitHub Actions Secrets

In repository Settings → Secrets and variables → Actions, add:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`
- `DROPBOX_APP_KEY`
- `DROPBOX_APP_SECRET`
- `DROPBOX_REFRESH_TOKEN`

Never paste secret values into ChatGPT, issues, PR comments, workflow YAML or repo
files. After all six secrets exist, run the workflow once manually and confirm a
JSON snapshot appears in Dropbox.

## Autonomy boundary

This workflow only collects and stores analytics. It does not edit titles,
descriptions, tags, thumbnails, published videos/audio, schedules, or publishing
code. The existing daily decision process can analyze completed snapshots and
perform only the previously approved reversible packaging experiments with
history and rollback. No content edits are performed by this workflow.
