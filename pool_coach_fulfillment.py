"""Pool Coach sandbox fulfillment verification.

Fail-closed helper for the controlled $1 commerce proof. This module does not
enable live checkout. It verifies signed Stripe checkout.session.completed
events and records only the exact sandbox product/amount we are testing.
"""
import os
import sqlite3
import stripe
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
DB_PATH = os.environ.get("DATABASE_PATH", "network.db")
WEBHOOK_SECRET = os.environ.get("POOL_COACH_WEBHOOK_SECRET", "").strip()

def init_pool_coach_store():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS pool_coach_entitlements (
        session_id TEXT PRIMARY KEY,
        payment_intent TEXT,
        amount_total INTEGER NOT NULL,
        currency TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

init_pool_coach_store()

@router.post("/v1/pool-coach/webhook")
@router.post("/api/v1/pool-coach/webhook")
async def pool_coach_webhook(request: Request):
    if not WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Pool Coach webhook verification is not configured")
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")
    if event.get("type") != "checkout.session.completed":
        return {"received": True}

    session = event["data"]["object"]
    metadata = session.get("metadata") or {}
    valid = (
        session.get("livemode") is False
        and session.get("payment_status") == "paid"
        and int(session.get("amount_total") or 0) == 100
        and session.get("currency") == "usd"
        and metadata.get("jakeai_capability") == "pool-coach-autopilot"
        and metadata.get("release_stage") == "sandbox_qa"
    )
    if not valid:
        return {"received": True, "entitled": False}

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT OR REPLACE INTO pool_coach_entitlements
        (session_id,payment_intent,amount_total,currency,status)
        VALUES (?,?,?,?,?)""",
        (session["id"], session.get("payment_intent"), 100, "usd", "sandbox_verified"),
    )
    conn.commit()
    conn.close()
    return {"received": True, "entitled": True}

@router.get("/v1/pool-coach/status")
@router.get("/api/v1/pool-coach/status")
def pool_coach_status(session_id: str):
    if not session_id.startswith("cs_test_") or len(session_id) > 200:
        raise HTTPException(status_code=400, detail="Invalid sandbox checkout session")
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT status,amount_total,currency FROM pool_coach_entitlements WHERE session_id=?",
        (session_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {"verified": False, "status": "pending"}
    return {
        "verified": row[0] == "sandbox_verified",
        "status": row[0],
        "amount_total": row[1],
        "currency": row[2],
        "product": "Pool Coach Autopilot",
        "sandbox": True,
    }

def register_pool_coach_routes(app):
    app.include_router(router)
