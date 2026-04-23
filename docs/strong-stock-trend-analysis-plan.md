# QuantVision Pro 強勢股搜尋與未來趨勢分析規劃 v1.1

**產出時間**：2026-04-23  
**規劃目標**：建立一套可落地到現有 `Screener`、`Market Overview`、`Macro`、`Chip` 工作區的「強勢股發掘 + 未來趨勢判讀」方法，避免系統只提供漲跌幅排行，卻無法回答「這檔為什麼強、還能不能追、何時算失效」。

---

## 1. 規劃結論

本功能不應把「強勢股」定義成單純的 `今日漲最多`，而應定義成：

- `市場環境允許出手`
- `價格結構明確偏強`
- `量能有跟上`
- `相對大盤或同族群更強`
- `有基本面 / 事件 / 籌碼支撐`

同樣地，「分析未來趨勢」也不應包裝成預測，而應定義成：

- `目前趨勢是剛起漲、延續中、過熱，還是轉弱`
- `未來 5 / 20 / 60 個交易日最可能的情境是什麼`
- `哪個條件出現時代表趨勢延續`
- `哪個條件出現時代表原本判斷失效`

對應到現有系統，建議走法不是新開一套獨立功能，而是：

- 以現有 `backend/screener_engine.py` 為核心擴充評分模型
- 以現有 `frontend/src/components/ScreenerWorkspace.vue` 為主要工作區
- 以現有 `frontend/src/components/workspaces/MarketOverviewWorkspace.vue` 的 `盤中強勢股` / `策略掃描結果` 作為入口
- 串接既有 `Macro Dashboard`、`事件中心`、`台股籌碼` 與後續基本面資料

---

## 2. 現況盤點

### 2.1 目前已經有的能力

目前系統其實已經具備強勢股功能的基礎骨架：

- `Screener` 已有：
  - `量比`
  - `接近 52W 高點`
  - `均線排列`
  - `Setup 品質`
  - `台股籌碼偏向`
  - `事件天數`
  - `市場 posture / macro adjustment`
- `Market Overview` 已有：
  - `盤中強勢股`
  - `盤中弱勢股`
  - `台股強勢股篩選`
  - `策略掃描結果`
- `Macro` 已能提供：
  - `defensive / selective / balanced / offensive` 類型的市場 posture
- `Chip` 模組已具備：
  - 台股法人資料
  - 大盤 / 期貨法人方向判讀基礎

### 2.2 目前還缺的能力

雖然已有基礎，但目前離「真的能找出強勢股並分析趨勢」還有幾個缺口：

- 缺少正式的 `強勢股定義`
- 缺少 `相對強弱` 指標
  - 目前比較偏絕對條件篩選，還不是市場內相對排名
- 缺少 `趨勢階段` 標籤
  - 例如剛起漲、確認趨勢、延伸過熱、拉回整理、趨勢破壞
- 缺少 `未來趨勢情境卡`
  - 目前較像「現在看起來不錯」，但還沒有「接下來看什麼」
- 缺少 `日級別持久化`
  - 若沒有把每日強勢分數、排名、趨勢狀態落地，後續就很難回測與驗證

### 2.3 規劃原則

這份規劃採以下原則：

- `先定義框架，再補欄位`
- `先定義可交易 universe，再做 ranking`
- `先能解釋為什麼強，再追求模型更複雜`
- `未來趨勢` 以情境分析為主，不做假精準的價格預測
- 所有正式判讀資料都要能 `本地落地`

---

## 3. 什麼叫強勢股

### 3.1 強勢股的六層定義

建議把強勢股定義成六層條件的疊加，而不是只看單一技術指標。

#### A. 市場環境層

先回答：

- 今天適不適合追價
- 現在是順風盤、震盪盤，還是高風險防守盤

沒有先看市場環境，單一股票再強，也很容易在風險關閉日失敗。

#### B. 價格結構層

核心是確認價格是否真的處在上升結構，而不是單日新聞拉抬。

第一版建議至少觀察：

- 價格是否站上 `MA20`
- `MA20` 是否高於 `MA50`
- 中長期是否接近 `52 週高點`
- 是否形成 `higher high / higher low`
- 是否為 `breakout` 或 `breakout 後第一次健康拉回`

#### C. 量能確認層

強勢股不能只有價格漂亮，還要有量能支持。

第一版建議至少觀察：

- `量比`
- 突破當天量能是否高於近期均量
- 拉回時量能是否縮小

