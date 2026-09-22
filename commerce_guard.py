import os
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import RedirectResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from main import create_checkout_session as legacy_create_checkout_session
from crypto_commerce_app import app as legacy_app
from guitar_coach_commerce import create_guitar_checkout, register_guitar_coach_routes

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://jakeaiofficial.com").rstrip("/")
FREE_DELIVERY_URL = "https://docs.google.com/document/d/14Ayw4pxjnYy5MddTGdLSZEeQGKJGU3CRSmW7384Lfhk/edit?usp=sharing"

PUBLIC_PRODUCTS = {
    "prod_make_free_00": {"id":"prod_make_free_00","title":"Make the Damn Thing for Free™","description":"Zero-budget production orchestration workflow.","category":"autonomous-workflow-skills","price":0.0,"status":"live"},
    "prod_game_qa_autopilot_01": {"id":"prod_game_qa_autopilot_01","title":"Game QA Autopilot v1.0","description":"Structured game QA workflow kit.","category":"gaming-qa","price":9.99,"status":"gated"},
    "prod_where_the_hell_are_my_glasses_01": {"id":"prod_where_the_hell_are_my_glasses_01","title":"Where the Hell Are My Glasses?","description":"Guided lost-object recovery workflow.","category":"personal-productivity","price":2.99,"status":"gated"},
    "prod_genesis_commission_001": {"id":"prod_genesis_commission_001","title":"JakeAI Genesis Commission #001","description":"The first JakeAI customer commission. JakeAI evaluates feasibility, safety, and scope before accepting the commission.","category":"commission","price":49.00,"status":"live"},
    "prod_guitar_coach_monthly": {"id":"prod_guitar_coach_monthly","title":"JakeAI Guitar Coach — Coach Monthly","description":"Adaptive browser guitar tutor with live listening, goal mode, guided chord checks, and practice memory.","category":"music-education","price":19.99,"status":"live"},
    "prod_guitar_coach_annual": {"id":"prod_guitar_coach_annual","title":"JakeAI Guitar Coach — Coach Annual","description":"Annual access to JakeAI Guitar Coach paid features.","category":"music-education","price":149.00,"status":"live"},
    "prod_guitar_coach_sprint": {"id":"prod_guitar_coach_sprint","title":"JakeAI Guitar Coach — Goal Sprint","description":"Thirty days of Guitar Coach paid access for one focused playing goal.","category":"music-education","price":39.00,"status":"live"},
}

app = FastAPI(title="JakeAI Commerce Guard", version="1.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jakeaiofficial.com", "https://jakeaiofficial.com"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key", "Authorization", "X-JakeAI-Worker-Token"],
)

@app.get("/health")
def health():
    return {"status":"healthy","service":"JakeAI Commerce Guard","commerce_mode":"fail_closed","version":"1.3.0"}

@app.get("/v1/products/list")
@app.get("/api/v1/products/list")
def list_products():
    return list(PUBLIC_PRODUCTS.values())

