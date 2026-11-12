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
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
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


def fetch_recent_upload_ids(access_token, max_pages=4):
    """Return up to 200 newest uploads from the channel's uploads playlist."""
    channel_query = urllib.parse.urlencode({"part":"contentDetails","mine":"true"})
    channels = http_json(YOUTUBE_CHANNELS_URL + "?" + channel_query,
        headers={"Authorization": f"Bearer {access_token}"})
    items = channels.get("items", [])
    if not items:
        raise RuntimeError("YouTube Data API returned no channel for the authorized account.")
    uploads_playlist = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not uploads_playlist:
        raise RuntimeError("The channel's uploads playlist was not returned by YouTube Data API.")

    video_ids, page_token = [], None
    for _ in range(max_pages):
        params = {"part":"contentDetails","playlistId":uploads_playlist,"maxResults":50}
        if page_token:
            params["pageToken"] = page_token
        data = http_json(YOUTUBE_PLAYLIST_ITEMS_URL + "?" + urllib.parse.urlencode(params),
            headers={"Authorization": f"Bearer {access_token}"})
        for item in data.get("items", []):
            video_id = item.get("contentDetails", {}).get("videoId")
            if video_id and video_id not in video_ids:
                video_ids.append(video_id)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return video_ids

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
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    try:
        run_attempt = max(1, int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
    except ValueError:
        raise RuntimeError("Invalid GITHUB_RUN_ATTEMPT; refusing an untracked analytics retry.")

    # Analytics window: daily at 12:00 Europe/Riga, starting 2026-11-12.
    anchor = date(2026, 11, 12)
    cadence_days = 1
    days_from_anchor = (now_riga.date() - anchor).days
    if days_from_anchor < 0 or days_from_anchor % cadence_days != 0:
        print(f"SKIP: {now_riga.date().isoformat()} is before the daily analytics anchor.")
        return

    # First attempts run only at the exact local noon window. A failed workflow
    # job may be rerun later on the same cycle date; retries on other dates are
    # rejected by the anchored-cycle check above.
    if event_name in ("schedule", "workflow_dispatch"):
        if now_riga.hour != 12 and run_attempt == 1:
            print("SKIP: first analytics attempt is allowed only at 12:00 Europe/Riga.")
            return
    else:
        raise RuntimeError(f"Unsupported analytics event {event_name!r}; refusing non-analytics trigger.")

    print(f"ANALYTICS_WINDOW_OK date={now_riga.date().isoformat()} attempt={run_attempt}")
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

    # Discover uploads independently: Analytics can omit newly published videos
    # before their first reportable activity.
    upload_inventory_error = None
    try:
        recent_upload_ids = fetch_recent_upload_ids(google_token, max_pages=4)
    except RuntimeError as exc:
        recent_upload_ids = []
        upload_inventory_error = str(exc)[:300]

    metric_ids = {str(row["video"]) for row in video_metrics if row.get("video")}
    missing_recent_ids = [video_id for video_id in recent_upload_ids if video_id not in metric_ids]
    targeted_metrics_error = None
    if missing_recent_ids:
        try:
            targeted_rows = fetch_report(
                google_token, start_date.isoformat(), end_date.isoformat(),
                "views,engagedViews,comments,likes,shares,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost",
                dimensions="video", filters="video==" + ",".join(missing_recent_ids[:200]),
                sort="-views", max_results=200)
            targeted_by_id = {str(row["video"]): row for row in targeted_rows if row.get("video")}
            video_metrics.extend(targeted_by_id.values())
            metric_ids.update(targeted_by_id)
        except RuntimeError as exc:
            targeted_metrics_error = str(exc)[:300]
            print(f"TARGETED_VIDEO_METRICS_UNAVAILABLE: {targeted_metrics_error[:250]}")

    # Keep recent uploads visible even when YouTube has not populated metrics.
    metric_columns = [
        "views","engagedViews","comments","likes","shares",
        "estimatedMinutesWatched","averageViewDuration","averageViewPercentage",
        "subscribersGained","subscribersLost"
    ]
    for video_id in recent_upload_ids:
        if video_id not in metric_ids:
            placeholder = {"video":video_id,"metrics_status":"query_error" if targeted_metrics_error else "not_yet_available"}
            placeholder.update({key:None for key in metric_columns})
            video_metrics.append(placeholder)
        else:
            for row in video_metrics:
                if str(row.get("video")) == video_id:
                    row["metrics_status"] = "available"
                    break

    ranked_ids = [str(row["video"]) for row in video_metrics
                  if row.get("video") and row.get("metrics_status") != "not_yet_available"]
    retention_ids = list(dict.fromkeys(ranked_ids[:20] + recent_upload_ids[:10]))[:30]
    all_video_ids = list(dict.fromkeys(
        [str(row["video"]) for row in video_metrics if row.get("video")] + recent_upload_ids
    ))
    metadata = fetch_video_metadata(google_token, all_video_ids) if all_video_ids else {}

    retention = {}
    for video_id in retention_ids:
        try:
            rows = fetch_report(
                google_token, start_date.isoformat(), end_date.isoformat(),
                "audienceWatchRatio,relativeRetentionPerformance,startedWatching,stoppedWatching,totalSegmentImpressions",
                dimensions="elapsedVideoTimeRatio", filters=f"video=={video_id}", max_results=200)
            retention[video_id] = {
                "status":"available" if rows else "no_data_yet",
                "rows":rows,
                "row_count":len(rows)
            }
        except RuntimeError as exc:
            retention[video_id] = {
                "status":"api_error","rows":[],"row_count":0,
                "unavailable_reason":str(exc)[:250]
            }

    snapshot = {
        "schema_version":1, "source":"YouTube Analytics API v2 (OAuth read-only)",
        "generated_at":datetime.now(timezone.utc).isoformat(), "timezone":"Europe/Riga",
        "analytics_window":{"anchor_date":"2026-11-12","cadence_days":cadence_days,"window_date":now_riga.date().isoformat(),"window_time":"12:00"},
        "period":{"start_date":start_date.isoformat(),"end_date":end_date.isoformat()},
        "channel_video_metrics":video_metrics, "daily_channel_metrics":daily_metrics,
        "video_metadata":metadata, "audience_retention_top_30":retention,
        "coverage":{
            "video_rows":len(video_metrics),"daily_rows":len(daily_metrics),
            "uploads_discovered":len(recent_upload_ids),
            "uploads_without_metrics":sum(1 for row in video_metrics if row.get("metrics_status") in ("not_yet_available","query_error")),
            "uploads_not_yet_reported":sum(1 for row in video_metrics if row.get("metrics_status") == "not_yet_available"),
            "targeted_metrics_error":targeted_metrics_error,
            "upload_inventory_error":upload_inventory_error,
            "retention_attempted":len(retention_ids),
            "retention_with_data":sum(1 for item in retention.values() if item.get("status") == "available"),
            "retention_no_data_yet":sum(1 for item in retention.values() if item.get("status") == "no_data_yet"),
            "retention_api_errors":sum(1 for item in retention.values() if item.get("status") == "api_error"),
            "retention_not_fetched_after_rank_30":max(0,len(all_video_ids)-30),
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
    print(f"ANALYTICS_EXPORT_OK date={end_date.isoformat()} videos={len(video_metrics)} uploads={len(recent_upload_ids)} daily_rows={len(daily_metrics)} retention_attempted={len(retention_ids)}")
    print(f"DROPBOX_SAVED path={uploaded.get('path_display',path)}")

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(f"ANALYTICS_EXPORT_FAILED: {exc}",file=sys.stderr)
        raise SystemExit(1)
