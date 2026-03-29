# QuantVision Pro 產品與系統完整規格書

## 1. 文件資訊

- 文件名稱：QuantVision Pro 產品與系統完整規格書
- 適用專案：`Stock-System`
- 文件版本：`v1.0`
- 文件狀態：`Baseline Draft`
- 建立日期：`2026-03-29`
- 目的：作為後續產品規劃、資料表設計、API 開發、前端實作、測試驗收與里程碑安排的單一依據

## 2. 專案定位

QuantVision Pro 是一套以股票、指數、期貨、選擇權與市場風險資訊為核心的分析平台，目標不是單純提供看盤，而是提供一套可提升交易決策品質、紀律與事後復盤能力的完整分析工作台。

本系統的核心價值如下：

- 將價格、技術面、法人籌碼、基本面、事件面與宏觀風險整合到同一套介面
- 將主觀分析流程沉澱成可保存、可回測、可追蹤、可檢討的工作流
- 讓使用者不只看到訊號，還能理解訊號來源、資料時間、適用情境與風險背景

## 3. 本期範圍與邊界

### 3.1 本期開發原則

- 前一輪整理出的建議全部列為必做
- 唯一明確暫緩項目為「即時報價串流」
- 暫緩原因：未來將改由券商 API 提供正式報價與可能的交易串接
- 因此本期只做「延遲報價 / 手動刷新 / 盤後同步 / 架構預留」，不做正式即時串流功能驗收
- 本系統所有正式需要的資料都必須落地存入本地資料庫，外部 API 只作為資料來源，不可作為唯一依賴

### 3.2 本期必做範圍

- 自選股與看板體驗升級
- 圖表分析與工作區持久化
- 完整警報引擎
- 完整回測模組
- 交易日誌與事後分析
- 法人籌碼模組深化
- 事件資訊中心
- 宏觀風險儀表板
- 台股進階籌碼模組
- 基本面資料模組
- 選股器 / 掃描器
- 通知中心
- 資料同步與資料品質機制
- 報價模組抽象化與券商 API 預留介面

### 3.3 本期暫不驗收項目

- 券商正式即時報價串流
- 正式下單、委託、成交回報
- 盤中即時推播必須以毫秒級或逐筆等級更新

### 3.4 本期必要預留

- `QuoteProvider` 抽象層
- `BrokerProvider` 抽象層
- 使用者、警報、工作區、交易紀錄資料結構都必須可在未來接上券商帳號
- 前端 UI 必須顯示資料時間，不得誤導使用者認為報價為即時串流

## 4. 產品目標

### 4.1 商業與產品目標

- 提升使用者對市場狀態的理解深度
- 降低因資訊分散造成的漏看與誤判
- 強化交易紀律與可回顧性
- 建立未來串接券商 API 的中樞平台

### 4.2 使用者目標

- 能快速知道今天市場是否適合出手
- 能清楚知道某一檔標的目前處於什麼技術與籌碼位置
- 能在事件發生前先知道風險
- 能回顧自己的策略、勝率、盈虧比與失誤模式

### 4.3 成功指標

- 使用者能在 3 次點擊內看到單一標的的價格、技術面、基本面、籌碼面、事件面摘要
- 90% 以上的所有主要畫面都能顯示資料來源與更新時間
- 所有警報可持久化，重新開啟系統後不遺失
- 所有回測策略都有明確可追蹤的交易明細
- 工作區、繪圖、回測參數、日誌與警報皆能保存並重用

## 5. 目標使用者與使用情境

### 5.1 目標使用者

- 台股與美股短中線交易者
- 重視技術分析的波段交易者
- 會觀察法人籌碼與市場結構的台指期 / 選擇權交易者
- 需要交易紀錄與檢討工具的自營型使用者

### 5.2 核心使用情境

- 開盤前快速判斷今日市場風險與事件
- 盤中或收盤後分析個股、指數、產業與法人籌碼
- 根據警報條件回頭檢查圖表與事件背景
- 執行回測並比較策略適配度
- 記錄一筆交易的進場理由、出場理由、檢討與截圖

