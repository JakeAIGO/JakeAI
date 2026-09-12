"""Activation-gated JakeAI merchant crypto checkout integration.

This wrapper extends the existing first-party commerce app with Base/native-USDC
invoice, verification, status, and protected delivery routes. It remains
fail-closed unless *both* CRYPTO_PAYMENTS_ENABLED and CRYPTO_LEGAL_APPROVED are
true. No private key, seed phrase, signing, exchange, customer custody, creator
payout, or third-party money transmission functionality exists here.

Manual compliance review is supported as a deliberately separate control. A
payment first lands in compliance_hold. An authorized reviewer must record a
clear decision for the exact transaction hash, after completing the approved
sanctions/risk procedure, before a second verification can mark the order paid.
"""

from __future__ import annotations

import hmac
import os
import re
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

import commerce_app
from crypto_payment_adapter import (
    BASE_MAINNET_CHAIN_ID,
    BASE_NATIVE_USDC_CONTRACT,
    CryptoPaymentConfig,
    PaymentInvoice,
    PaymentState,
)
from crypto_payment_integration import (
    ComplianceDecision,
    ComplianceProvider,
    SqliteTransactionRegistry,
)
from crypto_payment_rpc import BaseRpcClient, verify_submitted_payment

app = commerce_app.app
DB_PATH = commerce_app.DB_PATH


class CryptoCheckoutRequest(BaseModel):
    acknowledge_irreversible_payment: bool = Field(
        False,
        description="Buyer acknowledges blockchain transfers are irreversible and merchant refund terms govern refunds.",
    )
    source: Optional[str] = Field(default="crypto", max_length=80)


class CryptoVerifyRequest(BaseModel):
    order_id: str = Field(..., min_length=5, max_length=100)
    tx_hash: str = Field(..., min_length=66, max_length=66)


