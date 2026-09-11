import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

import stripe
from fastapi import Header, HTTPException, Request
from fastapi.responses import RedirectResponse

import main

app = main.app
DB_PATH = main.DB_PATH

# Only products with a verified deliverable are allowed to transact.
COMMERCE_ENABLED = {
    "prod_make_free_00",
    "prod_solar_guide_04",
}


def _init_commerce_tables() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS commerce_orders (
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
    conn.commit()
    conn.close()


def _create_order(product_id: str, amount_cents: int, status: str, source: Optional[str] = None) -> str:
    order_id = f"ord_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO commerce_orders (id, product_id, amount_cents, status, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (order_id, product_id, amount_cents, status, source, now),
    )
    conn.commit()
    conn.close()
    return order_id


def _mark_order_paid(order_id: str, stripe_session_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE commerce_orders SET status = 'paid', stripe_session_id = ?, completed_at = ? WHERE id = ?",
        (stripe_session_id, now, order_id),
    )
    conn.commit()
    conn.close()


def _get_order(order_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM commerce_orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


_init_commerce_tables()

# Remove the legacy checkout routes so the safer flow below is authoritative.
_legacy_paths = {"/v1/checkout/buy/{product_id}", "/v1/checkout/create-session"}
app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) not in _legacy_paths]


@app.get("/v1/checkout/buy/{product_id}")
async def buy_product(
    product_id: str,
    request: Request,
    source: Optional[str] = None,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    product = main.GENESIS_CATALOG.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product_id not in COMMERCE_ENABLED:
        raise HTTPException(status_code=409, detail="Checkout is not active for this product yet")

    amount_cents = int(round(float(product.get("price", 0)) * 100))
    delivery_url = product.get("download_url")
    if not delivery_url:
        raise HTTPException(status_code=409, detail="Product delivery is not configured")

    # Free acquisitions are real commerce events, but never touch Stripe.
    if amount_cents <= 0:
        order_id = _create_order(product_id, 0, "free_claim_complete", source or "direct")
        response = RedirectResponse(url=delivery_url, status_code=303)
        response.set_cookie(
            "jakeai_claim",
            order_id,
            max_age=60 * 60 * 24 * 30,
            secure=True,
            httponly=True,
            samesite="lax",
        )
        return response

    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        raise HTTPException(status_code=503, detail="Payment processor is temporarily unavailable")
    stripe.api_key = secret_key

    order_id = _create_order(product_id, amount_cents, "pending_payment", source or "direct")
    base_url = str(request.base_url).rstrip("/")
    success_url = f"{base_url}/v1/checkout/complete?session_id={{CHECKOUT_SESSION_ID}}&order_id={order_id}"
    cancel_url = f"https://www.jakeaiofficial.com/?payment=cancelled"

    kwargs = {}
    if idempotency_key:
        kwargs["idempotency_key"] = idempotency_key

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": product["title"],
                            "description": product["description"][:250],
                        },
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"jakeai_order_id": order_id, "product_id": product_id},
            **kwargs,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Checkout could not be created: {exc}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE commerce_orders SET stripe_session_id = ? WHERE id = ?",
        (session.id, order_id),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url=session.url, status_code=303)


@app.get("/v1/checkout/complete")
def complete_checkout(session_id: str, order_id: str):
    order = _get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["product_id"] not in COMMERCE_ENABLED:
        raise HTTPException(status_code=409, detail="Product is not enabled for commerce")

    product = main.GENESIS_CATALOG.get(order["product_id"])
    if not product or not product.get("download_url"):
        raise HTTPException(status_code=409, detail="Product delivery is not configured")

    # Idempotent completion: a previously verified order may be delivered again.
    if order["status"] == "paid" and order.get("stripe_session_id") == session_id:
        return RedirectResponse(url=product["download_url"], status_code=303)

    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        raise HTTPException(status_code=503, detail="Payment verification is temporarily unavailable")
    stripe.api_key = secret_key

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Payment verification failed: {exc}")

    metadata = getattr(session, "metadata", {}) or {}
    expected_cents = int(order["amount_cents"])
    if (
        getattr(session, "payment_status", None) != "paid"
        or metadata.get("jakeai_order_id") != order_id
        or metadata.get("product_id") != order["product_id"]
        or int(getattr(session, "amount_total", -1) or -1) != expected_cents
        or str(getattr(session, "currency", "")).lower() != "usd"
    ):
        raise HTTPException(status_code=402, detail="Payment has not been verified for this order")

    _mark_order_paid(order_id, session_id)
    response = RedirectResponse(url=product["download_url"], status_code=303)
    response.set_cookie(
        "jakeai_order",
        order_id,
        max_age=60 * 60 * 24 * 30,
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/v1/commerce/status/{order_id}")
def commerce_status(order_id: str):
    order = _get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_id": order["id"],
        "product_id": order["product_id"],
        "amount_cents": order["amount_cents"],
        "status": order["status"],
        "created_at": order["created_at"],
        "completed_at": order["completed_at"],
    }
