# Aegis · 小盾 ── 架構拍板紀錄

> **建立日:** 2026-05-11
> **拍板人:** Alex Boss(主對話小 M 替 Alex 整合 brief 後拍板)
> **觸發點:** 主對話小 M 在 Memoria session 5/10 晚上,Alex 提出「戰情網頁」需求,5 件事拍板第 4-5 件
> **完整 brief:** `C:\Alex\Github\nexus-academy-memoria\docs\agents\aegis-brief.md`(13 章)

---

## D1:Agent 命名 ── **Aegis · 小盾**

**Aegis** ── 神話中 Zeus 的神盾,守護全局視野
**小盾** ── 對齊 Pact / Echo / Buzz / Lens 命名美學(英文 + 中文諧音)

**否決選項:**
- ~~Watch · 小哨~~(瞭望)── 太被動
- ~~Pulse · 小搏~~(脈搏)── 太醫療
- ~~Lens · 小鏡~~ ── 已給推波數據監察 agent

---

## D2:獨立 repo,不在 Memoria 子目錄

**拍板:** Alex 選「A 獨立 repo」

理由:
- 對齊 Pact / Memoria / V1 三 repo 體系(brand 一致)
- Long-term scalable(Aegis 跑大後不用 split)
- 跨 agent / 跨產品線 read-only,獨立 repo 邏輯邊界清楚

---

## D3:技術 stack ── Flask + SQLite + Tailwind + Chart.js,Render deploy

**拍板對齊既有體系:**
- Flask ── V1 vocab-flashcards 已用,主對話小 M 熟,招新工程師也好接手
- SQLite ── 本地 cache,輕量(Phase 1 不需要 PG)
- Tailwind ── V1 / Memoria blog 已用,brand design language 對齊
- Chart.js ── 簡單 line / bar / pie chart 夠用,不需要 D3
- Render ── 既有 deploy pipeline(對齊 vocab-flashcards),free tier 夠用

**否決:**
- ~~Streamlit~~(太 Python-centric,UI 不對齊 brand)
- ~~Grafana~~(over-engineering,Alex 不需要 enterprise-level)
- ~~Next.js + React~~(學習曲線高,招新工程師範圍縮小)

---

## D4:Auth ── HTTP Basic Auth,密碼存 .env

**拍板:** Phase 1 只給 Alex Boss 一人看 ── HTTP Basic Auth 夠用

Phase 2 如果要給 工程團隊 / 投資人 看 ── 升級到 token-based auth(JWT / Render 託管)。

**紅線:** Auth 過後仍只顯示 aggregate,不顯示 per-user data(對齊 D7)。

---

## D5:Update 節奏 ── 每天 06:00 cron,Alex 早上喝咖啡時 ready

**拍板對齊 Alex Boss 作息:**
- 06:00 cron 自動跑(從各 source fetch + 更新 SQLite cache)
- 06:00 → 06:30 數據 ready
- Alex 早上 7-9 點看 dashboard 5 分鐘 review 全局

**異常 alert:** 不等 06:00,即時 push LINE Bot(Phase 2)。

---

## D6:Phase 4 階段啟動

| Phase | 範圍 | 啟動條件 |
|---|---|---|
| **Phase 1**(MVP) | Dashboard 框架 + 4 個基礎 cards(V1 MAU / Memoria PV / 推波 / 系統健康)| 即時動工 |
| **Phase 2** | LINE Bot 整合(daily summary + 異常 alert)| Phase 1 LIVE 後 |
| **Phase 3** | Pact / V2 整合 | Pact Phase 1.5 上線 + V2 啟用 後 |
| **Phase 4** | 跨產品線 KPI + 月度自動報告 + 季度趨勢 | Phase 1.5 跑滿 3 個月後 |

對齊 **Pact Phase 1.5 哲學:** 先 LIVE MVP,跑 1-2 週看真實 data 流量,再投資 LINE Bot / Pact 整合。

---

## D7:Read-only 紅線

**拍板:** Aegis 對所有外部 source(V1 / Pact / V3.5 / Buzz / Lens / Echo / Meta / YouTube / GA)都是 **read-only**。

**為什麼:** 避免 Aegis 一個 bug 連鎖污染整個 Nexus Academy 體系。

**例外:** Aegis 自己的 SQLite cache 可以 read-write(那是 Aegis 自家資料)。

---

## D8:不顯示 per-user data

**拍板:** Dashboard 只顯示 **aggregate 數字**(總訂閱者 / 總 reach / 總 click),不顯示:
- 哪個用戶訂閱了
- 哪個 affiliate 推了多少
- 哪個 IG follower 互動最多

**理由:**
1. 隱私(對齊 Pact 紅線「不洩漏老用戶資料」)
2. Dashboard 不該是「窺探用戶」工具,該是「決策」工具
3. 如果 Alex 真的要看 per-user,直接 query V1 customer_profile API(那是另一個 entry,不在 Aegis)

---

