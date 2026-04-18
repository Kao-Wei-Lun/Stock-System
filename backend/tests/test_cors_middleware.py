def test_cors_preflight_allows_expected_headers(client):
    response = client.options(
        "/api/settings/fubon-accounts",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization,x-requested-with",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    allowed_headers = {
        header.strip().lower()
        for header in response.headers["access-control-allow-headers"].split(",")
    }

    assert "*" not in allowed_headers
    assert "content-type" in allowed_headers
    assert "authorization" in allowed_headers
    assert "x-requested-with" in allowed_headers
