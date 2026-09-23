"""Fail-closed Shopify -> JakeAI paid-order bridge.

The bridge accepts Shopify orders/paid webhooks only when a dedicated webhook
secret is configured. It verifies the raw-body HMAC before parsing the payload.

For products whose JakeAI delivery already uses the generic protected-order
ledger (Scope Creep Guard and Invoice Nudge), a verified Shopify payment is
converted into the same internal paid-order record used by first-party checkout.

Other products are recorded as verified Shopify payments but remain
fulfillment-pending until their product-specific entitlement adapters support a
non-Stripe source. This prevents a Shopify sale from bypassing JakeAI gates.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

import commerce_app

router = APIRouter()

DB_PATH = commerce_app.COMMERCE_DB_PATH

# Shopify SKU -> canonical JakeAI commerce product / expected unit price / fulfillment policy.
SKU_MAP: dict[str, dict[str, Any]] = {
    "JAI-SCOPE-001": {
        "product_id": commerce_app.SCOPE_CREEP_PRODUCT_ID,
        "amount_cents": 1299,
        "fulfillment": "protected_order",
    },
    "JAI-INVOICE-001": {
        "product_id": commerce_app.INVOICE_NUDGE_PRODUCT_ID,
        "amount_cents": 999,
        "fulfillment": "protected_order",
    },
    "JAI-TATTOO-001": {
        "product_id": "JAI-TATTOO-001",
        "amount_cents": 1999,
        "fulfillment": "human_review",
    },
    "JAI-GUITAR-001-MONTHLY": {
        "product_id": "prod_guitar_coach_monthly",
        "amount_cents": 1999,
        "fulfillment": "product_entitlement_adapter_required",
    },
    "JAI-GUITAR-001-ANNUAL": {
        "product_id": "prod_guitar_coach_annual",
        "amount_cents": 14900,
        "fulfillment": "product_entitlement_adapter_required",
    },
    "JAI-GUITAR-001-SPRINT": {
        "product_id": "prod_guitar_coach_sprint",
        "amount_cents": 3900,
        "fulfillment": "product_entitlement_adapter_required",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _init_tables() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shopify_order_events (
                shopify_order_id TEXT NOT NULL,
                line_key TEXT NOT NULL,
                sku TEXT NOT NULL,
                product_id TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                state TEXT NOT NULL,
                internal_order_id TEXT,
                payload_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (shopify_order_id, line_key)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_shopify_order_events_state "
            "ON shopify_order_events(state)"
        )


_init_tables()


def _secret() -> str:
    return os.environ.get("SHOPIFY_WEBHOOK_SECRET", "").strip()


def _verify_hmac(raw: bytes, supplied: str | None) -> None:
    secret = _secret()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Shopify order bridge is not activated",
        )
    candidate = (supplied or "").strip()
    if not candidate:
        raise HTTPException(status_code=401, detail="Missing Shopify webhook signature")
    expected = base64.b64encode(
        hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()
    ).decode("ascii")
    if not hmac.compare_digest(candidate, expected):
        raise HTTPException(status_code=401, detail="Invalid Shopify webhook signature")


def _money_cents(value: Any) -> int:
    try:
        return int((Decimal(str(value)) * Decimal("100")).quantize(Decimal("1")))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid monetary value") from exc


def _existing(shopify_order_id: str, line_key: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM shopify_order_events
            WHERE shopify_order_id = ? AND line_key = ?
            """,
            (shopify_order_id, line_key),
        ).fetchone()
    return dict(row) if row else None