#### D. 相對強弱層

這是目前系統最需要補的核心。

要回答的不是：

- 這檔有沒有漲

而是：

- 這檔是否比大盤強
- 這檔是否比同產業強
- 大盤回檔時，這檔是否抗跌

建議新增：

- `RS_20D`：近 20 日相對大盤報酬
- `RS_60D`：近 60 日相對大盤報酬
- `Sector_RS`：相對同產業排名
- `Pullback_Resilience`：大盤回檔期間的相對抗跌分數

#### E. 確認訊號層

技術面很重要，但不能只靠技術面。

第一版建議整合：

- 台股 `法人買賣超偏向`
- 關鍵事件是否逼近
  - 財報
  - 法說會
  - 重大訊息
- 若已具備基本面資料：
  - 營收 / EPS 是否改善
  - 市場是否剛上修預期

#### F. 風險排除層

以下標的不應因為分數高就直接列為強勢股：

- 流動性不足
- 僅靠單日消息急拉，但沒有後續量價延續
- 長上影 / 爆量不漲
- 已遠離關鍵均線、屬於過度延伸
- 重大事件臨近，但波動風險未納入

### 3.2 Universe 與 Tradability 規則

這一塊應放在 `strength_score` 之前，而不是等高分後才排除。

原因是：

- 真正可交易的強勢股，必須同時滿足 `結構強` 與 `能成交`
- 若 universe 太鬆，ranking 很容易被小型飆股、低流動性標的與特殊商品污染

建議把 universe 拆成兩層：

- `Coverage Universe`
  - 系統理論上可抓資料的股票池
- `Tradable Universe`
  - 真正允許參與強勢股排序與交易模擬的股票池

第一版建議 `Tradable Universe` 至少過濾以下條件：

- `最低價格`
- `近 20 日平均成交值`
- `近 20 日平均成交量`
- `上市滿 X 個交易日`
- `最近 Y 日內未長期停牌`
- `非異常處置 / 特殊交易限制標的`
- `非策略明確要排除的商品類型`
  - 例如：
    - 槓反 ETF / ETN
    - 極低流動性 ETF
    - 結構複雜的受益證券

建議第一版就加入以下欄位：

- `is_tradeable`
- `tradability_flags`
- `avg_trade_value_20d`
- `avg_volume_20d`
- `days_since_listing`
- `security_type`

### 3.3 市場別應有不同的 Tradability Profile

台股與美股的交易結構不同，不建議共用同一組門檻。

建議至少拆成：

- `TW profile`
- `US profile`

每個 profile 可調：

- `min_price`
- `min_avg_trade_value_20d`
- `min_avg_volume_20d`
- `min_listing_days`
- `excluded_security_types`

第一版即使先用保守預設值，也應把 profile 抽成設定，不要寫死在程式中。

---

## 4. 強勢股評分模型建議

### 4.1 建議分數結構

建議把現有 `setup_quality` 擴充為更完整的 `strength_score (0-100)`。

| 維度 | 建議權重 | 主要回答問題 |
| --- | ---: | --- |
| 市場環境 | 15 | 現在是不是值得追強勢股 |
| 價格結構 | 25 | 趨勢是否完整 |
| 相對強弱 | 20 | 是否比大盤 / 同族群更強 |
| 量能確認 | 15 | 這波強勢是否有量支持 |
| 事件 / 基本面 / 籌碼確認 | 15 | 是否有延續趨勢的理由 |
| 風險扣分 | -20 ~ 0 | 是否過熱、事件風險高、流動性差 |

### 4.2 第一版分數規則

第一版不需要一開始就做機器學習，先做可解釋規則模型即可。

建議規則如下：

- `市場環境`
  - `offensive`：加分最高
  - `balanced`：中性
  - `selective`：只保留高品質標的
  - `defensive`：整體降權，但仍可保留極少數逆風強勢股
- `價格結構`
  - 站上 `MA20`、`MA50`、接近 52W high、突破前高，各自加分
- `相對強弱`
  - `RS_20D`、`RS_60D` 高於市場與產業中位數才加分
- `量能`
  - 突破量增、整理量縮才加分
- `事件 / 籌碼`
  - 法人偏多、財報前後正向延續、重大訊息利多但未過熱才加分
- `風險扣分`
  - 過度遠離均線
  - 爆量長黑
  - 重大事件前一日追價
  - 低流動性

### 4.3 第一版分級

建議結果分成三層：