## 6. 系統設計原則

### 6.1 資料透明

- 所有價格、籌碼、新聞、事件、基本面資料都要標示資料來源
- 所有資料都要顯示更新時間與適用交易日
- 延遲資料必須標註為延遲 / 盤後 / 快照，不得使用「即時」字樣

### 6.2 訊號可解釋

- 警報、策略訊號、法人異常值都要說明觸發依據
- 技術面摘要必須可回溯到具體指標或條件
- 回測結果必須可追到逐筆交易

### 6.3 單一工作台

- 使用者不需要在多個頁面來回切換，核心決策資訊要可在同一套工作流中串連
- 圖表、警報、法人、事件、回測、交易紀錄之間要能互相跳轉

### 6.4 可擴充

- 所有外部資料來源都應透過 provider 介面封裝
- 抽離報價、新聞、事件、籌碼、基本面供應器
- 未來換資料源或接券商 API 時，前端主要介面與業務邏輯不應大改

### 6.5 本地資料庫強制規範

- 本系統所有正式需要的資料都必須持久化到本地資料庫
- 外部 API、第三方網站、公開資料源與未來券商 API 都只能作為資料輸入來源，不能成為系統唯一資料依賴
- 凡是會影響畫面顯示、分析結果、警報判斷、回測結果、選股結果、通知、交易日誌、工作區還原、同步狀態與驗收結果的資料，都必須可由本地資料庫重建
- 前端 `localStorage`、記憶體快取、暫時檔只可作為非關鍵快取，不得作為正式資料唯一保存位置
- 若外部來源暫時不可用，系統仍應能使用本地資料庫中的最近可用資料提供查詢、檢視與降級服務
- 每一類資料都必須有對應的本地資料表或可追溯的本地持久化結構

## 7. 系統總體架構

### 7.1 技術架構

- 前端：Vue 3 + Vite
- 後端：FastAPI
- 資料庫：MySQL
- 排程 / 背景任務：FastAPI 啟動背景 loop，後續可擴充為獨立 scheduler / worker
- 通知：站內通知為基本需求，外部通知保留 email / Telegram / LINE / webhook 擴充

### 7.2 模組分層

- `Presentation Layer`
  - Dashboard
  - Chart Workspace
  - Institutional Dashboard
  - Screener
  - Event Center
  - Macro Dashboard
  - Trade Journal
  - Settings
- `Application Layer`
  - Watchlist Service
  - Alert Service
  - Backtest Service
  - Journal Service
  - Institutional Service
  - Event Service
  - Macro Service
  - Fundamental Service
  - Screener Service
  - Notification Service
  - Sync Service
- `Provider Layer`
  - QuoteProvider
  - OhlcvProvider
  - FundamentalProvider
  - InstitutionalProvider
  - EventProvider
  - NewsProvider
  - MacroProvider
  - TaiwanChipProvider
  - BrokerProvider
- `Persistence Layer`
  - MySQL tables
  - Local file / object store for screenshots if需要

### 7.3 Provider 抽象要求

本期必須建立以下介面定義，即使部分供應器先以現有公開資料來源實作：

- `QuoteProvider`
  - `get_quote(ticker)`
  - `get_quotes(tickers)`
  - `get_quote_timestamp(ticker)`
  - `stream_quotes(...)` 保留，不列入本期實作驗收
- `FundamentalProvider`
  - `get_profile(ticker)`
  - `get_ratios(ticker)`
  - `get_corporate_actions(ticker)`
- `EventProvider`
  - `get_earnings_calendar(...)`
  - `get_economic_calendar(...)`
  - `get_dividend_events(...)`
  - `get_company_events(...)`
- `BrokerProvider`
  - `authenticate()`
  - `stream_quotes(...)`
  - `place_order(...)`
  - `get_positions()`
  - `get_orders()`
  - 本期只定義介面，不實作

## 8. 功能規格

