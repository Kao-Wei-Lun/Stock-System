from datetime import date

import pytest

import taiwan_chip_provider as provider_module
from taiwan_chip_provider import TaiwanChipProvider, build_taiwan_chip_summary


class StubResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")
        return None

    def json(self):
        return self._payload


class StubSession:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.headers = {}

    def get(self, *_args, **_kwargs):
        return StubResponse(self.payload, status_code=self.status_code)


def test_taiwan_chip_provider_parses_current_t86_format(monkeypatch):
    monkeypatch.setattr(provider_module, "resolve_taiwan_ticker", lambda code: f"{code}.TW")
    payload = {
        "stat": "OK",
        "fields": [
            "\u8b49\u5238\u4ee3\u865f",
            "\u8b49\u5238\u540d\u7a31",
            "\u5916\u9678\u8cc7\u8cb7\u9032\u80a1\u6578(\u4e0d\u542b\u5916\u8cc7\u81ea\u71df\u5546)",
            "\u5916\u9678\u8cc7\u8ce3\u51fa\u80a1\u6578(\u4e0d\u542b\u5916\u8cc7\u81ea\u71df\u5546)",
            "\u5916\u9678\u8cc7\u8cb7\u8ce3\u8d85\u80a1\u6578(\u4e0d\u542b\u5916\u8cc7\u81ea\u71df\u5546)",
            "\u5916\u8cc7\u81ea\u71df\u5546\u8cb7\u9032\u80a1\u6578",
            "\u5916\u8cc7\u81ea\u71df\u5546\u8ce3\u51fa\u80a1\u6578",
            "\u5916\u8cc7\u81ea\u71df\u5546\u8cb7\u8ce3\u8d85\u80a1\u6578",
            "\u6295\u4fe1\u8cb7\u9032\u80a1\u6578",
            "\u6295\u4fe1\u8ce3\u51fa\u80a1\u6578",
            "\u6295\u4fe1\u8cb7\u8ce3\u8d85\u80a1\u6578",
            "\u81ea\u71df\u5546\u8cb7\u8ce3\u8d85\u80a1\u6578",
            "\u81ea\u71df\u5546\u8cb7\u9032\u80a1\u6578(\u81ea\u884c\u8cb7\u8ce3)",
            "\u81ea\u71df\u5546\u8ce3\u51fa\u80a1\u6578(\u81ea\u884c\u8cb7\u8ce3)",
            "\u81ea\u71df\u5546\u8cb7\u8ce3\u8d85\u80a1\u6578(\u81ea\u884c\u8cb7\u8ce3)",
            "\u81ea\u71df\u5546\u8cb7\u9032\u80a1\u6578(\u907f\u96aa)",
            "\u81ea\u71df\u5546\u8ce3\u51fa\u80a1\u6578(\u907f\u96aa)",
            "\u81ea\u71df\u5546\u8cb7\u8ce3\u8d85\u80a1\u6578(\u907f\u96aa)",
            "\u4e09\u5927\u6cd5\u4eba\u8cb7\u8ce3\u8d85\u80a1\u6578",
        ],
        "data": [
            [
                "2330",
                "\u53f0\u7a4d\u96fb",
                "1,000",
                "900",
                "100",
                "20",
                "10",
                "10",
                "50",
                "30",
                "20",
                "40",
                "60",
                "50",
                "10",
                "100",
                "80",
                "20",
                "170",
            ]
        ],
    }

    provider = TaiwanChipProvider(session=StubSession(payload))
    result = provider._fetch_daily_snapshot_sync(date(2026, 4, 10))

    assert result["format_version"] == "current"
    assert len(result["snapshots"]) == 1
    snapshot = result["snapshots"][0]
    assert snapshot["ticker"] == "2330.TW"
    assert snapshot["foreign_net_buy_sell"] == 110
    assert snapshot["investment_trust_net_buy_sell"] == 20
    assert snapshot["dealer_net_buy_sell"] == 40
    assert snapshot["institutional_net_buy_sell"] == 170
    assert snapshot["summary"]["bias"] == "bullish"
    assert snapshot["summary"]["signals"][0]["label"] == "\u4e09\u5927\u6cd5\u4eba\u5408\u8a08"