- `80-100`：`Priority Strong`
  - 可列入今日優先觀察 / 等觸發
- `65-79`：`Watch`
  - 結構可觀察，但需要更好 trigger
- `<65`：`Wait`
  - 暫不列為強勢追蹤

額外建議保留一種特殊類型：

- `Defensive Strong`
  - 市場很差，但這檔仍相對抗跌、結構完整  
  - 這類標的未必立刻進場，但常是下一波領漲候選

### 4.4 Feature Formula Spec

若要讓這套規劃可以穩定驗證與回測，第一版就應該把關鍵特徵公式化。

以下建議先採 `可解釋、可重算` 的規則版本：

#### A. Relative Strength

建議先用超額報酬定義：

```text
stock_return_N = close_t / close_t-N - 1
benchmark_return_N = benchmark_close_t / benchmark_close_t-N - 1
RS_N = stock_return_N - benchmark_return_N
```

建議第一版使用：

- `relative_strength_20d = RS_20`
- `relative_strength_60d = RS_60`

若為台股：

- benchmark 預設可用 `TWII`

若為美股：

- benchmark 預設可用 `SPY` 或主要寬基指數 proxy

#### B. Sector Relative Rank

建議定義為同產業內的百分位排名：

```text
sector_relative_rank =
percentile_rank(RS_20 within same sector and market)
```

第一版建議：

- 使用 `0-100` 百分位
- 若同產業樣本數太少，回退到 market rank

#### C. Pullback Resilience

建議定義為：

- 大盤近 `M` 日明顯回檔期間
- 個股相對 benchmark 的超額報酬
- 再加上是否守住 `MA20` / `MA50` 的結構條件

可先簡化為：

```text
pullback_resilience =
RS_during_benchmark_pullback
+ structure_bonus
```

其中 `structure_bonus`：

- 守住 `MA20`：加分
- 跌破 `MA50`：扣分

#### D. Breakout Status

第一版建議用明確規則：

- `fresh_breakout`
  - 近 `N` bars 內有效突破區間高點或前高
- `retest`
  - 突破後回踩關鍵區未破，且重新轉強
- `failed_breakout`
  - 突破後短時間跌回突破區下方
- `none`
  - 不符合以上條件

#### E. Volume Confirmation

建議第一版使用相對均量確認：

- `confirmed`
  - 突破當日或訊號當下 `volume_ratio >= threshold_high`
- `normal`
  - `threshold_low <= volume_ratio < threshold_high`
- `weak`
  - `volume_ratio < threshold_low`

閾值應由 market profile 控制，不建議全市場共用一組固定數字。

#### F. Trend Stage

第一版建議明確定義：

- `Emerging`
  - 剛脫離整理區
  - `close > MA20`
  - `MA20` 開始上彎
  - 近 `N` bars 內剛出現有效突破
- `Confirmed`
  - `close > MA20`
  - `MA20 > MA50`
  - `RS_20 > 0`
  - 無明顯失敗突破或 distribution 訊號
- `Extended`
  - 趨勢仍強
  - 但 `distance_from_ma20_pct` 或短週期過熱達到過度延伸門檻
- `Constructive Pullback`
  - 原本為 `Confirmed`
  - 拉回但未破壞主結構
  - 拉回量縮，且仍位於合理支撐上方
- `Broken`
  - 跌破主結構
  - 或失敗突破後 RS 明顯轉弱

#### G. Setup Type 需與總分分開

建議第一版就加：

- `setup_type`
  - `fresh_breakout`
  - `constructive_pullback`
  - `extended_leader`
  - `defensive_strong`

原因是：

- 即使總分都很高，不同 `setup_type` 的進場與風控方法也完全不同

### 4.5 第一版應先做「類型分流」，再做單一總分

建議流程：

1. 先過 `Tradable Universe`
2. 再做 `setup_type` 分流
3. 最後在類型內排序 `strength_score`

這會比把所有標的直接混成一條總分榜，更接近交易員的工作方式。

---

## 5. 如何分析未來趨勢

### 5.1 先修正定義

未來趨勢分析不應回答：

- 明天一定漲或一定跌

而應回答：

- 接下來比較像 `延續`, `震盪整理`, 還是 `轉弱`
- 若延續，最可能靠什麼延續
- 若失效，先壞掉的是哪個條件

### 5.2 趨勢分析的五層流程

#### A. 先看大盤 Regime

先判斷：

