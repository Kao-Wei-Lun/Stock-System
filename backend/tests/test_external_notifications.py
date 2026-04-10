import pytest

from external_notifications import ExternalNotificationDispatcher, build_external_alert_message


def test_build_external_alert_message_includes_trading_context():
    message = build_external_alert_message(
        {
            "title": "AAPL breakout",
            "message": "AAPL price 大於 210 -> 212",
            "payload": {
                "ticker": "AAPL",
                "source": "yahoo_finance",
                "trigger_value": 212,
                "threshold_value": 210,
            },
        }
    )

    assert "[QuantVision] AAPL breakout" in message
    assert "Ticker: AAPL" in message
    assert "Trigger: 212" in message
    assert "Threshold: 210" in message


@pytest.mark.anyio
async def test_external_dispatcher_sends_to_configured_channels():
    calls = []

    def fake_post(url, payload):
        calls.append((url, payload))

    dispatcher = ExternalNotificationDispatcher(
        telegram_bot_token="bot-token",
        telegram_chat_id="chat-id",
        discord_webhook_url="https://discord.com/api/webhooks/test",
        http_post=fake_post,
    )

    delivered = await dispatcher.send_alert(
        {
            "title": "AAPL breakout",
            "message": "AAPL price 大於 210 -> 212",
            "payload": {"ticker": "AAPL"},
        }
    )

    assert delivered == ["telegram", "discord"]
    assert calls[0][0] == "https://api.telegram.org/botbot-token/sendMessage"
    assert calls[0][1]["chat_id"] == "chat-id"
    assert calls[1][0] == "https://discord.com/api/webhooks/test"
    assert "AAPL breakout" in calls[1][1]["content"]
