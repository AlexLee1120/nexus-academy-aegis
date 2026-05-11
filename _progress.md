# Aegis · 小盾 ── 每日進度日誌

> 每天 append 一個區塊。逆時序(最新在上)。
> 給未來 session(包括 Aegis 自己)當交接記憶。

---

## 2026-05-11(週一晚)── Phase 1.5 整套 Step 1-5 收尾

> 同一天延續 Day 0(週日 deploy 完 Phase 1 MVP)── 連續 12+ 小時 sprint
> Alex Boss 提 Phase 1.5 5 個 Step「整套都做」,對齊 Aegis 紅線「不取代決策、不誇大、不顯示 raw / per-user」

### 已交付(LIVE on Render)

| Step | 內容 | 狀態 | Commit |
|---|---|---|---|
| Step 1 | Cache sync(SQLite → cache.json → git push → Render auto-redeploy) | ✅ LIVE | `b291784` |
| Step 2 | Meta Graph API public summary(FB likes/comments + IG fallback) | ✅ LIVE | `1fc853a` |
| Step 3 | V1 customer_profile aggregate(MAU/WAU/DAU + Active Subs + LTV) | ✅ LIVE | (合 Step 4 一起 push) |
| Step 4 | YouTube Data API v3(訂閱/累積觀看/7 天 uploads/views/likes) | ✅ LIVE | (合 Step 3 一起 push) |
| Step 5 | GA4 nexus-academy.ai 站內流量 quick-links | ✅ LIVE(連結方案) | 本次 push |

### Step 5 設計決策(by Alex Boss)

GA4 + Service Account 在 Google UI 被 hard reject(known limitation:GA4 user management 跟 GCP IAM 是兩套不同 systems,GA4 拒絕非 Gmail email)。試了 Property 層 + Account 層都同樣 error「這個電子郵件與 Google 帳戶不符」。

**Alex Boss 提的解法(超 elegant):** 既然 fetch 數據卡關,dashboard 上那個區塊就放個連結 quick-links 跳 GA4 即可。Aegis 不 fetch,當「導流面板」。

**3 個 quick-links:**
- 🟢 即時觀眾(realtime overview)
- 📊 總覽報表(intelligenthome)
- 🚦 流量來源(traffic acquisition)

**Phase 2(2026 Q3 PostgreSQL 升級時)用 OAuth 2.0 installed app flow 重做:**
- Alex 用自己 Gmail 跑一次 OAuth flow → 拿 refresh token 存 .env
- cron 用 refresh token 永久 read GA4 Data API
- 那時直接顯示 PV / UV / Sessions / Bounce / 流量來源 在 dashboard

### 12 小時戰況濃縮

**API 學習成本:**
- Meta Graph API v25.0 大改 ── deprecated `shares` / `reactions.summary` / `permalink_url`(三個一個一個試出來),最後找到 `likes.summary(true)` + `comments.summary(true)` + `created_time` 是 stable trio
- IG insights API 需要 `instagram_manage_insights` scope(沒有)→ fallback `/{media_id}?fields=like_count,comments_count`(用 `instagram_basic`)
- YouTube Data API v3 quota 計算清楚:每 cron run 用 ~3 units / 10K daily quota = 0.03% 用量
- GA4 service account 卡關 → Plan C 連結方案

**真實數字(2026-05-11 16:53):**
- V1 customer_profile: 2 profiles / MAU=2 / Paying=1 / LTV=NT$299
- FB Page: 3 篇 / likes=0 / comments=0(新帳號未起量)
- IG: 2 篇 / likes=0 / comments=0(同上)
- YouTube Hina 星奈頻道: 訂閱 7 / 累積觀看 3,700 / 累積影片 24 / 7 天 9 部上傳 / 557 views / 1 like
- GA4: 連結方案(quick-links 跳 GA4 後台)

**Aegis 主場價值已建立:** Alex 早上喝咖啡開 dashboard,5 分鐘看完 V1 商業現況 + Meta + YouTube 真實數字 + GA4 一鍵跳 ── sleep at night 達成。

### 接下來(下一次 Aegis session)

