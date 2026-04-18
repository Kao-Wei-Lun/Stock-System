# QuantVision Pro 籌碼功能改版規劃 v1.0

**產出時間**：2026-04-18  
**規劃範圍**：先聚焦「籌碼」功能，不動其他工作區主流程  
**規劃目標**：把「個股籌碼」與「大盤 / TAIFEX 法人籌碼」拆開顯示，並把個股籌碼從單日快覽升級為可觀察一段時間變化的研究工具

---

## 1. 現況診斷

### 1.1 畫面層目前混在同一個工作流

目前 `InstitutionalDashboard.vue` 同時承載兩種不同性質的資訊：

- 上方先顯示「目前標的籌碼快覽」
- 下方再接整套 TAIFEX / 大盤法人籌碼資料

這樣的問題是：

- 使用者剛進頁時，會先看到單一標的摘要，但頁面主體其實是大盤 / 期權法人分析
- 「個股」與「大盤」分析邏輯不同，混在同一條閱讀動線會讓判讀跳來跳去
- 個股區塊目前只有單日快覽，不足以支撐「籌碼變化」判斷

**相關檔案**

- `frontend/src/components/InstitutionalDashboard.vue`
- `frontend/src/components/workspaces/InstitutionalAnalysisWorkspace.vue`

### 1.2 個股籌碼資料目前只有單點，不是時間序列

現在前端載入個股籌碼時，只取得：

- `detail`
- `summary`

也就是單一日期的 snapshot，沒有正式提供最近 5 / 10 / 20 / 60 日的歷史變化。

**相關檔案**

- `frontend/src/composables/dashboard/dashboardMarketIntel.js`
- `frontend/src/api/dashboardApi.js`
- `backend/routers/intelligence.py`

### 1.3 後端其實已經具備歷史資料基礎，但還沒有正式暴露成 API

資料庫層已經有：

- `get_taiwan_chip_snapshot()`
- `list_taiwan_chip_snapshots()`

代表籌碼歷史資料不是零基礎，只是目前 API 與前端還停留在單日顯示模式。

**相關檔案**

- `backend/repositories/taiwan_chip.py`

---

## 2. 這次改版的核心方向

### 2.1 先把「個股籌碼」與「大盤籌碼」拆成兩個獨立閱讀區

建議不要再把個股快覽直接塞在大盤頁最上面，而是改成以下其中一種：

**方案 A：同頁雙分頁**

- `個股籌碼追蹤`
- `大盤 / TAIFEX 法人籌碼`

**方案 B：同頁上下分區，但視覺上完全切開**

- 上半部是「個股籌碼研究區」
- 下半部是「大盤籌碼研究區」
- 中間要有明確標題、說明、背景層級與導覽切換

**本次推薦**

- 優先採用 `方案 A：同頁雙分頁`

原因：

- 閱讀目標最清楚
- 行動裝置更容易處理
- 不會讓長頁面把兩種研究流程混在一起

### 2.2 個股籌碼改成「區間追蹤」，不是只看單日

個股籌碼的核心價值不是「今天買超多少」，而是：

- 外資是不是連續買超
- 投信是不是開始接手
- 自營商是不是逆勢調節
- 三大法人合計是否出現趨勢翻轉

所以個股區塊應改成：

- 預設顯示最近 `20 日`
- 可切換 `5 / 10 / 20 / 60 日`
- 每個法人與合計都能一起看時間序列

---

## 3. 新版資訊架構建議

## 3.1 工作區結構

`籌碼工作區`

- `Tab 1：個股籌碼追蹤`
- `Tab 2：大盤 / TAIFEX 法人籌碼`

### 3.2 個股籌碼追蹤區的建議結構

**區塊 A：標的摘要列**

- 標的名稱 / ticker
- 最新籌碼資料日
- 來源標籤（TWSE / TPEX）
- 當前偏向（偏多 / 偏空 / 中性）
- 近 20 日淨買超方向摘要

**區塊 B：籌碼趨勢主圖**

- X 軸：日期
- Y 軸：股數
- 系列：
  - 外資買賣超
  - 投信買賣超
  - 自營商買賣超
  - 三大法人合計

**建議圖型**

- 預設用多序列 bar / line 混合圖
- 合計可用 line
- 三大法人分項可用 stacked / grouped bar

**區塊 C：趨勢判讀卡**

- 近 5 日合計
- 近 10 日合計
- 近 20 日合計
- 連續買超 / 賣超天數
- 最大單日買超 / 賣超

**區塊 D：籌碼轉折日**

- 列出最近幾個重要轉折：
  - 外資由賣轉買
  - 投信連續加碼開始日
  - 合計由負轉正

**區塊 E：價格對照**

- 同步顯示股價區間變化
- 讓使用者能看到：
  - 籌碼增強但價格未動
  - 價格上漲但籌碼轉弱

### 3.3 大盤 / TAIFEX 法人籌碼區

這一塊保留現有 `InstitutionalDashboard` 主體，但不再把個股快覽塞在同一視覺段落。

建議保留：

- 期貨 / 選擇權 / 現貨法人資料
- Insights summary
- 趨勢 panels
- Leaderboards
- 成本帶分析
- Structured query

建議調整：

- 標題直接明確寫成「大盤 / 期權法人籌碼」
- 首屏只強調大盤資料，不再混入個股摘要卡

---

## 4. 建議新增的資料 API

### M1.1 新增個股籌碼歷史 API

**建議路由**

```text
GET /api/tw/chips/{ticker}/history?days=20
```

