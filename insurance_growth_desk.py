import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel

from direct_billing import _call_openai, _db_path, _direct_model

COOKIE_NAME = "jakeai_insurance_pilot"
VALID_MODES = {"general", "iul_annuity_leads", "first_term_marketing", "lead_review", "analytics"}
VALID_INTERESTS = {"iul", "annuity", "term", "unsure"}
VALID_CONSENT = {"opt_in_verified", "consent_pending", "do_not_contact"}
VALID_LEAD_STATES = {"new", "review", "contact_approved", "appointment", "application", "issued", "closed"}


class PilotLogin(BaseModel):
    access_code: str


class PilotRun(BaseModel):
    prompt: str
    mode: str = "general"


class LeadCreate(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    state: str = ""
    product_interest: str = "unsure"
    source: str = ""
    consent_status: str = "consent_pending"
    consent_evidence: str = ""
    notes: str = ""


class LeadStatus(BaseModel):
    status: str


def _now():
    return datetime.now(timezone.utc).isoformat()


def _conn():
    conn = sqlite3.connect(_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS insurance_pilot_sessions(
        token_hash TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        revoked_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS insurance_pilot_runs(
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        mode TEXT NOT NULL,
        model TEXT NOT NULL,
        prompt_chars INTEGER NOT NULL,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        status TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS insurance_leads(
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        name TEXT,
        email TEXT,
        phone TEXT,
        state TEXT,
        product_interest TEXT NOT NULL,
        source TEXT,
        consent_status TEXT NOT NULL,
        consent_evidence TEXT,
        status TEXT NOT NULL,
        notes TEXT
    )""")
    conn.commit()
    conn.close()


def _access_code():
    return os.environ.get("INSURANCE_PILOT_ACCESS_CODE", "").strip()


def _owner():
    return os.environ.get("INSURANCE_PILOT_OWNER", "Jim").strip() or "Jim"


def _brand():
    return os.environ.get("INSURANCE_BRAND_DISPLAY_NAME", "First Term Insurance").strip() or "First Term Insurance"


def _brand_verified():
    return os.environ.get("INSURANCE_BRAND_VERIFIED", "").strip().lower() in {"1", "true", "yes", "on"}


def _daily_limit():
    try:
        return max(1, int(os.environ.get("INSURANCE_PILOT_DAILY_RUN_LIMIT", "50")))
    except Exception:
        return 50


def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _require_session(request: Request):
    token = request.cookies.get(COOKIE_NAME, "")
    if not token:
        raise HTTPException(401, "Insurance Growth Desk session required")
    digest = _hash_token(token)
    conn = _conn()
    row = conn.execute(
        "SELECT token_hash FROM insurance_pilot_sessions WHERE token_hash=? AND revoked_at IS NULL",
        (digest,),
    ).fetchone()
    if row:
        conn.execute("UPDATE insurance_pilot_sessions SET last_seen_at=? WHERE token_hash=?", (_now(), digest))
        conn.commit()
    conn.close()
    if not row:
        raise HTTPException(401, "Insurance Growth Desk session is invalid")
    return digest


def _insurance_instructions(mode):
    identity = (
        f"The configured display brand is {_brand()}. Its legal identity, carrier relationships, and approved product language are "
        + ("verified in configuration." if _brand_verified() else "NOT verified. Do not make factual claims about the company, carriers, products, licensing, or approvals; use placeholders and flag verification required.")
    )
    base = f"""You are JakeAI Insurance Growth Desk, a private pilot workspace for {_owner()}.
Reuse JakeAI's controlled marketing and workflow approach. {identity}
Hard rules:
- Permission-based lead generation and campaign preparation only.
- Never claim you sent, posted, texted, emailed, called, purchased ads, deployed, or contacted anyone. External action always requires explicit human approval.
- Do not provide individualized insurance, investment, legal, or tax recommendations. Do not make annuity suitability or best-interest conclusions for a consumer.
- Do not promise or imply guaranteed market returns, guaranteed tax outcomes, or that an IUL is a stock-market investment.
- When discussing IUL illustrations, distinguish guaranteed from nonguaranteed values and flag carrier-approved illustration requirements.
- Do not score or target leads using sensitive traits such as race, religion, medical diagnoses, disability, sexual orientation, political affiliation, or other protected/sensitive personal data.
- Flag licensing, state, carrier, advertising approval, consent, DNC/opt-out, and disclosure requirements before any outbound use.
- Outward-facing copy is always DRAFT — HUMAN APPROVAL REQUIRED.
- Prefer concise, actionable output with assumptions, unknowns, compliance checks, next actions, and measurable outcomes."""
    modes = {
        "iul_annuity_leads": "
Focus on permission-based IUL and annuity lead acquisition: search intent, educational funnels, referrals, events, landing pages, qualification questions, consent evidence, attribution, and conversion measurement. Do not recommend a policy to an individual.",
        "first_term_marketing": "
Use the existing JakeAI Campaign Builder pattern. Prepare positioning, landing-page copy, educational content, ad concepts, creative briefs, SEO topics, campaign experiments, and measurement plans. Do not publish or spend.",
        "lead_review": "
Review only the lead information supplied. Summarize stated intent, source, consent status, missing information, and a compliant human next action. Do not infer suitability.",
        "analytics": "
Analyze supplied aggregate campaign and funnel data. Focus on attribution, conversion, cost, bottlenecks, experiments, and data quality; avoid sensitive-trait segmentation.",
        "general": "
Solve the request within the Insurance Growth Desk guardrails.",
    }
    return base + modes.get(mode, modes["general"])


def _wrapped_prompt(prompt, mode):
    return _insurance_instructions(mode) + "

USER REQUEST:
" + prompt.strip()


def _underlying_workflow(mode):
    if mode in {"iul_annuity_leads", "first_term_marketing"}:
        return "campaign"
    return "general"


def _run_count_today():
    prefix = datetime.now(timezone.utc).date().isoformat() + "%"
    conn = _conn()
    n = conn.execute("SELECT COUNT(*) FROM insurance_pilot_runs WHERE created_at LIKE ?", (prefix,)).fetchone()[0]
    conn.close()
    return int(n)


def _safe(v, limit=2000):
    return str(v or "").strip()[:limit]


def register_insurance_growth_routes(app):
    _init_db()

    @app.get("/v1/insurance/health")
    def insurance_health():
        return {
            "status": "ready" if bool(_access_code()) else "configuration_required",
            "product": "JakeAI Insurance Growth Desk",
            "pilot_owner": _owner(),
            "brand_display_name": _brand(),
            "brand_verified": _brand_verified(),
            "approval_gate": True,
            "public_lead_capture": False,
            "daily_run_limit": _daily_limit(),
        }

    @app.post("/v1/insurance/login")
    def insurance_login(body: PilotLogin, response: Response):
        configured = _access_code()
        if not configured:
            raise HTTPException(503, "Insurance pilot access is not configured")
        if not hmac.compare_digest(body.access_code.strip(), configured):
            raise HTTPException(401, "Invalid pilot access code")
        token = secrets.token_urlsafe(32)
        digest = _hash_token(token)
        now = _now()
        conn = _conn()
        conn.execute(
            "INSERT OR REPLACE INTO insurance_pilot_sessions(token_hash,created_at,last_seen_at,revoked_at) VALUES (?,?,?,NULL)",
            (digest, now, now),
        )
        conn.commit()
        conn.close()
        response.set_cookie(
            COOKIE_NAME, token, max_age=60 * 60 * 24 * 30, httponly=True,
            secure=True, samesite="lax", path="/"
        )
        return {"status": "ok", "pilot_owner": _owner(), "brand_display_name": _brand(), "brand_verified": _brand_verified()}

    @app.get("/v1/insurance/me")
    def insurance_me(request: Request):
        _require_session(request)
        return {
            "authenticated": True,
            "pilot_owner": _owner(),
            "brand_display_name": _brand(),
            "brand_verified": _brand_verified(),
            "approval_gate": True,
            "public_lead_capture": False,
            "daily_run_limit": _daily_limit(),
            "runs_today": _run_count_today(),
            "modes": sorted(VALID_MODES),
        }

    @app.post("/v1/insurance/logout")
    def insurance_logout(request: Request, response: Response):
        digest = _require_session(request)
        conn = _conn()
        conn.execute("UPDATE insurance_pilot_sessions SET revoked_at=? WHERE token_hash=?", (_now(), digest))
        conn.commit()
        conn.close()
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"status": "ok"}

    @app.post("/v1/insurance/run")
    def insurance_run(body: PilotRun, request: Request):
        _require_session(request)
        prompt = _safe(body.prompt, 12000)
        mode = _safe(body.mode, 60).lower() or "general"
        if not prompt:
            raise HTTPException(400, "Prompt is required")
        if mode not in VALID_MODES:
            raise HTTPException(400, "Unknown Insurance Growth Desk mode")
        if _run_count_today() >= _daily_limit():
            raise HTTPException(429, "Insurance pilot daily run limit reached")

        run_id = "insrun_" + uuid.uuid4().hex
        try:
            result = _call_openai(_wrapped_prompt(prompt, mode), _underlying_workflow(mode))
            status = "complete"
        except Exception:
            conn = _conn()
            conn.execute(
                "INSERT INTO insurance_pilot_runs(id,created_at,mode,model,prompt_chars,input_tokens,output_tokens,status) VALUES (?,?,?,?,?,?,?,?)",
                (run_id, _now(), mode, _direct_model(), len(prompt), 0, 0, "failed"),
            )
            conn.commit()
            conn.close()
            raise

        conn = _conn()
        conn.execute(
            "INSERT INTO insurance_pilot_runs(id,created_at,mode,model,prompt_chars,input_tokens,output_tokens,status) VALUES (?,?,?,?,?,?,?,?)",
            (
                run_id, _now(), mode, _safe(result.get("model"), 120), len(prompt),
                int(result.get("input_tokens") or 0), int(result.get("output_tokens") or 0), status,
            ),
        )
        conn.commit()
        conn.close()
        return {
            "run_id": run_id,
            "mode": mode,
            "text": result["text"],
            "model": result.get("model"),
            "approval_gate": "ON",
            "runs_today": _run_count_today(),
            "daily_run_limit": _daily_limit(),
        }

    @app.get("/v1/insurance/leads")
    def insurance_leads(request: Request):
        _require_session(request)
        conn = _conn()
        rows = conn.execute(
            """SELECT id,created_at,updated_at,name,email,phone,state,product_interest,source,
                      consent_status,consent_evidence,status,notes
               FROM insurance_leads ORDER BY created_at DESC LIMIT 500"""
        ).fetchall()
        conn.close()
        return {"leads": [dict(r) for r in rows], "public_lead_capture": False}

    @app.post("/v1/insurance/leads")
    def insurance_create_lead(body: LeadCreate, request: Request):
        _require_session(request)
        interest = _safe(body.product_interest, 30).lower() or "unsure"
        consent = _safe(body.consent_status, 40).lower() or "consent_pending"
        if interest not in VALID_INTERESTS:
            raise HTTPException(400, "Unknown product interest")
        if consent not in VALID_CONSENT:
            raise HTTPException(400, "Unknown consent state")
        evidence = _safe(body.consent_evidence, 2000)
        if consent == "opt_in_verified" and not evidence:
            raise HTTPException(400, "Verified opt-in requires consent evidence")
        if not any([_safe(body.name, 200), _safe(body.email, 320), _safe(body.phone, 80)]):
            raise HTTPException(400, "At least one lead identifier is required")

        lead_id = "lead_" + uuid.uuid4().hex[:16]
        now = _now()
        conn = _conn()
        conn.execute(
            """INSERT INTO insurance_leads(
                id,created_at,updated_at,name,email,phone,state,product_interest,source,
                consent_status,consent_evidence,status,notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                lead_id, now, now, _safe(body.name, 200), _safe(body.email, 320),
                _safe(body.phone, 80), _safe(body.state, 80), interest, _safe(body.source, 300),
                consent, evidence, "new", _safe(body.notes, 4000),
            ),
        )
        conn.commit()
        conn.close()
        return {"status": "created", "lead_id": lead_id, "lead_status": "new", "consent_status": consent}

    @app.post("/v1/insurance/leads/{lead_id}/status")
    def insurance_update_lead_status(lead_id: str, body: LeadStatus, request: Request):
        _require_session(request)
        status = _safe(body.status, 40).lower()
        if status not in VALID_LEAD_STATES:
            raise HTTPException(400, "Unknown lead state")
        conn = _conn()
        row = conn.execute(
            "SELECT id,consent_status,consent_evidence FROM insurance_leads WHERE id=?",
            (lead_id,),
        ).fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, "Lead not found")
        if status == "contact_approved":
            if row["consent_status"] != "opt_in_verified" or not _safe(row["consent_evidence"]):
                conn.close()
                raise HTTPException(409, "Contact approval requires verified opt-in evidence")
        conn.execute("UPDATE insurance_leads SET status=?,updated_at=? WHERE id=?", (status, _now(), lead_id))
        conn.commit()
        conn.close()
        return {"status": "updated", "lead_id": lead_id, "lead_status": status}