- 指數是否站在上升趨勢中
- 市場廣度是否支持
- 高風險事件是否逼近
- 目前是 `追價盤` 還是 `只適合低接最強股`

這一層建議延用現有 `macro posture`。

#### B. 再看個股所處階段

建議把每檔標的分成以下趨勢階段：

1. `Emerging`
   - 剛脫離整理區，開始轉強
2. `Confirmed`
   - 已站穩關鍵均線，趨勢明確
3. `Extended`
   - 離均線過遠，趨勢仍強但追價風險升高
4. `Constructive Pullback`
   - 強勢趨勢中拉回，等待二次發動
5. `Broken`
   - 跌破關鍵結構，原本強勢論述失效

#### C. 看驅動因子是什麼

未來趨勢能不能走，通常要靠驅動因子，不只是圖形本身。

建議判讀來源：

- 台股：
  - `TWSE 投資資訊中心`
  - `重大訊息`
  - `財務報告`
  - `法說會`
  - 法人交易分析
- 美股：
  - `10-K / 10-Q / 8-K`
  - 財報法說
  - guidance 調整

#### D. 寫成情境卡，而不是一句結論

每檔標的建議產出三個情境：

- `Bull case`
  - 例如：站穩前高、量能續增、事件結果優於預期
- `Base case`
  - 例如：高檔整理、沿 MA20 橫盤
- `Bear case`
  - 例如：跌破 MA20、量能失真、事件落空

每個情境都應附：

- `觸發條件`
- `確認條件`
- `失效條件`

#### E. 最後才給操作結論

操作結論不應只有 `可買 / 不可買`，建議改成：

- `可追突破`
- `只等拉回`
- `只能觀察`
- `暫不碰`

---

## 6. 建議新增的趨勢欄位

### 6.1 現有欄位可直接沿用

- `close`
- `change_pct`
- `volume_ratio`
- `near_52w_high_pct`
- `ma_alignment`
- `chip_bias`
- `next_event`
- `macro_adjustment`
- `decision_card`

### 6.2 第一版應補的欄位

- `relative_strength_20d`
- `relative_strength_60d`
- `sector_relative_rank`
- `pullback_resilience`
- `trend_stage`
- `trend_age_bars`
- `breakout_status`
  - `none / fresh_breakout / retest / failed_breakout`
- `pullback_quality`
  - `constructive / neutral / weak`
- `distance_from_ma20_pct`
- `distance_from_ma50_pct`
- `volume_confirmation`
  - `confirmed / normal / weak`
- `setup_type`
- `is_tradeable`
- `tradability_flags`
- `avg_trade_value_20d`
- `avg_volume_20d`
- `days_since_listing`
- `trend_risk_flags`
  - 例如：
    - `extended`
    - `event_risk`
    - `low_liquidity`
    - `distribution_day`

### 6.3 第二版可再補的欄位

- `adx`
- `rsi_state`
- `macd_state`
- `earnings_revision_bias`
- `revenue_acceleration`
- `leadership_cluster`
  - 是否屬於當前主流族群

---

## 7. UI / UX 規劃

### 7.1 Screener Workspace 不要只顯示分數，還要顯示「強在哪」

目前結果列已經有 `score`、`verdict`、`decision card`，這很好，但還不夠聚焦在強勢股判讀。

建議新增顯示：

- `Trend Stage`
- `RS 20D / 60D`
- `Volume Confirmation`
- `Breakout Status`
- `Risk Flags`

### 7.2 結果列的推薦呈現

每列除了目前的 `score` 外，再多一組 `Strength Strip`：

- `Regime`
- `Structure`
- `RS`
- `Volume`
- `Confirmation`
- `Risk`

讓使用者一眼看出：

- 是哪一層在撐這檔股票
- 哪一層最弱

### 7.3 決策卡應升級成「趨勢卡」

建議把目前的 `決策卡` 延伸成：

- `現在為什麼強`
- `接下來最可能怎麼走`
- `什麼情況算破壞`

建議區塊：

- `趨勢結構`
- `相對強弱`
- `量能確認`
- `事件 / 籌碼`
- `市場風險`
- `Bull / Base / Bear 三情境`

### 7.4 Market Overview 的入口調整

目前 `盤中強勢股` 與 `策略掃描結果` 已經有入口，建議再加一層語意區分：

- `今日最強動能`
  - 偏即時排行
- `可延續的強勢股`
  - 偏可交易的高品質候選

避免使用者把 `瞬間飆漲` 和 `可延續趨勢` 混為一談。

