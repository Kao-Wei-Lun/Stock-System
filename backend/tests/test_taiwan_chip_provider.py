from datetime import date

import pytest

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


def test_taiwan_chip_provider_parses_current_t86_format():
    payload = {
        "stat": "OK",
        "fields": [
            "證券代號",
            "證券名稱",
            "外陸資買進股數(不含外資自營商)",
            "外陸資賣出股數(不含外資自營商)",
            "外陸資買賣超股數(不含外資自營商)",
            "外資自營商買進股數",
            "外資自營商賣出股數",
            "外資自營商買賣超股數",
            "投信買進股數",
            "投信賣出股數",
            "投信買賣超股數",
            "自營商買賣超股數",
            "自營商買進股數(自行買賣)",
            "自營商賣出股數(自行買賣)",
            "自營商買賣超股數(自行買賣)",
            "自營商買進股數(避險)",
            "自營商賣出股數(避險)",
            "自營商買賣超股數(避險)",
            "三大法人買賣超股數",
        ],
        "data": [
            [
                "2330",
                "台積電",
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
    assert snapshot["summary"]["signals"][0]["label"] == "三大法人合計"


def test_taiwan_chip_provider_parses_legacy_t86_format():
    payload = {
        "stat": "OK",
        "fields": [
            "證券代號",
            "證券名稱",
            "外資買進股數",
            "外資賣出股數",
            "外資買賣超股數",
            "投信買進股數",
            "投信賣出股數",
            "投信買賣超股數",
            "自營商買賣超股數",
            "自營商買進股數",
            "自營商賣出股數",
            "三大法人買賣超股數",
        ],
        "data": [
            [
                "2303",
                "聯電",
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


@pytest.mark.anyio
async def test_taiwan_chip_provider_rejects_dates_before_t86_earliest():
    provider = TaiwanChipProvider(session=StubSession({"stat": "OK", "fields": [], "data": []}))

    with pytest.raises(ValueError, match="earliest date is 2012-05-02"):
        await provider.ensure_daily_snapshot("2012-05-01")


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
    assert [signal["label"] for signal in summary["signals"]] == ["三大法人合計", "外資", "投信", "自營商"]
