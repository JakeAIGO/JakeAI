import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()
COOKIE_NAME = "jakeai_library_session"
CREDITS_PER_DOLLAR = 100
MAX_BALANCE_CREDITS = 10000
MAX_DAILY_LOAD_CREDITS = 5000
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://jakeaiofficial.com").rstrip("/")

PACKS = {
    "starter_500": {"credits": 500, "price_cents": 500, "label": "500 credits", "price_env": "CREDITS_PRICE_500"},
    "plus_1100": {"credits": 1100, "price_cents": 1000, "label": "1,100 credits", "price_env": "CREDITS_PRICE_1100"},
    "universe_2400": {"credits": 2400, "price_cents": 2000, "label": "2,400 credits", "price_env": "CREDITS_PRICE_2400"},
}
REDEEMABLE_PRODUCTS = {
    "JAE-TTM-001": {"title": "The Time Machine — JakeAI Edition", "credits": 50, "active": False, "delivery_url": "/editions/time-machine.html"},
}

class CheckoutRequest(BaseModel):
    pack_id: str
class ActivateRequest(BaseModel):
    session_id: str
class RedeemRequest(BaseModel):
    product_id: str

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _bool_env(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

def _db_path():
    explicit = os.environ.get("CREDITS_DATABASE_PATH", "").strip()
    if explicit:
        return explicit
    shared = os.environ.get("DATABASE_PATH", "").strip()
    if shared:
        return shared
    return "/data/network.db" if os.path.isdir("/data") else "/tmp/jakeai-credits.db"

def _conn():
    path = _db_path()
    os.makedirs(os.path.dirname(path) or "/tmp", exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_credit_store():
    conn = _conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS credit_accounts(
        account_id TEXT PRIMARY KEY,
        stripe_customer_id TEXT UNIQUE,
        customer_email TEXT,
        purchased_credits INTEGER NOT NULL DEFAULT 0,
        promotional_credits INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL)""")
    conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_accounts_email
        ON credit_accounts(lower(customer_email)) WHERE customer_email IS NOT NULL""")
    conn.execute("""CREATE TABLE IF NOT EXISTS credit_events(
        event_id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        bucket TEXT NOT NULL,
        delta INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        reference TEXT,
        created_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS credit_checkout_sessions(
        checkout_session_id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        stripe_customer_id TEXT,
        customer_email TEXT,
        pack_id TEXT NOT NULL,
        credits INTEGER NOT NULL,
        amount_total INTEGER NOT NULL,
        currency TEXT NOT NULL,
        payment_status TEXT NOT NULL,
        grant_status TEXT NOT NULL,
        created_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS credit_entitlements(
        account_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        title TEXT NOT NULL,
        source_event_id TEXT NOT NULL,
        delivery_url TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY(account_id, product_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS credit_sessions(
        token_hash TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        revoked_at TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS credit_stripe_events(
        event_id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        created_at TEXT NOT NULL)""")
    conn.commit()
    conn.close()

init_credit_store()

def _topups_enabled():
    return _bool_env("CREDITS_LIVE_TOPUPS_ENABLED", False)
def _stripe_key():
    return os.environ.get("STRIPE_SECRET_KEY", "").strip()
def _webhook_secret():
    return os.environ.get("CREDITS_STRIPE_WEBHOOK_SECRET", "").strip()
def _expected_livemode():
    return _bool_env("CREDITS_STRIPE_EXPECT_LIVEMODE", True)
def _pack_price_id(pack):
    return os.environ.get(pack["price_env"], "").strip()
def _public_topup_ready():
    return bool(_topups_enabled() and _stripe_key() and _webhook_secret() and all(_pack_price_id(p) for p in PACKS.values()))
def _normalize_email(value):
    return str(value or "").strip().lower()[:320]
def _new_account_id():
    return "jac_" + secrets.token_urlsafe(18)

def _get_or_create_account(customer_id, email):
    email = _normalize_email(email)
    now = _now_iso()
    conn = _conn()
    row = None
    if customer_id:
        row = conn.execute("SELECT * FROM credit_accounts WHERE stripe_customer_id=?", (customer_id,)).fetchone()
    if row is None and email:
        row = conn.execute("SELECT * FROM credit_accounts WHERE lower(customer_email)=?", (email,)).fetchone()
    if row is None:
        account_id = _new_account_id()
        conn.execute("""INSERT INTO credit_accounts
            (account_id,stripe_customer_id,customer_email,created_at,updated_at)
            VALUES (?,?,?,?,?)""", (account_id, customer_id or None, email or None, now, now))
    else:
        account_id = row["account_id"]
        conn.execute("""UPDATE credit_accounts SET stripe_customer_id=COALESCE(stripe_customer_id,?),
            customer_email=COALESCE(customer_email,?),updated_at=? WHERE account_id=?""",
            (customer_id or None, email or None, now, account_id))
    conn.commit()
    conn.close()
    return account_id

def _record_event(conn, event_id, account_id, bucket, delta, event_type, reference=None):
    conn.execute("""INSERT INTO credit_events
        (event_id,account_id,bucket,delta,event_type,reference,created_at)
        VALUES (?,?,?,?,?,?,?)""", (event_id, account_id, bucket, int(delta), event_type, reference, _now_iso()))

def _issue_session(account_id):
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    now = _now_iso()
    conn = _conn()
    conn.execute("""INSERT INTO credit_sessions
        (token_hash,account_id,created_at,last_seen_at,revoked_at) VALUES (?,?,?,?,NULL)""",
        (digest, account_id, now, now))
    conn.commit()
    conn.close()
    return raw

def _account_from_request(request):
    raw = request.cookies.get(COOKIE_NAME, "")
    if not raw:
        return None
    digest = hashlib.sha256(raw.encode()).hexdigest()
    conn = _conn()
    row = conn.execute("""SELECT a.* FROM credit_sessions s
        JOIN credit_accounts a ON a.account_id=s.account_id
        WHERE s.token_hash=? AND s.revoked_at IS NULL""", (digest,)).fetchone()
    if row:
        conn.execute("UPDATE credit_sessions SET last_seen_at=? WHERE token_hash=?", (_now_iso(), digest))
        conn.commit()
    conn.close()
    return row

def _set_session_cookie(response, raw):
    response.set_cookie(COOKIE_NAME, raw, max_age=60*60*24*365, httponly=True, secure=True, samesite="lax", path="/")

def _balance_payload(row):
    purchased = int(row["purchased_credits"] or 0)
    promo = int(row["promotional_credits"] or 0)
    return {"purchased_credits": purchased, "promotional_credits": promo, "total_credits": purchased+promo, "max_balance_credits": MAX_BALANCE_CREDITS}

@router.get("/v1/credits/program")
@router.get("/api/v1/credits/program")
def credits_program():
    return {
        "program":"JakeAI Credits",
        "status":"live" if _public_topup_ready() else "ledger_live_topups_gated",
        "territory":"United States",
        "closed_loop":True,
        "redeemable_only_for":"JakeAI first-party goods and services",
        "transferable":False,
        "cash_redeemable":False,
        "cash_redemption_exception":"Where applicable law requires cash redemption or refund.",
        "expiration":None,
        "inactivity_fees":False,
        "service_fees":False,
        "credit_unit":"redemption unit; not a bank deposit, cryptocurrency, or investment",
        "max_balance_credits":MAX_BALANCE_CREDITS,
        "max_daily_load_credits":MAX_DAILY_LOAD_CREDITS,
        "paid_topups_enabled":_public_topup_ready(),
        "packs":[{"id":pid,"credits":p["credits"],"price_usd":p["price_cents"]/100,"available":_public_topup_ready()} for pid,p in PACKS.items()],
        "promotional_credits":{"supported":True,"tracked_separately":True,"purchasable":False},
        "library_url":f"{PUBLIC_BASE_URL}/library.html",
    }

@router.get("/v1/credits/me")
@router.get("/api/v1/credits/me")
def credits_me(request: Request):
    account = _account_from_request(request)
    if account is None:
        return {"authenticated":False,"balance":{"purchased_credits":0,"promotional_credits":0,"total_credits":0,"max_balance_credits":MAX_BALANCE_CREDITS},"entitlements":[]}
    conn = _conn()
    entitlements = [dict(r) for r in conn.execute("""SELECT product_id,title,delivery_url,created_at
        FROM credit_entitlements WHERE account_id=? ORDER BY created_at DESC""", (account["account_id"],)).fetchall()]
    conn.close()
    return {"authenticated":True,"email":account["customer_email"],"balance":_balance_payload(account),"entitlements":entitlements}

@router.post("/v1/credits/checkout")
@router.post("/api/v1/credits/checkout")
def create_credit_checkout(body: CheckoutRequest, request: Request):
    if not _public_topup_ready():
        raise HTTPException(status_code=503, detail={"status":"gated","reason":"Paid JakeAI Credits remain disabled until the payment-program compliance gate is cleared."})
    pack = PACKS.get(body.pack_id)
    if not pack:
        raise HTTPException(404, "Unknown credit pack")
    price_id = _pack_price_id(pack)
    stripe.api_key = _stripe_key()
    account = _account_from_request(request)
    metadata = {"jakeai_program":"credits","pack_id":body.pack_id,"credits":str(pack["credits"]),"expected_amount_cents":str(pack["price_cents"])}
    if account is not None:
        metadata["account_id"] = account["account_id"]
    session = stripe.checkout.Session.create(mode="payment",line_items=[{"price":price_id,"quantity":1}],
        success_url=f"{PUBLIC_BASE_URL}/library.html?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{PUBLIC_BASE_URL}/credits.html?checkout=cancelled",
        customer_creation="always",billing_address_collection="required",allow_promotion_codes=False,
        metadata=metadata,payment_intent_data={"metadata":metadata})
    return {"checkout_url":session.url,"session_id":session.id}

@router.post("/v1/credits/webhook")
@router.post("/api/v1/credits/webhook")
async def credits_webhook(request: Request):
    if not _public_topup_ready():
        raise HTTPException(status_code=503, detail="JakeAI Credits paid top-ups are gated")
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, _webhook_secret())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    if not event_id:
        raise HTTPException(status_code=400, detail="Stripe event id missing")
    conn = _conn()
    seen = conn.execute("SELECT event_id FROM credit_stripe_events WHERE event_id=?", (event_id,)).fetchone()
    if seen:
        conn.close()
        return {"received":True,"duplicate":True}
    conn.close()
    if event_type != "checkout.session.completed":
        conn = _conn()
        conn.execute("INSERT INTO credit_stripe_events(event_id,event_type,created_at) VALUES (?,?,?)",(event_id,event_type,_now_iso()))
        conn.commit(); conn.close()
        return {"received":True}
    session = event["data"]["object"]
    metadata = session.get("metadata") or {}
    if metadata.get("jakeai_program") != "credits":
        conn = _conn()
        conn.execute("INSERT INTO credit_stripe_events(event_id,event_type,created_at) VALUES (?,?,?)",(event_id,event_type,_now_iso()))
        conn.commit(); conn.close()
        return {"received":True,"credits":False}
    pack_id = metadata.get("pack_id")
    pack = PACKS.get(pack_id)
    if not pack:
        raise HTTPException(status_code=400, detail="Unknown credits pack in signed event")
    valid = (bool(session.get("livemode")) == _expected_livemode() and session.get("payment_status") == "paid"
        and session.get("currency") == "usd" and int(session.get("amount_total") or 0) == pack["price_cents"]
        and metadata.get("credits") == str(pack["credits"]) and metadata.get("expected_amount_cents") == str(pack["price_cents"]))
    if not valid:
        raise HTTPException(status_code=400, detail="Signed credits checkout did not match the approved pack")
    details = session.get("customer_details") or {}
    email = _normalize_email(details.get("email"))
    address = details.get("address") or {}
    country = str(address.get("country") or "").upper()
    if country and country != "US":
        raise HTTPException(status_code=409, detail="JakeAI Credits launch is U.S.-only")
    customer_id = str(session.get("customer") or "")
    account_id = str(metadata.get("account_id") or "") or _get_or_create_account(customer_id,email)
    if metadata.get("account_id"):
        c = _conn(); row = c.execute("SELECT * FROM credit_accounts WHERE account_id=?",(account_id,)).fetchone(); c.close()
        if row is None:
            account_id = _get_or_create_account(customer_id,email)
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT purchased_credits,promotional_credits FROM credit_accounts WHERE account_id=?",(account_id,)).fetchone()
        if row is None:
            raise RuntimeError("credit account missing")
        current_total = int(row["purchased_credits"]) + int(row["promotional_credits"])
        if current_total + pack["credits"] > MAX_BALANCE_CREDITS:
            raise HTTPException(status_code=409, detail="Credit balance cap would be exceeded")
        today_load = conn.execute("""SELECT COALESCE(SUM(delta),0) AS loaded FROM credit_events
            WHERE account_id=? AND bucket='purchased' AND delta>0 AND event_type='stripe_topup'
            AND substr(created_at,1,10)=substr(?,1,10)""",(account_id,_now_iso())).fetchone()["loaded"]
        if int(today_load or 0) + pack["credits"] > MAX_DAILY_LOAD_CREDITS:
            raise HTTPException(status_code=409, detail="Daily credit load cap would be exceeded")
        event_ref = "stripe:" + str(session.get("id"))
        already = conn.execute("SELECT event_id FROM credit_events WHERE reference=?",(event_ref,)).fetchone()
        if not already:
            conn.execute("UPDATE credit_accounts SET purchased_credits=purchased_credits+?,updated_at=? WHERE account_id=?",(pack["credits"],_now_iso(),account_id))
            _record_event(conn,"cred_"+event_id,account_id,"purchased",pack["credits"],"stripe_topup",event_ref)
        conn.execute("""INSERT OR REPLACE INTO credit_checkout_sessions
            (checkout_session_id,account_id,stripe_customer_id,customer_email,pack_id,credits,amount_total,currency,payment_status,grant_status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",(str(session.get("id")),account_id,customer_id or None,email or None,pack_id,pack["credits"],pack["price_cents"],"usd","paid","granted",_now_iso()))
        conn.execute("INSERT INTO credit_stripe_events(event_id,event_type,created_at) VALUES (?,?,?)",(event_id,event_type,_now_iso()))
        conn.commit()
    except Exception:
        conn.rollback(); conn.close(); raise
    conn.close()
    return {"received":True,"credits":True}

@router.post("/v1/credits/activate")
@router.post("/api/v1/credits/activate")
def activate_credit_session(body: ActivateRequest):
    session_id = str(body.session_id or "").strip()
    if not session_id.startswith("cs_") or len(session_id)>220:
        raise HTTPException(400, "Invalid checkout session")
    conn = _conn()
    row = conn.execute("SELECT account_id,grant_status FROM credit_checkout_sessions WHERE checkout_session_id=?",(session_id,)).fetchone()
    conn.close()
    if not row or row["grant_status"]!="granted":
        return JSONResponse({"activated":False,"status":"pending"},status_code=202)
    raw = _issue_session(row["account_id"])
    response = JSONResponse({"activated":True,"status":"ready"})
    _set_session_cookie(response,raw)
    return response

@router.post("/v1/credits/redeem")
@router.post("/api/v1/credits/redeem")
def redeem_credits(body: RedeemRequest, request: Request):
    account = _account_from_request(request)
    if account is None:
        raise HTTPException(401, "My Library session required")
    product = REDEEMABLE_PRODUCTS.get(body.product_id)
    if not product:
        raise HTTPException(404, "Unknown JakeAI Credits product")
    if not product["active"]:
        raise HTTPException(503, "This edition is still at the fulfillment QA gate and cannot consume credits yet.")
    conn = _conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT product_id FROM credit_entitlements WHERE account_id=? AND product_id=?",(account["account_id"],body.product_id)).fetchone()
        if existing:
            conn.rollback(); conn.close()
            return {"redeemed":True,"already_owned":True,"delivery_url":product["delivery_url"]}
        row = conn.execute("SELECT purchased_credits,promotional_credits FROM credit_accounts WHERE account_id=?",(account["account_id"],)).fetchone()
        cost = int(product["credits"]); promo=int(row["promotional_credits"]); purchased=int(row["purchased_credits"])
        if promo+purchased<cost:
            raise HTTPException(402, "Not enough JakeAI Credits")
        promo_used=min(promo,cost); purchased_used=cost-promo_used
        if promo_used:
            conn.execute("UPDATE credit_accounts SET promotional_credits=promotional_credits-?,updated_at=? WHERE account_id=?",(promo_used,_now_iso(),account["account_id"]))
        if purchased_used:
            conn.execute("UPDATE credit_accounts SET purchased_credits=purchased_credits-?,updated_at=? WHERE account_id=?",(purchased_used,_now_iso(),account["account_id"]))
        redeem_id="redeem_"+secrets.token_urlsafe(16)
        if promo_used: _record_event(conn,redeem_id+"_promo",account["account_id"],"promotional",-promo_used,"redemption",body.product_id)
        if purchased_used: _record_event(conn,redeem_id+"_purchased",account["account_id"],"purchased",-purchased_used,"redemption",body.product_id)
        conn.execute("""INSERT INTO credit_entitlements
            (account_id,product_id,title,source_event_id,delivery_url,created_at) VALUES (?,?,?,?,?,?)""",
            (account["account_id"],body.product_id,product["title"],redeem_id,product["delivery_url"],_now_iso()))
        conn.commit()
    except Exception:
        conn.rollback(); conn.close(); raise
    conn.close()
    return {"redeemed":True,"already_owned":False,"delivery_url":product["delivery_url"]}

def register_credit_routes(app):
    app.include_router(router)
