"""
cron_update_cache.py — Aegis · 小盾 每天 06:00 cron
====================================================

從各 source fetch 數據 + 寫進 SQLite cache + detect events

Phase 1 MVP 範圍(本地檔案 read only,不 call 外部 API,降低 fail 風險):
  ✅ V1 subscribers count(讀 JSON)
  ✅ Memoria blog articles count(glob v3.5-w*.md)
  ✅ Publish log 7-day stats(三平台 publish 篇數 + 成功率)
  ✅ Buzz captions count(glob v3.5-w*-captions.json)
  ✅ Lens reports count(glob weekly-review-W*.md)
  ✅ Token 過期警告(< 14 天提醒)

Phase 1.5(下階段加):
  ⏳ Meta Graph API insights(對 publish_log 內 post 拉 reach / engagement)
  ⏳ Cowork scheduled tasks health(last run / 連續失敗)

執行:
    python cron_update_cache.py
    python cron_update_cache.py --dry-run

排程:
    Cowork scheduled task `aegis-cron-update`(每天 06:00)
    或 PowerShell 手動 trigger 隨時更新

Author: 主對話小 M(2026-05-11,Aegis Phase 1 MVP)
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("❌ 缺套件,跑: pip install -r requirements.txt")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

V1_REPO_PATH = Path(os.getenv("V1_REPO_PATH", "C:/Alex/Github/vocab-flashcards"))
PUBLISH_LOG_PATH = Path(
    os.getenv("PUBLISH_LOG_PATH", "C:/Alex/Github/nexus-academy-memoria/scripts/publish_log.json")
)
LENS_REPORTS_PATH = Path(
    os.getenv("LENS_REPORTS_PATH", "C:/Alex/Github/nexus-academy-memoria/docs/lens-reports")
)
SQLITE_PATH = Path(os.getenv("SQLITE_PATH", str(SCRIPT_DIR / "aegis_cache.db")))
CACHE_JSON_PATH = SCRIPT_DIR / "aegis_cache.json"

# Phase 1.5 cache sync(git auto-push 給 Render)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "AlexLee1120")
GITHUB_REPO = os.getenv("GITHUB_REPO", "nexus-academy-aegis")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

# Phase 1.5 Step 2 ── Meta Graph API insights
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "").strip()
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "").strip()  # Phase 1 通常 = PAGE_ACCESS_TOKEN
META_GRAPH_API = "https://graph.facebook.com/v25.0"

# Phase 1.5 Step 4 ── YouTube Data API v3
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "").strip()
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"


# ─────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────

def init_db_if_needed(conn: sqlite3.Connection):
    """確保 schema 已 init"""
    schema_path = SCRIPT_DIR / "schema.sql"
    if schema_path.exists():
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()


def insert_metric(conn, name: str, value: float, unit: str, source: str, dry_run: bool = False):
    """寫一個 metric 到 SQLite"""
    if dry_run:
        print(f"   [dry-run] {name} = {value} ({unit}) from {source}")
        return
    conn.execute(
        "INSERT INTO metrics (metric_name, value, unit, source) VALUES (?, ?, ?, ?)",
        (name, value, unit, source),
    )


def insert_event(
    conn, event_type: str, severity: str, message: str, data: dict = None, dry_run: bool = False
):
    """寫一個 event 到 SQLite"""
    if dry_run:
        print(f"   [dry-run] EVENT [{severity}] {event_type}: {message}")
        return
    conn.execute(
        "INSERT INTO events (event_type, severity, message, data_json) VALUES (?, ?, ?, ?)",
        (event_type, severity, message, json.dumps(data or {}, ensure_ascii=False)),
    )


# ─────────────────────────────────────────────────────
# Fetch 各 source
# ─────────────────────────────────────────────────────

def fetch_v1_subscribers_count() -> int:
    """讀 V1 subscribers.json 算 active 訂閱者(legacy ── Phase 1.5 Step 3 後升級成 customer_profile)"""
    path = V1_REPO_PATH / "subscribers.json"
    if not path.exists():
        return -1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # subscribers.json 結構可能是 list 或 dict {email: ...}
        if isinstance(data, list):
            return len(data)
        elif isinstance(data, dict):
            return len(data)
        return -1
    except Exception:
        return -1


def fetch_v1_customer_profile_stats() -> dict:
    """讀 V1 customer_profile.json 算 aggregate 商業 metrics(Phase 1.5 Step 3 真實 MAU)
    Aegis 紅線:只 aggregate,不顯示 raw / per-user。

    return:
    {
        "total_profiles": N,         # 全 customer 數
        "mau_30d": N,                # 過去 30 天 last_active_at active
        "wau_7d": N,                 # 過去 7 天 last_active_at active
        "dau_1d": N,                 # 過去 1 天 last_active_at active
        "paying_users": N,           # total_orders > 0
        "active_subscriptions": N,   # subscription_status in ['active','converted']
        "total_ltv_twd": N,          # sum(lifetime_value_twd)
        "new_users_7d": N,           # 過去 7 天 created_at
        "avg_ltv_twd": N,            # total_ltv / paying_users
    }"""
    path = V1_REPO_PATH / "customer_profile.json"
    if not path.exists():
        return {"_error": f"customer_profile.json 不存在於 {path}"}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_error": f"customer_profile.json parse 失敗: {str(e)[:100]}"}

    profiles = data.get("profiles", [])
    if not isinstance(profiles, list):
        return {"_error": "customer_profile.json schema 異常(profiles 不是 list)"}

    now = datetime.now()
    cutoff_30d = now - timedelta(days=30)
    cutoff_7d = now - timedelta(days=7)
    cutoff_1d = now - timedelta(days=1)

    total = len(profiles)
    mau = wau = dau = 0
    paying = 0
    active_subs = 0
    total_ltv = 0
    new_7d = 0

    for p in profiles:
        # MAU / WAU / DAU
        last_active = p.get("last_active_at")
        if last_active:
            try:
                ts = datetime.fromisoformat(last_active)
                if ts >= cutoff_30d:
                    mau += 1
                if ts >= cutoff_7d:
                    wau += 1
                if ts >= cutoff_1d:
                    dau += 1
            except Exception:
                pass

        # Paying / Active Subs / LTV
        if (p.get("total_orders") or 0) > 0:
            paying += 1
        if p.get("subscription_status") in ("active", "converted"):
            active_subs += 1
        ltv = p.get("lifetime_value_twd") or 0
        try:
            total_ltv += int(ltv)
        except Exception:
            pass

        # New users 7d
        created_at = p.get("created_at")
        if created_at:
            try:
                ts = datetime.fromisoformat(created_at)
                if ts >= cutoff_7d:
                    new_7d += 1
            except Exception:
                pass

    avg_ltv = (total_ltv / paying) if paying > 0 else 0

    return {
        "total_profiles": total,
        "mau_30d": mau,
        "wau_7d": wau,
        "dau_1d": dau,
        "paying_users": paying,
        "active_subscriptions": active_subs,
        "total_ltv_twd": total_ltv,
        "new_users_7d": new_7d,
        "avg_ltv_twd": round(avg_ltv, 1),
    }


def fetch_memoria_blog_articles_count() -> int:
    """count v3.5-w*.md 文章數(不含 W00 總目錄)"""
    posts_dir = V1_REPO_PATH / "blog" / "posts"
    if not posts_dir.exists():
        return -1
    files = list(posts_dir.glob("v3.5-w[0-9][0-9]-*.md"))
    content_weeks = [f for f in files if not f.stem.startswith("v3.5-w00")]
    return len(content_weeks)


def fetch_publish_log_stats(days: int = 7) -> dict:
    """讀 publish_log.json 算 N 天內三平台 publish 篇數 + 成功率"""
    if not PUBLISH_LOG_PATH.exists():
        return {"total": 0, "success": 0, "fail": 0, "by_platform": {}}

    try:
        log = json.loads(PUBLISH_LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"total": 0, "success": 0, "fail": 0, "by_platform": {}}

    cutoff = datetime.now() - timedelta(days=days)
    by_platform = {"fb": {"success": 0, "fail": 0}, "ig": {"success": 0, "fail": 0}, "threads": {"success": 0, "fail": 0}}
    total_success = 0
    total_fail = 0

    for entry in log:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts < cutoff:
                continue
            platform = entry.get("platform", "?")
            success = entry.get("success", False)
            if platform in by_platform:
                if success:
                    by_platform[platform]["success"] += 1
                    total_success += 1
                else:
                    by_platform[platform]["fail"] += 1
                    total_fail += 1
        except Exception:
            continue

    return {
        "total": total_success + total_fail,
        "success": total_success,
        "fail": total_fail,
        "by_platform": by_platform,
    }


def fetch_buzz_captions_count() -> int:
    """count Buzz 已生的 v3.5-w*-captions.json"""
    posts_dir = V1_REPO_PATH / "blog" / "posts"
    if not posts_dir.exists():
        return -1
    files = list(posts_dir.glob("v3.5-w[0-9][0-9]-*-captions.json"))
    return len(files)


def fetch_lens_reports_count() -> int:
    """count Lens 已寫的 weekly-review-W*.md"""
    if not LENS_REPORTS_PATH.exists():
        return 0
    files = list(LENS_REPORTS_PATH.glob("weekly-review-W*.md"))
    return len(files)


# ─────────────────────────────────────────────────────
# Phase 1.5 Step 2 ── Meta Graph API insights
# ─────────────────────────────────────────────────────

def extract_post_ids_from_publish_log(days: int = 7) -> dict:
    """從 publish_log.json 抽出過去 N 天 success entries 的 post_id / media_id
    回傳 {"fb": [post_id, ...], "ig": [media_id, ...]}"""
    if not PUBLISH_LOG_PATH.exists():
        return {"fb": [], "ig": []}

    try:
        log = json.loads(PUBLISH_LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"fb": [], "ig": []}

    cutoff = datetime.now() - timedelta(days=days)
    fb_ids = []
    ig_ids = []

    for entry in log:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts < cutoff:
                continue
            if not entry.get("success"):
                continue
            platform = entry.get("platform", "")
            result = entry.get("result", {})

            if platform == "fb":
                # FB result format: {"id": "page_id_post_id"} or {"post_id": ...}
                pid = result.get("id") or result.get("post_id")
                if pid:
                    fb_ids.append(pid)
            elif platform == "ig":
                # IG result format: {"container_id": ..., "publish": {"id": "media_id"}}
                pub = result.get("publish", {})
                mid = pub.get("id") if isinstance(pub, dict) else None
                if mid:
                    ig_ids.append(mid)
        except Exception:
            continue

    return {"fb": fb_ids, "ig": ig_ids}


def fetch_fb_post_insights(post_id: str, token: str) -> dict:
    """call Meta Graph API 拿 FB Page post 互動數據
    return {"likes": int, "comments": int, "shares": int, "engagement": int}
    fail return 0s + log warning(不擋整個 cron)

    註(2026-05-11):
    - insights API 在 v25.0 對我們 token 全 #100 → 放棄
    - 改用 public summary fields(用 pages_read_engagement scope,已有)
    - v25.0 deprecate 掉了:shares、reactions.summary
    - 還活著:comments.summary(true)、likes.summary(true)── likes 是 OG endpoint,理論上最 stable
    - 同時印 raw response 給 debug,看 API 還支援什麼 fields"""
    try:
        resp = requests.get(
            f"{META_GRAPH_API}/{post_id}",
            params={
                "fields": "likes.summary(true),comments.summary(true),created_time",
                "access_token": token,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            err_detail = resp.text[:300]
            try:
                err_json = resp.json().get("error", {})
                err_detail = f"code={err_json.get('code')} | type={err_json.get('type')} | msg={err_json.get('message','')[:200]}"
            except Exception:
                pass
            return {"likes": 0, "comments": 0, "shares": 0, "engagement": 0, "_error": f"HTTP {resp.status_code} | {err_detail}"}
        data = resp.json()
        likes = int(data.get("likes", {}).get("summary", {}).get("total_count", 0) or 0)
        comments = int(data.get("comments", {}).get("summary", {}).get("total_count", 0) or 0)
        return {
            "likes": likes,
            "comments": comments,
            "shares": 0,  # v25.0 deprecate,顯示 N/A
            "engagement": likes + comments,
            "_raw_sample": {
                "created_time": data.get("created_time"),
                "available_keys": list(data.keys()),
            },
        }
    except Exception as e:
        return {"likes": 0, "comments": 0, "shares": 0, "engagement": 0, "_error": str(e)[:100]}


def fetch_ig_media_insights(media_id: str, token: str) -> dict:
    """call Meta Graph API 拿 IG media insights
    return {"reach": int, "saved": int, "likes": int, "comments": int, "interactions": int}

    註:IG insights API 需要 instagram_manage_insights scope(我們 OAuth 沒加,等 Phase 1.5 補)
    Phase 1.5 fallback:用 public fields(/{media_id}?fields=like_count,comments_count)
    這個 instagram_basic 就夠 ── 可拿 likes / comments(不需要 manage_insights)"""

    # Step 1:try insights API(可能 fail because scope missing)
    try:
        resp = requests.get(
            f"{META_GRAPH_API}/{media_id}/insights",
            params={
                "metric": "reach,saved,likes,comments,total_interactions",
                "access_token": token,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            # 成功(scope 夠)── 拿到完整 insights
            data = resp.json().get("data", [])
            result = {"reach": 0, "saved": 0, "likes": 0, "comments": 0, "interactions": 0}
            for item in data:
                name = item.get("name", "")
                values = item.get("values", [])
                if not values:
                    continue
                value = values[0].get("value", 0)
                if name == "reach":
                    result["reach"] = int(value or 0)
                elif name == "saved":
                    result["saved"] = int(value or 0)
                elif name == "likes":
                    result["likes"] = int(value or 0)
                elif name == "comments":
                    result["comments"] = int(value or 0)
                elif name == "total_interactions":
                    result["interactions"] = int(value or 0)
            return result
        # else: insights API fail → 走 fallback Step 2
        insights_err = ""
        try:
            insights_err = resp.json().get("error", {}).get("message", "")[:100]
        except Exception:
            pass
    except Exception as e:
        insights_err = str(e)[:100]

    # Step 2:fallback ── public fields(只需要 instagram_basic scope)
    try:
        resp2 = requests.get(
            f"{META_GRAPH_API}/{media_id}",
            params={
                "fields": "like_count,comments_count,timestamp,permalink,media_type",
                "access_token": token,
            },
            timeout=15,
        )
        if resp2.status_code == 200:
            data = resp2.json()
            return {
                "reach": 0,  # 沒有 fallback 來源
                "saved": 0,  # 沒有 fallback 來源
                "likes": int(data.get("like_count", 0) or 0),
                "comments": int(data.get("comments_count", 0) or 0),
                "interactions": int(data.get("like_count", 0) or 0) + int(data.get("comments_count", 0) or 0),
                "_fallback": f"用 public fields(insights scope 缺 instagram_manage_insights)",
                "_raw_sample": {
                    "like_count": data.get("like_count"),
                    "comments_count": data.get("comments_count"),
                    "timestamp": data.get("timestamp"),
                    "permalink": data.get("permalink"),
                    "media_type": data.get("media_type"),
                },
            }
        err_detail = resp2.text[:300]
        try:
            err_json = resp2.json().get("error", {})
            err_detail = f"code={err_json.get('code')} | type={err_json.get('type')} | msg={err_json.get('message','')[:200]}"
        except Exception:
            pass
        return {"reach": 0, "saved": 0, "likes": 0, "comments": 0, "interactions": 0, "_error": f"insights fail: {insights_err} | fallback fail: HTTP {resp2.status_code} | {err_detail}"}
    except Exception as e:
        return {"reach": 0, "saved": 0, "likes": 0, "comments": 0, "interactions": 0, "_error": f"insights fail: {insights_err} | fallback exception: {str(e)[:100]}"}


def fetch_meta_aggregate_insights(days: int = 7) -> dict:
    """聚合過去 N 天 FB + IG 真實觸及 / engagement
    return:
    {
        "fb": {"reach": N, "engaged": N, "clicks": N, "post_count": N, "errors": N},
        "ig": {"reach": N, "interactions": N, "saved": N, "likes": N, "comments": N, "post_count": N, "errors": N}
    }"""
    if not PAGE_ACCESS_TOKEN:
        return {
            "fb": {"likes": 0, "comments": 0, "shares": 0, "engagement": 0, "post_count": 0, "errors": 0, "_skipped": "PAGE_ACCESS_TOKEN 未設"},
            "ig": {"reach": 0, "interactions": 0, "saved": 0, "likes": 0, "comments": 0, "post_count": 0, "errors": 0, "_skipped": "PAGE_ACCESS_TOKEN 未設"},
        }

    ids = extract_post_ids_from_publish_log(days)
    fb_token = PAGE_ACCESS_TOKEN
    ig_token = IG_ACCESS_TOKEN or PAGE_ACCESS_TOKEN  # Phase 1 fallback

    # FB aggregate(2026-05-11:用 public summary fields ── likes/comments
    # insights API 在 v25.0 對我們 token 全 #100,放棄 insights 路線)
    fb_agg = {"likes": 0, "comments": 0, "shares": 0, "engagement": 0, "post_count": len(ids["fb"]), "errors": 0, "error_samples": [], "raw_samples": []}
    for pid in ids["fb"]:
        ins = fetch_fb_post_insights(pid, fb_token)
        if "_error" in ins:
            fb_agg["errors"] += 1
            if len(fb_agg["error_samples"]) < 2:
                fb_agg["error_samples"].append({"post_id": pid, "error": ins["_error"]})
        else:
            fb_agg["likes"] += ins.get("likes", 0)
            fb_agg["comments"] += ins.get("comments", 0)
            fb_agg["shares"] += ins.get("shares", 0)
            fb_agg["engagement"] += ins.get("engagement", 0)
            if len(fb_agg["raw_samples"]) < 2 and "_raw_sample" in ins:
                fb_agg["raw_samples"].append({"post_id": pid, **ins["_raw_sample"]})

    # IG aggregate
    ig_agg = {"reach": 0, "interactions": 0, "saved": 0, "likes": 0, "comments": 0, "post_count": len(ids["ig"]), "errors": 0, "error_samples": [], "fallback_count": 0, "raw_samples": []}
    for mid in ids["ig"]:
        ins = fetch_ig_media_insights(mid, ig_token)
        if "_error" in ins:
            ig_agg["errors"] += 1
            if len(ig_agg["error_samples"]) < 2:
                ig_agg["error_samples"].append({"media_id": mid, "error": ins["_error"]})
        else:
            if "_fallback" in ins:
                ig_agg["fallback_count"] += 1
                # 留前 2 筆 raw response sample 給 debug 用
                if len(ig_agg["raw_samples"]) < 2 and "_raw_sample" in ins:
                    ig_agg["raw_samples"].append({"media_id": mid, **ins["_raw_sample"]})
            ig_agg["reach"] += ins["reach"]
            ig_agg["interactions"] += ins["interactions"]
            ig_agg["saved"] += ins["saved"]
            ig_agg["likes"] += ins["likes"]
            ig_agg["comments"] += ins["comments"]

    return {"fb": fb_agg, "ig": ig_agg}


# ─────────────────────────────────────────────────────
# Phase 1.5 Step 4 ── YouTube Data API v3
# ─────────────────────────────────────────────────────

def fetch_youtube_stats(days: int = 7) -> dict:
    """Call YouTube Data API v3 拿頻道 aggregate stats
    return {
        "subscribers": N,           # 訂閱數
        "total_views": N,           # 累積觀看次數
        "total_videos": N,          # 累積影片數
        "uploads_7d": N,            # 過去 N 天上傳數
        "views_7d": N,              # 過去 N 天總觀看(對 7 天影片加總)
        "likes_7d": N,              # 過去 N 天總讚數
        "comments_7d": N,           # 過去 N 天總留言數
    }
    fail return {"_error": ...} (不擋整個 cron)

    API quota: ~3 units / cron run(10K daily quota = 3000 cron/day,完全不會超)"""
    if not YOUTUBE_API_KEY:
        return {"_skipped": "YOUTUBE_API_KEY 未設"}
    if not YOUTUBE_CHANNEL_ID:
        return {"_skipped": "YOUTUBE_CHANNEL_ID 未設"}

    # ── Step 1: channels.list 拿 statistics + uploads playlist ID(1 unit)
    try:
        resp = requests.get(
            f"{YOUTUBE_API}/channels",
            params={
                "part": "statistics,contentDetails",
                "id": YOUTUBE_CHANNEL_ID,
                "key": YOUTUBE_API_KEY,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            err_detail = resp.text[:300]
            try:
                err_json = resp.json().get("error", {})
                err_detail = f"code={err_json.get('code')} | msg={err_json.get('message','')[:200]}"
            except Exception:
                pass
            return {"_error": f"channels.list HTTP {resp.status_code} | {err_detail}"}
        items = resp.json().get("items", [])
        if not items:
            return {"_error": f"channels.list return 空 items(channel ID 對嗎?{YOUTUBE_CHANNEL_ID})"}
        channel = items[0]
        stats = channel.get("statistics", {})
        subscribers = int(stats.get("subscriberCount", 0) or 0)
        total_views = int(stats.get("viewCount", 0) or 0)
        total_videos = int(stats.get("videoCount", 0) or 0)
        uploads_playlist = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
        if not uploads_playlist:
            return {
                "subscribers": subscribers, "total_views": total_views, "total_videos": total_videos,
                "uploads_7d": 0, "views_7d": 0, "likes_7d": 0, "comments_7d": 0,
                "_warning": "channel 沒有 uploads playlist(罕見)",
            }
    except Exception as e:
        return {"_error": f"channels.list exception: {str(e)[:150]}"}

    # ── Step 2: playlistItems.list 拿過去 N 天上傳 video IDs(1 unit per page)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent_video_ids = []
    page_token = None
    pages_fetched = 0
    max_pages = 4  # 安全上限(50 items/page * 4 = 200 影片/N 天,Hina daily 7/週 遠遠夠)

    try:
        while pages_fetched < max_pages:
            params = {
                "part": "snippet,contentDetails",
                "playlistId": uploads_playlist,
                "maxResults": 50,
                "key": YOUTUBE_API_KEY,
            }
            if page_token:
                params["pageToken"] = page_token
            resp = requests.get(f"{YOUTUBE_API}/playlistItems", params=params, timeout=15)
            if resp.status_code != 200:
                break
            data = resp.json()
            items = data.get("items", [])
            stop_paging = False
            for item in items:
                published = item.get("contentDetails", {}).get("videoPublishedAt") or item.get("snippet", {}).get("publishedAt", "")
                vid_id = item.get("contentDetails", {}).get("videoId") or item.get("snippet", {}).get("resourceId", {}).get("videoId")
                if not vid_id or not published:
                    continue
                try:
                    pub_ts = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except Exception:
                    continue
                if pub_ts >= cutoff:
                    recent_video_ids.append(vid_id)
                else:
                    # uploads playlist 是 desc by date,遇到 < cutoff 就停 paging
                    stop_paging = True
                    break
            pages_fetched += 1
            page_token = data.get("nextPageToken")
            if stop_paging or not page_token:
                break
    except Exception as e:
        return {
            "subscribers": subscribers, "total_views": total_views, "total_videos": total_videos,
            "uploads_7d": 0, "views_7d": 0, "likes_7d": 0, "comments_7d": 0,
            "_warning": f"playlistItems exception: {str(e)[:150]}",
        }

    # ── Step 3: videos.list 對 7 天 video 拿 statistics 加總(1 unit per 50 IDs)
    views_7d = likes_7d = comments_7d = 0
    if recent_video_ids:
        try:
            # batch 50 個 ID 一次 query
            for i in range(0, len(recent_video_ids), 50):
                batch = recent_video_ids[i:i + 50]
                resp = requests.get(
                    f"{YOUTUBE_API}/videos",
                    params={
                        "part": "statistics",
                        "id": ",".join(batch),
                        "key": YOUTUBE_API_KEY,
                    },
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue
                for v in resp.json().get("items", []):
                    s = v.get("statistics", {})
                    views_7d += int(s.get("viewCount", 0) or 0)
                    likes_7d += int(s.get("likeCount", 0) or 0)
                    comments_7d += int(s.get("commentCount", 0) or 0)
        except Exception as e:
            return {
                "subscribers": subscribers, "total_views": total_views, "total_videos": total_videos,
                "uploads_7d": len(recent_video_ids), "views_7d": 0, "likes_7d": 0, "comments_7d": 0,
                "_warning": f"videos.list exception: {str(e)[:150]}",
            }

    return {
        "subscribers": subscribers,
        "total_views": total_views,
        "total_videos": total_videos,
        "uploads_7d": len(recent_video_ids),
        "views_7d": views_7d,
        "likes_7d": likes_7d,
        "comments_7d": comments_7d,
    }


# ─────────────────────────────────────────────────────
# Nexus Agent 戰情牌 ── 讀 agent_status.json(Cowork scheduled tasks 狀態)
# 2026-05-15:Alex Boss 要「一個畫面看哪個 agent 在跑/卡住」
# agent_status.json 由 aegis-cron-update Cowork task 每天 dump(它有 MCP access)
# cron_update_cache.py 純 Python 沒 MCP access,只負責 read + parse + 轉時區
# ─────────────────────────────────────────────────────

AGENT_STATUS_JSON_PATH = SCRIPT_DIR / "agent_status.json"

# task → agent 對應(從 description「---XXX」後綴 + 關鍵字 parse)
_AGENT_RULES = [
    # (判斷函式, agent 名, category)
    ("Echo 小迴", "Echo", "nexus_agent"),
    ("小M2", "M2", "nexus_agent"),
    ("小小星", "小小星", "nexus_agent"),
    ("Lumi 小光", "Lumi", "nexus_agent"),
    ("Verba 小語", "Verba", "nexus_agent"),
    ("Bibli", "Bibli", "nexus_agent"),
    ("Pact 小盟", "Pact", "nexus_agent"),
    ("Buzz · 小波", "Buzz", "nexus_agent"),
    ("Lens · 小鏡", "Lens", "nexus_agent"),
    ("Aegis · 小盾", "Aegis", "nexus_agent"),
    ("---小M", "主對話小 M", "nexus_agent"),
]


def _parse_agent(task_id: str, description: str) -> tuple:
    """從 task description / id parse 出 (agent 名, category)"""
    for keyword, agent, category in _AGENT_RULES:
        if keyword in description:
            return agent, category
    # 系統 task
    if task_id == "meta-publish-evening":
        return "Meta 推播", "system"
    if task_id == "memoria-blog-publish":
        return "Blog 自動上架", "system"
    # Alex 個人排程(產業情報 / 飆股 / 週報)
    if task_id.startswith("alex-"):
        return "Alex 個人", "alex_personal"
    return "(未分類)", "other"


def _utc_to_taipei(utc_iso: str) -> str:
    """UTC ISO → 台灣時間字串 MM/DD HH:MM。None / 空 → '──'"""
    if not utc_iso:
        return "──"
    try:
        # 處理 Z 結尾 + 毫秒
        s = utc_iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        tw = dt + timedelta(hours=8)
        return tw.strftime("%m/%d %H:%M")
    except Exception:
        return "??"


def fetch_agent_status() -> list:
    """讀 agent_status.json,parse agent 名 + 轉時區 + group by agent。
    回傳 list of agent dict(給 dashboard 顯示):
    [
        {"agent": "Echo", "category": "nexus_agent",
         "tasks": [{"task_id", "description", "schedule", "enabled",
                    "last_run_tw", "next_run_tw", "health"}, ...]},
        ...
    ]
    agent_status.json 不存在 → 回 [](dashboard 顯示「尚未 dump」)"""
    if not AGENT_STATUS_JSON_PATH.exists():
        return []
    try:
        data = json.loads(AGENT_STATUS_JSON_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"⚠️  agent_status.json parse 失敗: {e}")
        return []

    tasks = data.get("tasks", [])
    # group by agent
    groups = {}  # agent → {category, tasks: []}
    for t in tasks:
        agent, category = _parse_agent(t.get("task_id", ""), t.get("description", ""))
        enabled = t.get("enabled", True)
        health = "disabled" if not enabled else "ok"
        task_view = {
            "task_id": t.get("task_id", ""),
            "description": t.get("description", ""),
            "schedule": t.get("schedule", ""),
            "enabled": enabled,
            "last_run_tw": _utc_to_taipei(t.get("last_run_at")),
            "next_run_tw": _utc_to_taipei(t.get("next_run_at")),
            "health": health,
        }
        if agent not in groups:
            groups[agent] = {"agent": agent, "category": category, "tasks": []}
        groups[agent]["tasks"].append(task_view)

    # category 排序:nexus_agent 優先 → system → alex_personal → other
    cat_order = {"nexus_agent": 0, "system": 1, "alex_personal": 2, "other": 3}
    result = sorted(groups.values(), key=lambda g: (cat_order.get(g["category"], 9), g["agent"]))
    return result


# ─────────────────────────────────────────────────────
# Phase 1.5: Cache sync(SQLite → cache.json → git push 給 Render)
# ─────────────────────────────────────────────────────

def export_cache_to_json(conn: sqlite3.Connection, agent_status: list = None) -> dict:
    """從 SQLite query latest metrics + recent events,組成 cache.json schema
    給 Render dashboard 直接 read(避免 Render 環境讀不到 Windows local files)

    agent_status:由 fetch_agent_status() 傳入(不走 SQLite,直接放進 cache.json)"""
    cur = conn.cursor()

    # 拿每個 metric 的最新 value
    cur.execute(
        """
        SELECT metric_name, value, unit, source, MAX(collected_at) as collected_at
        FROM metrics
        GROUP BY metric_name
        """
    )
    latest_metrics = {}
    for row in cur.fetchall():
        name, value, unit, source, collected_at = row
        latest_metrics[name] = {
            "value": value,
            "unit": unit,
            "source": source,
            "collected_at": collected_at,
        }

    # 拿過去 7 天 events
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    cur.execute(
        """
        SELECT id, event_type, severity, message, data_json, created_at
        FROM events
        WHERE created_at >= ?
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (cutoff,),
    )
    events = []
    for row in cur.fetchall():
        eid, etype, sev, msg, data_json, created = row
        try:
            data = json.loads(data_json or "{}")
        except Exception:
            data = {}
        events.append({
            "id": eid,
            "event_type": etype,
            "severity": sev,
            "message": msg,
            "data": data,
            "created_at": created,
        })

    return {
        "schema_version": "1.6.0",
        "exported_at": datetime.now().isoformat(),
        "latest_metrics": latest_metrics,
        "recent_events": events,
        "agent_status": agent_status or [],
    }


