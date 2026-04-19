import pytest

from fx_rate_provider import TaifexDailyFxRateProvider


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _FakeSession:
    def __init__(self, content: bytes) -> None:
        self._content = content
        self.calls = 0

    def get(self, url, timeout=10):  # noqa: ANN001
        self.calls += 1
        return _FakeResponse(self._content)


def test_taifex_daily_fx_rate_provider_parses_latest_row_and_derives_twd_rates():
    csv_text = "\n".join(
        [
            "date,usd_twd,cny_twd,eur_usd,usd_jpy,gbp_usd,aud_usd,usd_hkd,usd_cny,usd_zar,nzd_usd",
            "20260417,32.1,4.43,1.08,154.2,1.27,0.65,7.82,7.24,18.55,0.59",
            "20260418,32.4,4.46,1.09,155.0,1.28,0.66,7.83,7.25,18.50,0.60",
        ]
    )
    provider = TaifexDailyFxRateProvider(session=_FakeSession(csv_text.encode("utf-8")), cache_ttl_seconds=0)

    payload = provider.fetch_latest_rates()
    rates = {item["from_currency"]: item["rate"] for item in payload["rates"]}

    assert payload["snapshot_date"] == "2026-04-18"
    assert payload["source"] == "taifex_daily_reference"
    assert rates["USD"] == pytest.approx(32.4)
    assert rates["EUR"] == pytest.approx(35.316)
    assert rates["JPY"] == pytest.approx(0.209032, abs=1e-6)
    assert rates["HKD"] == pytest.approx(4.137931, abs=1e-6)
    assert rates["CNY"] == pytest.approx(4.468966, abs=1e-6)
