import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import stripe
from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

DIRECT_PLAN_ID = "direct_founding_edition"
DIRECT_PRICE_CENTS = 2900
DEFAULT_ALLOWANCE_CENTS = 1000
COOKIE_NAME = "jakeai_direct_session"
ACTIVE_STATUSES = {"active", "trialing"}

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _bool_env(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

def _db_path():
    explicit = os.environ.get("DIRECT_DATABASE_PATH", "").strip()
    if explicit:
        return explicit
    catalog = os.environ.get("DATABASE_PATH", "").strip()
    if catalog:
        return os.path.join(os.path.dirname(catalog) or "/tmp", "jakeai-direct.db")
    return "/data/jakeai-direct.db" if os.path.isdir("/data") else "/tmp/jakeai-direct.db"

def _conn():
    path = _db_path()
    os.makedirs(os.path.dirname(path) or "/tmp", exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_direct_db():
    conn = _conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS direct_entitlements(
      stripe_subscription_id TEXT PRIMARY KEY,
      stripe_customer_id TEXT NOT NULL,
      checkout_session_id TEXT,
      customer_email TEXT,
      status TEXT NOT NULL,
      current_period_end INTEGER,
      cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
      allowance_cents INTEGER NOT NULL DEFAULT 1000,
      usage_cents INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS direct_sessions(
      token_hash TEXT PRIMARY KEY,
      stripe_customer_id TEXT NOT NULL,
      stripe_subscription_id TEXT NOT NULL,
      created_at TEXT NOT NULL,
      last_seen_at TEXT NOT NULL,
      revoked_at TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS direct_stripe_events(
      event_id TEXT PRIMARY KEY,
      event_type TEXT NOT NULL,
      created_at TEXT NOT NULL)""")
    conn.commit()
    conn.close()

def _stripe_secret():
    return os.environ.get("DIRECT_STRIPE_SECRET_KEY", "").strip() or os.environ.get("STRIPE_SECRET_KEY", "").strip()

def _stripe_key_mode():
    key = _stripe_secret()
    if "_test_" in key or key.startswith("sk_test") or key.startswith("rk_test"):
        return "test"
    if "_live_" in key or key.startswith("sk_live") or key.startswith("rk_live"):
        return "live"
    return "unknown" if key else "missing"

def _webhook_secret():
    return os.environ.get("DIRECT_STRIPE_WEBHOOK_SECRET", "").strip()

def _price_id():
    return os.environ.get("DIRECT_STRIPE_PRICE_ID", "").strip()

def _expected_livemode():
    return _bool_env("DIRECT_STRIPE_EXPECT_LIVEMODE", False)

def _billing_enabled():
    return _bool_env("DIRECT_BILLING_ENABLED", False)

def _configure_stripe():
    key = _stripe_secret()
    if not key:
        raise HTTPException(503, "Direct payment processor is not configured")
    stripe.api_key = key

def _assert_billing_config():
    if not _billing_enabled():
        raise HTTPException(503, "JakeAI Direct billing is gated")
    if not _price_id():
        raise HTTPException(503, "JakeAI Direct price is not configured")
    _configure_stripe()
    try:
        price = stripe.Price.retrieve(_price_id())
    except Exception as exc:
        raise HTTPException(503, f"Direct price verification failed: {exc}")
    recurring = getattr(price, "recurring", None)
    if not (
        bool(getattr(price, "active", False))
        and bool(getattr(price, "livemode", False)) == _expected_livemode()
        and int(getattr(price, "unit_amount", -1) or -1) == DIRECT_PRICE_CENTS
        and getattr(recurring, "interval", None) == "month"
    ):
        raise HTTPException(503, "Direct price or Stripe environment mismatch")

def _subscription_price_id(subscription):
    try:
        items = getattr(getattr(subscription, "items", None), "data", None) or []
        return getattr(getattr(items[0], "price", None), "id", None) if items else None
    except Exception:
        return None

def _upsert_entitlement(subscription, checkout_session_id=None, customer_email=None, reset_usage=False):
    sub_id = str(getattr(subscription, "id", "") or "")
    customer_id = str(getattr(subscription, "customer", "") or "")
    if not sub_id or not customer_id:
        raise ValueError("subscription identity missing")
    now = _now_iso()
    conn = _conn()
    existing = conn.execute("SELECT usage_cents,created_at FROM direct_entitlements WHERE stripe_subscription_id=?", (sub_id,)).fetchone()
    usage = 0 if reset_usage or existing is None else int(existing["usage_cents"])
    created = now if existing is None else existing["created_at"]
    allowance = int(os.environ.get("DIRECT_USAGE_ALLOWANCE_CENTS", str(DEFAULT_ALLOWANCE_CENTS)))
    conn.execute("""INSERT OR REPLACE INTO direct_entitlements
      (stripe_subscription_id,stripe_customer_id,checkout_session_id,customer_email,status,current_period_end,cancel_at_period_end,allowance_cents,usage_cents,created_at,updated_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
        sub_id,
        customer_id,
        checkout_session_id,
        customer_email,
        str(getattr(subscription, "status", "unknown") or "unknown"),
        int(getattr(subscription, "current_period_end", 0) or 0) or None,
        1 if bool(getattr(subscription, "cancel_at_period_end", False)) else 0,
        allowance,
        usage,
        created,
        now,
    ))
    conn.commit()
    conn.close()

def _issue_session(customer_id, subscription_id):
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    now = _now_iso()
    conn = _conn()
    conn.execute("INSERT INTO direct_sessions(token_hash,stripe_customer_id,stripe_subscription_id,created_at,last_seen_at,revoked_at) VALUES (?,?,?,?,?,NULL)",
                 (digest, customer_id, subscription_id, now, now))
    conn.commit()
    conn.close()
    return raw

def _session_entitlement(request, allow_inactive=False):
    raw = request.cookies.get(COOKIE_NAME, "")
    if not raw:
        raise HTTPException(401, "JakeAI Direct session required")
    digest = hashlib.sha256(raw.encode()).hexdigest()
    conn = _conn()
    row = conn.execute("""SELECT s.stripe_customer_id,s.stripe_subscription_id,s.revoked_at,
                                e.status,e.current_period_end,e.cancel_at_period_end,e.allowance_cents,e.usage_cents
                         FROM direct_sessions s
                         JOIN direct_entitlements e ON e.stripe_subscription_id=s.stripe_subscription_id
                         WHERE s.token_hash=?""", (digest,)).fetchone()
    if row:
        conn.execute("UPDATE direct_sessions SET last_seen_at=? WHERE token_hash=?", (_now_iso(), digest))
        conn.commit()
    conn.close()
    if not row or row["revoked_at"]:
        raise HTTPException(401, "JakeAI Direct session is invalid")
    if not allow_inactive and row["status"] not in ACTIVE_STATUSES:
        raise HTTPException(402, "JakeAI Direct subscription is not active")
    return dict(row)

def _consume_usage(subscription_id, amount_cents):
    if amount_cents <= 0:
        raise HTTPException(400, "Usage amount must be positive")
    conn = _conn()
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute("SELECT status,allowance_cents,usage_cents FROM direct_entitlements WHERE stripe_subscription_id=?",
                       (subscription_id,)).fetchone()
    if not row:
        conn.execute("ROLLBACK"); conn.close()
        raise HTTPException(404, "Direct entitlement not found")
    if row["status"] not in ACTIVE_STATUSES:
        conn.execute("ROLLBACK"); conn.close()
        raise HTTPException(402, "Direct subscription is not active")
    current = int(row["usage_cents"])
    allowance = int(row["allowance_cents"])
    new_usage = current + int(amount_cents)
    if new_usage > allowance:
        conn.execute("ROLLBACK"); conn.close()
        raise HTTPException(402, {"code":"DIRECT_USAGE_LIMIT","allowance_cents":allowance,"usage_cents":current,"requested_cents":amount_cents})
    conn.execute("UPDATE direct_entitlements SET usage_cents=?,updated_at=? WHERE stripe_subscription_id=?",
                 (new_usage, _now_iso(), subscription_id))
    conn.commit()
    conn.close()
    return {"usage_cents":new_usage,"allowance_cents":allowance,"remaining_cents":allowance-new_usage}

def register_direct_routes(app):
    init_direct_db()

    @app.get("/v1/direct/health")
    def direct_health():
        storage = "ready"
        try:
            conn = _conn(); conn.execute("SELECT 1").fetchone(); conn.close()
        except Exception:
            storage = "error"
        return {
            "status":"ready" if storage=="ready" else "degraded",
            "billing_enabled":_billing_enabled(),
            "storage":storage,
            "price_configured":bool(_price_id()),
            "payment_processor_configured":bool(_stripe_secret()),
            "payment_processor_mode":_stripe_key_mode(),
            "webhook_configured":bool(_webhook_secret()),
            "expected_livemode":_expected_livemode(),
            "plan":DIRECT_PLAN_ID,
            "price_cents":DIRECT_PRICE_CENTS,
            "usage_allowance_cents":int(os.environ.get("DIRECT_USAGE_ALLOWANCE_CENTS", str(DEFAULT_ALLOWANCE_CENTS))),
            "automatic_overages":False,
        }

    @app.get("/v1/direct/checkout")
    def direct_checkout(email: Optional[str] = None):
        _assert_billing_config()
        kwargs = {
            "mode":"subscription",
            "line_items":[{"price":_price_id(),"quantity":1}],
            "success_url":"https://jakeaiofficial.com/v1/direct/activate?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url":"https://jakeaiofficial.com/direct/?checkout=cancelled",
            "allow_promotion_codes":False,
            "billing_address_collection":"auto",
            "metadata":{"jakeai_product_id":DIRECT_PLAN_ID},
            "subscription_data":{"metadata":{"jakeai_plan":DIRECT_PLAN_ID,"provider_usage_allowance_usd":"10","automatic_overages":"disabled"}},
        }
        if email:
            kwargs["customer_email"] = email
        try:
            session = stripe.checkout.Session.create(**kwargs)
        except Exception as exc:
            raise HTTPException(400, f"Direct checkout could not be created: {exc}")
        return RedirectResponse(session.url, 303)

    @app.get("/v1/direct/activate")
    def direct_activate(session_id: str):
        _assert_billing_config()
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            subscription = stripe.Subscription.retrieve(session.subscription)
        except Exception as exc:
            raise HTTPException(400, f"Direct activation verification failed: {exc}")
        if getattr(session, "mode", None) != "subscription":
            raise HTTPException(400, "Not a Direct subscription checkout")
        if getattr(session, "payment_status", None) not in {"paid","no_payment_required"}:
            raise HTTPException(402, "Direct subscription payment is not verified")
        if _subscription_price_id(subscription) != _price_id():
            raise HTTPException(409, "Direct subscription price mismatch")
        if getattr(subscription, "status", None) not in ACTIVE_STATUSES:
            raise HTTPException(402, "Direct subscription is not active")
        details = getattr(session, "customer_details", None)
        email = getattr(details, "email", None) if details else None
        _upsert_entitlement(subscription, session_id, email)
        token = _issue_session(str(subscription.customer), str(subscription.id))
        response = RedirectResponse("https://jakeaiofficial.com/direct/app/", 303)
        response.set_cookie(COOKIE_NAME, token, httponly=True, secure=True, samesite="lax", max_age=2592000, path="/")
        return response

    @app.get("/v1/direct/me")
    def direct_me(request: Request):
        row = _session_entitlement(request)
        remaining = max(0, int(row["allowance_cents"]) - int(row["usage_cents"]))
        return {
            "plan":DIRECT_PLAN_ID,
            "subscription_status":row["status"],
            "cancel_at_period_end":bool(row["cancel_at_period_end"]),
            "current_period_end":row["current_period_end"],
            "usage_allowance_cents":row["allowance_cents"],
            "usage_cents":row["usage_cents"],
            "remaining_cents":remaining,
            "automatic_overages":False,
        }

    @app.get("/v1/direct/portal")
    def direct_portal(request: Request):
        _assert_billing_config()
        row = _session_entitlement(request, allow_inactive=True)
        try:
            portal = stripe.billing_portal.Session.create(customer=row["stripe_customer_id"], return_url="https://jakeaiofficial.com/direct/app/")
        except Exception as exc:
            raise HTTPException(400, f"Direct billing portal could not be created: {exc}")
        return RedirectResponse(portal.url, 303)

    @app.post("/v1/direct/logout")
    def direct_logout(request: Request):
        raw = request.cookies.get(COOKIE_NAME, "")
        if raw:
            digest = hashlib.sha256(raw.encode()).hexdigest()
            conn = _conn()
            conn.execute("UPDATE direct_sessions SET revoked_at=? WHERE token_hash=?", (_now_iso(), digest))
            conn.commit(); conn.close()
        response = JSONResponse({"status":"logged_out"})
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    @app.post("/v1/direct/usage/charge")
    def direct_usage_charge(subscription_id: str, amount_cents: int,
                            x_jakeai_internal_token: Optional[str] = Header(None, alias="X-JakeAI-Internal-Token")):
        expected = os.environ.get("DIRECT_INTERNAL_TOKEN", "").strip()
        if not expected or not secrets.compare_digest(x_jakeai_internal_token or "", expected):
            raise HTTPException(403, "Direct internal authorization required")
        return _consume_usage(subscription_id, amount_cents)

    @app.post("/v1/direct/webhook")
    async def direct_webhook(request: Request, stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature")):
        secret = _webhook_secret()
        if not secret:
            raise HTTPException(503, "Direct webhook is not configured")
        payload = await request.body()
        try:
            event = stripe.Webhook.construct_event(payload, stripe_signature or "", secret)
        except Exception:
            raise HTTPException(400, "Invalid Stripe webhook")
        event_id = str(getattr(event, "id", "") or event.get("id", ""))
        event_type = str(getattr(event, "type", "") or event.get("type", ""))
        if not event_id or not event_type:
            raise HTTPException(400, "Malformed Stripe event")
        conn = _conn()
        duplicate = conn.execute("SELECT 1 FROM direct_stripe_events WHERE event_id=?", (event_id,)).fetchone()
        if duplicate:
            conn.close()
            return {"received":True,"duplicate":True}
        conn.execute("INSERT INTO direct_stripe_events(event_id,event_type,created_at) VALUES (?,?,?)",
                     (event_id,event_type,_now_iso()))
        conn.commit(); conn.close()

        obj = event.data.object if hasattr(event, "data") else event["data"]["object"]
        try:
            if event_type.startswith("customer.subscription."):
                if _subscription_price_id(obj) == _price_id():
                    _upsert_entitlement(obj)
            elif event_type == "invoice.paid":
                sub_id = getattr(obj, "subscription", None)
                if sub_id:
                    _configure_stripe()
                    sub = stripe.Subscription.retrieve(sub_id)
                    if _subscription_price_id(sub) == _price_id():
                        _upsert_entitlement(sub, reset_usage=True)
            elif event_type == "invoice.payment_failed":
                sub_id = getattr(obj, "subscription", None)
                if sub_id:
                    conn = _conn()
                    conn.execute("UPDATE direct_entitlements SET status='past_due',updated_at=? WHERE stripe_subscription_id=?",
                                 (_now_iso(), str(sub_id)))
                    conn.commit(); conn.close()
        except Exception as exc:
            raise HTTPException(500, f"Direct webhook processing failed: {exc}")
        return {"received":True,"duplicate":False}
