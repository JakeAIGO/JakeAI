import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import stripe
from fastapi import Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

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
      customer_email TEXT,
      status TEXT NOT NULL,
      current_period_end INTEGER,
      cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
      allowance_cents INTEGER NOT NULL DEFAULT 1000,
      usage_cents INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS direct_checkout_sessions(
      checkout_session_id TEXT PRIMARY KEY,
      stripe_subscription_id TEXT NOT NULL,
      stripe_customer_id TEXT NOT NULL,
      customer_email TEXT,
      payment_status TEXT NOT NULL,
      created_at TEXT NOT NULL)""")
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

def _price_id():
    return os.environ.get("DIRECT_STRIPE_PRICE_ID", "").strip()

def _payment_link_url():
    return os.environ.get("DIRECT_PAYMENT_LINK_URL", "").strip()

def _payment_link_id():
    return os.environ.get("DIRECT_PAYMENT_LINK_ID", "").strip()

def _object_id(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    return str(getattr(value, "id", "") or "")

def _portal_login_url():
    return os.environ.get("DIRECT_PORTAL_LOGIN_URL", "").strip()

def _webhook_secret():
    return os.environ.get("DIRECT_STRIPE_WEBHOOK_SECRET", "").strip()

def _environment_name():
    return os.environ.get("DIRECT_ENVIRONMENT", "sandbox").strip() or "sandbox"

def _qa_token():
    return os.environ.get("DIRECT_QA_TOKEN", "").strip()

def _billing_enabled():
    return _bool_env("DIRECT_BILLING_ENABLED", False)

def _allowance_cents():
    return int(os.environ.get("DIRECT_USAGE_ALLOWANCE_CENTS", str(DEFAULT_ALLOWANCE_CENTS)))

def _public_billing_ready():
    return bool(_billing_enabled() and _price_id() and _payment_link_url() and _portal_login_url() and _webhook_secret())

def _subscription_price_id(subscription):
    try:
        items = getattr(getattr(subscription, "items", None), "data", None) or []
        if not items:
            return None
        price = getattr(items[0], "price", None)
        if isinstance(price, str):
            return price
        return getattr(price, "id", None)
    except Exception:
        return None

def _invoice_subscription_id(invoice):
    direct = getattr(invoice, "subscription", None)
    if direct:
        return str(direct)
    parent = getattr(invoice, "parent", None)
    details = getattr(parent, "subscription_details", None) if parent else None
    nested = getattr(details, "subscription", None) if details else None
    return str(nested) if nested else ""

def _subscription_period_end(subscription):
    top = getattr(subscription, "current_period_end", None)
    if top:
        return int(top)
    try:
        items = getattr(getattr(subscription, "items", None), "data", None) or []
        value = getattr(items[0], "current_period_end", None) if items else None
        return int(value) if value else None
    except Exception:
        return None

def _upsert_entitlement(subscription, customer_email=None, reset_usage=False):
    if _subscription_price_id(subscription) != _price_id():
        return False
    sub_id = str(getattr(subscription, "id", "") or "")
    customer_id = str(getattr(subscription, "customer", "") or "")
    if not sub_id or not customer_id:
        return False
    now = _now_iso()
    conn = _conn()
    existing = conn.execute(
        "SELECT usage_cents,created_at,customer_email FROM direct_entitlements WHERE stripe_subscription_id=?",
        (sub_id,),
    ).fetchone()
    usage = 0 if reset_usage or existing is None else int(existing["usage_cents"])
    created = now if existing is None else existing["created_at"]
    email = customer_email or (existing["customer_email"] if existing else None)
    conn.execute(
        """INSERT OR REPLACE INTO direct_entitlements
        (stripe_subscription_id,stripe_customer_id,customer_email,status,current_period_end,cancel_at_period_end,
         allowance_cents,usage_cents,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            sub_id,
            customer_id,
            email,
            str(getattr(subscription, "status", "unknown") or "unknown"),
            _subscription_period_end(subscription),
            1 if bool(getattr(subscription, "cancel_at_period_end", False)) else 0,
            _allowance_cents(),
            usage,
            created,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return True

def _persist_checkout(session_id, sub_id, customer_id, email, payment_status):
    if not session_id or not sub_id or not customer_id:
        return False
    conn = _conn()
    entitlement = conn.execute(
        "SELECT stripe_customer_id,status FROM direct_entitlements WHERE stripe_subscription_id=?",
        (sub_id,),
    ).fetchone()
    if not entitlement or entitlement["stripe_customer_id"] != customer_id:
        conn.close()
        return False
    conn.execute(
        """INSERT OR REPLACE INTO direct_checkout_sessions
        (checkout_session_id,stripe_subscription_id,stripe_customer_id,customer_email,payment_status,created_at)
        VALUES (?,?,?,?,?,?)""",
        (session_id, sub_id, customer_id, email, payment_status, _now_iso()),
    )
    conn.execute(
        "UPDATE direct_entitlements SET customer_email=COALESCE(customer_email,?),updated_at=? WHERE stripe_subscription_id=?",
        (email, _now_iso(), sub_id),
    )
    conn.commit()
    conn.close()
    return True

def _store_checkout_session(session):
    metadata = getattr(session, "metadata", None) or {}
    plan = metadata.get("jakeai_product_id") if hasattr(metadata, "get") else None
    link_id = _object_id(getattr(session, "payment_link", None))
    if getattr(session, "mode", None) != "subscription":
        return False
    if plan != DIRECT_PLAN_ID and (not _payment_link_id() or link_id != _payment_link_id()):
        return False

    session_id = _object_id(getattr(session, "id", None))
    sub_id = _object_id(getattr(session, "subscription", None))
    customer_id = _object_id(getattr(session, "customer", None))
    payment_status = str(getattr(session, "payment_status", "") or "")
    details = getattr(session, "customer_details", None)
    email = getattr(details, "email", None) if details else None

    conn = _conn()
    if customer_id and not sub_id:
        row = conn.execute(
            """SELECT stripe_subscription_id FROM direct_entitlements
               WHERE stripe_customer_id=? AND status IN ('active','trialing')
               ORDER BY updated_at DESC LIMIT 1""",
            (customer_id,),
        ).fetchone()
        if row:
            sub_id = row["stripe_subscription_id"]
    if sub_id and not customer_id:
        row = conn.execute(
            "SELECT stripe_customer_id FROM direct_entitlements WHERE stripe_subscription_id=?",
            (sub_id,),
        ).fetchone()
        if row:
            customer_id = row["stripe_customer_id"]
    if customer_id and email:
        conn.execute(
            "UPDATE direct_entitlements SET customer_email=COALESCE(customer_email,?),updated_at=? WHERE stripe_customer_id=?",
            (email, _now_iso(), customer_id),
        )
        conn.commit()
    conn.close()

    return _persist_checkout(session_id, sub_id, customer_id, email, payment_status)

def _issue_session(customer_id, subscription_id):
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    now = _now_iso()
    conn = _conn()
    conn.execute(
        "INSERT INTO direct_sessions(token_hash,stripe_customer_id,stripe_subscription_id,created_at,last_seen_at,revoked_at) VALUES (?,?,?,?,?,NULL)",
        (digest, customer_id, subscription_id, now, now),
    )
    conn.commit()
    conn.close()
    return raw

def _session_entitlement(request, allow_inactive=False):
    raw = request.cookies.get(COOKIE_NAME, "")
    if not raw:
        raise HTTPException(401, "JakeAI Direct session required")
    digest = hashlib.sha256(raw.encode()).hexdigest()
    conn = _conn()
    row = conn.execute(
        """SELECT s.stripe_customer_id,s.stripe_subscription_id,s.revoked_at,
                  e.status,e.current_period_end,e.cancel_at_period_end,e.allowance_cents,e.usage_cents
           FROM direct_sessions s
           JOIN direct_entitlements e ON e.stripe_subscription_id=s.stripe_subscription_id
           WHERE s.token_hash=?""",
        (digest,),
    ).fetchone()
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
    row = conn.execute(
        "SELECT status,allowance_cents,usage_cents FROM direct_entitlements WHERE stripe_subscription_id=?",
        (subscription_id,),
    ).fetchone()
    if not row:
        conn.execute("ROLLBACK")
        conn.close()
        raise HTTPException(404, "Direct entitlement not found")
    if row["status"] not in ACTIVE_STATUSES:
        conn.execute("ROLLBACK")
        conn.close()
        raise HTTPException(402, "Direct subscription is not active")
    current = int(row["usage_cents"])
    allowance = int(row["allowance_cents"])
    new_usage = current + int(amount_cents)
    if new_usage > allowance:
        conn.execute("ROLLBACK")
        conn.close()
        raise HTTPException(
            402,
            {
                "code": "DIRECT_USAGE_LIMIT",
                "allowance_cents": allowance,
                "usage_cents": current,
                "requested_cents": amount_cents,
            },
        )
    conn.execute(
        "UPDATE direct_entitlements SET usage_cents=?,updated_at=? WHERE stripe_subscription_id=?",
        (new_usage, _now_iso(), subscription_id),
    )
    conn.commit()
    conn.close()
    return {"usage_cents": new_usage, "allowance_cents": allowance, "remaining_cents": allowance - new_usage}

def _activation_pending_html(session_id):
    safe = "".join(ch for ch in session_id if ch.isalnum() or ch in "_-")
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <meta http-equiv="refresh" content="2;url=/v1/direct/activate?session_id={safe}">
    <title>Activating JakeAI Direct</title><style>body{{margin:0;background:#050912;color:#eefaff;font-family:system-ui;display:grid;place-items:center;min-height:100vh}}
    main{{max-width:620px;padding:32px;text-align:center}}b{{color:#65ecff}}p{{color:#9eb1c1}}</style></head>
    <body><main><b>JAKEAI DIRECT</b><h1>Finalizing your access…</h1><p>Stripe has completed checkout. JakeAI is waiting for the signed entitlement event. This page will retry automatically.</p></main></body></html>"""

def register_direct_routes(app):
    init_direct_db()

    @app.get("/v1/direct/health")
    def direct_health():
        storage = "ready"
        counts = {"entitlements": 0, "events": 0}
        try:
            conn = _conn()
            conn.execute("SELECT 1").fetchone()
            counts["entitlements"] = int(conn.execute("SELECT COUNT(*) FROM direct_entitlements").fetchone()[0])
            counts["events"] = int(conn.execute("SELECT COUNT(*) FROM direct_stripe_events").fetchone()[0])
            conn.close()
        except Exception:
            storage = "error"
        return {
            "status": "ready" if storage == "ready" else "degraded",
            "billing_enabled": _billing_enabled(),
            "public_billing_ready": _public_billing_ready(),
            "storage": storage,
            "price_configured": bool(_price_id()),
            "payment_link_configured": bool(_payment_link_url()),
            "portal_login_configured": bool(_portal_login_url()),
            "webhook_configured": bool(_webhook_secret()),
            "plan": DIRECT_PLAN_ID,
            "price_cents": DIRECT_PRICE_CENTS,
            "usage_allowance_cents": _allowance_cents(),
            "automatic_overages": False,
            "environment": _environment_name(),
            "event_count": counts["events"],
            "entitlement_count": counts["entitlements"],
        }

    @app.get("/v1/direct/checkout")
    def direct_checkout():
        if not _public_billing_ready():
            raise HTTPException(503, "JakeAI Direct billing is gated")
        return RedirectResponse(_payment_link_url(), 303)

    @app.get("/v1/direct/activate")
    def direct_activate(session_id: str):
        conn = _conn()
        checkout = conn.execute(
            "SELECT * FROM direct_checkout_sessions WHERE checkout_session_id=?",
            (session_id,),
        ).fetchone()
        entitlement = None
        if checkout:
            entitlement = conn.execute(
                "SELECT * FROM direct_entitlements WHERE stripe_subscription_id=?",
                (checkout["stripe_subscription_id"],),
            ).fetchone()
        conn.close()
        if not checkout or not entitlement:
            return HTMLResponse(_activation_pending_html(session_id), status_code=202)
        if checkout["payment_status"] not in {"paid", "no_payment_required"}:
            raise HTTPException(402, "Direct subscription payment is not verified")
        if entitlement["status"] not in ACTIVE_STATUSES:
            raise HTTPException(402, "Direct subscription is not active")
        token = _issue_session(checkout["stripe_customer_id"], checkout["stripe_subscription_id"])
        response = RedirectResponse("https://jakeaiofficial.com/direct/app/", 303)
        response.set_cookie(
            COOKIE_NAME,
            token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=2592000,
            path="/",
        )
        return response

    @app.get("/v1/direct/qa/status")
    def direct_qa_status(token: str):
        if _environment_name().lower() != "sandbox" or _billing_enabled():
            raise HTTPException(404, "Not found")
        expected = _qa_token()
        if not expected or not secrets.compare_digest(token, expected):
            raise HTTPException(404, "Not found")
        conn = _conn()
        checkouts = conn.execute(
            """SELECT checkout_session_id,stripe_subscription_id,stripe_customer_id,customer_email,payment_status,created_at
               FROM direct_checkout_sessions
               ORDER BY created_at DESC LIMIT 10"""
        ).fetchall()
        entitlements = conn.execute(
            """SELECT stripe_subscription_id,stripe_customer_id,customer_email,status,current_period_end,cancel_at_period_end,allowance_cents,usage_cents,created_at,updated_at
               FROM direct_entitlements
               ORDER BY updated_at DESC LIMIT 10"""
        ).fetchall()
        events = conn.execute(
            """SELECT event_id,event_type,created_at FROM direct_stripe_events
               ORDER BY created_at DESC LIMIT 20"""
        ).fetchall()
        conn.close()
        def tail(value, n=8):
            value = str(value or "")
            return value[-n:] if value else None
        return {
            "checkout_count": len(checkouts),
            "entitlement_count": len(entitlements),
            "checkouts": [
                {
                    "session_tail": tail(r["checkout_session_id"]),
                    "subscription_tail": tail(r["stripe_subscription_id"]),
                    "customer_tail": tail(r["stripe_customer_id"]),
                    "email": r["customer_email"],
                    "payment_status": r["payment_status"],
                    "created_at": r["created_at"],
                } for r in checkouts
            ],
            "events": [
                {"event_tail": tail(r["event_id"]), "event_type": r["event_type"], "created_at": r["created_at"]}
                for r in events
            ],
            "entitlements": [
                {
                    "subscription_tail": tail(r["stripe_subscription_id"]),
                    "customer_tail": tail(r["stripe_customer_id"]),
                    "email": r["customer_email"],
                    "status": r["status"],
                    "current_period_end": r["current_period_end"],
                    "cancel_at_period_end": bool(r["cancel_at_period_end"]),
                    "allowance_cents": r["allowance_cents"],
                    "usage_cents": r["usage_cents"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                } for r in entitlements
            ],
        }

    @app.get("/v1/direct/qa/backfill-checkout")
    def direct_qa_backfill_checkout(
        token: str,
        session_id: str,
        subscription_id: str,
        customer_id: str,
        email: str,
    ):
        if _environment_name().lower() != "sandbox" or _billing_enabled():
            raise HTTPException(404, "Not found")
        expected = _qa_token()
        if not expected or not secrets.compare_digest(token, expected):
            raise HTTPException(404, "Not found")
        ok = _persist_checkout(
            session_id,
            subscription_id,
            customer_id,
            email,
            "paid",
        )
        if not ok:
            raise HTTPException(409, "Sandbox checkout does not match an active entitlement")
        return {"ok": True, "environment": "sandbox"}

    @app.get("/v1/direct/qa/activate-latest")
    def direct_qa_activate_latest(token: str):
        if _environment_name().lower() != "sandbox" or _billing_enabled():
            raise HTTPException(404, "Not found")
        expected = _qa_token()
        if not expected or not secrets.compare_digest(token, expected):
            raise HTTPException(404, "Not found")
        conn = _conn()
        row = conn.execute(
            """SELECT c.stripe_customer_id,c.stripe_subscription_id
               FROM direct_checkout_sessions c
               JOIN direct_entitlements e ON e.stripe_subscription_id=c.stripe_subscription_id
               WHERE c.customer_email='jakeai-direct-qa@example.com'
                 AND e.status IN ('active','trialing')
               ORDER BY c.created_at DESC
               LIMIT 1"""
        ).fetchone()
        conn.close()
        if not row:
            raise HTTPException(404, "No sandbox QA entitlement found")
        session_token = _issue_session(row["stripe_customer_id"], row["stripe_subscription_id"])
        response = RedirectResponse("https://jakeaiofficial.com/direct/app/?qa=1", 303)
        response.set_cookie(
            COOKIE_NAME,
            session_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=3600,
            path="/",
        )
        return response

    @app.get("/v1/direct/me")
    def direct_me(request: Request):
        row = _session_entitlement(request)
        remaining = max(0, int(row["allowance_cents"]) - int(row["usage_cents"]))
        return {
            "plan": DIRECT_PLAN_ID,
            "subscription_status": row["status"],
            "cancel_at_period_end": bool(row["cancel_at_period_end"]),
            "current_period_end": row["current_period_end"],
            "usage_allowance_cents": row["allowance_cents"],
            "usage_cents": row["usage_cents"],
            "remaining_cents": remaining,
            "automatic_overages": False,
            "environment": _environment_name(),
        }

    @app.get("/v1/direct/portal")
    def direct_portal(request: Request):
        _session_entitlement(request, allow_inactive=True)
        if not _portal_login_url():
            raise HTTPException(503, "Direct billing portal is not configured")
        return RedirectResponse(_portal_login_url(), 303)

    @app.post("/v1/direct/logout")
    def direct_logout(request: Request):
        raw = request.cookies.get(COOKIE_NAME, "")
        if raw:
            digest = hashlib.sha256(raw.encode()).hexdigest()
            conn = _conn()
            conn.execute("UPDATE direct_sessions SET revoked_at=? WHERE token_hash=?", (_now_iso(), digest))
            conn.commit()
            conn.close()
        response = JSONResponse({"status": "logged_out"})
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    @app.post("/v1/direct/usage/charge")
    def direct_usage_charge(
        subscription_id: str,
        amount_cents: int,
        x_jakeai_internal_token: Optional[str] = Header(None, alias="X-JakeAI-Internal-Token"),
    ):
        expected = os.environ.get("DIRECT_INTERNAL_TOKEN", "").strip()
        if not expected or not secrets.compare_digest(x_jakeai_internal_token or "", expected):
            raise HTTPException(403, "Direct internal authorization required")
        return _consume_usage(subscription_id, amount_cents)

    @app.post("/v1/direct/webhook")
    async def direct_webhook(
        request: Request,
        stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    ):
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
        conn.close()
        if duplicate:
            return {"received": True, "duplicate": True}

        obj = event.data.object if hasattr(event, "data") else event["data"]["object"]
        try:
            if event_type == "checkout.session.completed":
                _store_checkout_session(obj)
            elif event_type.startswith("customer.subscription."):
                _upsert_entitlement(obj)
            elif event_type == "invoice.paid":
                sub_id = _invoice_subscription_id(obj)
                if sub_id:
                    conn = _conn()
                    conn.execute(
                        "UPDATE direct_entitlements SET usage_cents=0,updated_at=? WHERE stripe_subscription_id=?",
                        (_now_iso(), sub_id),
                    )
                    conn.commit()
                    conn.close()
            elif event_type == "invoice.payment_failed":
                sub_id = str(getattr(obj, "subscription", "") or "")
                if sub_id:
                    conn = _conn()
                    conn.execute(
                        "UPDATE direct_entitlements SET status='past_due',updated_at=? WHERE stripe_subscription_id=?",
                        (_now_iso(), sub_id),
                    )
                    conn.commit()
                    conn.close()
        except Exception as exc:
            raise HTTPException(500, f"Direct webhook processing failed: {exc}")

        conn = _conn()
        conn.execute(
            "INSERT INTO direct_stripe_events(event_id,event_type,created_at) VALUES (?,?,?)",
            (event_id, event_type, _now_iso()),
        )
        conn.commit()
        conn.close()
        return {"received": True, "duplicate": False}