### 8.1 儀表板與自選股

#### 目標

- 讓使用者快速掌握關注標的與市場概況

#### 必做功能

- 自選股群組建立、命名、刪除、排序、拖拉
- 自選股標籤分類
- 自選股欄位自訂
  - 代號
  - 名稱
  - 類別
  - 最新價
  - 漲跌幅
  - 量比
  - 成交量
  - 均量比
  - 相對強弱
  - 資料時間
- 自選股可排序與篩選
  - 依漲跌幅
  - 依成交量
  - 依量比
  - 依類別
  - 依標籤
- 全市場總覽群組
  - 台股指數
  - 美股主要指數
  - 半導體指數
  - 商品
  - 風險指標

#### 驗收要求

- 自選股狀態持久化，不因重新整理消失
- 自選股每一列必須顯示資料時間
- 若資料非即時，畫面需以文字明確標示

### 8.2 圖表分析工作區

#### 目標

- 讓使用者在單一分析畫面完成技術面研判與註記

#### 必做功能

- 多週期 K 線
  - 日 K
  - 週 K
  - 月 K
  - 季 K
- 顯示模式
  - K 線
  - 線圖
  - 面積圖
- 技術指標模板
  - 趨勢模板
  - 擺盪模板
  - 量價模板
  - 清爽模板
- 繪圖工具
  - 水平線
  - 垂直事件線
  - 趨勢線
  - 箭頭
  - 費波那契
  - 區間框
  - 測距
  - 文字註記
- 比較標的
  - 相對報酬
  - 絕對價格
- 工作區儲存
  - 指標狀態
  - 繪圖物件
  - 比較標的
  - 選取標的
  - 週期與版面

#### 驗收要求

- 工作區資料必須存入後端，不得只依賴 `localStorage`
- 繪圖物件重載後必須可還原
- 每份工作區必須可編輯名稱、複製、刪除

### 8.3 技術指標模組

#### 必做指標

- MA / EMA / 週月季年線
- Bollinger Bands
- Parabolic SAR
- Keltner Channels
- Donchian Channels
- VWAP
- Ichimoku
- SuperTrend
- RSI
- Aroon
- TRIX
- Williams %R
- MFI
- ROC
- Bollinger %B
- Bollinger Width
- MACD
- KD / Stochastic
- ATR
- CCI
- OBV
- ADX
- CMF

#### 必做能力

- 指標開關
- 指標參數自訂
- 模板切換
- 技術面摘要卡
- 指標訊號解釋

#### 驗收要求

- 技術面摘要不可只顯示結論，必須帶出至少 3 個關鍵依據
- 所有參數變更需可保存於工作區

### 8.4 警報引擎

#### 目標

- 讓警報成為可持久化、可管理、可追蹤、可擴充的正式模組

#### 必做功能

- 警報建立、編輯、刪除、暫停、恢復
- 警報條件
  - 價格大於 / 小於
  - 價格上穿 / 下穿
  - 漲跌幅大於 / 小於
  - RSI 大於 / 小於 / 上穿 / 下穿
  - MACD 黃金交叉 / 死亡交叉
  - 成交量放大
  - 量比異常
  - 法人異常值
  - Basis 偏離
  - 事件提醒
- 觸發頻率
  - 單次觸發
  - 每日首次觸發
  - 條件維持時重複提醒
- 觸發紀錄
- 站內通知
- 至少一種外部通知通道
  - webhook
  - email
  - Telegram
  - LINE
  - 可先擇一落地

#### 驗收要求

- 警報資料與觸發紀錄需落資料庫
- 系統重啟後警報不可遺失
- 觸發後需能回看觸發時的標的、數值、時間與來源資料時間

### 8.5 回測模組

#### 目標

- 讓使用者能對策略進行可追溯、可比較的回測

#### 必做策略

- MA 黃金 / 死亡交叉
- RSI 超買超賣
- MACD 交叉
- 布林通道突破
- KD 交叉

#### 必做功能