**建議回傳**

```json
{
  "ticker": "2330.TW",
  "days": 20,
  "resolved_range": {
    "from": "2026-03-20",
    "to": "2026-04-18"
  },
  "latest": {
    "snapshot_date": "2026-04-18",
    "source": "twse_t86",
    "summary": {}
  },
  "series": [
    {
      "snapshot_date": "2026-04-01",
      "foreign_net_buy_sell": 123456,
      "investment_trust_net_buy_sell": 4567,
      "dealer_net_buy_sell": -987,
      "institutional_net_buy_sell": 127036
    }
  ],
  "stats": {
    "foreign_5d_sum": 0,
    "foreign_10d_sum": 0,
    "institutional_20d_sum": 0,
    "institutional_streak_days": 0
  }
}
```

### M1.2 視需要把價格序列一起包進來

若要在同一區塊直接看「籌碼 vs 股價」，可擇一：

- 方案 A：API 直接附帶最近區間的收盤價
- 方案 B：前端沿用既有 OHLC / quote 資料自行對齊

**本次推薦**

- 先採 `方案 A`，在籌碼歷史 API 直接回傳簡化 price series  
  這樣前端做圖最直接，也比較不會出現日期對不上

---

## 5. 前端改版規劃

### M2.1 狀態層重構

目前 `dashboardMarketIntel.js` 只有：

- `taiwanChipDetail`
- `taiwanChipSummary`

建議擴充成：

- `taiwanChipLatest`
- `taiwanChipHistory`
- `taiwanChipRangeDays`
- `taiwanChipHistoryLoading`
- `taiwanChipHistoryError`

### M2.2 UI 組件拆分

建議把現在 `InstitutionalDashboard.vue` 中的個股籌碼區塊抽出成獨立元件：

- `frontend/src/components/chips/StockChipOverview.vue`
- `frontend/src/components/chips/StockChipTrendChart.vue`
- `frontend/src/components/chips/StockChipStatsStrip.vue`
- `frontend/src/components/chips/StockChipTurningPoints.vue`
- `frontend/src/components/chips/ChipWorkspaceTabs.vue`

大盤籌碼區則維持原本 institutional 元件群。

### M2.3 預設互動

建議行為：

- 若目前 ticker 為 `.TW` / `.TWO`，進入籌碼工作區時預設打開 `個股籌碼追蹤`
- 若不是台股個股，預設打開 `大盤 / TAIFEX 法人籌碼`
- 切換 ticker 時保留目前 tab，但若目標不支援個股籌碼，顯示空狀態並提供一鍵切回大盤 tab

---

## 6. 額外推薦優化項

下面這些不是一定要第一版全做，但我認為很值得排進後續：

### R1. 籌碼與價格背離提示

例如：

- 三大法人連 5 日買超，但價格仍在盤整
- 股價創高，但外資連 3 日轉賣

這種「背離」比單日買賣超更有決策價值。

### R2. 連續性與累積量視角

除了單日序列，應加入：

- 近 N 日累積買賣超
- 連續買超 / 賣超天數
- 轉正 / 轉負發生點

這比單純顯示今天數字更能看出籌碼趨勢。

### R3. 與產業 / 大盤相對比較

如果能做到，個股籌碼最好增加：

- 同產業平均籌碼方向
- 與加權指數籌碼方向對照

這能回答「這檔是跟大盤一起強，還是自身更強」。

### R4. 重要事件標記

在個股籌碼趨勢圖上加上：

- 財報日
- 法說會
- 除權息
- 重大新聞

可以更清楚判讀籌碼變化是不是由事件驅動。

### R5. 快速摘要句

在圖上方自動生成一句摘要：

- 「外資近 10 日持續偏多，投信 3 日前開始轉買，三大法人合計由負翻正。」

這能顯著降低閱讀門檻。

### R6. 警報整合

未來可直接從籌碼頁建立：

- 外資連買 N 日警報
- 三大法人合計由負轉正警報
- 籌碼與股價背離警報

---

## 7. 建議實作順序

### Phase 1：資料與結構先到位

- 新增個股籌碼歷史 API
- 前端 state 增加 history 載入
- 個股 / 大盤籌碼分頁骨架

### Phase 2：完成第一版可用畫面

- 個股籌碼趨勢圖
- 近 5 / 10 / 20 / 60 日切換
- 統計條與最新摘要列

### Phase 3：提升研究價值

- 價格對照
- 轉折日整理
- 背離提示
- 智能摘要句

### Phase 4：進階整合

- 事件標記
- 警報整合
- 產業 / 大盤相對比較

---

## 8. 驗收標準

完成第一階段後，至少要滿足：

- 使用者能明確分辨「個股籌碼」與「大盤 / TAIFEX 籌碼」是兩條不同分析線
- 台股個股不再只有單日快覽，能看最近一段時間變化
- 使用者能在 10 秒內回答：
  - 近 20 日三大法人是偏買還偏賣
  - 哪一類法人在主導方向
  - 籌碼與價格是否同步

---

## 9. 我對這個功能的優先推薦

如果只做最值得的一版，我建議優先順序是：

1. `個股 / 大盤籌碼分頁化`
2. `個股籌碼歷史 API`
3. `近 20 日趨勢圖 + 5/10/20/60 切換`
4. `價格對照`
5. `連買連賣 / 轉折日摘要`

這五項做完後，整個「籌碼」功能的可讀性會比現在高非常多，而且會真正從「資訊陳列」變成「研究工具」。

