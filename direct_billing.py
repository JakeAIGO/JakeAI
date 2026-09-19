import hashlib
import json
import math
import os
import secrets
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

import stripe
from fastapi import Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

DIRECT_PLAN_ID = "direct_founding_edition"
DIRECT_PRICE_CENTS = 2900
DEFAULT_ALLOWANCE_CENTS = 1000
COOKIE_NAME = "jakeai_direct_session"
ACTIVE_STATUSES = {"active", "trialing"}
ALLOWED_WORKFLOWS = {"general", "research", "rfp", "proposal", "campaign", "site"}

class DirectRunRequest(BaseModel):
    prompt: str
    workflow: Optional[str] = "general"


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
    conn.execute("""CREATE TABLE IF NOT EXISTS direct_runs(
      run_id TEXT PRIMARY KEY,
      stripe_subscription_id TEXT NOT NULL,
      created_at TEXT NOT NULL,
      workflow TEXT NOT NULL,
      model TEXT NOT NULL,
      prompt_chars INTEGER NOT NULL,
      input_tokens INTEGER NOT NULL DEFAULT 0,
      output_tokens INTEGER NOT NULL DEFAULT 0,
      usage_cents INTEGER NOT NULL DEFAULT 0,
      response_id TEXT,
      status TEXT NOT NULL)""")
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

def _openai_key():
    return os.environ.get("OPENAI_API_KEY", "").strip()

def _runtime_url():
    return os.environ.get("DIRECT_RUNTIME_URL", "").strip()

def _runtime_token():
    return os.environ.get("DIRECT_RUNTIME_INTERNAL_TOKEN", "").strip()

def _execution_configured():
    return bool((_runtime_url() and _runtime_token()) or _openai_key())

