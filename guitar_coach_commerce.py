import os
import time
import stripe
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

router = APIRouter()
PRODUCT_PAGE = "https://jakeaiofficial.com/guitar-coach.html"
PORTAL_CONFIG_ID = "bpc_1UIVgTJAnSnCHitFjdhBl6jx"
PRODUCT_KEY = "guitar_coach"

PLANS = {
    "prod_guitar_coach_monthly": {"plan":"coach_monthly","price_id":"price_1UIVg7JAnSnCHitFhMY0WN6F","mode":"subscription","amount_cents":1999},
    "prod_guitar_coach_annual": {"plan":"coach_annual","price_id":"price_1UIVgAJAnSnCHitFH5v69j0y","mode":"subscription","amount_cents":14900},
    "prod_guitar_coach_sprint": {"plan":"goal_sprint","price_id":"price_1UIVgCJAnSnCHitFGHWOnbwJ","mode":"payment","amount_cents":3900,"duration_days":30},
}

def _configure_stripe():
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="Payment service is not configured")
    stripe.api_key = key

def _session(session_id: str):
    _configure_stripe()
    if not session_id or len(session_id) > 255 or not session_id.startswith(("cs_live_", "cs_test_")):
        raise HTTPException(status_code=400, detail="Invalid checkout session")
    try:
        return stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
    except Exception:
        raise HTTPException(status_code=404, detail="Checkout session could not be verified")

def create_guitar_checkout(product_id: str, idempotency_key: str | None = None):
    plan = PLANS.get(product_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Unknown Guitar Coach plan")
    _configure_stripe()
    kwargs = {
        "line_items": [{"price": plan["price_id"], "quantity": 1}],
        "mode": plan["mode"],
        "success_url": f"{PRODUCT_PAGE}?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{PRODUCT_PAGE}?checkout=cancelled",
        "metadata": {"jakeai_product_id":PRODUCT_KEY,"jakeai_sku":product_id,"plan":plan["plan"]},
        "client_reference_id": product_id,
        "billing_address_collection": "auto",
    }
    if plan["mode"] == "subscription":
        kwargs["subscription_data"] = {"metadata":{"jakeai_product_id":PRODUCT_KEY,"jakeai_sku":product_id,"plan":plan["plan"]}}
    request_options = {}
    if idempotency_key:
        request_options["idempotency_key"] = idempotency_key
    try:
        session = stripe.checkout.Session.create(**kwargs, **request_options)
        return RedirectResponse(url=session.url, status_code=303)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Checkout could not be created: {str(exc)[:180]}")

def _entitlement_from_session(sess):
    metadata = getattr(sess, "metadata", None) or {}
    if metadata.get("jakeai_product_id") != PRODUCT_KEY:
        return {"entitled":False,"reason":"Session is not a Guitar Coach purchase"}
    sku = metadata.get("jakeai_sku")
    plan = PLANS.get(sku)
    if not plan:
        return {"entitled":False,"reason":"Unknown plan"}
    now = int(time.time())
    if plan["mode"] == "payment":
        created = int(getattr(sess, "created", 0) or 0)
        access_until = created + int(plan.get("duration_days", 30)) * 86400
        paid = getattr(sess, "payment_status", "") == "paid"
        return {"entitled":bool(paid and now < access_until),"plan":plan["plan"],"sku":sku,"access_until":access_until,"billing":"one_time"}
    sub = getattr(sess, "subscription", None)
    if isinstance(sub, str):
        try:
            sub = stripe.Subscription.retrieve(sub)
        except Exception:
            sub = None
    sub_status = getattr(sub, "status", "") if sub else ""
    return {"entitled":sub_status in {"active","trialing"},"plan":plan["plan"],"sku":sku,"subscription_status":sub_status or "unknown","billing":"subscription"}

@router.get("/v1/guitar-coach/status")
@router.get("/api/v1/guitar-coach/status")
def guitar_coach_status(session_id: str):
    sess = _session(session_id)
    result = _entitlement_from_session(sess)
    details = getattr(sess, "customer_details", None)
    result["email"] = getattr(details, "email", None) if details else None
    result["livemode"] = bool(getattr(sess, "livemode", False))
    return result

@router.get("/v1/guitar-coach/portal")
@router.get("/api/v1/guitar-coach/portal")
def guitar_coach_portal(session_id: str):
    sess = _session(session_id)
    result = _entitlement_from_session(sess)
    if result.get("billing") != "subscription":
        raise HTTPException(status_code=400, detail="Billing portal is available for subscription plans")
    customer = getattr(sess, "customer", None)
    if not customer:
        raise HTTPException(status_code=409, detail="Stripe customer is not available for this session")
    _configure_stripe()
    try:
        portal = stripe.billing_portal.Session.create(customer=customer,configuration=PORTAL_CONFIG_ID,return_url=PRODUCT_PAGE)
        return RedirectResponse(url=portal.url, status_code=303)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Billing portal is unavailable: {str(exc)[:180]}")

@router.get("/v1/guitar-coach/checkout/{product_id}")
@router.get("/api/v1/guitar-coach/checkout/{product_id}")
def guitar_coach_checkout(product_id: str):
    return create_guitar_checkout(product_id)

def register_guitar_coach_routes(app):
    app.include_router(router)
