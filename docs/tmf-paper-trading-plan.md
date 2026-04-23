# 微型臺指期貨（TMF）模擬交易規劃 v1.2

**產出時間**：2026-04-23  
**規劃目的**：先以「微型臺指期貨（TMF）」建立一套可實際運作的模擬交易（paper trading）閉環，驗證策略、風控、委託狀態流轉、資金控管與日內/短波段交易流程，之後再銜接富邦 API 真實帳戶。

**本次更新重點**：

- 盤中判斷資料源明確收斂為 `富邦 API futopt quote / intraday candles`
- 第一版即時判斷的核心條件調整為 `TX + TMF`，`TWII` 改列為日盤輔助參考，不列入 MVP 必要即時條件
- 補入一版可以直接落成程式的 `MVP 訊號草案`
- 補入 `TMF alias / 契約解析 / 富邦 SDK 依賴` 的實作前注意事項

---

## 1. 規劃結論

本功能第一版建議採用以下原則：

- `只下單商品`：`TMF`（微型臺指期貨）近月契約
- `主要方向參考`：`TX`（臺股期貨）近月契約
- `盤中判斷資料源`：`富邦 API` 的 `TX / TMF futopt quote + 1m candles`
- `現貨參考`：`TWII` / 加權指數，保留為日盤輔助欄位，不列入 MVP 必要即時條件
- `次要觀察`：`MTX`（小型臺指期貨）暫不納入第一版必要條件
- `交易風格`：以 `當日沖銷` 為主，`day_only` 為第一版核心驗收；`overnight_allowed` 僅保留實驗開關
- `執行環境`：先做 `paper trading`，不直接接真實下單
- `第一版必要補件`：`保守成交模型`、`正式成本模型`、`連續契約/轉倉規則`、`隔夜風險規則`

換句話說，第一版的核心不是「做很多商品」，而是把一個商品的交易閉環做好：

`行情 -> 訊號 -> 風控 -> 模擬委託 -> 模擬成交 -> 部位/損益更新 -> 日誌/檢討`

---

## 2. 商品定位與關係

### 2.1 TMF、MTX、TX 的關係

`TMF`、`MTX`、`TX` 都是追蹤同一個標的指數：

- `臺灣證券交易所發行量加權股價指數`

差異不在於「追蹤不同東西」，而在於：

- 契約乘數不同
- 每點損益不同
- 所需保證金不同
- 流動性與參與者結構不同

### 2.2 官方契約規格重點

- `TX`
  - 英文代碼：`TX`
  - 契約價值：指數乘上 `新臺幣 200 元`
  - 最小升降單位：1 點 = `200 元`
- `MTX`
  - 英文代碼：`MTX`
  - 契約價值：指數乘上 `新臺幣 50 元`
  - 最小升降單位：1 點 = `50 元`
- `TMF`
  - 英文代碼：`TMF`
  - 契約價值：指數乘上 `新臺幣 10 元`
  - 最小升降單位：1 點 = `10 元`

### 2.3 為什麼第一版執行商品選 TMF

- 未來真實帳戶主要交易 TMF
- 契約規模較小，適合先驗證風控與加減碼邏輯
- 模擬時比較容易用較細的口數階梯做資金管理
- 即使未來策略訊號主要參考 TX，實際成交與持倉管理仍可落在 TMF

---

## 3. 第一版是否需要同時納入 TX、MTX、TWII

### 3.1 結論

第一版即時判斷核心應納入 `TX` 與 `TMF`；`TWII` 保留為日盤輔助參考，但不列入 MVP 必要即時條件；`MTX` 仍不列入第一版必要條件。

### 3.2 建議的判斷分層

建議把判斷條件分成三層：

#### A. 方向層

用來回答「現在應該偏多、偏空，還是觀望」。

建議參考：

- `TX` 趨勢方向
- `TX` 結構強弱
- `TWII` 日盤現貨相對位置

#### B. 觸發層

用來回答「現在要不要進場」。

建議以 `TMF` 自己的：

- `1m` / `5m` K 棒
- breakout / pullback / reversal 條件
- 短週期成交量或波動條件

#### C. 過濾層

用來回答「即使有訊號，現在能不能做」。

建議包含：

- 時段限制
- 接近收盤是否禁止新倉
- 接近結算日是否禁止新倉
- quote 是否過舊
- 波動是否過大
- 期現貨偏離是否異常
- `TX / TMF` 跨商品時間戳是否超過可接受差距