def test_taiwan_chip_provider_parses_legacy_t86_format(monkeypatch):
    monkeypatch.setattr(provider_module, "resolve_taiwan_ticker", lambda code: f"{code}.TW")
    payload = {
        "stat": "OK",
        "fields": [
            "\u8b49\u5238\u4ee3\u865f",
            "\u8b49\u5238\u540d\u7a31",
            "\u5916\u8cc7\u8cb7\u9032\u80a1\u6578",
            "\u5916\u8cc7\u8ce3\u51fa\u80a1\u6578",
            "\u5916\u8cc7\u8cb7\u8ce3\u8d85\u80a1\u6578",
            "\u6295\u4fe1\u8cb7\u9032\u80a1\u6578",
            "\u6295\u4fe1\u8ce3\u51fa\u80a1\u6578",
            "\u6295\u4fe1\u8cb7\u8ce3\u8d85\u80a1\u6578",
            "\u81ea\u71df\u5546\u8cb7\u8ce3\u8d85\u80a1\u6578",
            "\u81ea\u71df\u5546\u8cb7\u9032\u80a1\u6578",
            "\u81ea\u71df\u5546\u8ce3\u51fa\u80a1\u6578",
            "\u4e09\u5927\u6cd5\u4eba\u8cb7\u8ce3\u8d85\u80a1\u6578",
        ],
        "data": [
            [
                "2303",
                "\u806f\u96fb",
                "46,911,000",
                "28,499,762",
                "18,411,238",
                "5,707,000",
                "0",
                "5,707,000",
                "646,000",
                "648,000",
                "2,000",
                "24,764,238",
            ]
        ],
    }

    provider = TaiwanChipProvider(session=StubSession(payload))
    result = provider._fetch_daily_snapshot_sync(date(2012, 5, 2))

    assert result["format_version"] == "legacy"
    snapshot = result["snapshots"][0]
    assert snapshot["ticker"] == "2303.TW"
    assert snapshot["foreign_net_buy_sell"] == 18411238
    assert snapshot["investment_trust_net_buy_sell"] == 5707000
    assert snapshot["dealer_net_buy_sell"] == 646000
    assert snapshot["institutional_net_buy_sell"] == 24764238
    assert snapshot["summary"]["bias"] == "bullish"


def test_taiwan_chip_provider_parses_tpex_json_format(monkeypatch):
    monkeypatch.setattr(provider_module, "resolve_taiwan_ticker", lambda code: {"6488": "6488.TWO"}.get(code))
    payload = {
        "stat": "ok",
        "tables": [
            {
                "date": "115/04/10",
                "fields": ["\u4ee3\u865f", "\u540d\u7a31"],
                "data": [
                    [
                        "6488",
                        "\u74b0\u7403\u6676",
                        "1,200",
                        "900",
                        "300",
                        "10",
                        "5",
                        "5",
                        "1,210",
                        "905",
                        "305",
                        "80",
                        "20",
                        "60",
                        "40",
                        "10",
                        "30",
                        "90",
                        "40",
                        "50",
                        "130",
                        "50",
                        "80",
                        "445",
                    ]
                ],
            }
        ],
    }

    provider = TaiwanChipProvider(session=StubSession(payload))
    result = provider._fetch_tpex_daily_snapshot_sync(date(2026, 4, 10))

    assert result["format_version"] == "current"
    assert len(result["snapshots"]) == 1
    snapshot = result["snapshots"][0]
    assert snapshot["ticker"] == "6488.TWO"
    assert snapshot["source"] == "tpex_3itrade_hedge"
    assert snapshot["foreign_net_buy_sell"] == 305
    assert snapshot["investment_trust_net_buy_sell"] == 60
    assert snapshot["dealer_net_buy_sell"] == 80
    assert snapshot["institutional_net_buy_sell"] == 445
    assert snapshot["summary"]["bias"] == "bullish"


