import sqlite3

import pytest
from fastapi import HTTPException

import commerce_app
import crypto_commerce_app as crypto
from crypto_commerce_app import ComplianceReviewRequest, ReviewedComplianceProvider


MERCHANT = "0x37e4865315579c160379b538f6d91736b56b64b1"
TX = "0x" + "ab" * 32


def setup_temp_db(monkeypatch, tmp_path):
    db = str(tmp_path / "commerce.sqlite3")
    monkeypatch.setattr(crypto, "DB_PATH", db)
    monkeypatch.setattr(commerce_app, "DB_PATH", db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE commerce_orders (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                status TEXT NOT NULL,
                stripe_session_id TEXT,
                source TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
    crypto._init_crypto_checkout_tables()
    return db


def test_crypto_requires_independent_payment_and_legal_gates(monkeypatch):
    monkeypatch.setenv("CRYPTO_MERCHANT_ADDRESS", MERCHANT)
    monkeypatch.setenv("CRYPTO_PAYMENTS_ENABLED", "false")
    monkeypatch.setenv("CRYPTO_LEGAL_APPROVED", "false")
    with pytest.raises(HTTPException) as exc:
        crypto._require_activation_ready()
    assert exc.value.status_code == 503

    monkeypatch.setenv("CRYPTO_PAYMENTS_ENABLED", "true")
    with pytest.raises(HTTPException) as exc:
        crypto._require_activation_ready()
    assert "legal" in str(exc.value.detail).lower()

    monkeypatch.setenv("CRYPTO_LEGAL_APPROVED", "true")
    config = crypto._require_activation_ready()
    assert config.merchant_address == MERCHANT


def test_crypto_order_uses_configured_merchant_and_persists(monkeypatch, tmp_path):
    setup_temp_db(monkeypatch, tmp_path)
    created = crypto._create_crypto_order("prod_test", 999, "crypto", MERCHANT)
    assert created["merchant_address"] == MERCHANT
    assert created["amount_usdc"] == "9.990000"
    order = commerce_app._get_order(created["order_id"])
    crypto_order = crypto._get_crypto_order(created["order_id"])
    assert order["status"] == "crypto_awaiting_payment"
    assert crypto_order["state"] == "awaiting_payment"


def test_manual_compliance_is_bound_to_exact_detected_transaction(monkeypatch, tmp_path):
    db = setup_temp_db(monkeypatch, tmp_path)
    created = crypto._create_crypto_order("prod_test", 500, "crypto", MERCHANT)
    crypto._update_crypto_state(created["order_id"], state="compliance_hold", tx_hash=TX)

    monkeypatch.setenv("CRYPTO_ADMIN_TOKEN", "unit-test-admin-token")
    result = crypto.record_crypto_compliance_review(
        created["order_id"],
        ComplianceReviewRequest(
            tx_hash=TX,
            clear=True,
            reviewer="unit-test",
            reference="review-123",
            reason="approved test procedure completed",
        ),
        admin_token="unit-test-admin-token",
    )
    assert result["decision"] == "clear"

    provider = ReviewedComplianceProvider(db, created["order_id"])
    decision = provider.screen(sender_address="0x" + "11" * 20, tx_hash=TX)
    assert decision.clear is True
    assert decision.reference == "review-123"


def test_compliance_review_rejects_wrong_transaction(monkeypatch, tmp_path):
    setup_temp_db(monkeypatch, tmp_path)
    created = crypto._create_crypto_order("prod_test", 500, "crypto", MERCHANT)
    crypto._update_crypto_state(created["order_id"], state="compliance_hold", tx_hash=TX)
    monkeypatch.setenv("CRYPTO_ADMIN_TOKEN", "unit-test-admin-token")

    with pytest.raises(HTTPException) as exc:
        crypto.record_crypto_compliance_review(
            created["order_id"],
            ComplianceReviewRequest(
                tx_hash="0x" + "cd" * 32,
                clear=True,
                reviewer="unit-test",
            ),
            admin_token="unit-test-admin-token",
        )
    assert exc.value.status_code == 409


def test_admin_review_fails_closed_without_server_token(monkeypatch):
    monkeypatch.delenv("CRYPTO_ADMIN_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        crypto._require_admin_token("anything")
    assert exc.value.status_code == 503