### 3.3 為什麼 TX 要放進核心條件

理由：

- TX 通常是臺指系列中更適合觀察主方向與價格發現的商品
- 用 TX 看大方向，再用 TMF 做執行，較符合未來真實交易習慣
- 可降低只看 TMF 時受到較小級別噪音干擾的風險

### 3.4 為什麼 TWII 保留為日盤輔助參考，但不列入 MVP 必要即時條件

理由：

- TWII 是現貨市場的指數錨點
- 可用來判斷期貨是否過度領先或貼水/升水異常
- 但夜盤時 TWII 並非即時交易商品，因此不能在夜盤把 TWII 當成主要觸發條件
- 第一版盤中 runtime 若以富邦 API 的期貨資料為主，直接用 `TX / TMF` 可得到同源、時間戳更一致的 futopt 資料
- 若把 `TWII` 納入硬性即時條件，反而會增加跨來源資料對齊、延遲判斷與 debug 複雜度

建議：

- `一般交易時段 MVP`：TX + TMF
- `一般交易時段進階版`：TX + TMF，再加 TWII 作輔助濾網或檢討欄位
- `盤後交易時段`：TX / TMF 為主，TWII 只作前一日或白天收盤參考，不作即時觸發

### 3.5 為什麼 MTX 暫時不列為 MVP 必要條件

理由：

- MTX 與 TMF 資訊重疊度高
- 第一版先加入的邊際價值有限
- 若同時監看太多近似商品，反而會增加條件設計與除錯複雜度

第二版可再評估加入：

- `TX - MTX - TMF` 之間的同步性
- `成交量/未平倉量/價差` 異常
- `主力商品領先` 的盤中結構判斷

---

## 4. 當沖減收保證金是什麼

### 4.1 白話定義

「當沖減收保證金」的意思是：

如果你做的是期交所規定可適用的期貨契約，而且這筆交易是 `同一交易日內開倉並平倉` 的當日沖銷交易，則期貨商對這筆交易收取的保證金，可以依規定比一般留倉交易少。

它不是：

- 免保證金
- 隨便都能用
- 任何商品都適用
- 隔夜還能沿用減收後金額

### 4.2 更直白的理解方式

一般留倉交易代表你可能把部位帶到下一個交易時段，因此風險較大，所以通常要收 `完整保證金`。  
但如果是當天進、當天出，理論上的持有風險時間較短，因此期交所對特定商品提供 `減收保證金` 機制。

### 4.3 重要限制

根據期交所「期貨契約當日沖銷交易減收保證金作業」資料，適用商品是：

- `TX`
- `TE`
- `TF`
- `MTX`

且限：

- `最近 2 個到期月份契約`

保證金收取標準是：

- 依一般交易保證金金額按 `50%` 減收後計算

這代表：

- `TMF` 目前 **不在該適用清單內**
- 所以微型臺指期貨模擬交易第一版，不應預設可以使用當沖減收保證金

### 4.4 對模擬系統的設計意義

TMF 第一版建議一律採：

- `完整原始保證金` 模型

不要先做：

- `TMF 可減收保證金`
- `日內保證金 / 留倉保證金動態切換`

原因：

- 比較保守
- 比較接近真實風險控管
- 可避免因券商規則差異造成模擬過度樂觀

第二版若有需要，再加：

- 商品別是否適用
- 是否為同日開平倉
- 是否在可適用到期月份
- 券商自訂風控覆蓋

---

## 5. 第一版資金與口數控管是否必要

結論：`一定要，而且要同時設定資金上限與口數上限。`

### 5.1 不夠只設最大口數

如果只設：

- `max_contracts = 10`

但沒有設：

- 初始資金
- 保證金占用上限
- 單筆停損風險
- 單日最大虧損

那模擬結果會非常失真，因為系統可能在資金不合理的情況下仍持續放大部位。

### 5.2 第一版建議至少要有的風控欄位

- `starting_equity`
  - 模擬帳戶初始權益
- `max_contracts_hard`
  - 硬上限口數
- `max_margin_usage_pct`
  - 最多允許使用多少比例的權益去占用保證金
- `risk_per_trade_pct`
  - 單筆交易最多可承受多少帳戶風險
- `daily_loss_limit_pct`
  - 單日虧損達多少比例後停止交易
- `max_open_loss_base`
  - 單筆持倉浮虧超過多少金額就強制處理
