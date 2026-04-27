from __future__ import annotations


def test_paper_trading_position_size_api_returns_contract_breakdown(client):
    response = client.post(
        "/api/paper-trading/risk/position-size",
        json={
            "product_symbol": "TMF",
            "futures_capital": 100000,
            "initial_margin": 26300,
            "stop_loss_points": 60,
            "stress_points": 2000,
            "margin_usage_limit": 0.6,
            "single_trade_risk_pct": 0.02,
            "total_position_risk_pct": 0.2,
            "user_max_contracts": 10,
        },
    )

    assert response.status_code == 200
    sizing = response.json()["sizing"]
    assert sizing["point_value"] == 10
    assert sizing["maintenance_margin"] == 20150
    assert sizing["margin_contracts"] == 2
    assert sizing["stress_contracts"] == 1
    assert sizing["risk_contracts"] == 3
    assert sizing["suggested_contracts"] == 1


def test_paper_trading_order_validate_blocks_oversized_order(client):
    response = client.post(
        "/api/paper-trading/orders/validate",
        json={
            "product_symbol": "TMF",
            "futures_capital": 100000,
            "initial_margin": 26300,
            "stop_loss_points": 60,
            "stress_points": 2000,
            "margin_usage_limit": 0.6,
            "single_trade_risk_pct": 0.02,
            "total_position_risk_pct": 0.2,
            "user_max_contracts": 10,
            "requested_qty": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["allowed"] is False
    assert payload["allowed_qty"] == 1
    assert payload["deny_reasons"] == ["order_size_exceeded"]
