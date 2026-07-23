from datetime import date

import pytest

import fubon_futopt_provider as futopt_module
from fubon_futopt_provider import FubonFutoptProvider


class FixedContractDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 5, 4)


@pytest.fixture(autouse=True)
def freeze_contract_resolution_date(monkeypatch):
    monkeypatch.setattr(futopt_module, "date", FixedContractDate)


class StubFutoptManager:
    def __init__(self):
        self.ticker_calls = []
        self.quote_calls = []
        self.candle_calls = []
        self.estimate_margin_calls = []

    async def fetch_futopt_tickers(self, **kwargs):
        self.ticker_calls.append(kwargs)
        product = str(kwargs.get("product") or "").upper()
        instrument_type = str(kwargs.get("type") or "FUTURE").upper()
        contract_type = kwargs.get("contractType")

        if instrument_type == "OPTION":
            if product and product != "TXO":
                return {"data": []}
            return {
                "data": [
                    {
                        "symbol": "TXO20000E4",
                        "name": "TAIEX Option 20000 Call Apr",
                        "type": "OPTION",
                        "contractType": contract_type,
                        "endDate": "2026-04-22",
                    },
                    {
                        "symbol": "TXO19800A4",
                        "name": "TAIEX Option 19800 Put Apr",
                        "type": "OPTION",
                        "contractType": contract_type,
                        "endDate": "2026-04-22",
                    },
                ]
            }

        if contract_type == "I":
            return {
                "data": [
                    {
                        "symbol": "TXFE6",
                        "name": "TAIEX Futures May",
                        "type": "FUTURE",
                        "contractType": "I",
                        "endDate": "2026-05-20",
                    },
                    {
                        "symbol": "MXFE6",
                        "name": "Mini TAIEX Futures May",
                        "type": "FUTURE",
                        "contractType": "I",
                        "endDate": "2026-05-20",
                    },
                ]
            }
        return {
            "data": [
                {
                    "symbol": "TXFI6",
                    "name": "TAIEX Futures Sep",
                    "type": "FUTURE",
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
            "name": "TAIEX Futures May",
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

    async def query_futopt_estimate_margin(self, symbol, **kwargs):
        self.estimate_margin_calls.append({"symbol": symbol, **kwargs})
        return {
            "is_success": True,
            "data": {
                "date": "2026/05/04",
                "currency": "TWD",
                "estimate_margin": 27100,
            },
        }


@pytest.mark.anyio
async def test_futopt_provider_resolves_nearest_contract_from_base_alias():
    provider = FubonFutoptProvider(StubFutoptManager())

    resolved = await provider.resolve_contract("TXF")

    assert resolved["requested_symbol"] == "TXF"
    assert resolved["resolved_symbol"] == "TXFE6"
    assert resolved["contract_type"] == "I"
    assert resolved["instrument_type"] == "future"


@pytest.mark.anyio
async def test_futopt_provider_resolves_dynamic_continuous_alias():
    provider = FubonFutoptProvider(StubFutoptManager())

    resolved = await provider.resolve_contract("*TXFF")

    assert resolved["requested_symbol"] == "*TXFF"
    assert resolved["resolved_symbol"] == "TXFE6"


@pytest.mark.anyio
async def test_futopt_provider_fetches_quote_with_resolved_symbol():
    manager = StubFutoptManager()
    provider = FubonFutoptProvider(manager)

    quote = await provider.fetch_quote("TXF", session="REGULAR")

    assert manager.quote_calls == [{"symbol": "TXFE6", "session": "REGULAR"}]
    assert quote["ticker"] == "TXFE6"
    assert quote["resolved_symbol"] == "TXFE6"
    assert quote["exchange"] == "TAIFEX"
    assert quote["market"] == "FUTURE"
    assert quote["is_delayed"] is False
    assert quote["bid"] == 20609
    assert quote["ask"] == 20610


@pytest.mark.anyio
async def test_futopt_provider_estimates_margin_with_resolved_contract():
    manager = StubFutoptManager()
    provider = FubonFutoptProvider(manager)

    payload = await provider.estimate_margin("TXF", session="REGULAR")

    assert payload["resolved_symbol"] == "TXFE6"
    assert payload["initial_margin_per_contract"] == 27100
    assert payload["currency"] == "TWD"
    assert manager.estimate_margin_calls == [
        {"symbol": "TXFE6", "price": 20610.0, "lot": 1, "session": "REGULAR"}
    ]


@pytest.mark.anyio
async def test_margin_estimate_uses_pool_selected_futures_manager():
    marketdata_manager = StubFutoptManager()
    futures_manager = StubFutoptManager()
    futures_manager.active_account_id = 5
    provider = FubonFutoptProvider(
        marketdata_manager,
        margin_manager_provider=lambda: futures_manager,
    )

    payload = await provider.estimate_margin("TXF", session="REGULAR")

    assert marketdata_manager.ticker_calls
    assert marketdata_manager.quote_calls == []
    assert futures_manager.quote_calls == [{"symbol": "TXFE6", "session": "REGULAR"}]
    assert futures_manager.estimate_margin_calls[0]["symbol"] == "TXFE6"
    assert payload["provider_account_id"] == 5


@pytest.mark.anyio
async def test_futopt_provider_fetches_quote_from_auto_afterhours_session(monkeypatch):
    monkeypatch.setattr(futopt_module, "resolve_futopt_session", lambda _session=None: "AFTERHOURS")
    manager = StubFutoptManager()
    provider = FubonFutoptProvider(manager)

    quote = await provider.fetch_quote("TXF")

    assert manager.quote_calls == [{"symbol": "TXFE6", "session": "AFTERHOURS"}]
    assert quote["ticker"] == "TXFE6"


@pytest.mark.anyio
async def test_futopt_provider_fetches_intraday_ohlc():
    manager = StubFutoptManager()
    provider = FubonFutoptProvider(manager)

    payload = await provider.fetch_intraday_ohlc("MXF", period="1d", interval="1m")

    # 因為 session 預設為 ALL，現在會平行抓取 REGULAR 與 AFTERHOURS
    assert {"symbol": "MXFE6", "timeframe": "1", "session": "REGULAR"} in manager.candle_calls
    assert {"symbol": "MXFE6", "timeframe": "1", "session": "AFTERHOURS"} in manager.candle_calls
    assert len(manager.candle_calls) == 2
    assert payload["ticker"] == "MXFE6"
    assert payload["interval"] == "1m"
    assert payload["data"][0]["source"] == "fubon_neo"


@pytest.mark.anyio
async def test_futopt_provider_searches_option_contracts_by_partial_query():
    manager = StubFutoptManager()
    provider = FubonFutoptProvider(manager)

    payload = await provider.search_contracts("TXO200", limit=5)

    assert payload[0]["ticker"] == "TXO20000E4"
    assert payload[0]["instrument_type"] == "option"
    assert payload[0]["market"] == "FUTOPT"
    assert any(call.get("product") == "TXO" for call in manager.ticker_calls)