- `max_drawdown_pct`
  - 自高點回撤達多少比例後停機
- `cooldown_bars`
  - 連續虧損後冷卻幾根 K 棒
- `flatten_before_close_minutes`
  - 收盤前幾分鐘必須平倉
- `holding_policy`
  - `day_only` 或 `overnight_allowed`

### 5.3 建議的下單口數計算方式

建議每次下單時，不是直接看「想下幾口」，而是取以下三種上限的最小值：

```text
可下口數 =
min(
  硬上限口數,
  保證金可承受口數,
  停損風險可承受口數
)
```

進一步可寫成：

```text
allow_qty = floor(min(
  max_contracts_hard,
  available_equity * max_margin_usage_pct / initial_margin_per_contract,
  account_equity * risk_per_trade_pct / (stop_loss_points * point_value + fee + slippage)
))
```

其中：

- `point_value` 對 TMF 為 `10`
- `initial_margin_per_contract` 不應寫死，應由期交所/券商規則表更新

### 5.4 第一版成本模型也必須正式存在

若要用 paper trading 驗證策略優勢，而不只是驗證流程有沒有跑通，則第一版就必須有正式成本模型。

建議至少納入：

- `broker_fee_per_side`
- `exchange_fee_per_side`
- `futures_tax_per_side`
- `slippage_ticks_day`
- `slippage_ticks_night`
- `cost_model_version`

系統在計算：

- 可下口數
- 預估單筆風險
- 已實現損益
- 回放績效

時，都應使用同一套成本模型，不得只在報表端事後扣除。

### 5.5 成本模型的第一版保守原則

建議：

- `日盤市價單`：至少預設 `1 tick` 滑價
- `夜盤市價單`：至少預設比日盤更保守的滑價
- `限價單`：若只是價格碰到，不應一律視為成交
- `停損單`：應用最不利方向的滑價估算

第一版寧可偏保守，也不要讓模擬績效過度樂觀。

---

## 6. 第一版交易與風控規則建議

### 6.1 商品、契約與盤中資料來源

- 交易商品固定為 `TMF`
- 策略看的商品代號可用 `TMF`
- 系統實際下單需解析成 `實際近月契約`
- 每筆委託與成交都要同時保存：
  - `requested_symbol`
  - `resolved_symbol`
- 第一版盤中判斷資料直接使用：
  - `富邦 API futopt quote`
  - `富邦 API futopt intraday candles`
- 方向商品建議查 `TXF` 並解析為近月，例如：`TXFE6`
- 執行商品建議查 `TMF` 並解析為近月，例如：`TMFE6`
- `TWII` 若要納入，只能視為額外參考資料源，不應阻塞 MVP 即時訊號

### 6.2 交易時段

依目前 TMF 商品規格，建議系統內明確分成兩個 session：

- `day_session`
  - `08:45 ~ 13:45`
- `night_session`
  - `15:00 ~ 次日 05:00`

另外必須注意：

- `到期月份契約最後交易日` 的一般交易時段到 `13:30`
- `到期月份契約最後交易日無盤後交易時段`

第一版建議支援兩種模式：

- `day_session_only`
- `day_and_night`

### 6.3 持倉政策

第一版建議直接做成開關，但驗收優先順序要明確：

- `day_only`
  - 收盤前固定平倉
  - `第一版核心驗收模式`
- `overnight_allowed`
  - 可保留到夜盤或下一交易日
  - `僅列為實驗模式，不作第一版必要驗收`

### 6.4 接近收盤的規則

當 `holding_policy = day_only` 時，建議：

- 收盤前 `N` 分鐘禁止新倉
- 收盤前 `M` 分鐘強制平倉

### 6.5 接近結算日規則

建議：

- 到期日當天不開新倉
- 到期日前 1~2 個交易日可設定只允許平倉、不允許開新倉
- 需要保留 `front_month_auto_roll` 的設計空間，但第一版先不自動轉倉

### 6.6 近月契約、連續契約與轉倉研究規則

這一塊不應只寫「解析近月契約」，還必須分清楚：

- `execution contract`
  - 真正模擬成交的實際契約
- `research continuous series`
  - 研究或長區間指標使用的連續契約序列

第一版建議規則：

- `所有實際成交與損益` 一律以 `execution contract` 為準
- `回放與績效統計` 不得把不同月份契約直接拼接成單一成交序列
- 若要做跨月研究，必須建立獨立的 `continuous series`，並保存 roll metadata