---

## 8. 後端與資料規劃

### 8.1 第一版建議延用現有 Screener Engine

不建議另外寫一套 `strong stock engine`，而是直接擴充現有：

- `backend/screener_engine.py`

原因：

- 目前它已經有：
  - filters normalization
  - setup quality
  - macro adjustment
  - decision card
- 這代表產品抽象其實已經對了，只是定義還不夠完整

### 8.2 建議新增的後端計算模組

可逐步拆成：

- `tradability_filters.py`
  - 算 `is_tradeable` 與 `tradability_flags`
- `strength_metrics.py`
  - 算 `RS_20D` / `RS_60D` / `pullback resilience`
- `trend_classifier.py`
  - 判斷 `trend_stage`
- `setup_classifier.py`
  - 判斷 `setup_type`
- `trend_scenarios.py`
  - 生成 `Bull / Base / Bear` 情境

第一版也可以先不拆檔，但邏輯上建議先分層。

### 8.3 正式資料落地

因為本專案已有「正式資料必須可由本地資料庫重建」原則，所以建議至少落地以下 derived data：

- `ticker_relative_strength_daily`
- `ticker_trend_state_daily`
- `ticker_strength_snapshot_daily`

建議欄位至少包含：

- `ticker`
- `market`
- `trade_date`
- `is_tradeable`
- `tradability_flags_json`
- `strength_score`
- `setup_type`
- `trend_stage`
- `rs_20d`
- `rs_60d`
- `sector_relative_rank`
- `pullback_resilience`
- `volume_confirmation`
- `breakout_status`
- `risk_flags_json`
- `source_snapshot_at`

### 8.4 API 建議

第一版優先走「擴充既有 API」：

- `POST /api/screener/run`
  - 回傳欄位新增：
    - `is_tradeable`
    - `tradability_flags`
    - `strength_score`
    - `setup_type`
    - `trend_stage`
    - `relative_strength_20d`
    - `relative_strength_60d`
    - `sector_relative_rank`
    - `pullback_resilience`
    - `volume_confirmation`
    - `breakout_status`

第二版可再加：

- `GET /api/strength/rankings`
  - 提供每日強勢股排名
- `GET /api/strength/{ticker}/trend-analysis`
  - 提供單一標的完整趨勢卡

---

## 9. 資料來源建議

### 9.1 台股

建議優先整合 / 沿用：

- `OHLCV`
- `TWSE 投資資訊中心`
  - 重大訊息
  - 財務報告
  - 法說會
  - 法人交易分析
- `台股籌碼歷史`
- `TAIFEX 三大法人`
  - 作為大盤風向輔助，不宜直接當單一個股買點依據

### 9.2 美股

建議優先整合 / 沿用：

- `OHLCV`
- `SEC 10-K / 10-Q / 8-K`
- 財報事件
- 公司 guidance 與重大公告

### 9.3 技術面使用原則

第一版技術面建議遵守：

- `均線` 用來看趨勢方向與結構
- `MACD` 用來做趨勢動能確認，不單獨作為買賣點
- `RSI` 用來看短週期過熱 / 過冷，不應脫離趨勢背景單獨使用
- `量能` 用來確認突破是否可信

### 9.4 As-of Data Rules

如果這套系統未來要拿來驗證 edge，而不是只做事後分析，則第一版就應該寫入資料可用時間規則。

每一筆事件 / 基本面 / 籌碼 / 公告資料，建議至少保存：

- `source_published_at`
- `source_effective_date`
- `ingested_at`
- `usable_from`

策略與驗證系統只能使用：

- `usable_from <= decision_timestamp`

的資料，不可直接使用「資料對應日期」作為可用時間。

### 9.5 保守的可用時間預設

若缺少精確時間戳，第一版建議採保守規則：

- `只有日期、沒有時間` 的資料
  - 一律從 `下一個交易時段` 才可用
- `日終籌碼 / 日終財務欄位`
  - 一律視為 `下一交易日` 才可用
- `盤後公布的公告 / 財報`
  - 一律視為 `下一交易日 regular session` 才可用
- `盤前已公布且時間戳明確`
  - 才允許在當日 regular session 使用

### 9.6 台股與美股建議的預設規則

台股第一版建議：

- `法人買賣超`
  - 預設 `下一交易日` 才納入策略判斷
- `重大訊息 / 財報 / 法說`
  - 若無精確盤中可用時間，預設 `下一交易日`

美股第一版建議：

