-- Aegis · 小盾 SQLite Schema
-- ====================================
-- Aegis 的本地 cache,每天 06:00 cron 從各 source fetch 後寫入
-- Phase 1 MVP:metrics + events + alerts 三表

-- 時間序列 metrics(每天一個快照)
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT NOT NULL,         -- 'v1_subscribers' / 'memoria_blog_pv_7d' / 'fb_reach_7d' / etc.
    value REAL NOT NULL,
    unit TEXT,                          -- 'count' / 'percentage' / 'currency_twd'
    source TEXT NOT NULL,               -- 'v1_subscribers_json' / 'meta_graph_api' / 'publish_log'
    collected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_metrics_name_time ON metrics(metric_name, collected_at);
CREATE INDEX IF NOT EXISTS idx_metrics_source_time ON metrics(source, collected_at);

-- 顯著事件(publish 失敗 / token 過期 / 流量暴跌 等)
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,           -- 'publish_fail' / 'token_expiring' / 'sandbox_outage' / 'reach_drop'
    severity TEXT NOT NULL,             -- 'info' / 'warning' / 'error' / 'critical'
    message TEXT NOT NULL,
    data_json TEXT,                     -- 序列化的詳細資料(stack trace / API response / context)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_time ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity, created_at);

-- 待 user dismiss 的 alert(避免相同 event type 連續推 LINE 騷擾)
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id),
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' / 'dismissed' / 'auto_resolved'
    line_pushed_at TIMESTAMP,                 -- LINE Bot 推送時間(Phase 2)
    dismissed_at TIMESTAMP,
    dismissed_by TEXT,                        -- 'user' / 'auto'
    UNIQUE(event_id)
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);

-- 系統健康檢查(Cowork scheduled tasks last run)
CREATE TABLE IF NOT EXISTS task_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL UNIQUE,             -- 'meta-publish-evening' / 'memoria-blog-publish' / etc.
    last_run_at TIMESTAMP,
    last_run_status TEXT,                     -- 'success' / 'failed' / 'pending'
    last_run_message TEXT,
    next_run_at TIMESTAMP,
    consecutive_failures INTEGER DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_task_health_failures ON task_health(consecutive_failures);

-- Phase 2 預留:LINE Bot push history(去重 + audit)
CREATE TABLE IF NOT EXISTS line_push_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    push_type TEXT NOT NULL,                  -- 'daily_summary' / 'alert' / 'monthly_kpi'
    message TEXT NOT NULL,
    sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    line_response TEXT
);

CREATE INDEX IF NOT EXISTS idx_line_push_time ON line_push_log(sent_at);