def write_cache_json(cache_data: dict, dry_run: bool = False):
    """把 cache_data 寫到 aegis_cache.json"""
    if dry_run:
        print(f"   [dry-run] 會寫 {CACHE_JSON_PATH}({len(cache_data['latest_metrics'])} metrics, {len(cache_data['recent_events'])} events)")
        return
    CACHE_JSON_PATH.write_text(
        json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   ✅ aegis_cache.json 寫好({CACHE_JSON_PATH})")


def git_push_cache(dry_run: bool = False):
    """git auto-commit + push aegis_cache.json 上 GitHub
    用 PAT 透過 HTTPS push,token 不寫進 git config"""
    if dry_run:
        print(f"   [dry-run] 會跑 git add aegis_cache.json + commit + push")
        return

    if not GITHUB_TOKEN:
        print(f"   ⚠️  GITHUB_TOKEN 沒設,skip git push(本地測試 OK,production 要設)")
        return

    cwd = SCRIPT_DIR

    def run(args: list, check: bool = True):
        result = subprocess.run(
            ["git"] + args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8"
        )
        if check and result.returncode != 0:
            safe_stderr = result.stderr.replace(GITHUB_TOKEN, "***TOKEN***")
            print(f"   ❌ git {' '.join(args[:2])} failed: {safe_stderr[:300]}")
            sys.exit(1)
        return result.stdout, result.stderr, result.returncode

    # 1. Add cache.json
    run(["add", "aegis_cache.json"])
    print(f"   ✅ git add aegis_cache.json")

    # 2. Commit(若無變動 skip)
    stdout, stderr, rc = run(["commit", "-m", f"chore(cache): auto update {datetime.now().strftime('%Y-%m-%d %H:%M')}"], check=False)
    if rc != 0:
        if "nothing to commit" in (stdout + stderr):
            print(f"   ℹ️  cache.json 無變動,skip commit + push")
            return
        else:
            print(f"   ❌ git commit failed: {stderr[:300]}")
            sys.exit(1)
    print(f"   ✅ git commit")

    # 3. pull --rebase --autostash(避免 fetch first error)
    push_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{GITHUB_OWNER}/{GITHUB_REPO}.git"
    run(["pull", "--rebase", "--autostash", push_url, GITHUB_BRANCH], check=False)

    # 4. Push
    stdout, stderr, rc = run(["push", push_url, GITHUB_BRANCH], check=False)
    if rc != 0:
        safe_stderr = stderr.replace(GITHUB_TOKEN, "***TOKEN***")
        print(f"   ❌ git push failed: {safe_stderr[:300]}")
        print(f"   提示:確認 PAT scope 包含 {GITHUB_OWNER}/{GITHUB_REPO} repo Contents=Read and write")
        sys.exit(1)
    print(f"   ✅ git push origin {GITHUB_BRANCH}")
    print(f"   → Render 5 分鐘內 auto-redeploy 拿最新 cache.json")


# ─────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Aegis · 小盾 每天 06:00 cron 更新 SQLite")
    parser.add_argument("--dry-run", action="store_true", help="不寫 SQLite,只 print")
    args = parser.parse_args()

    print("=" * 70)
    print(f"Aegis Cron Update | {datetime.now().isoformat()}")
    print("=" * 70)
    print()

    # 開 SQLite
    if not args.dry_run:
        conn = sqlite3.connect(str(SQLITE_PATH))
        init_db_if_needed(conn)
    else:
        conn = None

    # ── 1. V1 subscribers(legacy backup ── 新版用 v1_total_profiles)
    print("📊 1. V1 subscribers count(legacy)")
    v1_subs = fetch_v1_subscribers_count()
    if v1_subs < 0:
        print("   ⚠️  讀不到 V1 subscribers.json")
        insert_event(
            conn, "fetch_fail", "warning",
            "V1 subscribers.json 讀取失敗", {"source": str(V1_REPO_PATH)},
            dry_run=args.dry_run,
        )
    else:
        print(f"   ✅ {v1_subs} 訂閱者")
        insert_metric(conn, "v1_subscribers_count", float(v1_subs), "count", "v1_subscribers_json", dry_run=args.dry_run)

    # ── 1.5 V1 customer_profile aggregate stats(Phase 1.5 Step 3 真實 MAU + 商業現況)
    print("\n📊 1.5 V1 customer_profile 商業現況(Phase 1.5 Step 3)")
    cp_stats = fetch_v1_customer_profile_stats()
    if "_error" in cp_stats:
        print(f"   ⚠️  {cp_stats['_error']}")
        insert_event(
            conn, "fetch_fail", "warning",
            f"V1 customer_profile.json 讀取失敗: {cp_stats['_error']}", {"source": str(V1_REPO_PATH)},
            dry_run=args.dry_run,
        )
    else:
        print(f"   ✅ Total profiles: {cp_stats['total_profiles']}")
        print(f"   ✅ MAU(30d): {cp_stats['mau_30d']} | WAU(7d): {cp_stats['wau_7d']} | DAU(1d): {cp_stats['dau_1d']}")
        print(f"   ✅ Paying users: {cp_stats['paying_users']} | Active subs: {cp_stats['active_subscriptions']}")
        print(f"   ✅ Total LTV: NT${cp_stats['total_ltv_twd']:,} | Avg LTV/payer: NT${cp_stats['avg_ltv_twd']:,.0f}")
        print(f"   ✅ New users 7d: {cp_stats['new_users_7d']}")
        insert_metric(conn, "v1_total_profiles", float(cp_stats["total_profiles"]), "count", "v1_customer_profile_json", dry_run=args.dry_run)
        insert_metric(conn, "v1_mau_30d", float(cp_stats["mau_30d"]), "count", "v1_customer_profile_json", dry_run=args.dry_run)
        insert_metric(conn, "v1_wau_7d", float(cp_stats["wau_7d"]), "count", "v1_customer_profile_json", dry_run=args.dry_run)
        insert_metric(conn, "v1_dau_1d", float(cp_stats["dau_1d"]), "count", "v1_customer_profile_json", dry_run=args.dry_run)
        insert_metric(conn, "v1_paying_users", float(cp_stats["paying_users"]), "count", "v1_customer_profile_json", dry_run=args.dry_run)
        insert_metric(conn, "v1_active_subscriptions", float(cp_stats["active_subscriptions"]), "count", "v1_customer_profile_json", dry_run=args.dry_run)
        insert_metric(conn, "v1_total_ltv_twd", float(cp_stats["total_ltv_twd"]), "TWD", "v1_customer_profile_json", dry_run=args.dry_run)
        insert_metric(conn, "v1_avg_ltv_twd", float(cp_stats["avg_ltv_twd"]), "TWD", "v1_customer_profile_json", dry_run=args.dry_run)
        insert_metric(conn, "v1_new_users_7d", float(cp_stats["new_users_7d"]), "count", "v1_customer_profile_json", dry_run=args.dry_run)

    # ── 2. Memoria blog articles
    print("\n📊 2. Memoria 連載文章數")
    blog_count = fetch_memoria_blog_articles_count()
    if blog_count < 0:
        print("   ⚠️  讀不到 v3.5-w*.md")
    else:
        print(f"   ✅ {blog_count} / 19 週")
        insert_metric(conn, "memoria_articles_count", float(blog_count), "count", "vocab_flashcards_blog_posts", dry_run=args.dry_run)
        # progress %
        progress = (blog_count / 19) * 100
        insert_metric(conn, "memoria_progress_pct", progress, "percentage", "vocab_flashcards_blog_posts", dry_run=args.dry_run)

    # ── 3. Publish log 7-day stats
    print("\n📊 3. 推波 7 天 stats")
    stats = fetch_publish_log_stats(days=7)
    print(f"   總 publish: {stats['total']}({stats['success']} 成功 / {stats['fail']} 失敗)")
    for platform, data in stats["by_platform"].items():
        print(f"   {platform.upper()}: {data['success']} 成功 / {data['fail']} 失敗")
        insert_metric(conn, f"{platform}_publish_7d_success", float(data["success"]), "count", "publish_log", dry_run=args.dry_run)
        insert_metric(conn, f"{platform}_publish_7d_fail", float(data["fail"]), "count", "publish_log", dry_run=args.dry_run)

    if stats["fail"] > 0:
        insert_event(
            conn, "publish_fail", "warning",
            f"7 天內有 {stats['fail']} 次 publish 失敗",
            stats,
            dry_run=args.dry_run,
        )

    # ── 4. Buzz captions count
    print("\n📊 4. Buzz captions 已生數")
    captions_count = fetch_buzz_captions_count()
    if captions_count < 0:
        captions_count = 0
    print(f"   ✅ {captions_count} 份 captions.json")
    insert_metric(conn, "buzz_captions_count", float(captions_count), "count", "buzz_captions_json", dry_run=args.dry_run)

    # ── 5. Lens reports count
    print("\n📊 5. Lens weekly reviews 已寫數")
    lens_count = fetch_lens_reports_count()
    print(f"   ✅ {lens_count} 份 weekly-review-W*.md")
    insert_metric(conn, "lens_reviews_count", float(lens_count), "count", "lens_reports", dry_run=args.dry_run)

    # ── 6. Phase 1.5 Step 2:Meta Graph API insights(真實觸及)
    print("\n📊 6. Meta Graph API insights(過去 7 天 FB + IG 真實觸及)")
    meta_insights = fetch_meta_aggregate_insights(days=7)

    fb_ins = meta_insights["fb"]
    if fb_ins.get("_skipped"):
        print(f"   ⚠️  FB skip:{fb_ins['_skipped']}")
    else:
        print(f"   FB Page({fb_ins['post_count']} 篇,{fb_ins['errors']} errors):")
        print(f"     likes={fb_ins['likes']} | comments={fb_ins['comments']} | shares={fb_ins['shares']} | engagement={fb_ins['engagement']}")
        if fb_ins.get("raw_samples"):
            print(f"   🔍 FB raw response 樣本(前 2 筆,debug 用):")
            for r in fb_ins["raw_samples"]:
                print(f"     post_id={r.get('post_id')}")
                print(f"     created_time={r.get('created_time')} | available_keys={r.get('available_keys')}")
        if fb_ins.get("error_samples"):
            print(f"   ⚠️  FB errors 詳情(前 2 筆):")
            for e in fb_ins["error_samples"]:
                print(f"     post_id={e['post_id']}")
                print(f"     error: {e['error']}")
        insert_metric(conn, "fb_likes_7d", float(fb_ins["likes"]), "count", "meta_graph_api", dry_run=args.dry_run)
        insert_metric(conn, "fb_comments_7d", float(fb_ins["comments"]), "count", "meta_graph_api", dry_run=args.dry_run)
        insert_metric(conn, "fb_shares_7d", float(fb_ins["shares"]), "count", "meta_graph_api", dry_run=args.dry_run)
        insert_metric(conn, "fb_engagement_7d", float(fb_ins["engagement"]), "count", "meta_graph_api", dry_run=args.dry_run)

    ig_ins = meta_insights["ig"]
    if ig_ins.get("_skipped"):
        print(f"   ⚠️  IG skip:{ig_ins['_skipped']}")
    else:
        fallback_note = f" (fallback used for {ig_ins.get('fallback_count', 0)} posts)" if ig_ins.get("fallback_count", 0) > 0 else ""
        print(f"   IG({ig_ins['post_count']} 篇,{ig_ins['errors']} errors){fallback_note}:")
        print(f"     reach={ig_ins['reach']} | interactions={ig_ins['interactions']} | saved={ig_ins['saved']} | likes={ig_ins['likes']} | comments={ig_ins['comments']}")
        if ig_ins.get("fallback_count", 0) > 0:
            print(f"   ℹ️  IG fallback 模式(scope 缺 instagram_manage_insights):reach/saved=0,只拿 likes/comments")
        if ig_ins.get("raw_samples"):
            print(f"   🔍 IG fallback raw response 樣本(前 2 筆,debug 用):")
            for r in ig_ins["raw_samples"]:
                print(f"     media_id={r.get('media_id')}")
                print(f"     like_count={r.get('like_count')} | comments_count={r.get('comments_count')} | type={r.get('media_type')}")
                print(f"     permalink={r.get('permalink')}")
        if ig_ins.get("error_samples"):
            print(f"   ⚠️  IG errors 詳情(前 2 筆):")
            for e in ig_ins["error_samples"]:
                print(f"     media_id={e['media_id']}")
                print(f"     error: {e['error']}")
        insert_metric(conn, "ig_reach_7d", float(ig_ins["reach"]), "count", "meta_graph_api", dry_run=args.dry_run)
        insert_metric(conn, "ig_interactions_7d", float(ig_ins["interactions"]), "count", "meta_graph_api", dry_run=args.dry_run)
        insert_metric(conn, "ig_saved_7d", float(ig_ins["saved"]), "count", "meta_graph_api", dry_run=args.dry_run)
        insert_metric(conn, "ig_likes_7d", float(ig_ins["likes"]), "count", "meta_graph_api", dry_run=args.dry_run)
        insert_metric(conn, "ig_comments_7d", float(ig_ins["comments"]), "count", "meta_graph_api", dry_run=args.dry_run)

    # Detect events:errors > 0 → warning
    if fb_ins.get("errors", 0) > 0 or ig_ins.get("errors", 0) > 0:
        insert_event(
            conn, "meta_insights_partial_fail", "warning",
            f"Meta Graph API insights 部分 post 拉失敗(FB errors={fb_ins.get('errors',0)}, IG errors={ig_ins.get('errors',0)})",
            {"fb": fb_ins, "ig": ig_ins},
            dry_run=args.dry_run,
        )

    # ── 7. Phase 1.5 Step 4:YouTube Data API v3(Hina 星奈頻道真實流量)
    print("\n📊 7. YouTube Data API v3(Hina 星奈頻道)")
    yt = fetch_youtube_stats(days=7)
    if yt.get("_skipped"):
        print(f"   ⚠️  YouTube skip:{yt['_skipped']}")
    elif yt.get("_error"):
        print(f"   ❌ YouTube fail:{yt['_error']}")
        insert_event(
            conn, "youtube_api_fail", "error",
            f"YouTube Data API fail: {yt['_error']}", {"channel_id": YOUTUBE_CHANNEL_ID},
            dry_run=args.dry_run,
        )
    else:
        if yt.get("_warning"):
            print(f"   ⚠️  YouTube partial:{yt['_warning']}")
        print(f"   ✅ 訂閱:{yt['subscribers']} | 累積觀看:{yt['total_views']:,} | 累積影片:{yt['total_videos']}")
        print(f"   ✅ 過去 7 天上傳:{yt['uploads_7d']} 部 | 觀看:{yt['views_7d']:,} | 讚:{yt['likes_7d']} | 留言:{yt['comments_7d']}")
        insert_metric(conn, "yt_subscribers", float(yt["subscribers"]), "count", "youtube_data_api", dry_run=args.dry_run)
        insert_metric(conn, "yt_total_views", float(yt["total_views"]), "count", "youtube_data_api", dry_run=args.dry_run)
        insert_metric(conn, "yt_total_videos", float(yt["total_videos"]), "count", "youtube_data_api", dry_run=args.dry_run)
        insert_metric(conn, "yt_uploads_7d", float(yt["uploads_7d"]), "count", "youtube_data_api", dry_run=args.dry_run)
        insert_metric(conn, "yt_views_7d", float(yt["views_7d"]), "count", "youtube_data_api", dry_run=args.dry_run)
        insert_metric(conn, "yt_likes_7d", float(yt["likes_7d"]), "count", "youtube_data_api", dry_run=args.dry_run)
        insert_metric(conn, "yt_comments_7d", float(yt["comments_7d"]), "count", "youtube_data_api", dry_run=args.dry_run)

    # ── 8. Nexus Agent 戰情牌(讀 agent_status.json)
    print("\n📊 8. Nexus Agent 戰情牌(Cowork scheduled tasks 狀態)")
    agent_status = fetch_agent_status()
    if not agent_status:
        print("   ⚠️  agent_status.json 不存在 / 空 ── aegis-cron-update task 還沒 dump 過?")
    else:
        total_tasks = sum(len(g["tasks"]) for g in agent_status)
        disabled = sum(1 for g in agent_status for t in g["tasks"] if not t["enabled"])
        print(f"   ✅ {len(agent_status)} 個 agent / {total_tasks} 個排程({disabled} 個 disabled)")
        for g in agent_status:
            for t in g["tasks"]:
                mark = "⏸️" if not t["enabled"] else "✅"
                print(f"     {mark} {g['agent']:<10} {t['task_id']:<32} 上次 {t['last_run_tw']} | 下次 {t['next_run_tw']}")

    # ── Commit SQLite
    if not args.dry_run:
        conn.commit()
        print(f"\n✅ SQLite cache 更新完成: {SQLITE_PATH}")
    else:
        print("\n🛑 dry-run 模式 ── 沒寫 SQLite")

    # ── Phase 1.5:Export cache.json + git push 給 Render
    print()
    print("─" * 70)
    print("Phase 1.5: Cache sync(SQLite → cache.json → git push 給 Render)")
    print("─" * 70)

    if conn is not None:
        cache_data = export_cache_to_json(conn, agent_status=agent_status)
        write_cache_json(cache_data, dry_run=args.dry_run)
        git_push_cache(dry_run=args.dry_run)
        conn.close()
    else:
        print("   (dry-run 模式 ── 沒生 cache.json,沒 push)")

    print()
    print("=" * 70)
    print(f"Aegis cron 完成 | {datetime.now().isoformat()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
