# QuantVision Pro 個人資產追蹤功能規劃 v1.1（交易流水驅動版）

**產出時間**：2026-04-18  
**規劃前提**：主要持倉與資金不在富邦，需以手動輸入資料為主  
**規劃目標**：讓使用者手動輸入現金與台美股交易資訊後，系統可自動推導持倉、抓取最新股價、估算資產現值，並計算已實現與未實現損益

---

## 1. 規劃背景

目前系統已具備：

- `Journal` 交易日誌
- `Backtest` 回測
- `/api/quote/{ticker}` 報價查詢
- 台股 ticker 正規化
- 台股與美股報價基礎能力

目前尚未具備：

- 正式的個人資產帳戶模型
- 現金流水帳
- 交易流水帳
- 由交易紀錄自動推導目前持倉
- 由持倉與最新報價自動估值
- 已實現 / 未實現損益統計
- 手動對帳與校正機制

前一版規劃偏向「每日快照中心」，也就是手動輸入當日總資產或持倉快照。  
這個模式可以做，但如果使用者願意輸入：

- 現金變動
- 台股 / 美股交易紀錄

那麼更合理的產品方向，應該改為：

`交易流水驅動 + 最新股價估值 + 快照校正`

這樣使用者不需要每天重打一整份資產快照，系統就能根據：

- 歷史現金紀錄
- 歷史買賣紀錄
- 目前最新報價

自動推導出資產現值與損益資訊。

---

## 2. 產品目標

本功能要讓使用者能在 10 秒內回答以下問題：

- 我現在總資產現值是多少
- 我目前現金還有多少
- 我現在台股與美股各有哪些持倉
- 每檔持倉目前是賺還是賠
- 總體未實現損益是多少
- 總體已實現損益是多少
- 本月扣除入金 / 出金後的真實績效是多少
- 哪些標的對目前資產貢獻最大或拖累最多

---

## 3. 範圍與邊界

### 3.1 本次優先範圍

- 手動建立資產帳戶
- 手動輸入現金流水
- 手動輸入台股 / 美股交易流水
- 系統自動計算目前持倉
- 系統自動抓最新股價進行估值
- 系統自動計算已實現 / 未實現損益
- 提供手動對帳與校正功能

### 3.2 第一版暫不作為核心驗收

- 自動串接非富邦券商帳務
- 銀行自動同步
- 負債管理
- 信用卡與生活收支記帳
- 衍生性商品完整保證金模型
- 稅務申報
- 真正逐筆即時淨值更新

### 3.3 第一版產品定位

本功能第一版建議定位為：

`個人投資資產追蹤模組`

不是完整家庭財務管理系統，也不是只看單日總額的記帳工具。  
它的核心任務是用投資交易資料，自動還原目前資產狀態。

---

## 4. 核心產品概念

本功能改採四層模型：

### 4.1 Source of Truth：兩本帳

系統的原始資料來源為兩種 ledger：

- `現金流水帳`
- `交易流水帳`

### 4.2 Derived State：系統自動推導

系統根據兩本帳，自動推導：

- 目前現金餘額
- 目前持倉數量
- 平均成本
- 已實現損益

### 4.3 Valuation：用最新股價估值

系統再根據目前持倉與最新報價，自動計算：

- 持倉市值
- 未實現損益
- 總資產現值

### 4.4 Reconciliation：手動對帳校正

若實際帳戶數字與系統推導不同，使用者可輸入：

- 帳戶現金對帳值
- 持倉校正快照
- 特殊調整事件

以修正估值與庫存偏差。

---

## 5. 核心設計原則

### 5.1 手動輸入成立優先於券商串接

- 沒有任何券商同步時，功能仍必須完整成立
- 富邦或未來其他券商，只能作為加值輸入來源

### 5.2 交易流水優先於每日總額快照

- 每日總額快照是輔助資料
- 交易流水與現金流水才是核心真實來源

### 5.3 自動估值優先於手動重算

- 使用者不應每天重填每檔最新價格
- 對於支援 ticker，系統應自動拉最新報價
- 若報價不可得，再允許人工覆蓋

### 5.4 資產變化與現金流必須分離

系統必須明確區分：

