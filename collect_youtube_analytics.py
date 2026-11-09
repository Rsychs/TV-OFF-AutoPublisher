import csv
import json
import os
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "analytics"
SCOPES = ["https://www.googleapis.com/auth/yt-analytics.readonly"]

def main():
    required = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_ANALYTICS_REFRESH_TOKEN"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Missing GitHub Actions secrets: " + ", ".join(missing))

    credentials = Credentials(
        token=None,
        refresh_token=os.environ["YT_ANALYTICS_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    credentials.refresh(Request())
    service = build("youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False)

    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=27)
    response = service.reports().query(
        ids="channel==MINE",
        startDate=start.isoformat(),
        endDate=end.isoformat(),
        dimensions="day,video",
        metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost,likes,comments,shares",
        sort="-day",
        maxResults=200,
    ).execute()

    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "column_headers": response.get("columnHeaders", []),
        "rows": response.get("rows", []),
        "note": "YouTube Analytics API report by day and video. Rows may be delayed; Shorts-specific feed metrics and impressions CTR are not included in this first collector.",
    }
    (OUT / "youtube_daily.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    headers = [h["name"] for h in payload["column_headers"]]
    with (OUT / "youtube_daily.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if headers:
            writer.writerow(headers)
            writer.writerows(payload["rows"])

    print(f"Saved {len(payload['rows'])} daily video rows for {start} through {end}.")
    print("Metrics: views, watch time, average view duration/percentage, subscribers, likes, comments and shares.")

if __name__ == "__main__":
    main()
