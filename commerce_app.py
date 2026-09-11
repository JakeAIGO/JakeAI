import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode, urlparse

import stripe
from fastapi import Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

import main

app = main.app
DB_PATH = main.DB_PATH

GAME_QA_PRODUCT_ID = "prod_game_qa_autopilot_01"
GAME_QA_PRODUCT = {
    "title": "Game QA Autopilot v1.0",
    "description": "Practical game QA workflow kit for build fingerprinting, smoke tests, test matrices, edge cases, reproducible bug reports, regression queues, and release-readiness review. Human testing remains required.",
    "category": "gaming-qa-workflow",
    "price": 9.99,
    "download_url": "https://jakeai-secure-delivery-z0syg0.v2.appdeploy.ai/",
    "delivery_mode": "protected_order",
    "vendor_did": "did:a2a:jakeai_core",
}

# Product overlays can be promoted independently of the legacy catalog file while
# still participating in JakeAI's first-party order and verification system.
main.GENESIS_CATALOG[GAME_QA_PRODUCT_ID] = GAME_QA_PRODUCT

# Only products with a verified deliverable are allowed to transact.
COMMERCE_ENABLED = {
    "prod_make_free_00",
    "prod_solar_guide_04",
    GAME_QA_PRODUCT_ID,
}

# The legacy app used wildcard CORS with credentials. The commerce runtime is
# intentionally credential-free and limited to JakeAI browser origins.
app.user_middleware = [m for m in app.user_middleware if m.cls is not CORSMiddleware]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jakeaiofficial.com", "https://www.jakeaiofficial.com"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)


def is_safe_url(url: str) -> bool:
    """Allow delivery only to HTTPS destinations JakeAI has explicitly approved."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme != "https":
        return False
    hostname = (parsed.hostname or "").lower()
    return hostname in {
        "jakeaiofficial.com",
        "www.jakeaiofficial.com",
        "docs.google.com",
        "drive.google.com",
        "jakeai-secure-delivery-z0syg0.v2.appdeploy.ai",
    }


def is_product_checkout_enabled(product_id: str) -> bool:
    p = main.GENESIS_CATALOG.get(product_id)
    if not p:
        return False
    if p.get("requires_metering", False):
        return False
    if product_id not in COMMERCE_ENABLED:
        return False
    return bool(p.get("download_url")) and is_safe_url(p["download_url"])


def _delivery_target(product_id: str, product: dict, order_id: str) -> str:
    url = product["download_url"]
    if product.get("delivery_mode") != "protected_order":
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode({'order_id': order_id, 'product_id': product_id})}"


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
    # Keep the legacy product registry aware of the promoted product without
    # requiring it to own entitlement/delivery logic.
    conn.execute(
        """
        INSERT OR REPLACE INTO products (id, title, description, category, price, endpoint_url, vendor_did)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            GAME_QA_PRODUCT_ID,
            GAME_QA_PRODUCT["title"],
            GAME_QA_PRODUCT["description"],
            GAME_QA_PRODUCT["category"],
            GAME_QA_PRODUCT["price"],
            GAME_QA_PRODUCT["download_url"],
            GAME_QA_PRODUCT["vendor_did"],
        ),
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
    if not is_product_checkout_enabled(product_id):
        raise HTTPException(status_code=409, detail="Checkout is not active for this product yet")

    amount_cents = int(round(float(product.get("price", 0)) * 100))
    delivery_url = product.get("download_url")
    if not delivery_url or not is_safe_url(delivery_url):
        raise HTTPException(status_code=409, detail="Product delivery is not configured safely")

    # Free acquisitions are real commerce events, but never touch Stripe.
    if amount_cents <= 0:
        order_id = _create_order(product_id, 0, "free_claim_complete", source or "direct")
        response = RedirectResponse(url=_delivery_target(product_id, product, order_id), status_code=303)
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
    cancel_url = "https://www.jakeaiofficial.com/?payment=cancelled"

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
    if not is_product_checkout_enabled(order["product_id"]):
        raise HTTPException(status_code=409, detail="Product is not enabled for commerce")

    product = main.GENESIS_CATALOG.get(order["product_id"])
    if not product or not product.get("download_url") or not is_safe_url(product["download_url"]):
        raise HTTPException(status_code=409, detail="Product delivery is not configured safely")

    delivery_target = _delivery_target(order["product_id"], product, order_id)

    # Idempotent completion: a previously verified order may be delivered again.
    if order["status"] == "paid" and order.get("stripe_session_id") == session_id:
        return RedirectResponse(url=delivery_target, status_code=303)

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
    response = RedirectResponse(url=delivery_target, status_code=303)
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