研究用連續契約建議至少保存：

- `from_symbol`
- `to_symbol`
- `roll_timestamp`
- `roll_reason`

第一版建議的 research roll 邏輯：

- 若次月契約流動性已明顯超過近月，則切到次月
- 若未出現明顯主力轉移，也應在 `最後交易日前 2 個交易日` 前完成研究序列切換

### 6.7 夜盤規則

若支援夜盤，建議額外檢查：

- quote 是否過舊
- 成交量是否低於門檻
- 夜盤是否禁止逆勢加碼
- 夜盤是否降低最大口數
- 夜盤是否採用較保守滑價
- 夜盤是否限制某些突破型策略追價

### 6.8 隔夜風險規則

若開啟 `overnight_allowed`，建議額外強制以下規則：

- 隔夜持倉使用較保守的 `max_contracts` 上限
- 隔夜持倉使用較保守的 `max_margin_usage_pct`
- 禁止對虧損中的隔夜部位逆勢攤平
- 若進入最後交易日前一交易日，原則上只允許平倉，不允許開新隔夜倉
- 若遇最後交易日，必須在一般交易時段結束前完成平倉
- 若遭遇跳空、停損失效或漲跌幅限制造成無法即時出場，必須紀錄為 `risk_event`

### 6.9 日盤 / 夜盤風控與資料時間對齊

第一版不應把日盤與夜盤當成同一個微結構市場。

建議：

- 日盤與夜盤分開設定：
  - `max_qty`
  - `slippage`
  - `volume threshold`
  - `trigger parameters`
- 每次訊號都保存：
  - `tmf_quote_ts`
  - `tx_quote_ts`
  - `twii_quote_ts`
  - `quote_age_ms`
- 夜盤若 `TWII` 非即時，應自動降級為 `參考欄位`，不可當作即時確認條件
- 若跨商品時間戳超過可接受差距，訊號應直接失效，而不是硬判定偏多或偏空

---

## 7. 第一版訊號架構建議

### 7.1 建議架構

#### Layer 1：大方向

可用：

- TX 5m / 15m 趨勢
- 日內 VWAP 上下
- 前高/前低結構

#### Layer 2：TMF 進場觸發

可用：

- 突破前高/前低
- pullback 後再突破
- 開盤區間突破
- 均線結構轉折

#### Layer 3：禁止條件

可用：

- 連續虧損後冷卻
- 已達單日虧損上限
- 保證金占用超標
- 距離收盤過近
- 資料延遲
- 價差異常

### 7.2 盤中最小可用策略草案

這一版不是最終策略，只是第一版建議先落成、可直接被程式化驗證的最小規則。

#### A. 資料頻率

- `TX`：使用富邦 `1m candles`
- `TMF`：使用富邦 `1m candles`
- `TX 5m / 15m`：由同一份 `TX 1m` 在系統內聚合
- `quote freshness`：`TX / TMF` 任一時間戳過舊就直接失效

#### B. 方向判斷

- `short bias`
  - `TX 1m close < session VWAP`
  - `TX 最新 5m close < 前一根 5m close`
  - `TX 最新 15m close < 前一根 15m close`
- `long bias`
  - `TX 1m close > session VWAP`
  - `TX 最新 5m close > 前一根 5m close`
  - `TX 最新 15m close > 前一根 15m close`
- 若上述條件不完整成立，則為 `neutral`

#### C. 進場觸發

- `short entry`
  - 僅在 `short bias` 下考慮
  - `TMF 1m close` 跌破前 `5` 根 `1m` 的最低點
- `long entry`
  - 僅在 `long bias` 下考慮
  - `TMF 1m close` 突破前 `5` 根 `1m` 的最高點
- 第一版先不把 `TWII` 當成必須同步成立的硬條件

#### D. 進出場模型

- 進場價：`下一根 1m open + / - 預設滑價`
- 預設滑價：日盤先用 `1 tick`
- 停損：先用 `固定 60 點`
- 停利：先用 `固定 120 點`
- 停損後：冷卻 `3` 根 `1m`
- `day_only`：收盤前禁止新倉並強制平倉

#### E. 第一版先不要加進來的條件

- `TWII` 硬性同步確認
- `MTX` 同步性條件
- 複雜 pullback 多段結構
- 多套 regime 切換
- 動態停利參數自動調整

### 7.3 第一版不要做得太複雜

第一版不建議一開始就塞入：

