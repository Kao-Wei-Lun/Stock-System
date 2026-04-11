import pytest

from fubon_futopt_provider import FubonFutoptProvider


class StubFutoptManager:
    def __init__(self):
        self.ticker_calls = []
        self.quote_calls = []
        self.candle_calls = []

    async def fetch_futopt_tickers(self, **kwargs):
        self.ticker_calls.append(kwargs)
        contract_type = kwargs.get("contractType")
        if contract_type == "I":
            return {
                "data": [
                    {
                        "symbol": "TXFE6",
                        "name": "臺股期貨056",
                        "contractType": "I",
                        "endDate": "2026-05-20",
                    },
                    {
                        "symbol": "MXFE6",
                        "name": "小型臺指056",
                        "contractType": "I",
                        "endDate": "2026-05-20",
                    },
                ]
            }
        return {
            "data": [
                {
                    "symbol": "TXFI6",
                    "name": "臺股期貨096",
                    "contractType": "E",
                    "endDate": "2026-09-16",
                }
            ]
        }

    async def fetch_futopt_quote(self, symbol, **kwargs):
        self.quote_calls.append({"symbol": symbol, **kwargs})
        return {
            "symbol": symbol,
            "exchange": "TAIFEX",
            "name": "臺股期貨056",
            "previousClose": 20500,
            "openPrice": 20580,
            "highPrice": 20620,
            "lowPrice": 20560,
            "closePrice": 20610,
            "change": 110,
            "changePercent": 0.54,
            "lastUpdated": 1770000000000000,
            "bids": [{"price": 20609, "size": 35}],
            "asks": [{"price": 20610, "size": 28}],
            "total": {"tradeVolume": 65432},
        }

    async def fetch_futopt_intraday_candles(self, symbol, **kwargs):
        self.candle_calls.append({"symbol": symbol, **kwargs})
        return {
            "symbol": symbol,
            "data": [
                {
                    "date": "2026-04-11T09:00:00+08:00",
                    "open": 20550,
                    "high": 20580,
                    "low": 20540,
                    "close": 20570,
                    "volume": 1200,
                },
                {
                    "date": "2026-04-11T09:01:00+08:00",
                    "open": 20570,
                    "high": 20590,
                    "low": 20560,
                    "close": 20588,
                    "volume": 980,
                },
            ],
        }


@pytest.mark.anyio
async def test_futopt_provider_resolves_nearest_contract_from_base_alias():
    provider = FubonFutoptProvider(StubFutoptManager())

    resolved = await provider.resolve_contract("TXF")

    assert resolved["requested_symbol"] == "TXF"
    assert resolved["resolved_symbol"] == "TXFE6"
    assert resolved["contract_type"] == "I"


@pytest.mark.anyio
async def test_futopt_provider_fetches_quote_with_resolved_symbol():
    manager = StubFutoptManager()
    provider = FubonFutoptProvider(manager)

    quote = await provider.fetch_quote("TXF")

    assert manager.quote_calls == [{"symbol": "TXFE6", "session": "REGULAR"}]
    assert quote["ticker"] == "TXFE6"
    assert quote["resolved_symbol"] == "TXFE6"
    assert quote["exchange"] == "TAIFEX"
    assert quote["is_delayed"] is False
    assert quote["bid"] == 20609
    assert quote["ask"] == 20610


@pytest.mark.anyio
async def test_futopt_provider_fetches_intraday_ohlc():
    manager = StubFutoptManager()
    provider = FubonFutoptProvider(manager)

    payload = await provider.fetch_intraday_ohlc("MXF", period="1d", interval="1m")

    assert manager.candle_calls == [{"symbol": "MXFE6", "timeframe": "1", "session": "REGULAR"}]
    assert payload["ticker"] == "MXFE6"
    assert payload["interval"] == "1m"
    assert payload["data"][0]["source"] == "fubon_neo"
