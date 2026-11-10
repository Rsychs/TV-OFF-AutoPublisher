#!/usr/bin/env python3
"""Fetch read-only YouTube channel analytics and store a private Dropbox snapshot.

Credentials are supplied only through environment variables (GitHub Actions
Secrets). The script never prints tokens or report rows.
"""
from __future__ import annotations
import base64, json, os, sys, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
YOUTUBE_DATA_URL = "https://www.googleapis.com/youtube/v3/videos"
DROPBOX_TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
DROPBOX_UPLOAD_URL = "https://content.dropboxapi.com/2/files/upload"
RIGA = ZoneInfo("Europe/Riga")

def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

def http_json(url, method="GET", headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read(2048).decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {urllib.parse.urlsplit(url).netloc}: {body[:400]}") from None

def refresh_google_access_token():
    form = urllib.parse.urlencode({
        "client_id": required("GOOGLE_OAUTH_CLIENT_ID"),
        "client_secret": required("GOOGLE_OAUTH_CLIENT_SECRET"),
        "refresh_token": required("GOOGLE_OAUTH_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    result = http_json(GOOGLE_TOKEN_URL, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"}, data=form)
    if not result.get("access_token"):
        raise RuntimeError("Google token refresh returned no access token.")
    return result["access_token"]

def api_query(access_token, params):
    url = ANALYTICS_URL + "?" + urllib.parse.urlencode(params)
    return http_json(url, headers={"Authorization": f"Bearer {access_token}"})

def fetch_report(access_token, start, end, metrics, dimensions=None, filters=None,
                 sort=None, max_results=200):
    result_rows, start_index = [], 1
    while True:
        params = {"ids":"channel==MINE","startDate":start,"endDate":end,
                  "metrics":metrics,"maxResults":max_results,"startIndex":start_index}
        if dimensions: params["dimensions"] = dimensions
        if filters: params["filters"] = filters
        if sort: params["sort"] = sort
        result = api_query(access_token, params)
        names = [h["name"] for h in result.get("columnHeaders", [])]
        rows = result.get("rows", [])
        result_rows.extend(dict(zip(names, row)) for row in rows)
        if len(rows) < max_results: break
        start_index += len(rows)
    return result_rows

def fetch_video_metadata(access_token, ids):
    output = {}
    for offset in range(0, len(ids), 50):
        query = urllib.parse.urlencode({"part":"snippet,contentDetails","id":",".join(ids[offset:offset+50])})
        data = http_json(YOUTUBE_DATA_URL + "?" + query,
            headers={"Authorization": f"Bearer {access_token}"})
        for item in data.get("items", []):
            output[item["id"]] = {
                "title":item.get("snippet",{}).get("title"),
                "published_at":item.get("snippet",{}).get("publishedAt"),
                "duration":item.get("contentDetails",{}).get("duration"),
                "tags":item.get("snippet",{}).get("tags",[]),
            }
    return output

def refresh_dropbox_access_token():
    key, secret = required("DROPBOX_APP_KEY"), required("DROPBOX_APP_SECRET")
    basic = base64.b64encode(f"{key}:{secret}".encode()).decode()
    form = urllib.parse.urlencode({"refresh_token":required("DROPBOX_REFRESH_TOKEN"),
                                   "grant_type":"refresh_token"}).encode()
    result = http_json(DROPBOX_TOKEN_URL, method="POST",
        headers={"Authorization":f"Basic {basic}","Content-Type":"application/x-www-form-urlencoded"},
        data=form)
    if not result.get("access_token"):
        raise RuntimeError("Dropbox token refresh returned no access token.")
    return result["access_token"]

def upload_dropbox(access_token, path, payload):
    arg = json.dumps({"path":path,"mode":"overwrite","autorename":False,"mute":True})
    req = urllib.request.Request(DROPBOX_UPLOAD_URL, data=payload, method="POST",
        headers={"Authorization":f"Bearer {access_token}","Dropbox-API-Arg":arg,
                 "Content-Type":"application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read(2048).decode("utf-8", errors="replace")
        raise RuntimeError(f"Dropbox upload failed (HTTP {exc.code}): {body[:400]}") from None

def main():
    now_riga = datetime.now(RIGA)
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and now_riga.hour != 8:
        print("SKIP: this UTC schedule occurrence is not 08:00 Europe/Riga.")
        return
    end_date = now_riga.date() - timedelta(days=1)
    start_date = date.fromisoformat(os.environ.get("TV_OFF_ANALYTICS_START_DATE","2020-01-01"))
    if start_date > end_date:
        raise RuntimeError("Analytics start date is later than the available end date.")

    google_token = refresh_google_access_token()
    video_metrics = fetch_report(
        google_token, start_date.isoformat(), end_date.isoformat(),
        "views,engagedViews,comments,likes,shares,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost",
        dimensions="video", sort="-views", max_results=200)
    daily_metrics = fetch_report(
        google_token, start_date.isoformat(), end_date.isoformat(),
        "views,estimatedMinutesWatched,subscribersGained,subscribersLost",
        dimensions="day", sort="day", max_results=200)
    video_ids = [str(row["video"]) for row in video_metrics if row.get("video")]
    metadata = fetch_video_metadata(google_token, video_ids) if video_ids else {}

    retention = {}
    for video_id in video_ids[:30]:
        try:
            retention[video_id] = fetch_report(
                google_token, start_date.isoformat(), end_date.isoformat(),
                "audienceWatchRatio,relativeRetentionPerformance,startedWatching,stoppedWatching,totalSegmentImpressions",
                dimensions="elapsedVideoTimeRatio", filters=f"video=={video_id}", max_results=200)
        except RuntimeError as exc:
            retention[video_id] = {"unavailable_reason":str(exc)[:250]}

    snapshot = {
        "schema_version":1, "source":"YouTube Analytics API v2 (OAuth read-only)",
        "generated_at":datetime.now(timezone.utc).isoformat(), "timezone":"Europe/Riga",
        "period":{"start_date":start_date.isoformat(),"end_date":end_date.isoformat()},
        "channel_video_metrics":video_metrics, "daily_channel_metrics":daily_metrics,
        "video_metadata":metadata, "audience_retention_top_30":retention,
        "coverage":{
            "video_rows":len(video_metrics),"daily_rows":len(daily_metrics),
            "retention_attempted":min(len(video_ids),30),
            "retention_not_fetched_after_rank_30":max(0,len(video_ids)-30),
            "not_available_via_this_report":[
                "YouTube Studio thumbnail impressions and CTR",
                "Shorts shown-in-feed and viewed-vs-swiped-away",
                "Some Studio-specific traffic-source and audience panels"
            ]
        }
    }
    payload=(json.dumps(snapshot,ensure_ascii=False,indent=2)+"\n").encode()
    dropbox_token=refresh_dropbox_access_token()
    path=f"/youtube_analytics_{end_date.isoformat()}.json"
    uploaded=upload_dropbox(dropbox_token,path,payload)
    print(f"ANALYTICS_EXPORT_OK date={end_date.isoformat()} videos={len(video_metrics)} daily_rows={len(daily_metrics)} retention={min(len(video_ids),30)}")
    print(f"DROPBOX_SAVED path={uploaded.get('path_display',path)}")

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(f"ANALYTICS_EXPORT_FAILED: {exc}",file=sys.stderr)
        raise SystemExit(1)