class ComplianceReviewRequest(BaseModel):
    tx_hash: str = Field(..., min_length=66, max_length=66)
    clear: bool
    reviewer: str = Field(..., min_length=1, max_length=120)
    reference: Optional[str] = Field(default=None, max_length=300)
    reason: str = Field(default="", max_length=1000)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _legal_approved() -> bool:
    return os.environ.get("CRYPTO_LEGAL_APPROVED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _crypto_config() -> CryptoPaymentConfig:
    return CryptoPaymentConfig.from_env()


def _require_activation_ready() -> CryptoPaymentConfig:
    config = _crypto_config()
    errors = config.activation_errors()
    if errors:
        raise HTTPException(status_code=503, detail="Crypto checkout configuration is not activation-ready")
    if not config.enabled:
        raise HTTPException(status_code=503, detail="Crypto payments are disabled")
    if not _legal_approved():
        raise HTTPException(status_code=503, detail="Crypto checkout awaits legal/compliance approval")
    return config


def _require_tx_hash(value: str) -> str:
    value = str(value).strip().lower()
    if not re.fullmatch(r"0x[a-f0-9]{64}", value):
        raise HTTPException(status_code=422, detail="Invalid transaction hash")
    return value


def _init_crypto_checkout_tables() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crypto_checkout_orders (
                order_id TEXT PRIMARY KEY,
                amount_usdc TEXT NOT NULL,
                state TEXT NOT NULL,
                tx_hash TEXT,
                compliance_provider TEXT,
                compliance_reference TEXT,
                compliance_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crypto_compliance_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                tx_hash TEXT NOT NULL,
                decision TEXT NOT NULL CHECK(decision IN ('clear', 'deny')),
                reviewer TEXT NOT NULL,
                reference TEXT,
                reason TEXT,
                reviewed_at TEXT NOT NULL,
                UNIQUE(order_id, tx_hash)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_crypto_compliance_order_tx ON crypto_compliance_reviews(order_id, tx_hash)"
        )


class ReviewedComplianceProvider(ComplianceProvider):
    """Reads an explicit human compliance decision for one order/transaction.

    This provider does not itself perform sanctions screening. It only proves
    that an approved review record exists for the exact transaction hash.
    """

    def __init__(self, db_path: str, order_id: str) -> None:
        self.db_path = db_path
        self.order_id = order_id

    def screen(self, *, sender_address: str, tx_hash: str) -> ComplianceDecision:
        del sender_address  # Review binds to the exact transaction hash.
        normalized = _require_tx_hash(tx_hash)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT decision, reviewer, reference, reason
                FROM crypto_compliance_reviews
                WHERE order_id = ? AND tx_hash = ?
                """,
                (self.order_id, normalized),
            ).fetchone()
        if not row:
            return ComplianceDecision(
                clear=False,
                provider="manual-review",
                reason="no approved compliance review exists for this transaction",
            )
        clear = row["decision"] == "clear"
        reference = row["reference"] or f"reviewer:{row['reviewer']}"
        return ComplianceDecision(
            clear=clear,
            provider="manual-review",
            reference=reference,
            reason=row["reason"] or ("manual review cleared" if clear else "manual review denied"),
        )


def _create_crypto_order(product_id: str, amount_cents: int, source: str, merchant_address: str) -> dict:
    order_id = commerce_app._create_order(
        product_id,
        amount_cents,
        "crypto_awaiting_payment",
        source,
    )
    amount_usdc = (Decimal(amount_cents) / Decimal(100)).quantize(Decimal("0.000001"))
    invoice = PaymentInvoice.create(order_id, amount_usdc, merchant_address)
    now = _now()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO crypto_checkout_orders (
                order_id, amount_usdc, state, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, str(invoice.amount_usdc), PaymentState.AWAITING_PAYMENT.value, now, now),
        )
    return {
        "order_id": order_id,
        "amount_usdc": str(invoice.amount_usdc),
        "merchant_address": invoice.merchant_address,
    }


def _get_crypto_order(order_id: str) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM crypto_checkout_orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
    return dict(row) if row else None


def _update_crypto_state(
    order_id: str,
    *,
    state: str,
    tx_hash: Optional[str] = None,
    compliance: Optional[ComplianceDecision] = None,
) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE crypto_checkout_orders
            SET state = ?,
                tx_hash = COALESCE(?, tx_hash),
                compliance_provider = COALESCE(?, compliance_provider),
                compliance_reference = COALESCE(?, compliance_reference),
                compliance_reason = COALESCE(?, compliance_reason),
                updated_at = ?
            WHERE order_id = ?
            """,
            (
                state,
                tx_hash,
                compliance.provider if compliance else None,
                compliance.reference if compliance else None,
                compliance.reason if compliance else None,
                _now(),
                order_id,
            ),
        )


