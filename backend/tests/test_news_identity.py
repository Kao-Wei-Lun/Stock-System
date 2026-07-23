from news_identity import (
    canonicalize_news_url,
    news_url_hash,
    resolve_news_provider_id,
)


def test_news_url_identity_removes_tracking_and_normalizes_query_order():
    first = "HTTPS://Example.COM:443/story/?b=2&utm_source=mail&a=1#section"
    second = "https://example.com/story?a=1&b=2"

    assert canonicalize_news_url(first) == "https://example.com/story?a=1&b=2"
    assert news_url_hash(first) == news_url_hash(second)


def test_news_provider_id_supports_top_level_and_nested_payloads():
    assert resolve_news_provider_id({"provider_id": "direct"}) == "direct"
    assert resolve_news_provider_id({"payload": {"guid": "nested"}}) == "nested"
    assert resolve_news_provider_id({}) is None