- 回測參數設定
  - 起始日
  - 結束日
  - 初始資金
  - 手續費
  - 滑價
  - 停損
  - 停利
  - 部位大小
- 回測結果
  - 總報酬
  - 最終資金
  - 勝率
  - 交易次數
  - 平均獲利
  - 平均虧損
  - 盈虧比
  - 最大回撤
  - Sharpe
  - Buy and Hold 對照
- 逐筆交易明細
- 權益曲線
- 參數組合保存
- 回測紀錄保存

#### 驗收要求

- UI 上出現的策略必須全部有實作
- 回測結果必須可展開查看逐筆交易
- 系統需避免前視偏誤
- 回測資料範圍與來源需可追溯

### 8.6 交易日誌與檢討

#### 目標

- 建立「做交易」與「檢討交易」的閉環

#### 必做功能

- 建立交易紀錄
  - 標的
  - 市場
  - 多空方向
  - 進場時間與價格
  - 出場時間與價格
  - 倉位大小
  - 停損
  - 停利
  - 交易策略
  - 進場理由
  - 出場理由
  - 情緒註記
  - 截圖
  - 標籤
- 交易結果分析
  - 總筆數
  - 勝率
  - 盈虧比
  - 平均持有時間
  - 最大連敗
  - 最大連勝
  - 策略別績效
  - 市場別績效
  - 標籤別績效
- 可從圖表工作區直接建立交易日誌

#### 驗收要求

- 交易日誌需可搜尋、篩選、排序
- 截圖需與紀錄綁定
- 所有統計需能從真實交易紀錄重建

### 8.7 法人籌碼模組

#### 目標

- 將現有 TAIFEX 法人資料升級為可操作的決策模組

#### 必做功能

- 期貨、選擇權、現貨三大法人整合檢視
- 商品切換
- 歷史區間切換
- 主力多空排行榜
- 成本推估
- Basis 分析
- 異常值偵測
- 自動觀點摘要
- 與圖表疊圖
- 與警報條件整合

#### 驗收要求

- 異常值必須附計算依據
- Basis 頁需標示現貨參考來源與實際資料日
- 若資料缺漏，必須顯示降級訊息而非靜默失敗

### 8.8 事件資訊中心

#### 目標

- 降低技術訊號被事件風險破壞的機率

#### 必做事件類型

- 財報公告日
- 法說會 / 投資人會議
- 除權息 / 股利
- 重大新聞
- 經濟日曆
  - CPI
  - PPI
  - 利率決議
  - 非農
  - PMI
- 台股與國際市場休市日曆

#### 必做功能

- 事件總覽頁
- 標的事件卡
- 市場事件篩選
- 事件警報
- 事件與圖表垂直線連動

#### 驗收要求

- 所有事件需有日期、來源、標的或市場範圍
- 圖表中可看到事件標記

### 8.9 宏觀風險儀表板

#### 目標

- 讓使用者快速判斷整體風險環境是否支持交易

#### 必做指標

- VIX
- DXY
- 美國 10 年期公債殖利率
- 台幣匯率
- S&P 500
- NASDAQ
- SOX
- 台灣加權指數
- 櫃買指數
- 漲跌家數
- 產業輪動強弱
- 原油、黃金等風險偏好相關資產

#### 必做功能

- 風險溫度計
- 指標趨勢圖
- 日內 / 日線切換
- 宏觀摘要
- 風險警示

### 8.10 台股進階籌碼模組

#### 必做內容

- 融資餘額
- 融券餘額
- 借券賣出
- 分點 / 主力進出
- 外資、投信、自營商個股買賣超
- 台指期近遠月價差
- Put / Call Ratio
- 最大 OI 支撐壓力

#### 驗收要求

- 個股頁可查看台股籌碼摘要
- 期權頁可查看關鍵支撐壓力與 PCR
- 可用於警報與選股條件

### 8.11 基本面資料模組

#### 必做欄位