- `盤前公告`
  - 若時間戳明確且早於 regular session open，當日可用
- `盤後公告`
  - 預設下一 regular session 才可用
- `SEC filing`
  - 若無法保證處理延遲與取得時間，預設下一 bar 或下一 session 使用

### 9.7 這一層的目的

這些規則不是為了保守而保守，而是為了避免：

- look-ahead bias
- 回測漂亮、實盤失真
- 事件反應速度被錯誤高估

---

## 10. AI API 輔助分析規劃

### 10.1 是否需要引入 AI API

建議：

- `MVP 不把 AI 放進核心選股引擎`
- `第二階段再引入 AI 作為研究輔助層`

原因是：

- 強勢股搜尋的核心必須 `可回測`
- 核心評分必須 `可解釋`
- 核心結果必須 `可重建`
- 若一開始把 ranking 與分數交給 AI，會讓驗證、除錯與歷史重跑都變困難

因此本規劃建議把架構分成兩層：

- `Deterministic Layer`
  - 用規則、指標、相對強弱、事件欄位與市場 regime 算出 `strength_score`
- `AI Assistance Layer`
  - 只負責摘要、解釋、歸因、情境整理與自然語言互動

### 10.2 AI 適合負責的工作

AI 最適合處理的是 `非結構化資訊` 與 `研究輔助輸出`。

第一批建議導入的能力：

- `事件摘要`
  - 整理重大訊息、法說會、財報重點、SEC 文件的核心變化
- `催化因子 / 風險點抽取`
  - 從文本中整理出上修、下修、展望、法規、供應鏈、產品週期等因素
- `趨勢情境卡`
  - 根據既有結構化特徵，生成 `Bull / Base / Bear`
- `決策卡文字化`
  - 把分數、欄位與條件轉成可閱讀的中文說明
- `自然語言查詢`
  - 讓使用者用中文描述想找的型態，由系統轉成篩選條件
- `研究歸因`
  - 幫助使用者理解這檔股票強在技術、族群、事件，還是籌碼

### 10.3 不建議交給 AI 的工作

以下工作不建議交給 AI 當核心邏輯：

- 直接決定 `strength_score`
- 直接決定每日 `ranking`
- 沒有明確引用來源就生成 `目標價`
- 直接生成 `買 / 賣 / 加碼 / 停損` 指令
- 在沒有 deterministic guardrail 的情況下自動建立警報或下單

換句話說，AI 應該回答：

- `為什麼這檔強`
- `接下來要看什麼`
- `有哪些文本催化因子與風險`

而不是直接回答：

- `這檔一定會漲`
- `今天就該買`

### 10.4 AI 輔助架構建議

建議資料流如下：

1. `Deterministic Engine`
   - 先產出 `strength_score`、`trend_stage`、`relative_strength`、`risk_flags`
2. `Retriever`
   - 取出與該標的相關的公告、法說、財報、重大訊息、新聞摘要
3. `AI Analysis Service`
   - 用固定 schema 產出研究輔助結果
4. `Persistence`
   - 將 AI 分析結果與來源版本正式落地
5. `UI`
   - 在 `ScreenerWorkspace` / `Ticker Detail` 顯示趨勢卡與事件摘要

建議 AI 的輸入不要直接丟整個畫面，而是只餵兩種資料：

- `結構化特徵 JSON`
- `檢索後的原始文本片段`

### 10.5 建議的 AI 輸入

AI request 建議包含：

- `ticker`
- `market`
- `trade_date`
- `strength_score`
- `trend_stage`
- `relative_strength_20d`
- `relative_strength_60d`
- `volume_confirmation`
- `breakout_status`
- `risk_flags`
- `chip_bias`
- `next_event`
- `selected_source_documents`

這樣 AI 的角色會更像：

- `高階研究整理器`

而不是：

- `黑箱選股器`

### 10.6 建議的 AI 輸出 Schema

建議 AI 一律使用固定 schema 回傳，避免自由文字難以驗證。

第一版建議欄位：

- `trend_summary`
- `primary_drivers`
- `catalysts`
- `risks`
- `bull_case`
- `base_case`
- `bear_case`
- `invalidations`
- `confidence_label`
- `source_refs`
- `generated_at`
- `model_version`

其中每個情境至少應包含：

- `summary`
- `trigger`
- `confirmation`
- `failure_condition`

### 10.7 持久化建議

若導入 AI API，正式結果也必須本地落地。

建議新增：

