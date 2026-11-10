# TV OFF Analytics — Cloud OAuth

Read-only channel analytics run on GitHub-hosted Actions and are saved directly
to the private Dropbox App Folder. No personal computer or
browser automation is required.

## Security

- Google scopes: `youtube.readonly` and `yt-analytics.readonly` only.
- No upload/manage scope and no Google password.
- Google OAuth client secret and refresh token are stored only in GitHub Actions Secrets.
- Dropbox app key, app secret and refresh token are stored only in GitHub Actions Secrets.
- Metrics are uploaded directly to the private Dropbox App Folder, never committed to this public repo
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

Two UTC cron entries (05:00 and 06:00 UTC) cover the Europe/Riga daylight-saving
offsets. The script checks local Riga time and only proceeds at 08:00; the other
invocation exits without fetching. Manual `workflow_dispatch` is also available.

## Google OAuth setup (one-time)

1. In Google Cloud Console create a project and enable **YouTube Analytics API**
   and **YouTube Data API v3**.
2. Configure the OAuth consent screen as External. Add the Google account that
   owns TV OFF as a test user while setting up.
3. Create OAuth Client ID → **Web application**. Add this redirect URI exactly:
   `https://developers.google.com/oauthplayground`.
4. Open [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground). In Settings select **Use your own OAuth credentials** and set access type to **Offline**. Enter the client ID and secret from Cloud Console. Keep both private.
5. Request these scopes:
   `https://www.googleapis.com/auth/youtube.readonly`
   `https://www.googleapis.com/auth/yt-analytics.readonly`
6. Authorize the Google account that owns TV OFF. Exchange the authorization code in Step 2 and copy the **refresh token** from the response. The refresh token is the long-lived credential; do not copy the short-lived access token instead.
7. For unattended operation, set the OAuth consent app to **In production** after
   validation. An External app left in Testing can issue refresh tokens that expire
   after seven days for these scopes. Production apps may show an unverified-app
   warning or require verification for broader distribution; this setup is for the
   channel owner's own use.

## Dropbox OAuth setup (one-time)

1. In [Dropbox App Console](https://www.dropbox.com/developers/apps) create a **Scoped access → App folder** app named `TV OFF Analytics`. Grant only `files.content.write`. The app will save snapshots inside its private app folder (`/Apps/TV OFF Analytics` in Dropbox); it does not need access to the rest of your Dropbox files.
2. Open this authorization URL in your browser, replacing `YOUR_APP_KEY` with the app key: `https://www.dropbox.com/oauth2/authorize?client_id=YOUR_APP_KEY&response_type=code&token_access_type=offline`. Approve access; Dropbox displays an authorization code.
3. Exchange the code at `https://api.dropboxapi.com/oauth2/token` using `grant_type=authorization_code`, the code, app key and app secret. Copy the returned **refresh_token**. Keep the app key, app secret and refresh token private.
4. Do not send Dropbox credentials or tokens in chat.

## GitHub Actions Secrets

In repository Settings → Secrets and variables → Actions, add:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REFRESH_TOKEN`
- `DROPBOX_APP_KEY`
- `DROPBOX_APP_SECRET`
- `DROPBOX_REFRESH_TOKEN`

Never paste secret values into ChatGPT, issues, PR comments, workflow YAML or repo
files. Also add the repository Actions variable `TV_OFF_ANALYTICS_ENABLED=true`.
Until that variable is true, the scheduled and manual workflow jobs are skipped.
After all six secrets and the variable exist, run the workflow once manually and
confirm a JSON snapshot appears in `Apps/TV OFF Analytics`.

## Autonomy boundary

This workflow only collects and stores analytics. It does not edit titles,
descriptions, tags, thumbnails, published videos/audio, schedules, or publishing
code. The existing daily decision process can analyze completed snapshots and
perform only the previously approved reversible packaging experiments with
history and rollback. No content edits are performed by this workflow.