- 公司名稱
- 產業
- 子產業
- 市值
- 本益比
- 殖利率
- 52 週高低
- 平均成交量
- 公司簡介
- 幣別
- 交易所
- 國家 / 市場
- 財報公告日
- 配息 / 除息日

#### 必做功能

- 標的基本資料卡
- 基本面摘要
- 與事件中心連動
- 搜尋可依名稱 / 代號 / 產業查找

### 8.12 選股器 / 掃描器

#### 目標

- 將觀察從單一標的擴展到全市場機會搜尋

#### 必做條件

- 價格突破區間高點
- 接近 52 週新高
- MA 多頭排列
- MACD 剛翻多 / 翻空
- RSI 由弱轉強
- KD 黃金交叉
- ATR 壓縮後擴張
- 量增突破
- 法人異常值
- 基本面條件
- 事件條件

#### 必做功能

- 篩選條件保存
- 結果排序
- 快速加入自選
- 一鍵跳圖
- 匯出 CSV

### 8.13 通知中心

#### 必做功能

- 站內通知列表
- 依警報 / 事件 / 系統 / 同步結果分類
- 已讀 / 未讀
- 搜尋與篩選
- 保留天數設定
- 外部通知通道設定

### 8.14 設定與個人化

#### 必做功能

- 時區設定
- 市場偏好設定
- 預設工作區
- 預設自選群組
- 指標預設值
- 通知通道設定
- 資料刷新偏好
- 圖表顯示偏好

## 9. 報價與券商整合規格

### 9.1 本期報價定義

- 本期只提供延遲報價、快照報價、盤後報價或手動刷新報價
- 畫面上禁止使用「即時」、「streaming」、「live quote」等會造成誤解的詞
- 所有價格資料需顯示：
  - 資料時間
  - 資料來源
  - 延遲 / 盤後 / 快照標記

### 9.2 本期必做

- 將現有報價存取封裝為 `QuoteProvider`
- 既有 `GET /api/quote/{ticker}` 改為明確定義成「最新可用快照」
- WebSocket 只保留介面相容性或未來預留，不作為本期核心驗收項
- 自選列表、主圖、法人頁若顯示價格，皆需一併顯示資料時間

### 9.3 未來券商 API 預留

- 保留 `BrokerProvider`
- 保留 WebSocket 訂閱模型
- 保留登入、授權、持倉、委託、成交回報資料模型
- 報價模組不得與回測、警報、工作區資料耦合在同一層

## 10. 資料來源規格

### 10.1 現行可沿用資料來源

- OHLCV：Yahoo Finance
- 台指 / 期權法人：TAIFEX
- 台股現貨法人摘要：TWSE
- 備援現貨法人 / 台股日資料：FinMind

### 10.2 本期需新增或補完的資料來源類別

- 基本面資料來源
- 新聞資料來源
- 事件日曆資料來源
- 宏觀資料來源
- 台股籌碼資料來源

### 10.3 資料來源通則

- 每一類資料來源都需具備 fallback 或降級策略
- 所有來源異常都需記錄於同步日誌
- 前端需能顯示資料是否來自主來源、備援來源或快取
- 外部來源取得的正式資料在進入業務流程前，必須同步寫入本地資料庫

## 11. 資料模型與資料表規格

### 11.1 使用者層

雖然本期預設可先以單使用者模式運作，但所有核心資料需具備 `owner_id`，預留未來多使用者能力。

#### `user_profiles`

- `id`
- `username`
- `display_name`
- `timezone`
- `default_market`
- `created_at`
- `updated_at`

#### `user_preferences`

- `owner_id`
- `dashboard_json`
- `notification_json`
- `chart_json`
- `updated_at`

### 11.2 市場資料層

#### `ohlcv`

- 保留現有結構
- 新增建議欄位：
  - `source`
  - `market`
  - `asset_type`
  - `data_quality_flag`
  - `updated_at`

#### `market_quotes_latest`

