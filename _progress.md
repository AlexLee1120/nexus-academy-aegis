# Aegis · 小盾 ── 每日進度日誌

> 每天 append 一個區塊。逆時序(最新在上)。
> 給未來 session(包括 Aegis 自己)當交接記憶。

---

## 2026-05-13(週三)── Sprint A Day 1 完整 LIVE

> **Nexus Academy 第一次完整漏斗接通的日子。**
> 從早上「Aegis dashboard 顯示 0 lead magnet / 0 真實外部用戶」到下午「PDF 上線 + Channel banner LIVE + 5 部影片 description+pin LIVE」── 1 天搞定。

### 已交付清單(全 LIVE)

| Step | 內容 | 狀態 | 位置 |
|---|---|---|---|
| **Aegis** | alert UX 改最新 3 筆 + 收納(by Alex feedback) | ✅ LIVE | aegis commit `1b250ad` |
| **Sprint A spec** | 整合版 v1 spec(含字圖整合) | ✅ Live | memoria docs/sprints/sprint-A-youtube-funnel-fix.md |
| **D5 PDF** | 動漫場景記憶 100 字圖鑑 v1(80 頁 + 動漫化例句) | ✅ LIVE | Google Drive 公開 URL |
| **D8 Helper scripts** | preview_a_grade / build_100words / generate_examples / simplify_pos / copy_100words_images | ✅ LIVE | memoria scripts/ |
| **D3 Channel banner** | Hina + 「動漫英文學姊」+ CTA 按鈕 | ✅ LIVE | YouTube channel |
| **D4 About page** | 完整品牌敘事 + 5,778 字 + 動漫場景記憶法 | ✅ LIVE | YouTube about |
| **Channel links** | 4 個 CTA(試學/故事/PDF/Discord) | ✅ LIVE | YouTube channel link |
| **D1 影片 description** | 5 部高觀看影片更新 CTA 模板 | ✅ LIVE | YouTube 5 部 |
| **D2 Pin comment** | 5 部影片置頂留言 + PDF download CTA | ✅ LIVE | YouTube 5 部 |

### 漏斗完整接通(從 0 到 1)

```
YouTube Shorts 觀眾
    ↓ Description / Pin Comment / Channel Banner CTA
Google Drive 公開 PDF(任何人不用登入)
    ↓ Discord 邀請 / nexus-academy.ai 試學
留住觀眾 → 進 Discord / 試學註冊
    ↓
V1 customer_profile.json 多 1 個外部 user(真實第一個)
    ↓ Aegis dashboard 反映
真實流量 metric 出現
```

### 真實 metric snapshot(Day 1 結束時)

- YouTube 訂閱:7(待 14d 後看是否 +8 → 15+ target)
- YouTube 累積觀看:3,700+
- YouTube 7 天觀看:557(daily upload pipeline 持續跑)
- conflict 影片留言驗證:粉絲說「Conflict 原來 con 是一起的意思 🤔」── **真實學到了!IP hook 起作用**
- 100 字圖鑑 PDF download:0 → 待 14d review
- V1 customer_profile 外部用戶:0 → 待 14d review

### 學到的事(寫進記憶)

**設計 +工程經驗:**
- Canva Bulk Create 對「文字 100% 自動套」,「圖片不會自動換」── 必須 plan
- Google Drive 公開分享連結最佳實踐:用 `view?usp=sharing` mode(觀眾預覽 + 可下載),避免 direct download 24MB PDF 觸發 virus scan warning
- GitHub raw URL 對 private repo 手機不能下載 ── 重要 lead magnet 必須走 Google Drive / Cloudflare R2 / 公開 storage

**商業 + IP 經驗:**
- master_premium.csv 只有 381 字,A 級內 only 77 字 ── 不夠 PDF 100 字
- 改用 AI 生「動漫化例句 + 中譯 + 中文解釋」+ Hina/Ren 角色出場 → Claude Haiku 4.5 cost $0.0664 USD / 100 字,可重複生成
- Aegis dashboard 紅線「不為好看加假數據」對齊:Sprint A v1 ship 80 頁(Canva trial 限制) + 圖片同一張(Bulk Create 限制)── 都誠實接受
- 「英」box 殘留:Canva 設計檔之間複製貼上要小心,debug 時要看完整 layout

### Sprint A 14 天 review(2026-05-27)

由 Lens · 小鏡 動手寫 weekly review,分析:
- 5 部影片 description / pin comment 改造後 → 訂閱率變化
- PDF download 真實數據(Google Drive analytics)
- Discord 新成員數
- 14 天後 Pass / Fail 決定 Sprint B 啟動

### 下一步(下次 Alex 動工)

- [ ] **Sprint B:統一 link-in-bio**(半天 ── nexus-academy.ai/links 統一 landing page)
- [ ] **Sprint C:社會證明建立**(1 天 ── testimonial 收集)
- [ ] **Lens 寫 Sprint A Week 1 review**(2026-05-20)
- [ ] **Aegis Phase 2:GA4 OAuth route**(取代現在 quick-links 方案)
- [ ] **D5 PDF v2:圖片真的換成各 word 對應字圖**(70 min 苦工,但可 deferred to 2 週後 iterate)

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
