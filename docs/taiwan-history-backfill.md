# Taiwan Full History Backfill

Taiwan stock history used by the daily AI report is stored locally from Fubon API only. The first full load can be started manually, then the backend can keep repairing missing symbols and appending incremental data during the non-trading window.

## Manual CLI

Full first-time backfill:

```bash
cd backend
python run_taiwan_history_backfill.py --force-full
```

Smoke test only a few symbols:

```bash
cd backend
python run_taiwan_history_backfill.py --force-full --max-tickers 5 --delay-seconds 0
```

## Manual API

Run these while the backend is running:

```bash
curl -X POST "http://localhost:8001/api/tw/history/backfill/full"
curl -X POST "http://localhost:8001/api/tw/history/backfill/missing"
curl "http://localhost:8001/api/tw/universe/coverage?interval=1d"
curl "http://localhost:8001/api/tw/history/status?interval=1d&limit=50"
```

## Automatic Non-Trading Repair

Enable the automatic repair job in `.env`:

```env
TW_FULL_HISTORY_SYNC_ENABLED=true
TW_FULL_HISTORY_SYNC_START=15:30
TW_FULL_HISTORY_SYNC_STOP=08:00
TW_FULL_HISTORY_INTERVALS=1d,1wk,1mo
TW_FULL_HISTORY_PERIOD=max
TW_FULL_HISTORY_INCREMENTAL_PERIOD=5d
TW_FULL_HISTORY_DELAY_SECONDS=0.8
TW_FULL_HISTORY_INCLUDE_ETF=true
```