- `ticker`
- `price`
- `open`
- `high`
- `low`
- `prev_close`
- `change`
- `change_pct`
- `volume`
- `quote_timestamp`
- `source`
- `quote_type`
  - `snapshot`
  - `delayed`
  - `after_hours`
- `updated_at`

#### `stock_info`

- 保留現有結構
- 必須真正補齊：
  - `sector`
  - `industry`
  - `pe_ratio`
  - `dividend_yield`
  - `week_52_high`
  - `week_52_low`
  - `avg_volume`
  - `description`

#### `fundamental_snapshots`

- `id`
- `ticker`
- `snapshot_date`
- `payload_json`
- `source`
- `created_at`

### 11.3 自選與工作區

#### `watchlist_groups`

- 保留現有結構
- 新增：
  - `owner_id`
  - `color`
  - `is_system`

#### `watchlist_items`

- 保留現有結構
- 新增：
  - `tags_json`
  - `notes`

#### `workspace_presets`

- `id`
- `owner_id`
- `name`
- `current_ticker`
- `layout`
- `snapshot_json`
- `created_at`
- `updated_at`

### 11.4 警報

#### `alerts`

- 沿用現有資料表概念，但需正式化
- 核心欄位：
  - `id`
  - `owner_id`
  - `ticker`
  - `scope_type`
    - `ticker`
    - `market`
    - `event`
    - `institutional`
  - `alert_type`
    - `price`
    - `pct`
    - `rsi`
    - `macd`
    - `volume`
    - `basis`
    - `institutional`
    - `event`
  - `condition`
  - `value1`
  - `value2`
  - `cooldown_minutes`
  - `repeat_mode`
  - `is_active`
  - `last_checked_at`
  - `last_triggered_at`
  - `notify_channels_json`
  - `created_at`
  - `updated_at`

#### `alert_trigger_logs`

- `id`
- `alert_id`
- `triggered_value_json`
- `message`
- `source`
- `quote_timestamp`
- `created_at`

### 11.5 回測

#### `backtest_runs`

- `id`
- `owner_id`
- `name`
- `ticker`
- `strategy_code`
- `params_json`
- `period_start`
- `period_end`
- `summary_json`
- `created_at`

#### `backtest_trades`

- `id`
- `run_id`
- `trade_no`
- `side`
- `entry_date`
- `entry_price`
- `exit_date`
- `exit_price`
- `shares`
- `fee`
- `slippage`
- `pnl`
- `pnl_pct`

### 11.6 交易日誌

#### `trade_journal_entries`

- `id`
- `owner_id`
- `ticker`
- `market`
- `direction`
- `strategy_code`
- `entry_time`
- `entry_price`
- `exit_time`
- `exit_price`
- `size`
- `stop_loss`
- `take_profit`
- `entry_reason`
- `exit_reason`
- `emotion_tag`
- `review_notes`
- `result_json`
- `created_at`
- `updated_at`

#### `trade_journal_tags`

- `id`
- `entry_id`
- `tag`

#### `trade_journal_attachments`

- `id`
- `entry_id`
- `file_path`
- `file_type`
- `created_at`

### 11.7 事件與新聞

#### `market_events`

- `id`
- `event_type`
- `market`
- `ticker`
- `title`
- `description`
- `event_date`
- `event_time`
- `importance`
- `source`
- `url`
- `created_at`

#### `news_articles`

- `id`
- `ticker`
- `market`
- `title`
- `summary`
- `published_at`
- `source`
- `url`
- `sentiment`
- `created_at`

### 11.8 宏觀與籌碼

#### `macro_snapshots`

- `id`
- `metric_code`
- `metric_name`
- `value`
- `date`
- `source`
- `payload_json`

#### `taiwan_chip_snapshots`

- `id`
- `ticker`
- `trade_date`
- `margin_balance`
- `short_balance`
- `securities_lending`
- `foreign_net`
- `trust_net`
- `dealer_net`
- `branch_payload_json`
- `source`

#### `institutional_snapshots`

- 保留現有結構
- 可維持為法人主資料表

### 11.9 通知與同步

