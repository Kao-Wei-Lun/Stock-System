# Yahoo／海外行情更新維運手冊

## 目的

海外股票、指數、商品與加密資產由同一個 market-aware coordinator 更新。台股、台灣指數與台灣期貨仍走富邦／TAIFEX，不會以 Yahoo 作一般 fallback。

## 更新策略

- 畫面正在使用且市場開盤：預設 60 秒。
- 背景觀察池且市場開盤：預設 300 秒。
- 加密資產：24/7，預設 180 秒。
- 休市商品：預設 1,800 秒，freshness 依最近完成交易時段判斷。
- 同代號採 single-flight；Yahoo 全域並行上限預設 2。
- 手動刷新最小間隔預設 10 秒。
- 429 會啟動 provider-wide backoff；timeout、空回應與其他錯誤採代號級指數退避。

香港、日本與中國市場包含午休時段；紐約與歐洲時區由 `zoneinfo` 自動處理日光節約時間。部署若有交易所假日資料，可透過 market calendar 介面的 holiday set 注入；未注入時，資料品質仍保留一個完成交易日的假日寬限。

## 狀態檢查

- `GET /api/system/performance`
  - `overseas_quote_refresh.max_concurrency`
  - `active_requests`
  - `peak_concurrency`
  - `degraded_count`
  - `provider_backoff_until`
- `GET /api/system/data-quality`
  - `components.overseas_quotes`
  - `components.watchlist.stale_items[].stale_reason`
- `GET /api/quote/{ticker}`
  - 回傳 freshness、下一次更新與 provider degraded 說明。
- `POST /api/quote/{ticker}/refresh`
  - 手動刷新；過度連點會回傳最近快照及 `refresh_status=throttled`。

## 回滾

設定 `OVERSEAS_QUOTE_REFRESH_ENABLED=false` 後重啟，即可停用自動海外行情排程。手動刷新、已保存快照及 freshness 說明仍可使用。
