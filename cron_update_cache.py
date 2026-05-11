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
    from dotenv import load_dotenv
except ImportError:
    print("❌ 缺 python-dotenv,跑: pip install -r requirements.txt")
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
    """讀 V1 subscribers.json 算 active 訂閱者"""
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
# Phase 1.5: Cache sync(SQLite → cache.json → git push 給 Render)
# ─────────────────────────────────────────────────────

def export_cache_to_json(conn: sqlite3.Connection) -> dict:
    """從 SQLite query latest metrics + recent events,組成 cache.json schema
    給 Render dashboard 直接 read(避免 Render 環境讀不到 Windows local files)"""
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
        "schema_version": "1.5.0",
        "exported_at": datetime.now().isoformat(),
        "latest_metrics": latest_metrics,
        "recent_events": events,
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

    # ── 1. V1 subscribers
    print("📊 1. V1 subscribers count")
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
        cache_data = export_cache_to_json(conn)
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