#### `notifications`

- `id`
- `owner_id`
- `type`
- `title`
- `message`
- `payload_json`
- `is_read`
- `created_at`

#### `sync_jobs`

- `id`
- `job_type`
- `scope`
- `status`
- `started_at`
- `finished_at`
- `summary_json`

#### `sync_job_logs`

- `id`
- `job_id`
- `entity_key`
- `status`
- `message`
- `created_at`

## 12. API 規格

### 12.1 原則

- 以 `/api/*` 為 REST 主入口
- 回應必須統一包含成功或錯誤訊息
- 重要查詢需支援 `source`、`updated_at`、`data_timestamp`
- 新增 API 時需盡量保留與現有路由相容

### 12.2 既有 API 保留與補強

- `GET /api/watchlist`
- `POST /api/watchlist/groups`
- `PATCH /api/watchlist/groups/{group_id}`
- `DELETE /api/watchlist/groups/{group_id}`
- `POST /api/watchlist/items`
- `DELETE /api/watchlist/items/{item_id}`
- `PUT /api/watchlist/groups/{group_id}/items/order`
- `GET /api/kline/{ticker}`
- `GET /api/quote/{ticker}`
  - 本期定義為延遲 / 快照報價
- `GET /api/info/{ticker}`
- `POST /api/sync/{ticker}`
- `POST /api/sync/all`
- `GET /api/search`
- `GET /api/db/stats`
- `GET /api/taifex/institutional`
- `GET /api/taifex/institutional/insights`

### 12.3 新增 API

#### 工作區

- `GET /api/workspaces`
- `POST /api/workspaces`
- `GET /api/workspaces/{id}`
- `PATCH /api/workspaces/{id}`
- `DELETE /api/workspaces/{id}`

#### 警報

- `GET /api/alerts`
- `POST /api/alerts`
- `PATCH /api/alerts/{id}`
- `DELETE /api/alerts/{id}`
- `POST /api/alerts/{id}/pause`
- `POST /api/alerts/{id}/resume`
- `GET /api/alerts/{id}/triggers`

#### 回測

- `POST /api/backtests/run`
- `GET /api/backtests`
- `GET /api/backtests/{id}`
- `DELETE /api/backtests/{id}`

#### 交易日誌

- `GET /api/journal/trades`
- `POST /api/journal/trades`
- `GET /api/journal/trades/{id}`
- `PATCH /api/journal/trades/{id}`
- `DELETE /api/journal/trades/{id}`

#### 事件與新聞

- `GET /api/events/calendar`
- `GET /api/events/{ticker}`
- `GET /api/news`
- `GET /api/news/{ticker}`

#### 宏觀與籌碼

- `GET /api/market/macro`
- `GET /api/tw/chips/{ticker}`
- `GET /api/options/summary`

#### 基本面

- `GET /api/fundamentals/{ticker}`
- `GET /api/fundamentals/{ticker}/events`

#### 選股器

- `POST /api/screener/run`
- `GET /api/screener/presets`
- `POST /api/screener/presets`
- `DELETE /api/screener/presets/{id}`

#### 通知

- `GET /api/notifications`
- `PATCH /api/notifications/{id}/read`
- `POST /api/notifications/read-all`

### 12.4 WebSocket 規格

- 本期不將 WebSocket 即時報價作為核心驗收
- 如保留 `/ws`，僅視為未來券商報價串流預留
- 不得讓 UI 宣稱其為正式即時報價

## 13. 前端頁面與資訊架構

### 13.1 必做主頁

- Dashboard 首頁
- 圖表分析頁
- 法人籌碼頁
- 事件中心
- 宏觀風險頁
- 選股器頁
- 交易日誌頁
- 通知中心
- 設定頁

### 13.2 Dashboard

- 左側：自選群組 / 市場群組
- 中央：圖表工作區
- 右側：指標 / 警報 / 回測 / 資料庫 / 交易紀錄快捷區
- 頂部：搜尋、時間區間、市場開盤狀態、通知入口
- 底部：後端狀態、資料時間、延遲標記