## D9:URL ── `aegis.nexus-academy.ai`

**拍板:** subdomain,Render 託管,DNS CNAME 過去

**為什麼不用 nexus-academy.ai/aegis 子路徑:**
- 子路徑要跟 vocab-flashcards Flask 整合(架構複雜)
- subdomain 完全獨立 deploy,降低 V1 prod 風險

---

## D10:LINE Bot 用 既有 V1 LINE Bot pipeline 還是 新建

**拍板:** Phase 2 啟動時再決定,**lean towards 用既有 V1 LINE Bot**(對齊 vocab-flashcards/agents/drip_marketing/ 既有 LINE message templates)。

---

## D11:命名 KPI metric 規範

對齊跨產品線統一 baseline(Aegis 紅線 ✅ 跨產品線統一 baseline):

| Metric | 定義 | 來源 |
|---|---|---|
| **MAU** | 上 30 天有 activity 的 user 數 | V1 customer_profile |
| **訂閱者** | active email subscribers | V1 subscribers.json |
| **Reach** | unique 看到貼文的 user 數 | Meta Graph API insights |
| **Engagement** | like + comment + share / impressions | Meta Graph API |
| **Conversion rate** | new subscribers / link clicks | V1 + Meta |
| **Affiliate funnel** | clicks → conversions → payout | Pact(Phase 1.5 後)|
| **Blog PV** | nexus-academy.ai/blog/* page view | Google Analytics(Phase 4)|

**Timezone:** 全部 GMT+8 Asia/Taipei(對齊 Alex Boss 作息)
**Date boundary:** 00:00 ~ 23:59 Asia/Taipei

---

## D12:當前 deferred 議題(待 Phase 啟動時拍板)

- LINE Bot 用 既有 V1 還是新建(D10)── Phase 2 決定
- Pact API key 機制(已 by Pact spec Phase 1.5 設計)── Phase 3 整合時 follow
- V2 訂閱 metrics 怎麼跟 V1 區分(V2 用 Stripe?ECPay?)── V2 啟用前
- 月度報告 LINE push 還是 email(Phase 4)

---

## D13:Step 5 GA4 ── 改用 quick-links 連結方案(非 fetch)

**拍板日:** 2026-05-11(by Alex Boss)
**觸發:** Phase 1.5 Step 5 GA4 整合,service account 被 Google UI hard reject

### 問題
- GA4 Property + Account 兩層 access management UI 都 reject `aegis-ga4-reader@openclaw-workspace-487015.iam.gserviceaccount.com`
- Error message:「這個電子郵件與 Google 帳戶不符」
- 這是 Google known limitation:GA4 user management(認 Google Account)跟 GCP IAM(認 service account)是兩套不同 systems
- Property ID `534428855` 已 confirm,GA Data API 已啟用,JSON key 已建,但卡在 user invite

### 拍板:Plan C「連結方案」
**Aegis dashboard 不 fetch GA4 數據,改放 3 個 quick-links 跳 GA4 後台:**
1. 🟢 即時觀眾(realtime overview)
2. 📊 總覽報表(intelligenthome)
3. 🚦 流量來源(traffic acquisition)

### 為什麼選連結方案(否決 OAuth route)
- ✅ **零 over-engineer:** 不耗 1-2 小時走 OAuth flow + refresh token 管理
- ✅ **對齊 Aegis 紅線「不誇大、不 mock」:** 既然 fetch 卡關,誠實告訴 dashboard reader 「點這裡看詳細」
- ✅ **Alex 12 小時 sprint 收尾健康選擇**
- ❌ 否決 OAuth installed app flow:複雜度高,Phase 2 PostgreSQL 升級時順便做
- ❌ 否決 Google Group workaround:個人 Gmail 的 group 對 service account 接受度不確定,風險高

### Phase 2 重做計畫(2026 Q3)
- 用 OAuth 2.0 installed app flow:Alex 用自己 Gmail 跑一次授權 → refresh token 永久存 .env
- cron 用 refresh token 直接 read GA4 Data API
- dashboard 顯示 7 天 PV / UV / Sessions / Bounce / 流量來源 top 3

### 廢棄資源(本地保留,GCP 留著)
- `service_account.json` 在 aegis repo(`.gitignore` 保護不會 push)── Phase 2 OAuth 不需要,可選擇刪除
- GCP IAM service account `aegis-ga4-reader@...` 留著(沒 active access,不費 quota)

---

## 文件修訂歷程

| 日期 | 版本 | 修訂者 | 內容 |
|---|---|---|---|
| 2026-05-11 | v1.0 | 主對話小 M | Aegis 初次拍板,對齊 Memoria session 5/10 五件事 |
| 2026-05-11 晚 | v1.1 | 主對話小 M | 加 D13:Phase 1.5 Step 5 GA4 改連結方案(by Alex Boss) |
| (待) | v1.2 | Aegis 自己 | Phase 1 MVP LIVE 後 calibrate D3/D5/D6 |
