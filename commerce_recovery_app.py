import os
from datetime import datetime, timezone

import stripe
from fastapi import Request

import commerce_app
from crypto_commerce_app import app


def _metadata_dict(session):
    metadata = getattr(session, "metadata", None)
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return metadata
    try:
        return metadata.to_dict()
    except Exception:
        try:
            return dict(metadata)
        except Exception:
            return {}


def _recover_paid_order_from_stripe(order_id: str, session_id: str) -> bool:
    """Rebuild a lost local commerce order only from a fully verified paid Stripe session."""
    secret = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret or not order_id or not session_id:
        return False

    stripe.api_key = secret
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        return False

    metadata = _metadata_dict(session)
    product_id = metadata.get("product_id")
    product = commerce_app.main.GENESIS_CATALOG.get(product_id) if product_id else None
    if not product:
        return False

    expected_amount = int(round(float(product.get("price", 0)) * 100))
    paid = getattr(session, "payment_status", None) == "paid"
    metadata_matches = metadata.get("jakeai_order_id") == order_id
    amount_matches = int(getattr(session, "amount_total", -1) or -1) == expected_amount
    currency_matches = str(getattr(session, "currency", "")).lower() == "usd"
    if not (paid and metadata_matches and amount_matches and currency_matches):
        return False

    try:
        now = datetime.now(timezone.utc).isoformat()
        conn = commerce_app._commerce_conn()
        conn.execute(
            "INSERT OR IGNORE INTO commerce_orders "
            "(id,product_id,amount_cents,status,stripe_session_id,source,created_at,completed_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                order_id,
                product_id,
                expected_amount,
                "paid",
                session_id,
                "stripe_recovered_after_runtime_restart",
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()
        return commerce_app._get_order(order_id) is not None
    except Exception:
        return False


def _recover_recent_paid_orders_from_stripe(limit: int = 50) -> int:
    secret = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret:
        return 0
    stripe.api_key = secret
    recovered = 0
    try:
        sessions = stripe.checkout.Session.list(status="complete", limit=limit)
    except Exception:
        return 0

    for session in getattr(sessions, "data", []) or []:
        try:
            if getattr(session, "payment_status", None) != "paid":
                continue
            metadata = _metadata_dict(session)
            order_id = metadata.get("jakeai_order_id")
            product_id = metadata.get("product_id")
            if not order_id or not product_id:
                continue
            try:
                if commerce_app._get_order(order_id) is not None:
                    continue
            except Exception:
                pass
            if _recover_paid_order_from_stripe(order_id, getattr(session, "id", "")):
                recovered += 1
        except Exception:
            continue
    return recovered


@app.on_event("startup")
def recover_paid_orders_on_startup():
    try:
        recovered = _recover_recent_paid_orders_from_stripe()
        print(f"Recovered {recovered} verified paid Stripe order(s) from recent checkout history")
    except Exception as exc:
        print(f"Stripe order recovery skipped safely: {exc}")


@app.middleware("http")
async def recover_checkout_order_after_ephemeral_storage_loss(request: Request, call_next):
    if request.url.path == "/v1/checkout/complete":
        order_id = request.query_params.get("order_id", "")
        session_id = request.query_params.get("session_id", "")
        if order_id and session_id:
            try:
                missing = commerce_app._get_order(order_id) is None
            except Exception:
                missing = True
            if missing:
                _recover_paid_order_from_stripe(order_id, session_id)

    return await call_next(request)

# ---------------------------------------------------------------------------
# Genesis #001 private human-review routes
# ---------------------------------------------------------------------------
# Railway boots this module directly (see Dockerfile). Register the review
# surface here so it is guaranteed to exist in the production ASGI app even
# though the underlying review logic remains owned by main.py.
from typing import Optional
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field

legacy_main = commerce_app.main

class GenesisReviewProxyRequest(BaseModel):
    session_id: str = Field(min_length=5, max_length=200)

_REVIEW_PATHS = {
    "/v1/genesis/001/review/health",
    "/v1/genesis/001/review/pending",
    "/v1/genesis/001/review/accept",
    "/v1/genesis/001/review/decline-refund",
    "/api/v1/genesis/001/review/health",
    "/api/v1/genesis/001/review/pending",
    "/api/v1/genesis/001/review/accept",
    "/api/v1/genesis/001/review/decline-refund",
}
# Remove any earlier copies of these routes from the shared FastAPI app and
# re-register them at the actual Railway entrypoint.
app.router.routes[:] = [
    route for route in app.router.routes
    if getattr(route, "path", None) not in _REVIEW_PATHS
]

def _review_handler(name: str):
    handler = getattr(legacy_main, name, None)
    if not callable(handler):
        raise HTTPException(status_code=503, detail="Genesis review backend is not loaded in this deployment")
    return handler

@app.get("/v1/genesis/001/review/health")
@app.get("/api/v1/genesis/001/review/health")
def genesis_review_health_runtime():
    names = (
        "genesis_001_pending_review",
        "genesis_001_accept",
        "genesis_001_decline_refund",
    )
    handlers = {name: callable(getattr(legacy_main, name, None)) for name in names}
    return {
        "status": "ready" if all(handlers.values()) else "incomplete",
        "runtime": "commerce_recovery_app",
        "handlers": handlers,
    }

@app.get("/v1/genesis/001/review/pending")
@app.get("/api/v1/genesis/001/review/pending")
def genesis_review_pending_runtime(
    x_genesis_admin_token: Optional[str] = Header(None, alias="X-Genesis-Admin-Token"),
):
    return _review_handler("genesis_001_pending_review")(x_genesis_admin_token)

@app.post("/v1/genesis/001/review/accept")
@app.post("/api/v1/genesis/001/review/accept")
def genesis_review_accept_runtime(
    req: GenesisReviewProxyRequest,
    x_genesis_admin_token: Optional[str] = Header(None, alias="X-Genesis-Admin-Token"),
):
    return _review_handler("genesis_001_accept")(req, x_genesis_admin_token)

@app.post("/v1/genesis/001/review/decline-refund")
@app.post("/api/v1/genesis/001/review/decline-refund")
def genesis_review_decline_refund_runtime(
    req: GenesisReviewProxyRequest,
    x_genesis_admin_token: Optional[str] = Header(None, alias="X-Genesis-Admin-Token"),
):
    return _review_handler("genesis_001_decline_refund")(req, x_genesis_admin_token)


# ---------------------------------------------------------------------------
# JakeAI Direct subscription / entitlement routes (gated by environment vars)
# ---------------------------------------------------------------------------
from direct_billing import register_direct_routes
register_direct_routes(app)

from secret_vault import register_secret_vault_routes
register_secret_vault_routes(app)

from unreal_bridge import register_unreal_bridge_routes
register_unreal_bridge_routes(app)