### 13.3 標的詳情頁最少資訊

- 價格快照
- 圖表
- 技術面摘要
- 基本面資料
- 事件資訊
- 台股籌碼
- 法人疊圖
- 可直接新增警報、加入自選、建立交易日誌

## 14. 非功能性需求

### 14.1 效能

- Dashboard 首屏載入時間目標：3 秒內
- 單一標的資料切換目標：2 秒內完成主要內容更新
- 選股器執行回應目標：10 秒內返回首批結果

### 14.2 可用性

- 支援桌機與平板
- 重要表格支援捲動與固定表頭
- 長列表需支援分頁或虛擬捲動

### 14.3 資料正確性

- 每筆資料需帶來源與時間
- 異常或缺漏時需顯示降級訊息
- 同步失敗需有 log 與通知
- 任何正式功能不得直接依賴前端暫存或外部即時回應作為唯一資料來源

### 14.4 安全性

- 外部 API 金鑰使用 `.env`
- 不得將敏感資訊暴露於前端
- 未來券商 API 權杖需獨立加密儲存

### 14.5 可維運性

- 每個同步工作需可觀測
- 主要 API 需有錯誤紀錄與必要統計
- Provider 層需可單獨測試

## 15. 測試與驗收規格

### 15.1 單元測試

- 指標計算
- 回測策略邏輯
- 警報條件判斷
- 異常值偵測
- Provider fallback 邏輯

### 15.2 整合測試

- 自選建立到圖表載入
- 建立警報到觸發通知
- 建立回測到保存結果
- 建立交易日誌到統計更新
- 事件資料與圖表垂直線連動

### 15.3 驗收測試

- 重啟系統後，工作區、警報、回測紀錄、交易日誌全部保留
- 當資料來源失敗時，前端可顯示備援或錯誤資訊
- 所有畫面至少有一處可見的資料時間標示
- UI 上出現的功能不得是半成品占位

## 16. 開發里程碑

### Phase 1：基礎能力補強

- Provider 抽象層
- 工作區後端化
- 警報資料模型與 API
- 延遲報價與資料時間標示
- 基本面資料補齊

### Phase 2：策略與紀律工具

- 完整回測
- 交易日誌
- 通知中心
- 自選股進階排序與篩選

### Phase 3：市場資訊擴張

- 事件中心
- 宏觀風險頁
- 台股進階籌碼
- 選股器

### Phase 4：整合與優化

- 法人與圖表 / 警報 / 選股器整合
- 效能優化
- 資料品質監控
- 券商 API 前置介面完成

## 17. 與現有程式碼的落地要求

### 17.1 現有功能可沿用

- Watchlist 群組基礎能力
- K 線與指標繪製框架
- 法人籌碼頁主要視覺與資料流程
- 基本資料同步與資料庫初始化流程

### 17.2 必須優先重構的區塊

- 警報目前僅存在前端記憶體，需改為正式後端模組
- 工作區目前僅存在瀏覽器儲存，需改為後端持久化
- 回測 UI 與實作策略不一致，需補齊
- 報價顯示需由「看似即時」改為「明確標示快照 / 延遲」
- 基本面欄位需真正補齊資料來源與同步流程

## 18. 完成定義

下列條件全部滿足時，才視為本規格完成：

- 所有必做模組皆有對應資料表、API、前端入口與驗收測試
- 所有資訊都可顯示來源與資料時間
- 不再依賴前端暫存作為唯一資料來源
- 所有正式需要的資料皆可由本地資料庫重建
- 警報、回測、交易日誌、工作區形成完整閉環
- 即時報價雖未實作，但報價抽象層與券商 API 預留已完成

## 19. 後續文件建議

建議依本規格再拆出以下子文件：

- `docs/database-schema.md`
- `docs/api-spec.md`
- `docs/frontend-information-architecture.md`
- `docs/provider-interface-spec.md`
- `docs/roadmap.md`