def _direct_model():
    return os.environ.get("DIRECT_OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"

def _refund_usage(subscription_id, amount_cents):
    if amount_cents <= 0:
        return
    conn = _conn()
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute(
        "SELECT usage_cents FROM direct_entitlements WHERE stripe_subscription_id=?",
        (subscription_id,),
    ).fetchone()
    if not row:
        conn.execute("ROLLBACK")
        conn.close()
        return
    next_usage = max(0, int(row["usage_cents"]) - int(amount_cents))
    conn.execute(
        "UPDATE direct_entitlements SET usage_cents=?,updated_at=? WHERE stripe_subscription_id=?",
        (next_usage, _now_iso(), subscription_id),
    )
    conn.commit()
    conn.close()

def _record_run(run_id, subscription_id, workflow, model, prompt_chars, input_tokens, output_tokens, usage_cents, response_id, status):
    conn = _conn()
    conn.execute(
        """INSERT OR REPLACE INTO direct_runs
        (run_id,stripe_subscription_id,created_at,workflow,model,prompt_chars,input_tokens,output_tokens,usage_cents,response_id,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            run_id, subscription_id, _now_iso(), workflow, model, int(prompt_chars),
            int(input_tokens or 0), int(output_tokens or 0), int(usage_cents or 0),
            response_id, status,
        ),
    )
    conn.commit()
    conn.close()

def _extract_output_text(data):
    parts = []
    for item in data.get("output", []) or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []) or []:
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(str(content["text"]))
    return "\n".join(parts).strip()

def _workflow_instructions(workflow):
    base = (
        "You are JakeAI Direct, a professional AI orchestration workspace. "
        "Be concise, concrete, and useful. Never claim that you sent, posted, purchased, deployed, "
        "contacted anyone, or changed an external system. External actions always require explicit human approval. "
        "Do not request or expose passwords, API keys, private keys, or access tokens. "
        "When an external action would be useful, prepare a draft or staged plan and clearly label the approval gate."
    )
    modes = {
        "research": " Produce a structured research brief from the information available in the prompt; clearly label unknowns and do not invent sources.",
        "rfp": " Act as an RFP/RFQ analyst. Extract requirements, risks, deadlines, qualification questions, and a packaging checklist.",
        "proposal": " Produce a professional proposal draft with assumptions, scope, evidence gaps, and a clear next-step section.",
        "campaign": " Produce campaign copy and creative direction only. Do not send or publish anything; mark outbound material as awaiting human approval.",
        "site": " Produce a staged website change plan or code-oriented implementation brief. Do not claim deployment; mark release as awaiting human approval.",
        "general": " Solve the user's request directly while respecting the approval gate.",
    }
    return base + modes.get(workflow, modes["general"])

def _call_openai(prompt, workflow):
    runtime_url = _runtime_url()
    runtime_token = _runtime_token()
    if runtime_url and runtime_token:
        payload = {"prompt": prompt, "workflow": workflow}
        req = urllib.request.Request(
            runtime_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "X-JakeAI-Internal-Token": runtime_token,
                "Content-Type": "application/json",
                "User-Agent": "JakeAI-Direct-Commerce/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=55) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise HTTPException(502, "JakeAI Direct runtime rejected the request") from exc
        except Exception as exc:
            raise HTTPException(502, "JakeAI Direct runtime is unavailable") from exc
        text = str(data.get("text") or "").strip()
        if not text:
            raise HTTPException(502, "JakeAI Direct runtime returned no usable model output")
        return {
            "text": text,
            "model": str(data.get("model") or _direct_model()),
            "response_id": str(data.get("response_id") or ""),
            "input_tokens": int(data.get("input_tokens") or 0),
            "output_tokens": int(data.get("output_tokens") or 0),
        }

    key = _openai_key()
    if not key:
        raise HTTPException(503, "JakeAI Direct model runtime is not configured")
    model = _direct_model()
    payload = {
        "model": model,
        "instructions": _workflow_instructions(workflow),
        "input": prompt,
        "max_output_tokens": 1400,
        "reasoning": {"effort": "low"},
        "store": False,
        "metadata": {"product": "jakeai_direct", "workflow": workflow},
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "User-Agent": "JakeAI-Direct/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise HTTPException(502, "JakeAI Direct model provider rejected the request") from exc
    except Exception as exc:
        raise HTTPException(502, "JakeAI Direct model provider is unavailable") from exc
    text = _extract_output_text(data)
    if not text:
        raise HTTPException(502, "JakeAI Direct received no usable model output")
    usage = data.get("usage") or {}
    return {
        "text": text,
        "model": str(data.get("model") or model),
        "response_id": str(data.get("id") or ""),
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
    }

def _rounded_provider_cost_cents(input_tokens, output_tokens):
    input_rate = float(os.environ.get("DIRECT_INPUT_USD_PER_MILLION", "0.20"))
    output_rate = float(os.environ.get("DIRECT_OUTPUT_USD_PER_MILLION", "1.20"))
    usd = (float(input_tokens) * input_rate + float(output_tokens) * output_rate) / 1000000.0
    return max(1, int(math.ceil(usd * 100.0)))

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
        counts = {"entitlements": 0, "events": 0, "active": 0, "pending_cancel": 0}
        try:
            conn = _conn()
            conn.execute("SELECT 1").fetchone()
            counts["entitlements"] = int(conn.execute("SELECT COUNT(*) FROM direct_entitlements").fetchone()[0])
            counts["events"] = int(conn.execute("SELECT COUNT(*) FROM direct_stripe_events").fetchone()[0])
            counts["active"] = int(conn.execute("SELECT COUNT(*) FROM direct_entitlements WHERE status IN ('active','trialing')").fetchone()[0])
            counts["pending_cancel"] = int(conn.execute("SELECT COUNT(*) FROM direct_entitlements WHERE cancel_at_period_end=1 AND status IN ('active','trialing')").fetchone()[0])
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
            "execution_configured": _execution_configured(),
            "execution_mode": "remote_runtime" if (_runtime_url() and _runtime_token()) else ("local_key" if _openai_key() else "disabled"),
            "execution_model": _direct_model(),
            "event_count": counts["events"],
            "entitlement_count": counts["entitlements"],
            "active_entitlement_count": counts["active"],
            "pending_cancellation_count": counts["pending_cancel"],
        }

    @app.get("/v1/direct/qa/runtime-probe-8f2c")
    def direct_runtime_probe():
        if _environment_name() != "sandbox" or _billing_enabled():
            raise HTTPException(404, "Not found")
        run_id = "dir_qa_runtime_20260919"
        conn = _conn()
        prior = conn.execute("SELECT status,model,input_tokens,output_tokens,usage_cents FROM direct_runs WHERE run_id=?", (run_id,)).fetchone()
        if prior and prior["status"] == "complete":
            ent = conn.execute("SELECT usage_cents,allowance_cents FROM direct_entitlements WHERE status IN ('active','trialing') ORDER BY updated_at DESC LIMIT 1").fetchone()
            conn.close()
            return {
                "status": "already_complete",
                "model": prior["model"],
                "input_tokens": prior["input_tokens"],
                "output_tokens": prior["output_tokens"],
                "usage_cents": prior["usage_cents"],
                "remaining_cents": (int(ent["allowance_cents"]) - int(ent["usage_cents"])) if ent else None,
                "approval_gate": "on",
                "external_actions_executed": False,
            }
        ent = conn.execute("SELECT stripe_subscription_id FROM direct_entitlements WHERE status IN ('active','trialing') ORDER BY updated_at DESC LIMIT 1").fetchone()
        conn.close()
        if not ent:
            raise HTTPException(503, "No active sandbox entitlement")
        subscription_id = ent["stripe_subscription_id"]
        reserve = _consume_usage(subscription_id, 1)
        prompt = "Reply with exactly: JAKEAI DIRECT RUNTIME OK"
        try:
            result = _call_openai(prompt, "general")
        except Exception:
            _refund_usage(subscription_id, 1)
            _record_run(run_id, subscription_id, "general", _direct_model(), len(prompt), 0, 0, 0, None, "failed")
            raise
        actual_cents = _rounded_provider_cost_cents(result["input_tokens"], result["output_tokens"])
        if actual_cents > 1:
            reserve = _consume_usage(subscription_id, actual_cents - 1)
        _record_run(run_id, subscription_id, "general", result["model"], len(prompt), result["input_tokens"], result["output_tokens"], actual_cents, result["response_id"], "complete")
        return {
            "status": "complete",
            "output": result["text"],
            "model": result["model"],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "usage_cents": actual_cents,
            "remaining_cents": reserve["remaining_cents"],
            "approval_gate": "on",
            "external_actions_executed": False,
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
            "execution_configured": _execution_configured(),
            "execution_mode": "remote_runtime" if (_runtime_url() and _runtime_token()) else ("local_key" if _openai_key() else "disabled"),
            "execution_model": _direct_model(),
        }

    @app.post("/v1/direct/run")
    def direct_run(body: DirectRunRequest, request: Request):
        row = _session_entitlement(request)
        prompt = str(body.prompt or "").strip()
        workflow = str(body.workflow or "general").strip().lower()
        if workflow not in ALLOWED_WORKFLOWS:
            raise HTTPException(400, "Unknown JakeAI Direct workflow")
        if not prompt:
            raise HTTPException(400, "Prompt is required")
        if len(prompt) > 12000:
            raise HTTPException(413, "Prompt is too large for this Direct run")
        if not _execution_configured():
            raise HTTPException(503, "JakeAI Direct model runtime is not configured")

        subscription_id = row["stripe_subscription_id"]
        reserve = _consume_usage(subscription_id, 1)
        run_id = "dir_" + secrets.token_urlsafe(12)
        try:
            result = _call_openai(prompt, workflow)
        except Exception:
            _refund_usage(subscription_id, 1)
            _record_run(run_id, subscription_id, workflow, _direct_model(), len(prompt), 0, 0, 0, None, "failed")
            raise

        actual_cents = _rounded_provider_cost_cents(result["input_tokens"], result["output_tokens"])
        if actual_cents > 1:
            try:
                reserve = _consume_usage(subscription_id, actual_cents - 1)
            except Exception:
                _refund_usage(subscription_id, 1)
                _record_run(
                    run_id, subscription_id, workflow, result["model"], len(prompt),
                    result["input_tokens"], result["output_tokens"], 0, result["response_id"], "usage_rejected"
                )
                raise HTTPException(402, "JakeAI Direct usage allowance was reached")
        elif actual_cents < 1:
            actual_cents = 1

        _record_run(
            run_id, subscription_id, workflow, result["model"], len(prompt),
            result["input_tokens"], result["output_tokens"], actual_cents, result["response_id"], "complete"
        )
        return {
            "run_id": run_id,
            "workflow": workflow,
            "output": result["text"],
            "model": result["model"],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "usage_cents": actual_cents,
            "remaining_cents": reserve["remaining_cents"],
            "approval_gate": "on",
            "external_actions_executed": False,
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