- 總資產變化
- 入金 / 出金
- 交易產生的已實現損益
- 持倉價格波動帶來的未實現損益

### 5.5 演算法先求穩定，再求完整

第一版建議用：

- `加權平均成本法`

而不是一開始就做：

- FIFO
- LIFO
- 稅務成本法

原因是第一版目標是先穩定算出持倉與損益，不是先處理完整稅務會計。

### 5.6 所有正式資料都要落地

以下資料都必須落資料庫：

- 帳戶主檔
- 現金流水
- 交易流水
- 對帳校正紀錄
- 匯率資料
- 估值快照或可重建的估值結果

---

## 6. 使用流程設計

### 6.1 初始設定

使用者先建立資產帳戶，例如：

- 台灣證券帳戶
- 美國券商帳戶
- 投資用銀行帳戶

### 6.2 輸入現金流水

使用者輸入：

- 入金
- 出金
- 股利
- 手續費
- 稅
- 匯費
- 帳戶間轉帳

### 6.3 輸入交易流水

使用者輸入：

- 買進
- 賣出

每筆至少包含：

- 日期
- 帳戶
- ticker
- 市場
- 幣別
- 買賣方向
- 數量
- 成交價
- 手續費
- 稅費

### 6.4 系統自動推導持倉

系統根據所有交易流水，自動計算：

- 每帳戶目前庫存
- 每檔目前持股數
- 平均成本
- 已實現損益

### 6.5 系統自動抓取最新報價

對於支援的 ticker：

- 台股優先使用現有台股報價來源
- 美股使用現有 quote provider 的 snapshot / delayed quote

### 6.6 系統自動估值

系統將最新報價套用到目前持倉，計算：

- 每檔市值
- 每檔未實現損益
- 帳戶總市值
- 總資產現值

### 6.7 手動校正

若實際券商 App 顯示數字與系統推導不一致，使用者可透過：

- 帳戶現金校正
- 持倉數量校正
- 特殊公司行動調整

進行 reconciliation。

---

## 7. 第一版支援資產範圍

### 7.1 第一版推薦完整支援

- 台股股票
- 台股 ETF
- 美股股票
- 美股 ETF
- 現金 TWD / USD

### 7.2 第一版可先以降級方式支援

- 港股
- 加密資產
- 非標準 ticker 資產
- 海外基金

對這些可採：

- 手動價格輸入
- 手動估值覆蓋

### 7.3 第一版先不完整處理的事件

- 股票分割
- 減資
- 配股配息自動回補
- 代號更名
- 複雜 corporate actions

這些可先以：

- `adjustment event`

方式手動記錄，第二階段再做精緻化。

---

## 8. 核心功能模組

### 8.1 帳戶管理

用於管理資產容器。

建議欄位：

- 帳戶名稱
- 機構名稱
- 帳戶類型
- 基準幣別
- 是否列入總資產
- 排序
- 備註

### 8.2 現金流水帳

用於管理所有會影響現金的事件。

建議類型：

- `deposit`
- `withdraw`
- `dividend`
- `interest`
- `fee`
- `tax`
- `fx_fee`
- `transfer_in`
- `transfer_out`
- `adjustment`

### 8.3 交易流水帳

用於管理所有會影響持倉的事件。

第一版建議支援：

- `buy`
- `sell`

第二版再擴充：

- `split`
- `symbol_change`
- `position_adjustment`

### 8.4 持倉推導引擎

系統根據交易流水自動推導：

- 持倉數量
- 平均成本
- 成本基礎
- 已實現損益

### 8.5 報價估值引擎

系統根據持倉與最新報價，自動計算：

- 即時或最新可用市值
- 未實現損益
- 當日損益估算

### 8.6 對帳校正模組

當使用者實際帳戶數字與系統推導不一致時，可建立校正紀錄。

建議支援：

- 現金校正
- 持倉數量校正
- 成本校正
- 手動估值覆蓋

### 8.7 資產總覽與分析

第一版至少提供：

- 總資產現值
- 現金總額
- 持倉總市值
- 已實現損益
- 未實現損益
- 當日估值變化
- 本月績效
- 帳戶配置
- 市場配置
- 標的權重

---

## 9. 關鍵計算規則

### 9.1 現金餘額

