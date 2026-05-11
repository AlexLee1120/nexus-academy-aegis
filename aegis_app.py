"""
aegis_app.py — Aegis · 小盾 Flask Dashboard
============================================

Phase 1 MVP:
  - HTTP Basic Auth(只給 Alex Boss)
  - GET / → render dashboard.html(4 KPI cards + 推波 metrics + 系統健康 + 異常 alert)
  - GET /api/metrics → JSON(時間序列 metrics,給 Chart.js)
  - GET /api/events → JSON(events list,7 天內)
  - GET /healthz → simple health(no auth)

執行:
    python aegis_app.py            # 本地 localhost:5000
    gunicorn aegis_app:app         # production(Render)

Author: 主對話小 M(2026-05-11,Aegis Phase 1 MVP)
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

try:
    from flask import Flask, jsonify, render_template, request, Response
    from dotenv import load_dotenv
except ImportError:
    print("❌ 缺套件,跑: pip install -r requirements.txt")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

AEGIS_USERNAME = os.getenv("AEGIS_USERNAME", "alex")
AEGIS_PASSWORD = os.getenv("AEGIS_PASSWORD", "")
SQLITE_PATH = Path(os.getenv("SQLITE_PATH", str(SCRIPT_DIR / "aegis_cache.db")))

app = Flask(__name__, template_folder=str(SCRIPT_DIR / "templates"))


# ─────────────────────────────────────────────────────
# Auth middleware
# ─────────────────────────────────────────────────────

def check_auth(username, password):
    return username == AEGIS_USERNAME and password == AEGIS_PASSWORD and AEGIS_PASSWORD != ""


def authenticate():
    return Response(
        "Authentication required.\n"
        "Aegis · 小盾 戰情 Dashboard ── 限 Alex Boss 存取\n",
        401,
        {"WWW-Authenticate": 'Basic realm="Aegis Dashboard"'},
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_latest_metric(metric_name: str) -> dict | None:
    """取最新的 metric value(by collected_at)"""
    if not SQLITE_PATH.exists():
        return None
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM metrics WHERE metric_name = ? ORDER BY collected_at DESC LIMIT 1",
            (metric_name,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_metric_history(metric_name: str, days: int = 30) -> list:
    """取 N 天內的 metric history(時間序列)"""
    if not SQLITE_PATH.exists():
        return []
    conn = get_conn()
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """
            SELECT metric_name, value, unit, collected_at
            FROM metrics
            WHERE metric_name = ? AND collected_at >= ?
            ORDER BY collected_at ASC
            """,
            (metric_name, cutoff),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recent_events(days: int = 7, limit: int = 50) -> list:
    """取最近 events"""
    if not SQLITE_PATH.exists():
        return []
    conn = get_conn()
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """
            SELECT id, event_type, severity, message, data_json, created_at
            FROM events
            WHERE created_at >= ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["data"] = json.loads(d.pop("data_json") or "{}")
            except Exception:
                d["data"] = {}
            result.append(d)
        return result
    finally:
        conn.close()


# ─────────────────────────────────────────────────────
# Dashboard data 組裝
# ─────────────────────────────────────────────────────

def build_dashboard_data() -> dict:
    """組 dashboard 顯示用的 data dict"""
    # ── KPI cards
    v1_subs = get_latest_metric("v1_subscribers_count")
    memoria_articles = get_latest_metric("memoria_articles_count")
    memoria_progress = get_latest_metric("memoria_progress_pct")

    # ── 推波 7 天 stats
    fb_success = get_latest_metric("fb_publish_7d_success")
    fb_fail = get_latest_metric("fb_publish_7d_fail")
    ig_success = get_latest_metric("ig_publish_7d_success")
    ig_fail = get_latest_metric("ig_publish_7d_fail")
    threads_success = get_latest_metric("threads_publish_7d_success")
    threads_fail = get_latest_metric("threads_publish_7d_fail")

    # ── 系統健康
    captions_count = get_latest_metric("buzz_captions_count")
    lens_count = get_latest_metric("lens_reviews_count")

    # ── Events
    events = get_recent_events(days=7, limit=20)

    # ── Last update timestamp
    last_update = None
    if v1_subs:
        last_update = v1_subs.get("collected_at")

    def safe_value(metric: dict | None, default=0):
        if metric is None:
            return default
        return metric.get("value", default)

    return {
        "last_update": last_update or "(尚未更新,跑 cron_update_cache.py)",
        "kpi": {
            "v1_subscribers": int(safe_value(v1_subs, 0)),
            "v2_subscriptions": "未啟用",
            "memoria_articles": int(safe_value(memoria_articles, 0)),
            "memoria_progress_pct": round(safe_value(memoria_progress, 0), 1),
            "pact_status": "Phase 1.5 pending",
        },
        "publish_7day": {
            "fb": {"success": int(safe_value(fb_success)), "fail": int(safe_value(fb_fail))},
            "ig": {"success": int(safe_value(ig_success)), "fail": int(safe_value(ig_fail))},
            "threads": {"success": int(safe_value(threads_success)), "fail": int(safe_value(threads_fail))},
        },
        "system_health": {
            "buzz_captions_count": int(safe_value(captions_count, 0)),
            "lens_reviews_count": int(safe_value(lens_count, 0)),
        },
        "events": events,
    }


# ─────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────

@app.route("/")
@requires_auth
def dashboard():
    data = build_dashboard_data()
    return render_template("dashboard.html", data=data)


@app.route("/api/metrics")
@requires_auth
def api_metrics():
    """JSON ── 給 future Chart.js / 外部 query 用"""
    data = build_dashboard_data()
    return jsonify(data)


@app.route("/api/metrics/<metric_name>/history")
@requires_auth
def api_metric_history(metric_name: str):
    """單一 metric 的 30 天時間序列(給 Chart.js line chart)"""
    days = int(request.args.get("days", 30))
    history = get_metric_history(metric_name, days)
    return jsonify({"metric_name": metric_name, "days": days, "data": history})


@app.route("/api/events")
@requires_auth
def api_events():
    days = int(request.args.get("days", 7))
    limit = int(request.args.get("limit", 50))
    events = get_recent_events(days, limit)
    return jsonify({"days": days, "limit": limit, "events": events})


@app.route("/healthz")
def healthz():
    """No auth ── for Render health check"""
    sqlite_exists = SQLITE_PATH.exists()
    return jsonify({
        "status": "ok",
        "service": "aegis",
        "sqlite_cache_exists": sqlite_exists,
        "timestamp": datetime.now().isoformat(),
    })


# ─────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────

if __name__ == "__main__":
    if not AEGIS_PASSWORD:
        print("⚠️  AEGIS_PASSWORD 沒設,Auth 會永遠 401")
        print("   到 .env 設 AEGIS_PASSWORD=xxx 再跑")
        sys.exit(1)

    port = int(os.getenv("FLASK_PORT", 5000))
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"

    print("=" * 70)
    print(f"🛡️  Aegis · 小盾 Dashboard")
    print("=" * 70)
    print(f"   URL: http://localhost:{port}/")
    print(f"   Auth: {AEGIS_USERNAME} / {'*' * len(AEGIS_PASSWORD)}")
    print(f"   SQLite: {SQLITE_PATH} (exists: {SQLITE_PATH.exists()})")
    print()

    app.run(host=host, port=port, debug=debug)
