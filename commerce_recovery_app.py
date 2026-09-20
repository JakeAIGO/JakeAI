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


# ---------------------------------------------------------------------------
# Crypto wallet RC2 isolated preview console
# ---------------------------------------------------------------------------
import hmac as _wallet_hmac
import crypto_commerce_app as crypto_runtime
from fastapi.responses import HTMLResponse as _WalletHTMLResponse, JSONResponse as _WalletJSONResponse

_WALLET_TRUE = {"1", "true", "yes", "on"}

def _wallet_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _WALLET_TRUE

def _require_wallet_preview_key(provided: Optional[str]) -> None:
    expected = os.environ.get("JAKEAI_COMMERCE_PREVIEW_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Wallet preview authorization is not configured")
    candidate = (provided or "").strip()
    if not candidate or not _wallet_hmac.compare_digest(candidate, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")

def _wallet_preview_status() -> dict:
    config = crypto_runtime._crypto_config()
    activation_errors = config.activation_errors()
    legal = crypto_runtime._legal_approved()
    return {
        "runtime": "commerce-wallet-preview",
        "mode": "merchant_only_non_custodial",
        "network": "Base Mainnet",
        "chain_id": crypto_runtime.BASE_MAINNET_CHAIN_ID,
        "asset": "USDC",
        "token_contract": crypto_runtime.BASE_NATIVE_USDC_CONTRACT,
        "merchant_configured": bool(config.merchant_address),
        "rpc_configured": bool(os.environ.get("BASE_RPC_URL", "").strip()),
        "admin_review_configured": bool(os.environ.get("CRYPTO_ADMIN_TOKEN", "").strip()),
        "payments_enabled": bool(config.enabled),
        "legal_approved": bool(legal),
        "auto_fulfill_enabled": bool(config.auto_fulfill_enabled),
        "canary_enabled": _wallet_bool("JAKEAI_CRYPTO_CANARY_ENABLED"),
        "preview_only_lock": _wallet_bool("JAKEAI_WALLET_PREVIEW_ONLY"),
        "minimum_confirmations": max(1, int(os.environ.get("CRYPTO_MIN_CONFIRMATIONS", "2"))),
        "activation_ready": bool(not activation_errors and config.enabled and legal),
        "activation_errors": activation_errors,
        "customer_custody": False,
        "creator_payouts": False,
        "exchange_or_swaps": False,
        "private_signing_material_in_app": False,
    }

class WalletCanaryRequest(BaseModel):
    acknowledge_irreversible_payment: bool = False


class WalletCanaryComplianceRequest(BaseModel):
    order_id: str = Field(..., min_length=5, max_length=100)
    tx_hash: str = Field(..., min_length=66, max_length=66)
    reviewer: str = Field(..., min_length=1, max_length=120)
    reference: Optional[str] = Field(default=None, max_length=300)
    reason: str = Field(default="Controlled JakeAI wallet canary review", max_length=1000)
    attest_external_review_complete: bool = False


@app.middleware("http")
async def lock_isolated_wallet_crypto_routes(request: Request, call_next):
    path = request.url.path
    if _wallet_bool("JAKEAI_WALLET_PREVIEW_ONLY") and path.startswith("/v1/checkout/crypto/"):
        expected = os.environ.get("JAKEAI_COMMERCE_PREVIEW_KEY", "").strip()
        provided = request.headers.get("X-JakeAI-Preview-Key", "").strip()
        if not expected or not provided or not _wallet_hmac.compare_digest(provided, expected):
            return _WalletJSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


@app.get("/v1/commerce/wallet-preview/status")
def wallet_preview_status(
    preview_key: Optional[str] = Header(default=None, alias="X-JakeAI-Preview-Key"),
):
    _require_wallet_preview_key(preview_key)
    return _wallet_preview_status()


@app.get("/v1/commerce/wallet-preview/public-status")
def wallet_preview_public_status():
    status = _wallet_preview_status()
    return {
        "runtime": status["runtime"],
        "mode": status["mode"],
        "network": status["network"],
        "chain_id": status["chain_id"],
        "asset": status["asset"],
        "token_contract": status["token_contract"],
        "merchant_configured": status["merchant_configured"],
        "rpc_configured": status["rpc_configured"],
        "admin_review_configured": status["admin_review_configured"],
        "payments_enabled": status["payments_enabled"],
        "legal_approved": status["legal_approved"],
        "auto_fulfill_enabled": status["auto_fulfill_enabled"],
        "canary_enabled": status["canary_enabled"],
        "preview_only_lock": status["preview_only_lock"],
        "minimum_confirmations": status["minimum_confirmations"],
        "activation_ready": status["activation_ready"],
        "customer_custody": status["customer_custody"],
        "creator_payouts": status["creator_payouts"],
        "exchange_or_swaps": status["exchange_or_swaps"],
        "private_signing_material_in_app": status["private_signing_material_in_app"],
    }

@app.post("/v1/commerce/wallet-preview/create-canary")
def wallet_preview_create_canary(
    req: WalletCanaryRequest,
    preview_key: Optional[str] = Header(default=None, alias="X-JakeAI-Preview-Key"),
):
    _require_wallet_preview_key(preview_key)
    if not _wallet_bool("JAKEAI_CRYPTO_CANARY_ENABLED"):
        raise HTTPException(status_code=409, detail="Real-money crypto canary is disabled")
    if not req.acknowledge_irreversible_payment:
        raise HTTPException(status_code=422, detail="Blockchain payment acknowledgement is required")
    config = crypto_runtime._require_activation_ready()
    if not config.merchant_address:
        raise HTTPException(status_code=503, detail="Merchant receiving address is not configured")
    created = crypto_runtime._create_crypto_order(
        "prod_crypto_canary_preview",
        10,
        "crypto-test",
        config.merchant_address,
    )
    return {
        **created,
        "price_usd_cents": 10,
        "network": "Base Mainnet",
        "chain_id": crypto_runtime.BASE_MAINNET_CHAIN_ID,
        "asset": "USDC",
        "token_contract": crypto_runtime.BASE_NATIVE_USDC_CONTRACT,
        "state": "awaiting_payment",
        "auto_fulfillment": False,
        "instructions": "Send exactly 0.10 native USDC on Base to the merchant address, then submit the transaction hash for verification.",
        "warnings": [
            "TEST ONLY — this is a real blockchain transfer if you send it.",
            "Do not send another token or use another network.",
            "No product delivery is attached to this canary order.",
        ],
    }


@app.post("/v1/commerce/wallet-preview/compliance-clear")
def wallet_preview_compliance_clear(
    req: WalletCanaryComplianceRequest,
    preview_key: Optional[str] = Header(default=None, alias="X-JakeAI-Preview-Key"),
):
    _require_wallet_preview_key(preview_key)
    if not _wallet_bool("JAKEAI_CRYPTO_CANARY_ENABLED"):
        raise HTTPException(status_code=409, detail="Real-money crypto canary is disabled")
    if not req.attest_external_review_complete:
        raise HTTPException(status_code=422, detail="External compliance review attestation is required")
    order = commerce_app._get_order(req.order_id)
    if not order or order.get("product_id") != "prod_crypto_canary_preview" or order.get("source") != "crypto-test":
        raise HTTPException(status_code=409, detail="Compliance bridge is limited to the isolated canary order")
    token = os.environ.get("CRYPTO_ADMIN_TOKEN", "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="Crypto compliance administration is not configured")
    review = crypto_runtime.ComplianceReviewRequest(
        tx_hash=req.tx_hash,
        clear=True,
        reviewer=req.reviewer,
        reference=req.reference,
        reason=req.reason,
    )
    return crypto_runtime.record_crypto_compliance_review(
        req.order_id,
        review,
        admin_token=token,
    )


@app.get("/wallet-preview", response_class=_WalletHTMLResponse)
def wallet_preview_console():
    status = _wallet_preview_status()
    status_fields = [
        ("Merchant wallet configured", status["merchant_configured"]),
        ("Base RPC configured", status["rpc_configured"]),
        ("Compliance admin configured", status["admin_review_configured"]),
        ("Preview-only lock", status["preview_only_lock"]),
        ("Public crypto payments", status["payments_enabled"]),
        ("Legal activation", status["legal_approved"]),
        ("10¢ real-chain canary", status["canary_enabled"]),
        ("Automatic fulfillment", status["auto_fulfill_enabled"]),
    ]
    status_html = "".join(
        f'<div class="stat"><b>{label}</b><br><span class="{"ok" if value else "off"}">{"ON / READY" if value else "OFF"}</span></div>'
        for label, value in status_fields
    )
    summary = (
        '<p class="ok"><b>Infrastructure ready.</b> Wallet address, Base RPC, compliance admin, and preview lock are configured.</p>'
        if status["merchant_configured"] and status["rpc_configured"] and status["admin_review_configured"] and status["preview_only_lock"]
        else '<p class="warn"><b>Configuration incomplete.</b> One or more required preview components are missing.</p>'
    )
    html = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="robots" content="noindex,nofollow,noarchive"><title>JakeAI Wallet RC2</title><style>:root{color-scheme:dark;--bg:#03070b;--line:#21445a;--cyan:#5ce8ff;--muted:#91abba;--ok:#68efba;--warn:#ffd27e}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 50% 0,#12334c,var(--bg) 48%);color:#eefaff;font:15px/1.45 system-ui,sans-serif}main{max-width:760px;margin:auto;padding:28px 16px 70px}.brand{font-size:28px;font-weight:950}.brand b{color:var(--cyan)}.eyebrow{font-size:10px;letter-spacing:.18em;color:var(--cyan);font-weight:900}h1{font-size:36px;line-height:1;margin:12px 0}p{color:var(--muted)}.panel{margin-top:15px;padding:18px;border:1px solid var(--line);border-radius:18px;background:#07121dcc}.row{display:grid;grid-template-columns:1fr 1fr;gap:8px}.stat{padding:11px;border:1px solid #ffffff16;border-radius:12px;background:#ffffff05;font-size:12px}.ok{color:var(--ok)}.off{color:#ffc267}input,button{width:100%;padding:14px;margin-top:10px;border-radius:12px;font:inherit}input{background:#03080d;border:1px solid #315067;color:#fff}button{border:0;background:#56ddff;color:#00131b;font-weight:900}button.secondary{background:#132535;color:#dffaff;border:1px solid #315067}button:disabled{opacity:.4}pre{white-space:pre-wrap;word-break:break-word;background:#02070b;padding:12px;border-radius:10px;color:#a9efff;min-height:42px}.warn{border-color:#725823}.tiny{font-size:11px}.attest{display:flex;gap:8px;align-items:flex-start;color:var(--muted);font-size:12px}.attest input{width:auto;margin-top:3px}</style></head><body><main><div class="brand">Jake<b>AI</b></div><div class="eyebrow">WALLET RC2 · ISOLATED TEST CONSOLE</div><h1>Base USDC checkout.</h1><p>Merchant-only, non-custodial and fail-closed. The app never holds a customer's wallet and never signs or broadcasts a transaction.</p><section class="panel"><b>Wallet readiness</b><p class="tiny">Loaded automatically from the JakeAI wallet service. No password and no button required.</p>__SUMMARY__<div class="row">__STATUS__</div><p class="tiny">Network: Base Mainnet · Chain ID 8453 · Asset: native USDC · Minimum confirmations: 2</p><p class="tiny">Refresh this page only if you want to re-check the state.</p></section><section class="panel warn"><b>10¢ real-chain canary</b><p class="tiny">Creating an invoice moves no money. Sending USDC is a real irreversible Base transaction. The canary has no product fulfillment.</p><label class="attest"><input id="ack" type="checkbox">I understand the canary payment is a real blockchain transfer.</label><button id="create" disabled>Create 0.10 USDC canary invoice</button><div id="invoice"></div></section><section class="panel"><b>Verify transaction</b><input id="order" placeholder="Order ID"><input id="tx" placeholder="0x transaction hash"><button class="secondary" id="verify">Verify transaction</button><pre id="verifyOut"></pre></section><section class="panel"><b>Human compliance gate</b><p class="tiny">This does not perform sanctions/risk screening. Use only after the approved external review has actually been completed for this exact transaction.</p><input id="reviewer" placeholder="Reviewer name"><input id="reference" placeholder="External review reference"><label class="attest"><input id="reviewed" type="checkbox">I attest that the approved external review was completed for this exact order and transaction.</label><button class="secondary" id="clear">Record compliance clear</button><pre id="clearOut"></pre></section></main><script>
const q=s=>document.querySelector(s),create=q('#create'),invoice=q('#invoice');const key={value:''};
async function api(path,opt={}){opt.headers={...(opt.headers||{}),'X-JakeAI-Preview-Key':key.value};const x=await fetch(path,opt);let j={};try{j=await x.json()}catch{}if(!x.ok)throw new Error(typeof j.detail==='string'?j.detail:JSON.stringify(j.detail||('HTTP '+x.status)));return j}
q('#ack').onchange=()=>{create.disabled=true};
create.onclick=async()=>{try{const j=await api('/v1/commerce/wallet-preview/create-canary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({acknowledge_irreversible_payment:q('#ack').checked})});q('#order').value=j.order_id;invoice.innerHTML='<pre>'+JSON.stringify(j,null,2)+'</pre>'}catch(e){invoice.innerHTML='<pre>'+e.message+'</pre>'}}
q('#verify').onclick=async()=>{try{const j=await api('/v1/checkout/crypto/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({order_id:q('#order').value,tx_hash:q('#tx').value})});q('#verifyOut').textContent=JSON.stringify(j,null,2)}catch(e){q('#verifyOut').textContent=e.message}}
q('#clear').onclick=async()=>{try{const j=await api('/v1/commerce/wallet-preview/compliance-clear',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({order_id:q('#order').value,tx_hash:q('#tx').value,reviewer:q('#reviewer').value,reference:q('#reference').value||null,attest_external_review_complete:q('#reviewed').checked})});q('#clearOut').textContent=JSON.stringify(j,null,2)}catch(e){q('#clearOut').textContent=e.message}}
</script></body></html>"""
    html = html.replace("__STATUS__", status_html).replace("__SUMMARY__", summary)
    return _WalletHTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store, max-age=0",
            "X-Robots-Tag": "noindex, nofollow, noarchive",
        },
    )