```text
帳戶現金餘額 = 現金流水累計 + 交易買賣對現金的影響
```

其中：

- 買進會減少現金
- 賣出會增加現金
- 手續費與稅費需同步扣回現金

### 9.2 持倉數量

```text
持倉數量 = 累計買進數量 - 累計賣出數量 + 調整事件
```

### 9.3 平均成本

第一版採用加權平均成本法：

```text
新平均成本 = (原持倉成本 + 新買進成本) / 新持倉總數量
```

### 9.4 已實現損益

賣出時：

```text
已實現損益 = 賣出收入 - 已售出部位成本 - 手續費 - 稅費
```

### 9.5 未實現損益

```text
未實現損益 = 目前市值 - 目前持倉成本
```

### 9.6 總資產現值

```text
總資產現值 = 現金總額 + 全部持倉市值 + 其他列入資產
```

### 9.7 期間真實績效

```text
期間真實績效 = 期末總資產現值 - 期初總資產現值 - 期間淨流入資金
```

### 9.8 基準幣別換算

第一版建議預設基準幣別為 `TWD`，但保留可設定能力。

多幣別換算邏輯：

```text
基準幣別市值 = 原幣市值 × 匯率
```

---

## 10. 與現有報價系統的整合方式

### 10.1 可直接沿用的能力

目前 repo 已具備：

- `/api/quote/{ticker}` 單檔報價查詢
- ticker 正規化
- 台股與美股基礎 quote provider

### 10.2 第一版報價策略

- 台股：優先使用現有台股報價來源
- 美股：使用現有 Yahoo snapshot / delayed quote
- 無法取得 quote 的資產：允許手動輸入最新價格或手動覆蓋估值

### 10.3 第一版限制

- 美股價格多半不是真正逐筆即時
- 報價時間要在 UI 清楚標示
- 若 quote 失敗，不能讓整個資產頁靜默失敗

---

## 11. 資料模型建議

本規劃建議把資料表分成：

- `Source tables`
- `Derived tables`
- `Reconciliation tables`

### 11.1 `asset_accounts`

用途：帳戶主檔

建議欄位：

- `id`
- `owner_id`
- `name`
- `institution`
- `account_type`
- `base_currency`
- `include_in_total`
- `sort_order`
- `notes`
- `created_at`
- `updated_at`

### 11.2 `asset_cash_ledger`

用途：現金流水來源表

建議欄位：

- `id`
- `owner_id`
- `account_id`
- `flow_date`
- `flow_type`
- `amount`
- `currency`
- `fx_rate_to_base`
- `counterparty`
- `note`
- `created_at`
- `updated_at`

### 11.3 `asset_trade_ledger`

用途：交易流水來源表

建議欄位：

- `id`
- `owner_id`
- `account_id`
- `trade_date`
- `ticker`
- `display_name`
- `market`
- `asset_type`
- `currency`
- `side`
- `quantity`
- `price`
- `gross_amount`
- `fee_amount`
- `tax_amount`
- `net_amount`
- `fx_rate_to_base`
- `source`
- `note`
- `created_at`
- `updated_at`

### 11.4 `asset_positions_current`

用途：系統推導出的目前持倉快取表

建議欄位：

- `id`
- `owner_id`
- `account_id`
- `ticker`
- `display_name`
- `market`
- `asset_type`
- `currency`
- `quantity`
- `avg_cost`
- `cost_basis`
- `realized_pnl`
- `updated_at`

### 11.5 `asset_valuations_current`

用途：目前估值結果快取表

建議欄位：

- `id`
- `owner_id`
- `account_id`
- `ticker`
- `quote_source`
- `quote_type`
- `is_delayed`
- `quote_timestamp`
- `last_price`
- `market_value`
- `unrealized_pnl`
- `unrealized_pnl_pct`
- `fx_rate_to_base`
- `market_value_base`
- `updated_at`

### 11.6 `asset_reconciliation_snapshots`

用途：手動對帳與校正

建議欄位：

- `id`
- `owner_id`
- `account_id`
- `snapshot_date`
- `cash_actual`
- `cash_system`
- `market_value_actual`
- `market_value_system`
- `positions_payload_json`
- `note`
- `created_at`

### 11.7 `asset_fx_rates_daily`