- 太多跨商品條件
- 太多多空例外
- 太多盤中 regime 切換

建議先把最小可用策略做穩：

- `TX 決定方向`
- `TMF 觸發進場`
- `固定停損 + 固定停利/移動停損`
- `日內強制平倉`

### 7.4 但參數不能把日盤與夜盤混成同一套

即使第一版策略邏輯保持簡單，也建議至少把以下參數分開：

- `day_open_profile`
- `day_regular_profile`
- `night_profile`

每個 profile 至少可調：

- `stop_loss_points`
- `take_profit_points`
- `trail_stop_points`
- `max_qty`
- `volume_threshold`
- `slippage_assumption`

否則看似回測穩定，實際上只是把不同市場結構混在一起平均掉。

---

## 8. 系統架構建議

### 8.1 核心模組

- `Futures Strategy Engine`
  - 產生 `buy / sell / close / reverse`
- `Fubon Futopt Market Data Adapter`
  - 封裝 `quote / intraday candles / contract resolution`
- `Futures Risk Engine`
  - 檢查資金、口數、單日虧損、時段、結算日、資料新鮮度
- `Simulation Broker`
  - 接收模擬委託、產生模擬成交
- `Execution Model`
  - 定義市價、可成交限價、停損觸發的模擬成交規則
- `Cost Model`
  - 統一管理手續費、期交稅、滑價與版本
- `Paper Account Engine`
  - 管理可用權益、已實現損益、未實現損益、保證金占用
- `Contract Resolver`
  - 將 `TMF` 解析為實際近月契約
- `Continuous Contract Builder`
  - 產生 research 用連續契約與轉倉紀錄
- `Execution Journal`
  - 紀錄訊號、風控決策、委託、成交、平倉原因

### 8.2 為什麼不要直接沿用股票資產模型

因為期貨和股票的風險結構不同：

- 期貨看的是 `權益 / 保證金 / 可動用資金`
- 股票看的是 `現金 + 持倉市值`

所以第一版建議：

- 期貨 paper trading 做成獨立 runtime
- 不直接套用現有 `asset_tracking_service.py` 的持倉估值模型

### 8.3 富邦盤中資料接入前提

若盤中 runtime 要直接用富邦期貨資料判斷，規劃上要先滿足：

- Python 環境可安裝 `fubon_neo` SDK
- 系統內已有可用的富邦帳戶設定
- futopt 資料讀取使用：
  - `fetch_futopt_quote`
  - `fetch_futopt_intraday_candles`
- `TXF / TMF` 都能被正確解析到實際近月契約
- 訊號層必須保存：
  - `quote_timestamp`
  - `candle_timestamp`
  - `resolved_symbol`
  - `data_source`

### 8.4 第一版 Simulation Broker 的最低要求

若要讓 breakout / pullback 類策略的 paper trading 有參考價值，`Simulation Broker` 不能只做「有下單就成交」。

第一版最低要求建議：

- 僅正式支援：
  - `market`
  - `marketable_limit`
  - `stop_market`
- `被動限價單` 若只是價格碰到，不保證成交
- `停損單` 應允許發生滑價，不得強制成交在停損價
- 所有 fill 都要保存：
  - `fill_price`
  - `fill_qty`
  - `slippage_ticks`
  - `fill_reason`

### 8.5 第一版回放模式的保守成交原則

如果 Phase 1 先用歷史分 K 回放，建議採保守近似：

- `market order`
  - 以 `下一可成交價格 + session slippage` 模擬
- `marketable_limit`
  - 只有在 bar 內明確可成交時才成交
- `passive_limit`
  - 第一版可不納入正式驗收，避免假成交高估績效

這樣做雖然保守，但更接近真實交易。

---

## 9. 建議資料表

第一版可先規劃：

- `paper_trading_accounts`
- `paper_trading_bots`
- `paper_trading_positions`
- `paper_trading_orders`
- `paper_trading_fills`
- `paper_trading_equity_snapshots`
- `paper_trading_risk_events`
- `paper_trading_contract_resolutions`
- `paper_trading_cost_models`
- `paper_trading_replay_runs`
- `paper_trading_continuous_rolls`

---

## 10. 建議 API

### 10.1 Bot 管理

```text
GET    /api/paper-trading/bots
POST   /api/paper-trading/bots
PATCH  /api/paper-trading/bots/{id}
POST   /api/paper-trading/bots/{id}/start
POST   /api/paper-trading/bots/{id}/stop
```

