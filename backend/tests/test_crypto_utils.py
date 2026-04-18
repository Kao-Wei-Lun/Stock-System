from __future__ import annotations

import pytest

import crypto_utils


@pytest.fixture(autouse=True)
def reset_crypto_state(monkeypatch):
    monkeypatch.setenv("APP_ENCRYPT_KEY", "unit-test-encrypt-key")
    crypto_utils._get_fernet.cache_clear()
    yield
    crypto_utils._get_fernet.cache_clear()


def test_encrypt_decrypt_roundtrip():
    plaintext = "my-secret-password"

    ciphertext = crypto_utils.encrypt_field(plaintext)

    assert ciphertext
    assert ciphertext != plaintext
    assert crypto_utils.decrypt_field(ciphertext) == plaintext


def test_encrypt_produces_different_ciphertext():
    first = crypto_utils.encrypt_field("same-plaintext")
    second = crypto_utils.encrypt_field("same-plaintext")

    assert first != second


def test_decrypt_wrong_key_returns_empty(monkeypatch):
    ciphertext = crypto_utils.encrypt_field("secret")

    monkeypatch.setenv("APP_ENCRYPT_KEY", "wrong-key")
    crypto_utils._get_fernet.cache_clear()

    assert crypto_utils.decrypt_field(ciphertext) == ""


def test_encrypt_empty_string():
    assert crypto_utils.encrypt_field("") == ""
    assert crypto_utils.decrypt_field("") == ""


def test_missing_key_raises(monkeypatch):
    monkeypatch.setenv("APP_ENCRYPT_KEY", "")
    crypto_utils._get_fernet.cache_clear()

    with pytest.raises(RuntimeError, match="APP_ENCRYPT_KEY"):
        crypto_utils.encrypt_field("test")
