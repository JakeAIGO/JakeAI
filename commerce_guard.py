import os
import stripe
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import RedirectResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from main import app as legacy_app

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://jakeaiofficial.com").rstrip("/")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
SOLAR_GUIDE_DELIVERY_URL = os.environ.get("SOLAR_GUIDE_DELIVERY_URL", "").strip()
FREE_DELIVERY_URL = "https://docs.google.com/document/d/14Ayw4pxjnYy5MddTGdLSZEeQGKJGU3CRSmW7384Lfhk/edit?usp=sharing"

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

PUBLIC_PRODUCTS = {
    "prod_make_free_00": {"id":"prod_make_free_00","title":"Make the Damn Thing for Free™","description":"Zero-budget production orchestration workflow.","category":"autonomous-workflow-skills","price":0.0,"status":"live"},
    "prod_solar_guide_04": {"id":"prod_solar_guide_04","title":"Commercial Solar & BESS Guide","description":"Technical reference for commercial solar and battery-storage sizing concepts.","category":"digital-guide","price":3.0,"status":"live" if SOLAR_GUIDE_DELIVERY_URL else "gated"},
    "prod_game_qa_autopilot_01": {"id":"prod_game_qa_autopilot_01","title":"Game QA Autopilot v1.0","description":"Structured game QA workflow kit.","category":"gaming-qa","price":9.99,"status":"gated"},
    "prod_where_the_hell_are_my_glasses_01": {"id":"prod_where_the_hell_are_my_glasses_01","title":"Where the Hell Are My Glasses?","description":"Guided lost-object recovery workflow.","category":"personal-productivity","price":2.99,"status":"gated"},
}

app = FastAPI(title="JakeAI Commerce Guard", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jakeaiofficial.com", "https://www.jakeaiofficial.com"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)

@app.get("/health")
def health():
    return {"status":"healthy","service":"JakeAI Commerce Guard","commerce_mode":"fail_closed","version":"1.1.0"}

@app.get("/v1/products/list")
@app.get("/api/v1/products/list")
def list_products():
    return list(PUBLIC_PRODUCTS.values())

def _create_checkout(product_id: str, idempotency_key: str | None):
    product = PUBLIC_PRODUCTS.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product is not in the public commerce allowlist")
    if product["status"] != "live":
        raise HTTPException(status_code=503, detail="Checkout is temporarily gated until delivery and QA are verified")
    if product_id == "prod_make_free_00":
        return RedirectResponse(FREE_DELIVERY_URL, status_code=303)
    if product_id != "prod_solar_guide_04" or not SOLAR_GUIDE_DELIVERY_URL:
        raise HTTPException(status_code=503, detail="Paid fulfillment is not configured")
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payment processor is not configured")
    kwargs = {}
    if idempotency_key:
        kwargs["idempotency_key"] = idempotency_key
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{"price_data":{"currency":"usd","product_data":{"name":product["title"]},"unit_amount":int(round(product["price"]*100))},"quantity":1}],
            metadata={"product_id":product_id},
            success_url=f"{PUBLIC_BASE_URL}/api/v1/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{PUBLIC_BASE_URL}/?payment=cancelled",
            **kwargs,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to create checkout session") from exc
    return RedirectResponse(session.url, status_code=303)

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
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payment verification is unavailable")
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to verify checkout session") from exc
    if session.payment_status != "paid":
        raise HTTPException(status_code=402, detail="Payment has not been verified")
    if (session.metadata or {}).get("product_id") != "prod_solar_guide_04":
        raise HTTPException(status_code=403, detail="Session is not entitled to this delivery")
    if not SOLAR_GUIDE_DELIVERY_URL:
        raise HTTPException(status_code=503, detail="Delivery is temporarily unavailable")
    return RedirectResponse(SOLAR_GUIDE_DELIVERY_URL, status_code=303)

@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    solar_status = "LIVE" if SOLAR_GUIDE_DELIVERY_URL else "GATED"
    return f"""# JakeAI Universe — Machine-Readable Public Catalog
> Human release authority remains required for public releases.
> Public commerce is fail-closed when fulfillment is not verified.

## LIVE
- Make the Damn Thing for Free™ — $0 — Product ID: prod_make_free_00
- Commercial Solar & BESS Guide — $3.00 — Status: {solar_status}

## GATED / NOT FOR SALE
- Game QA Autopilot v1.0 — delivery QA pending
- Where the Hell Are My Glasses? — delivery QA pending
- Metered/API-credit products — entitlement and metering required before paid activation

Terms: {PUBLIC_BASE_URL}/terms.html
Privacy: {PUBLIC_BASE_URL}/privacy.html
Refunds: {PUBLIC_BASE_URL}/refunds.html
"""

@app.get("/.well-known/agent.json")
def agent_card():
    return {
        "name":"JakeAI Universe",
        "url":PUBLIC_BASE_URL,
        "description":"Autonomous workflow, game and media ecosystem with human-gated public releases.",
        "protocol_version":"3.0",
        "commerce":{"mode":"fail_closed","transactable_product_ids":[p["id"] for p in PUBLIC_PRODUCTS.values() if p["status"]=="live"]},
        "legal":{"terms_url":f"{PUBLIC_BASE_URL}/terms.html","privacy_url":f"{PUBLIC_BASE_URL}/privacy.html","refunds_url":f"{PUBLIC_BASE_URL}/refunds.html"},
        "active_catalog":list(PUBLIC_PRODUCTS.values()),
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

app.mount("/", legacy_app)