def _record(
    *,
    shopify_order_id: str,
    line_key: str,
    sku: str,
    product_id: str,
    amount_cents: int,
    state: str,
    payload_hash: str,
    internal_order_id: str | None = None,
) -> None:
    now = _now()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO shopify_order_events (
                shopify_order_id, line_key, sku, product_id, amount_cents,
                state, internal_order_id, payload_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(shopify_order_id, line_key) DO UPDATE SET
                state = excluded.state,
                internal_order_id = COALESCE(
                    shopify_order_events.internal_order_id,
                    excluded.internal_order_id
                ),
                payload_hash = excluded.payload_hash,
                updated_at = excluded.updated_at
            """,
            (
                shopify_order_id,
                line_key,
                sku,
                product_id,
                amount_cents,
                state,
                internal_order_id,
                payload_hash,
                now,
                now,
            ),
        )


def _bridge_protected_order(
    *,
    product_id: str,
    amount_cents: int,
    shopify_order_id: str,
    line_key: str,
) -> str:
    internal_order_id = commerce_app._create_order(
        product_id,
        amount_cents,
        "pending_payment",
        "shopify",
    )
    commerce_app._mark_order_paid(
        internal_order_id,
        f"shopify:{shopify_order_id}:{line_key}",
    )
    return internal_order_id


@router.get("/v1/shopify/bridge/health")
@router.get("/api/v1/shopify/bridge/health")
def shopify_bridge_health():
    return {
        "status": "ready" if bool(_secret()) else "awaiting_activation",
        "hmac_verification": bool(_secret()),
        "automatic_protected_order_fulfillment": [
            commerce_app.SCOPE_CREEP_PRODUCT_ID,
            commerce_app.INVOICE_NUDGE_PRODUCT_ID,
        ],
        "other_products": "verified payments are held for product-specific fulfillment",
    }


@router.post("/v1/shopify/webhooks/orders-paid")
@router.post("/api/v1/shopify/webhooks/orders-paid")
async def shopify_orders_paid(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(
        default=None, alias="X-Shopify-Hmac-Sha256"
    ),
    x_shopify_topic: str | None = Header(default=None, alias="X-Shopify-Topic"),
):
    raw = await request.body()
    _verify_hmac(raw, x_shopify_hmac_sha256)

    if (x_shopify_topic or "").strip().lower() not in {"orders/paid", "orders_paid"}:
        raise HTTPException(status_code=409, detail="Unexpected Shopify webhook topic")

    try:
        order = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Shopify webhook body") from exc

    financial_status = str(order.get("financial_status") or "").lower()
    if financial_status != "paid":
        raise HTTPException(status_code=409, detail="Shopify order is not fully paid")

    shopify_order_id = str(order.get("id") or "").strip()
    if not shopify_order_id:
        raise HTTPException(status_code=422, detail="Shopify order ID is missing")

    payload_hash = hashlib.sha256(raw).hexdigest()
    results: list[dict[str, Any]] = []

    for index, line in enumerate(order.get("line_items") or []):
        sku = str(line.get("sku") or "").strip()
        if not sku or sku not in SKU_MAP:
            continue

        spec = SKU_MAP[sku]
        line_key = str(line.get("id") or f"index-{index}")
        quantity = int(line.get("quantity") or 0)
        if quantity != 1:
            _record(
                shopify_order_id=shopify_order_id,
                line_key=line_key,
                sku=sku,
                product_id=spec["product_id"],
                amount_cents=0,
                state="hold_invalid_quantity",
                payload_hash=payload_hash,
            )
            results.append({"sku": sku, "state": "hold_invalid_quantity"})
            continue

        try:
            amount_cents = _money_cents(line.get("price"))
        except ValueError:
            amount_cents = -1

        if amount_cents != int(spec["amount_cents"]):
            _record(
                shopify_order_id=shopify_order_id,
                line_key=line_key,
                sku=sku,
                product_id=spec["product_id"],
                amount_cents=max(amount_cents, 0),
                state="hold_price_mismatch",
                payload_hash=payload_hash,
            )
            results.append({"sku": sku, "state": "hold_price_mismatch"})
            continue

        previous = _existing(shopify_order_id, line_key)
        if previous and previous.get("state") == "fulfilled_to_jakeai_order":
            results.append(
                {
                    "sku": sku,
                    "state": "already_processed",
                    "internal_order_id": previous.get("internal_order_id"),
                }
            )
            continue

        if spec["fulfillment"] == "protected_order":
            internal_order_id = _bridge_protected_order(
                product_id=spec["product_id"],
                amount_cents=amount_cents,
                shopify_order_id=shopify_order_id,
                line_key=line_key,
            )
            _record(
                shopify_order_id=shopify_order_id,
                line_key=line_key,
                sku=sku,
                product_id=spec["product_id"],
                amount_cents=amount_cents,
                state="fulfilled_to_jakeai_order",
                internal_order_id=internal_order_id,
                payload_hash=payload_hash,
            )
            results.append(
                {
                    "sku": sku,
                    "state": "fulfilled_to_jakeai_order",
                    "internal_order_id": internal_order_id,
                }
            )
        else:
            state = (
                "paid_human_review"
                if spec["fulfillment"] == "human_review"
                else "paid_entitlement_adapter_pending"
            )
            _record(
                shopify_order_id=shopify_order_id,
                line_key=line_key,
                sku=sku,
                product_id=spec["product_id"],
                amount_cents=amount_cents,
                state=state,
                payload_hash=payload_hash,
            )
            results.append({"sku": sku, "state": state})

    return {
        "status": "accepted",
        "shopify_order_id": shopify_order_id,
        "processed": results,
    }


def register_shopify_order_bridge_routes(app) -> None:
    app.include_router(router)
