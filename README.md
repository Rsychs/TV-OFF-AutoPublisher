# TV OFF — YouTube AutoPublisher

Free, self-hosted YouTube uploader using the official YouTube Data API and GitHub Actions. The workflow checks the schedule hourly and can also be started manually.

## Current TV OFF content strategy

New releases are limited to three categories:
- White Noise — original synthetic audio generated locally.
- Brown Noise — original synthetic audio generated locally.
- Original Music — locally synthesized ambient compositions, with no third-party recordings, samples, or borrowed melodies.

Nature sounds and external field recordings are retired from new production. Legacy schedule and backlog CSV queues have been cleared to prevent accidental nature uploads. Long-form videos retain the 10-hour duration and fully black screen; Shorts use the same three-category rotation.

## Mobile-first setup

### 1. Google Cloud
1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable **YouTube Data API v3**.
3. Configure the OAuth consent screen. Add the Google account that manages **TV OFF (@tvoffsounds)** as a test user if the app is in Testing.
4. Create an OAuth client ID of type **Web application**.
5. Add this exact Authorized redirect URI: `https://developers.google.com/oauthplayground`.
6. Save the **Client ID** and **Client secret** privately.

### 2. Get a refresh token on your phone
1. Open [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground).
2. Open its settings (gear icon), enable **Use your own OAuth credentials**, and enter the Client ID and Client secret from step 1.
3. In **Step 1**, enter this scope:
   `https://www.googleapis.com/auth/youtube.upload`
4. Click **Authorize APIs** and sign in with the Google account that manages the TV OFF channel. Approve access.
5. In **Step 2**, click **Exchange authorization code for tokens**.
6. Copy the returned **refresh_token**. Do not send it in chat or put it in a public file.

### 3. Add GitHub Actions secrets
Open [repository Actions secrets](https://github.com/Rsychs/TV-OFF-AutoPublisher/settings/secrets/actions) and create these three **Repository secrets**:

| Name | Value |
|---|---|
| `YT_CLIENT_ID` | OAuth Client ID from Google Cloud |
| `YT_CLIENT_SECRET` | OAuth Client secret from Google Cloud |
| `YT_REFRESH_TOKEN` | refresh_token from OAuth Playground |

Never add these values to repository files, issues, or chat. They are stored as GitHub Actions secrets.

### 3a. Enable read-only channel analytics (required for the growth dashboard)

The uploader token above only requests upload permission. Do not replace it. The analytics collector uses a separate refresh token.

1. In the same Google Cloud project, enable **YouTube Analytics API**.
2. Open [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground), use the same OAuth client credentials, and enter this scope in Step 1:
   `https://www.googleapis.com/auth/yt-analytics.readonly`
3. Authorize with the Google account that owns TV OFF and exchange the code for tokens.
4. Copy the new **refresh_token** privately. Do not paste it into chat or commit it.
5. In GitHub repository Settings → Secrets and variables → Actions, add a new repository secret:
   - `YT_ANALYTICS_REFRESH_TOKEN` = the new analytics refresh token.
6. Leave `YT_REFRESH_TOKEN` unchanged; it continues to be used for publishing.

After adding the secret, open the repository Actions tab, select **TV OFF — YouTube Analytics Collector**, and click **Run workflow**. The collector runs daily at 03:17 UTC and saves the last 28 complete days of per-video data to `analytics/youtube_daily.csv` and `analytics/youtube_daily.json`.

The first collector records views, watch time, average view duration/percentage, subscribers gained/lost, likes, comments and shares. Reporting can be delayed by YouTube. Shorts feed-specific viewed-vs-swiped metrics and impression CTR are not part of this first API collector.

### 4. Add videos and schedule
1. Add MP4 files under `videos/` in the repository.
2. Edit `schedule.csv` using this format:

```csv
filename,title,description,tags,publish_at
videos/Fireplace.mp4,Fireplace Ambience,Relaxing fireplace sounds,fireplace;relax;sleep,2026-11-08T20:00:00+02:00
```

- `filename`: path to the MP4 inside the repository.
- `tags`: optional, separated by semicolons.
- `publish_at`: ISO 8601 with timezone offset. Riga is UTC+2 in winter and UTC+3 in summer; use the correct offset for the date.
- Future publication times are uploaded as private and scheduled with YouTube. Past/current times are published public.

### 5. Run
Open the repository's **Actions** tab, select **YouTube AutoPublisher**, and choose **Run workflow** to test it. It also runs hourly.

## Important limitations
- Do not commit OAuth credentials or private video files to a public repository. Secrets belong only in GitHub Actions Secrets.
- Anyone can download files in a public repository. Only add videos you are comfortable making public.
- Google may show an unverified-app warning. Only proceed if the OAuth consent screen and project are yours.
- OAuth apps left in Testing can issue refresh tokens that expire after 7 days for non-basic scopes. For ongoing unattended uploads, configure the OAuth consent screen for Production and complete any verification Google requires.
- YouTube API projects that have not passed the required audit may have uploads restricted to private visibility.
- The workflow tracks uploaded video IDs in `state.json` to avoid duplicate uploads. It does not upload files that are missing from `videos/`.
