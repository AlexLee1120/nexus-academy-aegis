# Aegis · 小盾 ── 工作順序佇列(無時程)

> **規則:** 不排日期。照順序一直做下去,完成一項打勾,推下一項。
> **節奏控制權:** 在 Alex Boss,他想加速 / 暫停 / 插隊都可以。
> **外部依賴**用 blocker tracker 標,不擋當下能做的事 ── 卡到就跳下一個 step。

---

## Phase 1:MVP Dashboard

**目標:** 一個能跑的 Aegis dashboard,4 個基礎 cards LIVE,Render auto-deploy 通,Cowork cron 每天 06:00 更新 SQLite。
**完工定義:** Step 1-12 全勾 + Alex 從 `aegis.nexus-academy.ai` 看到第一份真實數據 cards。

### 順序佇列

1. [x] Repo 開好 + Cowork mount(2026-05-11 完成)
2. [x] CLAUDE.md / _decisions.md / _timeline.md / _progress.md 4 主場文件(2026-05-11 完成)
3. [ ] **← 現在這裡** README.md(給工程團隊接手用)
4. [ ] requirements.txt + .env.example + .gitignore + render.yaml
5. [ ] schema.sql(SQLite tables: metrics / events / alerts)
6. [ ] cron_update_cache.py(每天 06:00 從各 source fetch,寫進 SQLite)
   - V1 customer_profile / subscribers.json read-only query
   - publish_log.json read
   - Meta Graph API insights call(用既有 PAGE_ACCESS_TOKEN)
   - 系統健康 check(Cowork scheduled tasks 列表 + last run)
7. [ ] aegis_app.py(Flask main)
   - Routes: GET / (dashboard) / GET /api/metrics (JSON) / POST /api/webhook (receive alert)
   - HTTP Basic Auth middleware
8. [ ] templates/dashboard.html(layout 對齊 brief Section 3.3)
   - 4 個 KPI cards
   - 推波 metrics table
   - 訂閱 funnel
   - 系統健康 list
   - 異常 alert
   - Tailwind + Chart.js
9. [ ] 本地測試(python aegis_app.py + 看 localhost:5000)
10. [ ] Render deploy
   - 在 Render 開新 service connected to nexus-academy-aegis repo
   - 設環境變數(從 .env)
   - 設 DNS aegis.nexus-academy.ai CNAME
11. [ ] Cowork scheduled task `aegis-cron-update`(每天 06:00 跑 cron_update_cache.py)
12. [ ] Alex 第一次打開 aegis.nexus-academy.ai → 確認 4 cards 顯示真實數據

---

## Phase 2:LINE Bot 整合

**目標:** 每天 07:00 LINE Bot push daily summary;異常 alert 即時 push。
**啟動條件:** Phase 1 LIVE + 跑滿 1-2 週 baseline 穩定。

### 工作模組

| 模組 | 估時 |
|---|---|
| LINE Bot Channel 申請 / token 設定 | 1 天 |
| Aegis 寫 LINE message template + push endpoint | 1 天 |
| 整合 V1 既有 LINE Bot pipeline(對齊 D10) | 1 天 |
| 異常 alert trigger logic | 1 天 |
| 端到端測試 | 1 天 |

---

## Phase 3:Pact / V2 整合

**目標:** Affiliate referral funnel + V2 訂閱 metrics 進 dashboard。
**啟動條件:** Pact Phase 1.5 上線 + V2 啟用。

### 工作模組

| 模組 | 估時 |
|---|---|
| Pact API endpoint 對接(Pact 已提供 spec)| 1 天 |
| V2 訂閱 metrics 整合(Stripe / ECPay)| 1 天 |
| Dashboard 加 Pact / V2 cards | 1 天 |

---

## Phase 4:跨產品線 KPI + 月度自動報告

**目標:** 跨 V1 / V2 / V3.5 / Pact ROI 對比;每月 1 號自動生 monthly KPI report;季度趨勢分析。
**啟動條件:** Phase 1.5 跑滿 3 個月 + Phase 3 整合完成。

### 工作模組

| 模組 | 估時 |
|---|---|
| Google Analytics 整合(blog PV) | 1 天 |
| 跨產品線 KPI 邏輯 | 2 天 |
| 月度報告 markdown 自動生 | 1 天 |
| 季度趨勢 chart | 1 天 |

---

## 外部依賴(Blocker Tracker)

照順序做事的時候,如果某個 step 卡到下表的依賴,就跳過去做下一個 step,不停擺。

| Blocker | 等誰 / 等什麼 | 影響哪個 step | 狀態 |
|---|---|---|---|
| 🟡 Cowork sandbox 服務恢復 | Cowork 平台側 | Step 11(scheduled task 設了也不會跑) | 等中(2026-05-11 outage) |
| 🟢 V1 customer_profile API | 小小星(已 LIVE 5/8) | Step 6(read MAU) | ✅ ready |
| 🟢 PAGE_ACCESS_TOKEN | 主對話小 M(.env 已有) | Step 6(Meta API insights) | ✅ ready |
| 🟡 Render account / service | Alex 投資承諾(Free tier) | Step 10 | 等 Step 1-9 完工 |
| 🟡 DNS 設定權限 | Alex(domain admin) | Step 10 | 等 Step 1-9 完工 |
| 🟡 Pact Phase 1.5 上線 | Pact + 主對話小 M(等 V1 PG 升級) | Phase 3 | 等 ~2026 Q3 |
| 🟡 V2 訂閱 上線 | 主對話小 M | Phase 3 | 等 ~2026 Q4-2027 Q1 |
| 🟡 LINE Bot Channel | Alex(LINE Developer Console)| Phase 2 | 等 Phase 1 LIVE |

---

## 紅線

- ❌ 不取代 agent 商業決策(Pact / Echo / 主對話小 M)── Aegis 提供數據,他們下決策
- ❌ 不洩漏個資 / token / API key 在 dashboard
- ❌ 不誇大數據 / 加假數據 / 截斷 y 軸 misleading
- ❌ Aegis 對所有外部 source 都是 read-only(對齊 D7)
- ✅ 任何商業大方向變動 → 找 Alex Boss 拍板
- ✅ 任何技術整合 → 找主對話小 M review
- ✅ 任何跨 V1 / Pact / V2 schema 變動 → 找對應 agent 協調