- `ticker_ai_analysis_runs`
- `ticker_ai_event_digests`

建議欄位：

- `ticker`
- `market`
- `trade_date`
- `analysis_type`
- `input_features_json`
- `retrieved_sources_json`
- `output_json`
- `model_name`
- `model_snapshot`
- `prompt_version`
- `created_at`

這樣未來才能做到：

- 重播同一天的分析
- 比較 prompt 版本差異
- 檢查 hallucination 或來源錯誤

### 10.8 OpenAI API 導入建議

若採用 OpenAI API，建議優先用：

- `Responses API`
  - 作為主要互動入口
- `Structured Outputs`
  - 確保回傳 JSON 穩定
- `Batch API`
  - 用於每日大量摘要與背景分析任務

模型分工建議：

- `gpt-5.4-nano`
  - 適合高量分類、抽取、標籤化、初步 ranking 輔助
- `gpt-5.4-mini`
  - 適合事件摘要、趨勢卡、情境卡、研究歸因
- `gpt-5.4`
  - 只保留給少量高價值深度分析，不建議全市場批次使用

### 10.9 成本與延遲控管

AI 層若沒有成本治理，很容易在全市場批次上失控。

建議：

- 只有 `Priority Strong` 與少數 `Watch` 標的才跑完整 AI 分析
- `Wait` 標的不跑深度分析
- 事件摘要採 `批次排程`
- 同一份來源文本要做 `快取`
- 相同輸入與 prompt version 盡量重用結果

### 10.10 AI 品質與安全要求

AI 輔助結果必須符合以下要求：

- 每個重要結論都能回溯到 `source_refs`
- 若來源不足，必須明確標示 `資料不足`
- 不得把摘要包裝成確定性預測
- 不得生成未被來源支持的目標價或保證性語句

建議 UI 顯示文案：

- `AI 研究摘要`
- `依據目前資料整理，不構成保證性預測`

### 10.11 對本規劃的結論

因此本功能的 AI 位置建議是：

- `不是核心選股引擎`
- `而是第二層研究輔助服務`

這樣的好處是：

- 核心分數仍可回測
- AI 只處理它最擅長的文本整理與情境生成
- 使用者可以同時看到 `硬指標` 與 `研究摘要`

---

## 11. 驗證方式

### 11.1 不用問「神不神」，而要問「有沒有統計優勢」

這套規劃的驗證方式不應是主觀覺得準，而應驗證：

- 分數最高的標的，未來 `5 / 10 / 20 / 60` 日表現是否優於市場
- `Priority Strong` 的表現是否優於 `Watch`
- `Constructive Pullback` 是否比 `Extended` 有更佳風險報酬比
- `Bull case` 觸發後的延續率是否夠高

### 11.2 建議驗證指標

- 命中率
- 平均報酬
- 中位數報酬
- 最大不利波動 `MAE`
- 最大有利波動 `MFE`
- 假突破比率
- 事件前後表現分層

### 11.3 建議驗證切片

- 市場別：`TW / US`
- 環境別：`offensive / selective / defensive`
- 標的型態：
  - fresh breakout
  - constructive pullback
  - defensive strong

### 11.4 交易化驗證規格

從交易員角度，不能只驗證「高分股後面有沒有漲」，還要驗證「這些 setup 能不能交易」。

因此建議把驗證分兩層：

- `Ranking Validation`
  - 驗證高分股未來表現是否優於低分股
- `Trade Simulation Validation`
  - 驗證特定 setup 的進出場規則是否具備實際 edge

### 11.5 第一版建議先建立標準進出場模板

至少應有以下標準模板：

- `fresh_breakout_entry_template`
- `constructive_pullback_entry_template`
- `defensive_strong_watch_template`

建議第一版先不要讓每種 setup 都自由發揮，而是統一定義：

- `signal_timestamp`
- `entry_rule`
- `entry_price_assumption`
- `initial_stop_rule`
- `trail_stop_rule`
- `time_stop_rule`
- `max_holding_days`
- `fee_model`
- `slippage_model`

### 11.6 建議的模板示例

例如：

- `fresh_breakout`
  - entry:
    - 突破成立後 `next bar open` 或 `breakout price + slippage`
  - stop:
    - 訊號 bar low / 區間下沿 / 固定 ATR 倍數
- `constructive_pullback`
  - entry:
    - 回踩後重新站回訊號位時進場
  - stop:
    - 跌破拉回支撐位或 `MA20`