用途：多幣別換算

建議欄位：

- `id`
- `snapshot_date`
- `from_currency`
- `to_currency`
- `rate`
- `source`
- `created_at`

### 11.8 第二階段可選資料表

- `asset_position_adjustments`
- `asset_monthly_snapshots`
- `asset_import_jobs`

---

## 12. API 規劃建議

### 12.1 帳戶管理

```text
GET    /api/assets/accounts
POST   /api/assets/accounts
GET    /api/assets/accounts/{id}
PATCH  /api/assets/accounts/{id}
DELETE /api/assets/accounts/{id}
```

### 12.2 現金流水

```text
GET    /api/assets/cash-ledger?from=2026-01-01&to=2026-04-18
POST   /api/assets/cash-ledger
PATCH  /api/assets/cash-ledger/{id}
DELETE /api/assets/cash-ledger/{id}
```

### 12.3 交易流水

```text
GET    /api/assets/trades?from=2026-01-01&to=2026-04-18
POST   /api/assets/trades
PATCH  /api/assets/trades/{id}
DELETE /api/assets/trades/{id}
```

### 12.4 推導與估值結果

```text
GET /api/assets/holdings/current
GET /api/assets/summary/current
GET /api/assets/allocation/current?group_by=market
GET /api/assets/contributors/current
GET /api/assets/performance?range=30d
```

### 12.5 對帳校正

```text
GET  /api/assets/reconciliation
POST /api/assets/reconciliation
GET  /api/assets/reconciliation/{id}
```

### 12.6 匯入

```text
POST /api/assets/import/trades-csv
POST /api/assets/import/cash-csv
```

### 12.7 建議的 `POST /api/assets/trades` payload

```json
{
  "account_id": 2,
  "trade_date": "2026-04-18T09:30:00",
  "ticker": "AAPL",
  "display_name": "Apple Inc.",
  "market": "US",
  "asset_type": "stock",
  "currency": "USD",
  "side": "buy",
  "quantity": 10,
  "price": 192.5,
  "fee_amount": 1.0,
  "tax_amount": 0,
  "fx_rate_to_base": 32.4,
  "note": "手動輸入歷史交易"
}
```

### 12.8 建議的 `POST /api/assets/cash-ledger` payload

```json
{
  "account_id": 2,
  "flow_date": "2026-04-18",
  "flow_type": "deposit",
  "amount": 5000,
  "currency": "USD",
  "fx_rate_to_base": 32.4,
  "note": "補充美股帳戶資金"
}
```

---

## 13. 前端資訊架構建議

### 13.1 入口位置

第一版仍建議先放在 `Review` 工作區下，新增第三個分頁：

- `交易日誌`
- `系統回測`
- `資產追蹤`

理由：

- 與復盤 / 紀律 / 績效檢查脈絡一致
- 能降低第一版導覽改動成本

### 13.2 頁面主要區塊

**區塊 A：資產總覽卡**

- 總資產現值
- 現金總額
- 持倉總市值
- 已實現損益
- 未實現損益
- 今日估值變化

**區塊 B：帳戶摘要**

- 各帳戶現金
- 各帳戶持倉市值
- 各帳戶總資產

**區塊 C：目前持倉表**

- ticker
- 數量
- 平均成本
- 最新價
- 市值
- 未實現損益
- 權重

**區塊 D：交易流水**

- 最近交易紀錄
- 手動新增交易
- 編輯與刪除

**區塊 E：現金流水**

- 入金 / 出金 / 股利 / 費用列表
- 手動新增現金事件

**區塊 F：對帳與例外**

- quote 失敗標的
- 手動價格覆蓋
- 對帳誤差提示

### 13.3 第一版互動建議

- 使用者新增交易後，頁面立即重算持倉與估值
- 對 quote 失敗的標的顯示可手動填價
- 顯示 quote 時間與是否 delayed
- 如果帳戶存在對帳差異，頁面顯示醒目 warning

---

## 14. 與現有模組整合建議

### 14.1 與 Quote Provider 整合

直接沿用現有 quote API 能力作為估值來源。

### 14.2 與 Journal 整合

第二階段可考慮：

- 從交易日誌直接匯入交易事件
- 將已平倉交易對應到已實現損益

