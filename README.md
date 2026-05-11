# Nexus Academy: Aegis ── 戰情 Dashboard

> Aegis · 小盾 ── 跨產品線數據聚合 + Dashboard 維護 + LINE Bot 通知 + 異常 alert
> Production URL: `aegis.nexus-academy.ai`(Phase 1 MVP 完工後 LIVE)

---

## 0. 三秒鐘 TL;DR

聚合 V1 vocab-flashcards / V3.5 Memoria / Pact Affiliate 全產品線 metrics,給 Alex Boss 每天清晨 5 分鐘 review 全局。

---

## 1. 完整設計 brief

詳細工作職掌 + 跨 agent 介面 + Phase 1-4 設計 → 看:
- `CLAUDE.md`(Aegis 主場 + 紅線)
- `_decisions.md`(12 個架構拍板)
- `_timeline.md`(順序佇列 + blocker tracker)
- 或 Memoria session 寫的原始 brief: `C:\Alex\Github\nexus-academy-memoria\docs\agents\aegis-brief.md`(13 章)

---

## 2. 技術 Stack

| Layer | 技術 |
|---|---|
| Frontend | Vanilla HTML + Tailwind CSS(CDN) + Chart.js(CDN) |
| Backend | Flask(Python 3.10+) |
| Database | SQLite(本地 cache,每天 06:00 cron 更新) |
| Hosting | Render(free tier) |
| Auth | HTTP Basic Auth(Phase 1) |

---

## 3. Setup ── 本地開發

```powershell
# 1. Clone(Alex 已 clone 到 C:\Alex\Github\nexus-academy-aegis)
cd C:\Alex\Github\nexus-academy-aegis

# 2. 安裝套件
pip install -r requirements.txt

# 3. 設環境變數
copy .env.example .env
# 編輯 .env,從 nexus-academy-memoria/scripts/.env 複製 PAGE_ACCESS_TOKEN / IG_BUSINESS_ID 等

# 4. 初始化 SQLite
python -c "import sqlite3; conn = sqlite3.connect('aegis_cache.db'); conn.executescript(open('schema.sql').read()); conn.close(); print('✅ SQLite initialized')"

# 5. 第一次 cron 更新(從 source fetch + 寫 SQLite)
python cron_update_cache.py

# 6. 跑 Flask app
python aegis_app.py

# 7. 開瀏覽器
# http://localhost:5000
# 使用 .env 的 AEGIS_USERNAME / AEGIS_PASSWORD 登入
```

---

## 4. Deploy ── Render

1. 在 Render 開新 Web Service
2. Connect to `AlexLee1120/nexus-academy-aegis` repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn aegis_app:app --bind 0.0.0.0:$PORT`
5. 設環境變數(從 .env 複製進 Render dashboard)
6. Auto-deploy on push to `main`
7. 在 Render Custom Domains 加 `aegis.nexus-academy.ai`
8. DNS CNAME `aegis` → Render 提供的 URL(類似 `aegis-nexus-academy.onrender.com`)

---

## 5. 排程

- **每天 06:00** ── Cowork scheduled task `aegis-cron-update` 跑 `cron_update_cache.py`(對齊 Render free tier 不會 keep alive cron 限制)
- **異常 alert** ── 即時觸發(Phase 2 整合 LINE Bot)
- **每月 1 號** ── Cowork scheduled task `aegis-monthly-kpi`(Phase 4)

---

## 6. 維運手冊

### 場景 A:Page / IG Token 過期(60 天)
- Memoria session 跑 `python extend_token.py`(在 nexus-academy-memoria/scripts/)
- 拿新 PAGE_ACCESS_TOKEN
- 同步更新本 repo `.env` + Render 環境變數

### 場景 B:SQLite cache 損壞 / reset
```powershell
del aegis_cache.db
python -c "import sqlite3; conn = sqlite3.connect('aegis_cache.db'); conn.executescript(open('schema.sql').read()); conn.close()"
python cron_update_cache.py
```

### 場景 C:Render deploy fail
- 看 Render dashboard 的 logs
- 常見原因:requirements.txt 缺套件 / startCommand 錯
- 重 push 一次觸發 redeploy

### 場景 D:某個 metric 在 dashboard 顯示 N/A
- 看 events table 是否有對應 fetch error
- check source(V1 customer_profile / publish_log.json / Meta API)是否還活著
- 手動跑 `python cron_update_cache.py` 看完整 stderr

---

## 7. 跨 agent 介面(read-only)

| Source | Read Path | Phase |
|---|---|---|
| V1 vocab-flashcards customer_profile | JSON file at `V1_REPO_PATH/customer_profile.json` | Phase 1 |
| V1 subscribers | JSON at `V1_REPO_PATH/subscribers.json` | Phase 1 |
| Memoria publish_log | JSON at `PUBLISH_LOG_PATH` | Phase 1 |
| Meta Graph API insights | HTTPS GET `/{post-id}/insights` | Phase 1 |
| Buzz captions | JSON at `V1_REPO_PATH/blog/posts/v3.5-w*-captions.json` | Phase 1 |
| Lens weekly review | MD at `nexus-academy-memoria/docs/lens-reports/weekly-review-W*.md` | Phase 1 |
| Pact Affiliate API | HTTPS GET(spec by Pact)| Phase 3 |
| YouTube Data API | HTTPS GET | Phase 4 |
| Google Analytics | API | Phase 4 |
| LINE Bot push | HTTPS POST(LINE Messaging API)| Phase 2 |

---

## 8. Phase 1 MVP 範圍(本次)

✅ 4 個基礎 KPI cards
- V1 MAU(approximation:active subscribers count)
- V2 訂閱(placeholder「未啟用」)
- Memoria blog 7-day metrics(blog post count + Meta reach)
- Pact(placeholder「Phase 1.5 pending」)

✅ 推波 metrics 區塊
- 三平台對比(FB / IG / Threads pending)
- 5 種 hook 排行(從 Buzz captions.json + Meta insights join)

✅ 系統健康區塊
- Cowork scheduled tasks(列表 + last run timestamp)
- Token 過期警告(< 14 天剩餘)

✅ 異常 alert 區塊
- 過去 7 天 events table 顯示

❌ Phase 1 不做
- LINE Bot push(Phase 2)
- 月度報告自動生(Phase 4)
- Pact / V2 整合(Phase 3)
- YouTube / GA(Phase 4)

---

## 9. 紅線(對齊 CLAUDE.md)

❌ 不取代 agent 商業決策(Pact / Echo / 主對話小 M)── Aegis 提供數據,他們下決策
❌ 不洩漏個資 / token / API key 在 dashboard
❌ 不誇大數據(raw 顯示,不截斷 y 軸 misleading)
❌ 不為「dashboard 好看」加假數據
❌ Aegis 對所有外部 source 都是 read-only
✅ 每天 06:00 ritualized update
✅ 異常 alert 即時 LINE push(Phase 2)
✅ 跨產品線統一 baseline(GMT+8 / 同 metric definition)

---

## 10. 文件修訂歷程

| 日期 | 版本 | 修訂者 | 內容 |
|---|---|---|---|
| 2026-05-11 | v1.0 | 主對話小 M | Aegis Phase 1 MVP 啟動,README 初稿 |