- `extended_leader`
  - 不一定是立即可買 setup
  - 可列入 observation，不一定納入第一版交易化驗證

### 11.7 交易化驗證應增加的指標

除了原本的未來報酬與 `MAE/MFE` 外，建議新增：

- expectancy
- profit factor
- payoff ratio
- average holding days
- turnover
- slippage sensitivity
- gap risk impact
- regime-specific expectancy

### 11.8 驗證切片要加入 Setup Type 與流動性

建議額外切：

- `setup_type`
- `tradability bucket`
- `market cap / liquidity bucket`
- `event proximity`
- `day 0 breakout` vs `day 1 follow-through`

### 11.9 何時才算真的達到目的

這份功能真正達標，不是只要能列出高分標的，而是要同時滿足：

- 高分標的在統計上更強
- 特定 setup 經過交易化驗證後仍有正向 expectancy
- 在保守滑價與成本下，結果仍不崩潰
- 不同 regime 下知道哪些 setup 有效、哪些無效

這樣它才不是「好看的排行榜」，而是接近可執行的研究工具。

---

## 12. 實作階段建議

### Phase A：定義強勢股 v1

目標：

- 先把「強勢股」從概念變成正式欄位與分數
- `此階段不引入 AI 到核心評分`

內容：

- 定義 `Tradable Universe`
- 擴充 `screener_engine`
- 新增 `is_tradeable`
- 新增 `setup_type`
- 新增 `relative_strength_20d / 60d`
- 新增 `sector_relative_rank`
- 新增 `pullback_resilience`
- 新增 `trend_stage`
- 新增 `risk_flags`
- 補 `as-of data rules`
- 補 `feature formula spec`
- UI 顯示 `Strength Strip`

### Phase B：導入 AI 研究輔助層

目標：

- 在不破壞核心 ranking 可回測性的前提下，補上文本理解與情境整理能力

內容：

- 事件摘要
- 催化因子 / 風險點抽取
- 新增 `bull / base / bear`
- 決策卡升級成 `AI 輔助趨勢卡`
- 引入固定 JSON schema 與 `source_refs`

### Phase C：日級別落地、AI 結果保存與驗證

目標：

- 讓系統能回答「這套方法是否真的有效」

內容：

- 落地每日強勢快照
- 建立 ranking history
- 落地 AI analysis runs
- 加入績效驗證報表
- 加入 setup-based trade simulation validation
- 加入 AI 結果的來源檢查與品質評估

### Phase D：與警報 / 日誌 / 回測整合

目標：

- 讓強勢股搜尋從看板功能升級成完整工作流

內容：

- 強勢股轉警報
- 強勢股轉觀察池
- 強勢股轉交易日誌 seed
- 與回測模組對接驗證

---

## 13. 驗收標準

第一版完成後，系統至少應能回答以下問題：

- 哪些股票因為流動性、資料時間或商品型態問題，根本不應列入強勢股排名
- 今天有哪些不是只有漲、而是結構真的強的股票
- 這些股票強在：
  - 趨勢
  - 量能
  - 相對強弱
  - 籌碼 / 事件
  - 市場順風
- 這些股票目前屬於：
  - 剛起漲
  - 趨勢延續
  - 高檔過熱
  - 健康拉回
  - 趨勢破壞
- 這些股票屬於哪一種 `setup_type`
- 接下來應該：
  - 追突破
  - 等拉回
  - 只觀察
  - 暫不碰

---

## 14. 最終建議

這份功能的關鍵，不是再多加幾個技術指標，而是把系統的回答從：

- `這檔今天有漲`

升級成：

- `這檔是高品質強勢股`
- `它目前在趨勢哪個階段`
- `未來最可能的延續條件是什麼`
- `失效時該看哪個警訊`

因此本規劃最推薦的切入點是：

1. 先擴充現有 `Screener Engine`
2. 先把 `Tradable Universe + Feature Formula Spec + As-of Rules` 補齊
3. 再把 `相對強弱 + 趨勢階段 + 風險旗標 + setup_type` 補齊
4. 再把 AI 放進 `研究輔助層`
5. 最後把決策卡升級成 `可引用來源的趨勢情境卡`

這樣做的好處是：

- 與現有架構相容
- 可快速進入第一版驗收
- 核心 ranking 仍能回測與重建
- 不會因 look-ahead bias 或低流動性標的而高估 edge
- 後續也能直接銜接警報、回測、交易日誌與真正的研究工作流