但第一版不建議強依賴 Journal，因為：

- 不是所有真實交易都一定已記進 Journal
- 資產模組必須能獨立成立

### 14.3 與 Watchlist 整合

可考慮：

- 從持倉一鍵加入 watchlist
- 從 watchlist 快速建立交易輸入草稿

### 14.4 與 Alert 整合

第三階段可新增：

- 總資產創高提醒
- 總資產回撤超標提醒
- 單一持倉權重過高提醒
- 持倉浮虧超標提醒

---

## 15. 分階段實作建議

### Phase 1：建立交易流水驅動核心

目標：先讓系統能從現金與交易資料自動還原資產現值

範圍：

- `asset_accounts`
- `asset_cash_ledger`
- `asset_trade_ledger`
- `asset_positions_current`
- `asset_valuations_current`
- 目前持倉推導
- 最新報價估值
- 總資產總覽
- 交易與現金輸入表單

完成後至少可回答：

- 現在總資產現值是多少
- 目前有哪些持倉
- 每檔目前賺賠多少
- 總未實現損益是多少

### Phase 2：補上對帳與配置分析

範圍：

- `asset_reconciliation_snapshots`
- 帳戶配置
- 市場配置
- 權重分布
- quote 失敗標的手動覆蓋
- CSV 匯入

完成後至少可回答：

- 系統推導和實際帳戶差多少
- 哪些帳戶或市場占比過高
- 匯入歷史資料的效率是否足夠

### Phase 3：補上績效深化

範圍：

- 期間真實績效
- 已實現 / 未實現拆分圖
- 月度熱力圖
- 高點回撤
- FX 強化
- Journal 整合

### Phase 4：補上進階事件與自動化

範圍：

- split / adjustment event
- corporate action 支援
- 批次重算
- 更多匯入格式
- 進階提醒

---

## 16. 驗收標準

第一階段完成後，至少要滿足：

- 使用者能建立資產帳戶
- 使用者能輸入現金流水
- 使用者能輸入台股 / 美股交易流水
- 系統能根據交易紀錄正確推導目前持倉
- 系統能根據最新報價估算持倉市值
- 系統能正確計算未實現損益
- 畫面能顯示報價來源、報價時間與 delayed 標記
- 資料在系統重啟後不遺失

第二階段完成後，至少要滿足：

- 使用者能做帳戶對帳
- quote 失敗標的能人工補價
- 系統能顯示配置分布

第三階段完成後，至少要滿足：

- 使用者能看期間真實績效
- 使用者能分辨已實現與未實現損益

---

## 17. 風險與注意事項

### 17.1 若歷史交易不完整，推導結果一定會失真

這個模型的核心前提是：

- 現金流水要完整
- 交易流水要完整

否則系統推導出的持倉與現金不會準。

### 17.2 quote 可用性不是百分之百

若某些標的：

- ticker 不標準
- 市場不支援
- 報價來源暫時失敗

就必須有人工補價或估值覆蓋方案。

### 17.3 美股報價多半不是逐筆即時

因此 UI 必須清楚說明：

- 資產現值是根據最新可用報價估算
- 並非保證與券商畫面逐秒一致

### 17.4 corporate actions 會影響成本與庫存

若遇到：

- split
- 減資
- 配股
- 代號異動

第一版需至少提供手動調整事件，否則長期持倉可能失真。

---

## 18. 本規劃的優先推薦

若只做最值得的第一版，我建議優先順序如下：

1. `帳戶 + 現金流水 + 交易流水`
2. `持倉推導 + 平均成本`
3. `最新股價估值 + 總資產現值`
4. `目前持倉表 + 未實現損益`
5. `對帳校正 + 匯入`

這樣做的價值是：

- 你不需要每天重填總資產
- 只要補交易與現金事件，系統就能自動算資產現值
- 更貼近真實投資使用情境
- 也更容易與現有 quote 能力整合

---

## 19. 建議後續延伸文件

若要正式開發，建議下一步可再拆出：

- `docs/asset-tracking-ledger-schema.md`
- `docs/asset-tracking-api-spec.md`
- `docs/asset-tracking-reconciliation-flow.md`
- `docs/asset-tracking-phase-task-checklist.md`