### 10.2 狀態與執行紀錄

```text
GET /api/paper-trading/accounts/current
GET /api/paper-trading/positions/current
GET /api/paper-trading/orders
GET /api/paper-trading/fills
GET /api/paper-trading/equity
GET /api/paper-trading/risk-events
```

### 10.3 回放與模擬

```text
POST /api/paper-trading/replay/run
POST /api/paper-trading/replay/step
GET  /api/paper-trading/replay/runs
```

---

## 11. 分階段實作建議

### Phase 1：TMF 回放式模擬

目標：

- 用歷史分 K 重播
- 驗證策略、風控、委託與成交流程
- `以 day_only 為正式驗收模式`

範圍：

- TMF / TX 資料讀取
- TWII 僅保留為可選研究欄位，不列為 MVP 必要輸入
- 策略訊號
- 風控
- 模擬成交
- 成本模型
- 契約解析與轉倉 metadata
- 紙上部位與損益
- 執行日誌

### Phase 2：即時 paper trading

目標：

- 用富邦期貨即時行情驅動 bot
- 不下真單，但按真實市場時鐘執行
- `overnight_allowed` 若要驗收，建議從這一階段才開始

範圍：

- futopt quote / candles 即時訂閱
- `TXF -> TXFE6`、`TMF -> TMFE6` 類型的近月契約解析
- quote freshness / 跨商品時間戳檢查
- bot scheduler
- 即時風控
- 即時委託/成交模擬

### Phase 3：真實券商對接前準備

目標：

- 將 `Simulation Broker` 抽象成 `Broker Provider`
- 準備銜接富邦真實下單

範圍：

- broker interface
- order lifecycle 對齊
- 帳戶同步
- 例外與失敗重試

---

## 12. Repo 對齊注意事項

目前 repo 內部對期貨 alias 的部分內容仍使用：

- `MXF`

但官方微型臺指期貨代碼是：

- `TMF`

正式開發前，建議先盤點並修正相關 alias / search / provider 邏輯，以免未來接富邦 API 時，搜尋、契約解析與商品代碼發生混淆。

另外，第一版若要直接用富邦盤中期貨資料做判斷，至少還要確認以下幾點：

- `TMF` 必須補進 alias / query normalization，否則無法直接以 `TMF` 解析近月契約
- `MXF` 應明確保留為 `小型臺指期貨`，不可再混作 `微型臺指期貨`
- `TX / TMF` 的即時訊號應使用同一來源的 futopt 資料，避免跨來源時間差造成假訊號
- `TWII` 若有加入，只能作輔助濾網、報表或檢討欄位，不應回頭變成 MVP 的硬性阻塞條件

---

## 13. 本規劃的最小落地版本

如果只做最值得的第一版，建議優先順序如下：

1. `TMF 回放式 paper trading`
2. `TX 作為方向條件`
3. `TMF 作為進出場觸發`
4. `富邦 futopt 作為盤中資料源`
5. `保守成交模型 + 正式成本模型`
6. `完整資金/口數/單日虧損風控`
7. `day_only 模式`
8. `契約解析、結算日前限制與轉倉 metadata`
9. `執行日誌與檢討畫面`

先不要急著做：

- 多商品組合
- 自動轉倉
- 複雜被動限價單成交模擬
- TMF 的當沖減收保證金模擬
- 把 `overnight_allowed` 當成第一版核心驗收
- 真實下單

---

## 14. 參考資料

- 臺股期貨（TX）商品規格  
  https://www.taifex.com.tw/cht/2/tX

- 小型臺指期貨（MTX）商品規格  
  https://www.taifex.com.tw/cht/2/mTX

- 微型臺指期貨（TMF）商品規格  
  https://www.taifex.com.tw/cht/2/tMF

- 期貨契約當日沖銷交易減收保證金作業  
  https://www.taifex.com.tw/chinese/event/train1030304/lecture/%E6%9C%9F%E8%B2%A8%E5%A5%91%E7%B4%84%E7%95%B6%E6%97%A5%E6%B2%96%E9%8A%B7%E4%BA%A4%E6%98%93%E6%B8%9B%E6%94%B6%E4%BF%9D%E8%AD%89%E9%87%91%E4%BD%9C%E6%A5%AD.pdf

- SPAN 參數/保證金說明  
  https://www.taifex.com.tw/cht/5/spanRiskParameter