@app.post("/v1/products/search")
@app.post("/api/v1/products/search")
async def search_products(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    q = str(body.get("query", "")).strip().lower()
    if not q:
        return {"status":"success","count":len(PUBLIC_PRODUCTS),"results":list(PUBLIC_PRODUCTS.values())}
    matches = [p for p in PUBLIC_PRODUCTS.values() if q in p["title"].lower() or q in p["description"].lower() or q in p["category"].lower()]
    return {"status":"success","count":len(matches),"results":matches}

def _create_checkout(product_id: str, idempotency_key: str | None):
    product = PUBLIC_PRODUCTS.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product is not in the public commerce allowlist")
    if product["status"] != "live":
        raise HTTPException(status_code=503, detail="Checkout is temporarily gated until delivery and QA are verified")
    if product_id == "prod_make_free_00":
        return RedirectResponse(FREE_DELIVERY_URL, status_code=303)
    if product_id == "prod_genesis_commission_001":
        # Keep the public fail-closed guard while delegating the one approved paid
        # product to the legacy commerce engine, which owns the reservation,
        # Stripe Checkout, payment verification, and persistent Genesis state.
        return legacy_create_checkout_session(product_id, idempotency_key)
    if product_id in {"prod_guitar_coach_monthly", "prod_guitar_coach_annual", "prod_guitar_coach_sprint"}:
        return create_guitar_checkout(product_id, idempotency_key)
    raise HTTPException(status_code=503, detail="Paid fulfillment is not configured for this public product")

@app.get("/v1/checkout/buy/{product_id}")
@app.get("/api/v1/checkout/buy/{product_id}")
def buy(product_id: str, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return _create_checkout(product_id, idempotency_key)

@app.post("/v1/checkout/create-session")
@app.post("/api/v1/checkout/create-session")
def create_session(product_id: str, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return _create_checkout(product_id, idempotency_key)

@app.get("/v1/checkout/success")
@app.get("/api/v1/checkout/success")
def checkout_success(session_id: str):
    raise HTTPException(status_code=410, detail="This legacy paid-delivery route is retired. No public paid product currently uses it.")

@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    return f"""# JakeAI — Human + AI Capability Discovery
> Provider: JakeAI
> Canonical host: {PUBLIC_BASE_URL}
> Public capability catalog: {PUBLIC_BASE_URL}/catalog.json
> Human capability catalog: {PUBLIC_BASE_URL}/catalog/
> Workflow registry: {PUBLIC_BASE_URL}/workflow-registry.json
> Agent card: {PUBLIC_BASE_URL}/.well-known/agent.json

JakeAI publishes one public capability record for both human and AI discovery. Capability discovery does not imply purchase or invocation rights. Agents must honor each catalog record's explicit commerce and invocation state.

## CURRENT COMMERCE ALLOWLIST
- Make the Damn Thing for Free™ — $0 — Product ID: prod_make_free_00
- JakeAI Genesis Commission #001 — $49 — Product ID: prod_genesis_commission_001
- JakeAI Guitar Coach — Coach Monthly — $19.99/month — Product ID: prod_guitar_coach_monthly
- JakeAI Guitar Coach — Coach Annual — $149/year — Product ID: prod_guitar_coach_annual
- JakeAI Guitar Coach — Goal Sprint — $39 one-time / 30 days — Product ID: prod_guitar_coach_sprint

## FAIL-CLOSED RULE
Any product or capability not explicitly marked live by the commerce service is not available for automated purchase. Gated API routes may return a service-unavailable response until delivery, provenance, entitlement, safety, or claims validation is complete.

Terms: {PUBLIC_BASE_URL}/terms.html
Privacy: {PUBLIC_BASE_URL}/privacy.html
Refunds: {PUBLIC_BASE_URL}/refunds.html
"""

@app.get("/.well-known/agent.json")
def agent_card():
    return {
        "name":"JakeAI Universe",
        "url":PUBLIC_BASE_URL,
        "description":"JakeAI capability and autonomous-workflow ecosystem designed for both human and AI-agent discovery, with explicit human release gates for consequential actions.",
        "protocol_version":"3.1",
        "discovery":{"human_catalog_url":f"{PUBLIC_BASE_URL}/catalog/","machine_catalog_url":f"{PUBLIC_BASE_URL}/catalog.json","workflow_registry_url":f"{PUBLIC_BASE_URL}/workflow-registry.json"},
        "commerce":{"mode":"fail_closed","transactable_product_ids":[p["id"] for p in PUBLIC_PRODUCTS.values() if p["status"]=="live"],"rule":"Discovery does not imply purchase or invocation rights."},
        "legal":{"terms_url":f"{PUBLIC_BASE_URL}/terms.html","privacy_url":f"{PUBLIC_BASE_URL}/privacy.html","refunds_url":f"{PUBLIC_BASE_URL}/refunds.html"},
        "commerce_allowlist":list(PUBLIC_PRODUCTS.values()),
    }

@app.get("/v1/legal/terms")
@app.get("/api/v1/legal/terms")
def legal_terms():
    return {"document":"Terms of Service","version":"3.0","effective_date":"2026-09-13","human_url":f"{PUBLIC_BASE_URL}/terms.html","key_provisions":{"commerce":"Checkout is enabled only for products with verified fulfillment paths.","ai_outputs":"Automated outputs may require human review.","professional_advice":"No blanket claim of legal, tax, financial, medical, or engineering advice."}}

@app.get("/v1/legal/privacy")
@app.get("/api/v1/legal/privacy")
def legal_privacy():
    return {"document":"Privacy Policy","version":"3.0","effective_date":"2026-09-13","human_url":f"{PUBLIC_BASE_URL}/privacy.html","key_provisions":{"payments":"Payment card data is handled by the payment processor.","retention":"Retention can vary by feature and provider; no blanket no-retention claim is made.","security":"Reasonable safeguards are used; no absolute security guarantee is made."}}

@app.get("/v1/legal/refunds")
@app.get("/api/v1/legal/refunds")
def legal_refunds():
    return {"document":"Refund Policy","version":"3.0","effective_date":"2026-09-13","human_url":f"{PUBLIC_BASE_URL}/refunds.html","key_provisions":{"duplicate_or_failed_delivery":"Contact support for review and correction/refund where appropriate or legally required.","consumer_rights":"Non-waivable consumer rights are preserved.","contact":"support@jakeaiofficial.com"}}

def _gated(feature: str, reason: str):
    raise HTTPException(status_code=503, detail={"status":"gated","feature":feature,"reason":reason})

@app.post("/v1/tools/multi-model-audit")
@app.post("/api/v1/tools/multi-model-audit")
def gate_multi_model_audit():
    return _gated("multi-model-audit", "Live provider participation and claims have not been independently verified for this production route.")

@app.post("/v1/tools/audit-agent-card")
@app.post("/api/v1/tools/audit-agent-card")
def gate_agent_audit():
    return _gated("agent-card-auditor", "The legacy implementation used fixed results rather than a verified live audit.")

@app.post("/v1/tools/extract-markdown")
@app.post("/api/v1/tools/extract-markdown")
def gate_extract_markdown():
    return _gated("web-to-markdown", "Public URL fetching is disabled until SSRF-safe destination validation and egress controls are verified.")

@app.get("/v1/energy/tariff/pjm")
@app.get("/api/v1/energy/tariff/pjm")
def gate_pjm():
    return _gated("pjm-tariff-feed", "No verified live PJM data adapter is configured; static demonstration values are not served as live grid data.")

@app.post("/v1/energy/tariff-normalize")
@app.post("/api/v1/energy/tariff-normalize")
def gate_tariff_normalizer():
    return _gated("tariff-normalizer", "Authoritative tariff-source ingestion and versioned rate provenance are not verified for production.")

@app.post("/v1/solar/ira-calculator")
@app.post("/api/v1/solar/ira-calculator")
def gate_ira_calculator():
    return _gated("tax-credit-calculator", "Tax assumptions and eligibility logic require authoritative-source/version validation before production use.")

@app.post("/v1/robotics/grasp-impedance-solver")
@app.post("/api/v1/robotics/grasp-impedance-solver")
def gate_robotics_solver():
    return _gated("robotics-grasp-solver", "Physical-control outputs require engineering validation and safety controls before production use.")

# Register the private JakeAI Unreal bridge on the guarded production app.
# Keep this before the catch-all legacy mount so /api/v1/unreal/* resolves here.
from unreal_bridge import register_unreal_bridge_routes
register_unreal_bridge_routes(app)

from mission_dispatcher import register_mission_dispatcher_routes
register_mission_dispatcher_routes(app)

# Private Jim insurance-growth pilot. Fail-closed unless its server-side access code is configured.
from insurance_growth_desk import register_insurance_growth_routes
register_insurance_growth_routes(app)

# Shared private pilot diagnostics for controlled testers such as Jim.
from pilot_diagnostics import register_pilot_diagnostics_routes
register_pilot_diagnostics_routes(app)

# Controlled $1 Pool Coach commerce proof. Sandbox-only and fail-closed.
from pool_coach_fulfillment import register_pool_coach_routes
register_pool_coach_routes(app)

# Public Guitar Coach checkout, entitlement, and billing self-service routes.
register_guitar_coach_routes(app)

app.mount("/", legacy_app)