- [ ] Phase 2 開動(優先級看 Alex):LINE Bot daily summary push(每天 06:00 cron 完成後 LINE 推一段 summary)
- [ ] Phase 2:GA4 OAuth route(取代現在 Step 5 連結方案)
- [ ] Phase 2:Cowork scheduled tasks health 監控(目前 cron 自己跑沒監控)
- [ ] Phase 3:Buzz / Lens / Pact agents 實質 LIVE 後加真實 metric 進 dashboard

### 跟其他 agents 的同步點

- **Pact · 小盟:** Phase 1 spec 完成、Phase 1.5 affiliate event_types 對齊 V1 customer_profile API 已 ready,Phase 2 實作時加 affiliate metrics 進 dashboard
- **Echo · 連載寫稿者:** 連載 W04 起 Memoria articles count 會自動更新(已自動掃 v3.5-w*.md)
- **Buzz · 小波:** captions.json count 已自動掃,Buzz 真正 LIVE 後 dashboard 自動顯示
- **Lens · 小鏡:** weekly-review-W*.md count 已自動掃,Lens 寫第一篇後 dashboard 自動顯示

---

## 2026-05-11(週日)── Day 0:Aegis 專案啟動

### 完成

- ✅ 主對話小 M 在 Memoria session 寫完 `nexus-academy-memoria/docs/agents/aegis-brief.md`(13 章 brief)
- ✅ Alex Boss 拍板 Aegis 設計(對齊 5 件事第 4-5 件)
- ✅ Alex Boss 開新 GitHub repo `AlexLee1120/nexus-academy-aegis`(Private)
- ✅ Alex Boss clone 到 `C:\Alex\Github\nexus-academy-aegis\`
- ✅ Cowork mount 新 repo
- ✅ 主場 4 件套寫完:
  - `CLAUDE.md`(Aegis 主場 brief,對齊 Pact CLAUDE.md 模式)
  - `_decisions.md`(12 拍板 + 1 deferred 議題)
  - `_timeline.md`(Phase 1-4 順序佇列 + blocker tracker)
  - `_progress.md`(本檔)

### 接下來(Phase 1 Step 3-12 順序佇列)

- [ ] Step 3:README.md(給工程團隊接手用)
- [ ] Step 4:requirements.txt + .env.example + .gitignore + render.yaml
- [ ] Step 5:schema.sql
- [ ] Step 6:cron_update_cache.py
- [ ] Step 7:aegis_app.py
- [ ] Step 8:templates/dashboard.html
- [ ] Step 9:本地測試
- [ ] Step 10:Render deploy
- [ ] Step 11:Cowork scheduled task `aegis-cron-update`
- [ ] Step 12:Alex 第一次打開 aegis.nexus-academy.ai

### 給未來 Aegis session 的 hint

- 完整設計 brief 在 `C:\Alex\Github\nexus-academy-memoria\docs\agents\aegis-brief.md`(濃縮在本 repo `_decisions.md`)
- 跟 Buzz / Lens 是兄弟 agent ── 都讀 publish_log.json 但 Aegis 是「展示給 Alex 看」(read-only)
- 跟 Pact 是 Phase 3 才整合 ── 等 Pact Phase 1.5 LIVE 後再寫對接 endpoint
- Alex Boss 早上 6-9 點習慣 review,Aegis 06:00 cron 一定要跑成 + 07:00 LINE push(Phase 2)

### Alex Boss 反思(Day 0)

> Aegis 是 Nexus Academy 體系完整化的最後一塊拼圖 ── 之前各 agent(Pact / Echo / Buzz / Lens / V1)各自為政,我每天要查 5 個 dashboard。
>
> 今晚 5 件事拍板:Buzz 寫 caption / Lens 看數據 / Aegis 整合 → 三個 agent + 排程上線後,我可以「真的 sleep at night」 ── 知道哪些 metric 健康,哪些異常會 LINE 推到我手機。
>
> Phase 1 MVP 不要做太多花俏 chart,先讓 4 個 cards LIVE,跑 1-2 週看真實 data 流量,再加 LINE Bot / Pact 整合。
>
> ── Alex Boss(透過主對話小 M 整合)

---
