from pathlib import Path

import crypto_commerce_app as crypto

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_crypto_product_allowlist_is_fail_closed(monkeypatch):
    monkeypatch.delenv("CRYPTO_PRODUCT_ALLOWLIST", raising=False)
    assert crypto._crypto_product_allowlist() == set()
    assert crypto._crypto_product_allowed("prod_game_qa_autopilot_01") is False


def test_crypto_product_allowlist_accepts_only_named_products(monkeypatch):
    monkeypatch.setenv("CRYPTO_PRODUCT_ALLOWLIST", "prod_one, prod_two")
    assert crypto._crypto_product_allowed("prod_one") is True
    assert crypto._crypto_product_allowed("prod_two") is True
    assert crypto._crypto_product_allowed("prod_three") is False


def test_public_crypto_config_does_not_expose_merchant_address(monkeypatch):
    monkeypatch.setenv("CRYPTO_MERCHANT_ADDRESS", "0x1111111111111111111111111111111111111111")
    payload = crypto.crypto_checkout_public_config()
    assert "merchant_address" not in payload
    assert payload["custody"] is False
    assert payload["exchange"] is False


def test_production_guard_mounts_activation_gated_crypto_runtime():
    guard = read("commerce_guard.py")
    assert "from crypto_commerce_app import app as legacy_app" in guard


def test_customer_checkout_is_unlinked_and_noindex_in_release_candidate():
    page = read("crypto-checkout.html")
    index = read("index.html")
    assert 'name="robots" content="noindex,nofollow,noarchive"' in page
    assert "/api/v1/checkout/crypto/config" in page
    assert "/api/v1/checkout/crypto/create/" in page
    assert "/api/v1/checkout/crypto/verify" in page
    assert "crypto-checkout.html" not in index


def test_crypto_terms_privacy_and_refund_disclosures_are_present():
    terms = read("terms.html")
    refunds = read("refunds.html")
    privacy = read("privacy.html")
    assert "native USDC on Base Mainnet" in terms
    assert "wrong network" in terms.lower()
    assert "Digital-asset payments" in refunds
    assert "public blockchain records" in privacy
    assert "seed phrase" in privacy


def test_canary_is_non_fulfilling_and_requires_external_review_attestation():
    runtime = read("commerce_recovery_app.py")
    assert '"prod_crypto_canary_preview"' in runtime
    assert '"auto_fulfillment": False' in runtime
    assert "attest_external_review_complete" in runtime
    assert "Compliance bridge is limited to the isolated canary order" in runtime
    assert 'path.startswith("/v1/checkout/crypto/")' in runtime