@pytest.mark.anyio
async def test_taiwan_chip_provider_rejects_dates_before_t86_earliest():
    provider = TaiwanChipProvider(session=StubSession({"stat": "OK", "fields": [], "data": []}))

    with pytest.raises(ValueError, match="earliest date is 2012-05-02"):
        await provider.ensure_daily_snapshot("2012-05-01")


@pytest.mark.anyio
async def test_taiwan_chip_provider_allows_pre_2012_tpex_requests(monkeypatch):
    monkeypatch.setattr(provider_module, "resolve_taiwan_ticker", lambda code: f"{code}.TWO")

    class MultiPayloadSession:
        def __init__(self):
            self.headers = {}

        def get(self, url, *args, **kwargs):
            if "3itrade_hedge_result.php" in url:
                return StubResponse(
                    {
                        "stat": "ok",
                        "tables": [
                            {
                                "date": "101/05/01",
                                "fields": ["\u4ee3\u865f", "\u540d\u7a31"],
                                "data": [
                                    [
                                        "6488",
                                        "\u74b0\u7403\u6676",
                                        "100",
                                        "50",
                                        "50",
                                        "0",
                                        "0",
                                        "0",
                                        "100",
                                        "50",
                                        "50",
                                        "0",
                                        "0",
                                        "0",
                                        "0",
                                        "0",
                                        "0",
                                        "0",
                                        "0",
                                        "0",
                                        "0",
                                        "0",
                                        "0",
                                        "50",
                                    ]
                                ],
                            }
                        ],
                    }
                )
            return StubResponse({"stat": "OK", "fields": [], "data": []})

    async def get_taiwan_chip_snapshot_source_counts(_snapshot_date):
        return {}

    async def upsert_taiwan_chip_snapshots(items):
        return len(items)

    async def get_latest_taiwan_chip_snapshot_date(on_or_before=None):
        return None

    async def get_taiwan_chip_snapshot_count(snapshot_date):
        return 0

    monkeypatch.setattr(provider_module.db, "get_taiwan_chip_snapshot_source_counts", get_taiwan_chip_snapshot_source_counts)
    monkeypatch.setattr(provider_module.db, "upsert_taiwan_chip_snapshots", upsert_taiwan_chip_snapshots)
    monkeypatch.setattr(provider_module.db, "get_latest_taiwan_chip_snapshot_date", get_latest_taiwan_chip_snapshot_date)
    monkeypatch.setattr(provider_module.db, "get_taiwan_chip_snapshot_count", get_taiwan_chip_snapshot_count)

    provider = TaiwanChipProvider(session=MultiPayloadSession())
    result = await provider.ensure_daily_snapshot("2012-05-01", sources=("tpex",), allow_fallback=False)

    assert result["resolved_date"] == "2012-05-01"
    assert result["row_count"] == 1


def test_build_taiwan_chip_summary_uses_official_signals_when_available():
    summary = build_taiwan_chip_summary(
        {
            "ticker": "2330.TW",
            "snapshot_date": "2026-04-10",
            "source": "twse_t86",
            "foreign_net_buy_sell": 110,
            "investment_trust_net_buy_sell": 20,
            "dealer_net_buy_sell": -15,
            "institutional_net_buy_sell": 115,
        }
    )

    assert summary["bias"] == "bullish"
    assert [signal["label"] for signal in summary["signals"]] == [
        "\u4e09\u5927\u6cd5\u4eba\u5408\u8a08",
        "\u5916\u8cc7",
        "\u6295\u4fe1",
        "\u81ea\u71df\u5546",
    ]