def _mark_crypto_paid(order_id: str, tx_hash: str, compliance: ComplianceDecision) -> None:
    now = _now()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("BEGIN IMMEDIATE")
        crypto_row = conn.execute(
            "SELECT state FROM crypto_checkout_orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
        order_row = conn.execute(
            "SELECT status FROM commerce_orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        if not crypto_row or not order_row:
            raise HTTPException(status_code=404, detail="Crypto order not found")
        conn.execute(
            """
            UPDATE crypto_checkout_orders
            SET state = 'paid', tx_hash = ?, compliance_provider = ?,
                compliance_reference = ?, compliance_reason = ?, updated_at = ?
            WHERE order_id = ?
            """,
            (
                tx_hash,
                compliance.provider,
                compliance.reference,
                compliance.reason,
                now,
                order_id,
            ),
        )
        conn.execute(
            """
            UPDATE commerce_orders
            SET status = 'paid', completed_at = ?
            WHERE id = ?
            """,
            (now, order_id),
        )


def _require_admin_token(provided: Optional[str]) -> None:
    expected = os.environ.get("CRYPTO_ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Crypto compliance administration is not configured")
    candidate = (provided or "").strip()
    if not candidate or not hmac.compare_digest(candidate, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _rpc_client() -> BaseRpcClient:
    rpc_url = os.environ.get("BASE_RPC_URL", "").strip()
    if not rpc_url:
        raise HTTPException(status_code=503, detail="Base RPC verification is not configured")
    try:
        return BaseRpcClient(rpc_url)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Base RPC verification is misconfigured") from exc


_init_crypto_checkout_tables()


@app.post("/v1/checkout/crypto/create/{product_id}")
def create_crypto_checkout(product_id: str, req: CryptoCheckoutRequest):
    config = _require_activation_ready()
    if not req.acknowledge_irreversible_payment:
        raise HTTPException(status_code=422, detail="Blockchain payment acknowledgement is required")
    if not commerce_app.is_product_checkout_enabled(product_id):
        raise HTTPException(status_code=409, detail="Checkout is not active for this product")

    product = commerce_app.main.GENESIS_CATALOG.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    amount_cents = int(round(float(product.get("price", 0)) * 100))
    if amount_cents <= 0:
        raise HTTPException(status_code=409, detail="Crypto checkout is only used for paid products")
    if not config.merchant_address:
        raise HTTPException(status_code=503, detail="Merchant receiving address is not configured")

    created = _create_crypto_order(
        product_id,
        amount_cents,
        req.source or "crypto",
        config.merchant_address,
    )
    return {
        **created,
        "product_id": product_id,
        "price_usd_cents": amount_cents,
        "network": "Base Mainnet",
        "chain_id": BASE_MAINNET_CHAIN_ID,
        "asset": "USDC",
        "token_contract": BASE_NATIVE_USDC_CONTRACT,
        "state": PaymentState.AWAITING_PAYMENT.value,
        "instructions": "Send exactly the stated amount of native USDC on Base to the merchant address, then submit the transaction hash for verification.",
        "warnings": [
            "Do not send bridged USDbC or another token.",
            "Do not use another network.",
            "Blockchain transfers are irreversible; merchant refund terms govern refunds.",
        ],
    }


@app.post("/v1/checkout/crypto/verify")
def verify_crypto_checkout(req: CryptoVerifyRequest):
    config = _require_activation_ready()
    tx_hash = _require_tx_hash(req.tx_hash)
    order = commerce_app._get_order(req.order_id)
    crypto_order = _get_crypto_order(req.order_id)
    if not order or not crypto_order:
        raise HTTPException(status_code=404, detail="Crypto order not found")
    if order["status"] == "paid" and crypto_order.get("tx_hash") == tx_hash:
        return {
            "order_id": req.order_id,
            "state": "paid",
            "tx_hash": tx_hash,
            "delivery_ready": bool(config.auto_fulfill_enabled),
        }
    if order.get("source") not in {"crypto", "crypto-test", "crypto_api"}:
        raise HTTPException(status_code=409, detail="Order was not created for crypto checkout")
    if not config.merchant_address:
        raise HTTPException(status_code=503, detail="Merchant receiving address is not configured")

    amount_usd = Decimal(int(order["amount_cents"])) / Decimal(100)
    invoice = PaymentInvoice.create(req.order_id, amount_usd, config.merchant_address)
    registry = SqliteTransactionRegistry(DB_PATH)
    compliance_provider = ReviewedComplianceProvider(DB_PATH, req.order_id)
    try:
        result = verify_submitted_payment(
            rpc=_rpc_client(),
            config=config,
            invoice=invoice,
            tx_hash=tx_hash,
            compliance_provider=compliance_provider,
            registry=registry,
            minimum_confirmations=max(1, int(os.environ.get("CRYPTO_MIN_CONFIRMATIONS", "2"))),
            usd_fmv=amount_usd,
        )
    except (ValueError, RuntimeError, OSError) as exc:
        _update_crypto_state(req.order_id, state=PaymentState.FAILED.value, tx_hash=tx_hash)
        raise HTTPException(status_code=422, detail=f"Crypto payment could not be verified: {exc}") from exc

    _update_crypto_state(
        req.order_id,
        state=result.validation.state.value,
        tx_hash=result.tx_hash,
        compliance=result.compliance,
    )
    if result.recorded and result.validation.accepted:
        _mark_crypto_paid(req.order_id, result.tx_hash, result.compliance)

    return {
        "order_id": req.order_id,
        "state": "paid" if result.recorded else result.validation.state.value,
        "accepted": result.validation.accepted,
        "reason": result.validation.reason,
        "tx_hash": result.tx_hash,
        "block_number": result.block_number,
        "compliance_provider": result.compliance.provider,
        "compliance_reference": result.compliance.reference,
        "delivery_ready": bool(result.recorded and config.auto_fulfill_enabled),
    }


@app.get("/v1/checkout/crypto/status/{order_id}")
def crypto_checkout_status(order_id: str):
    order = commerce_app._get_order(order_id)
    crypto_order = _get_crypto_order(order_id)
    if not order or not crypto_order:
        raise HTTPException(status_code=404, detail="Crypto order not found")
    return {
        "order_id": order_id,
        "product_id": order["product_id"],
        "price_usd_cents": order["amount_cents"],
        "state": crypto_order["state"],
        "tx_hash": crypto_order["tx_hash"],
        "created_at": crypto_order["created_at"],
        "updated_at": crypto_order["updated_at"],
    }


@app.get("/v1/checkout/crypto/complete/{order_id}")
def complete_crypto_checkout(order_id: str):
    config = _require_activation_ready()
    if not config.auto_fulfill_enabled:
        raise HTTPException(status_code=409, detail="Automatic crypto fulfillment is disabled")
    order = commerce_app._get_order(order_id)
    crypto_order = _get_crypto_order(order_id)
    if not order or not crypto_order:
        raise HTTPException(status_code=404, detail="Crypto order not found")
    if order["status"] != "paid" or crypto_order["state"] != "paid" or not crypto_order["tx_hash"]:
        raise HTTPException(status_code=402, detail="Crypto payment is not verified and cleared")
    product = commerce_app.main.GENESIS_CATALOG.get(order["product_id"])
    if not product or not commerce_app.is_product_checkout_enabled(order["product_id"]):
        raise HTTPException(status_code=409, detail="Product is not enabled for delivery")
    response = RedirectResponse(
        url=commerce_app._delivery_target(order["product_id"], product, order_id),
        status_code=303,
    )
    response.set_cookie(
        "jakeai_order",
        order_id,
        max_age=60 * 60 * 24 * 30,
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return response


@app.post("/v1/admin/crypto/compliance/{order_id}")
def record_crypto_compliance_review(
    order_id: str,
    req: ComplianceReviewRequest,
    admin_token: Optional[str] = Header(default=None, alias="X-JakeAI-Admin-Token"),
):
    _require_admin_token(admin_token)
    tx_hash = _require_tx_hash(req.tx_hash)
    order = commerce_app._get_order(order_id)
    crypto_order = _get_crypto_order(order_id)
    if not order or not crypto_order:
        raise HTTPException(status_code=404, detail="Crypto order not found")
    known_tx = (crypto_order.get("tx_hash") or "").lower()
    if not known_tx or known_tx != tx_hash:
        raise HTTPException(status_code=409, detail="Review transaction does not match the transaction detected for this order")
    decision = "clear" if req.clear else "deny"
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO crypto_compliance_reviews (
                    order_id, tx_hash, decision, reviewer, reference, reason, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    tx_hash,
                    decision,
                    req.reviewer,
                    req.reference,
                    req.reason,
                    _now(),
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="A compliance decision already exists for this order and transaction") from exc
    return {
        "order_id": order_id,
        "tx_hash": tx_hash,
        "decision": decision,
        "reviewer": req.reviewer,
        "reference": req.reference,
        "next_step": "Re-submit the transaction hash to the verification endpoint." if req.clear else "Do not fulfill; follow the approved denied/blocked-payment procedure.",
    }
