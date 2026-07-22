import logging

import repositories.fubon_accounts as fubon_accounts_module
from logging_config import configure_logging
from repositories.fubon_accounts import FubonAccountRepository
from security_sanitizer import redact_sensitive_data, redact_sensitive_text


def test_redacts_labeled_and_explicit_credentials():
    secret = "real-password-value"
    message = f'login failed password={secret}, api_key="ABC123", Authorization: Bearer token-value raw={secret}'

    redacted = redact_sensitive_text(message, secrets=[secret])

    assert secret not in redacted
    assert "ABC123" not in redacted
    assert "token-value" not in redacted
    assert redacted.count("****") >= 3


def test_recursive_redaction_covers_runtime_diagnostics():
    result = redact_sensitive_data({
        "password": "secret",
        "nested": {"api_key": "key", "last_error": "token=abc"},
    })
    assert result == {
        "password": "****",
        "nested": {"api_key": "****", "last_error": "token=****"},
    }


def test_fubon_repository_public_shape_never_contains_secret_columns():
    row = {
        "id": 1, "label": "Primary", "user_id": "P123456789",
        "cert_path": "C:/cert/account.pfx", "has_cert_password": 1,
        "password_enc": "encrypted-password", "cert_password_enc": "encrypted-cert",
        "api_key_enc": "encrypted-key", "is_active": 1, "is_enabled": 1,
    }
    public = FubonAccountRepository._public_row(row)
    assert public["has_password"] is True
    assert public["has_cert_password"] is True
    assert public["has_api_key"] is True
    assert not ({"password", "cert_password", "api_key", "password_enc", "cert_password_enc", "api_key_enc"} & public.keys())


def test_decrypted_account_drops_encrypted_source_columns(monkeypatch):
    monkeypatch.setattr(fubon_accounts_module, "decrypt_field", lambda value: f"plain:{value}")
    result = FubonAccountRepository._with_decrypted_secrets({
        "id": 1, "password_enc": "pw", "cert_password_enc": "cert", "api_key_enc": "key",
    })
    assert result["password"] == "plain:pw"
    assert result["api_key"] == "plain:key"
    assert "password_enc" not in result
    assert "api_key_enc" not in result


def test_log_formatter_redacts_credentials(tmp_path):
    logger = logging.getLogger("quantvision.security-log-test")
    logger.handlers.clear()
    logger.propagate = False
    log_path = tmp_path / "security.log"
    configure_logging(logger=logger, log_path=log_path)

    logger.error("login rejected api_key=%s", "TOP-SECRET-KEY")
    for handler in logger.handlers:
        handler.flush()

    content = log_path.read_text(encoding="utf-8")
    assert "TOP-SECRET-KEY" not in content
    assert "api_key=****" in content
    logger.handlers.clear()
