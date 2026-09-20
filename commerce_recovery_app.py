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
BASE_SEPOLIA_CHAIN_ID = 84532
BASE_SEPOLIA_USDC_CONTRACT = "0x036cbd53842c5426634e7929541ec2318f3dcf7e"

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


def _canary_runtime_ready() -> tuple[bool, list[str]]:
    config = crypto_runtime._crypto_config()
    errors = []
    if config.chain_id != crypto_runtime.BASE_MAINNET_CHAIN_ID:
        errors.append("unsupported chain")
    if config.token_contract != crypto_runtime.BASE_NATIVE_USDC_CONTRACT:
        errors.append("unsupported token contract")
    if not config.merchant_address:
        errors.append("merchant address missing")
    if not os.environ.get("BASE_RPC_URL", "").strip():
        errors.append("Base RPC missing")
    return (not errors, errors)


def _get_or_create_canary_invoice() -> Optional[dict]:
    if not _wallet_bool("JAKEAI_CRYPTO_CANARY_ENABLED"):
        return None
    ready, errors = _canary_runtime_ready()
    if not ready:
        raise HTTPException(status_code=503, detail="Canary configuration incomplete: " + ", ".join(errors))
    conn = commerce_app._commerce_conn()
    conn.row_factory = __import__("sqlite3").Row
    row = conn.execute(
        """
        SELECT id, status
        FROM commerce_orders
        WHERE product_id = ? AND source = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        ("prod_crypto_canary_preview", "crypto-test"),
    ).fetchone()
    conn.close()
    if row and row["status"] in {"crypto_awaiting_payment", "pending_payment"}:
        crypto_order = crypto_runtime._get_crypto_order(row["id"])
        if crypto_order:
            return {
                "order_id": row["id"],
                "amount_usdc": crypto_order["amount_usdc"],
                "merchant_address": crypto_runtime._crypto_config().merchant_address,
            }
    config = crypto_runtime._crypto_config()
    return crypto_runtime._create_crypto_order(
        "prod_crypto_canary_preview",
        10,
        "crypto-test",
        config.merchant_address,
    )


def _testnet_canary_runtime_ready() -> tuple[bool, list[str]]:
    base = crypto_runtime._crypto_config()
    errors = []
    if not base.merchant_address:
        errors.append("merchant address missing")
    if not os.environ.get("BASE_SEPOLIA_RPC_URL", "").strip():
        errors.append("Base Sepolia RPC missing")
    return (not errors, errors)


def _get_or_create_testnet_invoice() -> Optional[dict]:
    if not _wallet_bool("JAKEAI_CRYPTO_TESTNET_ENABLED"):
        return None
    ready, errors = _testnet_canary_runtime_ready()
    if not ready:
        raise HTTPException(status_code=503, detail="Testnet configuration incomplete: " + ", ".join(errors))
    conn = commerce_app._commerce_conn()
    conn.row_factory = __import__("sqlite3").Row
    row = conn.execute(
        """
        SELECT id, status
        FROM commerce_orders
        WHERE product_id = ? AND source = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        ("prod_crypto_canary_sepolia_preview", "crypto-testnet"),
    ).fetchone()
    conn.close()
    if row and row["status"] in {"crypto_awaiting_payment", "pending_payment"}:
        crypto_order = crypto_runtime._get_crypto_order(row["id"])
        if crypto_order:
            return {
                "order_id": row["id"],
                "amount_usdc": crypto_order["amount_usdc"],
                "merchant_address": crypto_runtime._crypto_config().merchant_address,
            }
    base = crypto_runtime._crypto_config()
    return crypto_runtime._create_crypto_order(
        "prod_crypto_canary_sepolia_preview",
        10,
        "crypto-testnet",
        base.merchant_address,
    )


class WalletCanaryVerifyRequest(BaseModel):
    order_id: str = Field(..., min_length=5, max_length=100)
    tx_hash: str = Field(..., min_length=66, max_length=66)


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
    ready, errors = _canary_runtime_ready()
    if not ready:
        raise HTTPException(status_code=503, detail="Canary configuration incomplete: " + ", ".join(errors))
    created = _get_or_create_canary_invoice()
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


@app.post("/v1/commerce/wallet-preview/verify-canary")
def wallet_preview_verify_canary(req: WalletCanaryVerifyRequest):
    if not _wallet_bool("JAKEAI_CRYPTO_CANARY_ENABLED"):
        raise HTTPException(status_code=409, detail="Real-money crypto canary is disabled")
    order = commerce_app._get_order(req.order_id)
    crypto_order = crypto_runtime._get_crypto_order(req.order_id)
    if not order or not crypto_order:
        raise HTTPException(status_code=404, detail="Canary order not found")
    if order.get("product_id") != "prod_crypto_canary_preview" or order.get("source") != "crypto-test":
        raise HTTPException(status_code=409, detail="This verification route is limited to the isolated canary order")
    base = crypto_runtime._crypto_config()
    ready, errors = _canary_runtime_ready()
    if not ready:
        raise HTTPException(status_code=503, detail="Canary configuration incomplete: " + ", ".join(errors))
    config = crypto_runtime.CryptoPaymentConfig(
        enabled=True,
        auto_fulfill_enabled=False,
        chain_id=base.chain_id,
        token_contract=base.token_contract,
        merchant_address=base.merchant_address,
        creator_payouts_enabled=False,
        customer_custody_enabled=False,
        exchange_functions_enabled=False,
    )
    tx_hash = crypto_runtime._require_tx_hash(req.tx_hash)
    amount_usd = crypto_runtime.Decimal(int(order["amount_cents"])) / crypto_runtime.Decimal(100)
    invoice = crypto_runtime.PaymentInvoice.create(req.order_id, amount_usd, config.merchant_address)
    registry = crypto_runtime.SqliteTransactionRegistry(crypto_runtime.DB_PATH)
    compliance_provider = crypto_runtime.ReviewedComplianceProvider(crypto_runtime.DB_PATH, req.order_id)
    try:
        result = crypto_runtime.verify_submitted_payment(
            rpc=crypto_runtime._rpc_client(),
            config=config,
            invoice=invoice,
            tx_hash=tx_hash,
            compliance_provider=compliance_provider,
            registry=registry,
            minimum_confirmations=max(1, int(os.environ.get("CRYPTO_MIN_CONFIRMATIONS", "2"))),
            usd_fmv=amount_usd,
        )
    except (ValueError, RuntimeError, OSError) as exc:
        crypto_runtime._update_crypto_state(req.order_id, state=crypto_runtime.PaymentState.FAILED.value, tx_hash=tx_hash)
        raise HTTPException(status_code=422, detail=f"Canary payment could not be verified: {exc}") from exc

    crypto_runtime._update_crypto_state(
        req.order_id,
        state=result.validation.state.value,
        tx_hash=result.tx_hash,
        compliance=result.compliance,
    )
    if result.recorded and result.validation.accepted:
        crypto_runtime._mark_crypto_paid(req.order_id, result.tx_hash, result.compliance)

    return {
        "order_id": req.order_id,
        "state": "paid" if result.recorded else result.validation.state.value,
        "accepted": result.validation.accepted,
        "reason": result.validation.reason,
        "tx_hash": result.tx_hash,
        "block_number": result.block_number,
        "confirmations_required": max(1, int(os.environ.get("CRYPTO_MIN_CONFIRMATIONS", "2"))),
        "compliance_provider": result.compliance.provider,
        "compliance_reference": result.compliance.reference,
        "delivery_ready": False,
        "next_step": "If state is compliance_hold, stop. JakeAI must complete the separate compliance review before final clearance.",
    }


@app.post("/v1/commerce/wallet-preview/verify-testnet-canary")
def wallet_preview_verify_testnet_canary(req: WalletCanaryVerifyRequest):
    if not _wallet_bool("JAKEAI_CRYPTO_TESTNET_ENABLED"):
        raise HTTPException(status_code=409, detail="Testnet crypto canary is disabled")
    order = commerce_app._get_order(req.order_id)
    crypto_order = crypto_runtime._get_crypto_order(req.order_id)
    if not order or not crypto_order:
        raise HTTPException(status_code=404, detail="Testnet canary order not found")
    if order.get("product_id") != "prod_crypto_canary_sepolia_preview" or order.get("source") != "crypto-testnet":
        raise HTTPException(status_code=409, detail="This route is limited to the isolated Base Sepolia canary")
    ready, errors = _testnet_canary_runtime_ready()
    if not ready:
        raise HTTPException(status_code=503, detail="Testnet configuration incomplete: " + ", ".join(errors))
    base = crypto_runtime._crypto_config()
    config = crypto_runtime.CryptoPaymentConfig(
        enabled=True,
        auto_fulfill_enabled=False,
        chain_id=BASE_SEPOLIA_CHAIN_ID,
        token_contract=BASE_SEPOLIA_USDC_CONTRACT,
        merchant_address=base.merchant_address,
        creator_payouts_enabled=False,
        customer_custody_enabled=False,
        exchange_functions_enabled=False,
    )
    tx_hash = crypto_runtime._require_tx_hash(req.tx_hash)
    amount_usd = crypto_runtime.Decimal(int(order["amount_cents"])) / crypto_runtime.Decimal(100)
    invoice = crypto_runtime.PaymentInvoice.create(req.order_id, amount_usd, config.merchant_address)
    registry = crypto_runtime.SqliteTransactionRegistry(crypto_runtime.DB_PATH)
    compliance_provider = crypto_runtime.ReviewedComplianceProvider(crypto_runtime.DB_PATH, req.order_id)
    rpc_url = os.environ.get("BASE_SEPOLIA_RPC_URL", "").strip()
    try:
        result = crypto_runtime.verify_submitted_payment(
            rpc=crypto_runtime.BaseRpcClient(rpc_url),
            config=config,
            invoice=invoice,
            tx_hash=tx_hash,
            compliance_provider=compliance_provider,
            registry=registry,
            minimum_confirmations=max(1, int(os.environ.get("CRYPTO_MIN_CONFIRMATIONS", "2"))),
            usd_fmv=amount_usd,
        )
    except (ValueError, RuntimeError, OSError) as exc:
        crypto_runtime._update_crypto_state(req.order_id, state=crypto_runtime.PaymentState.FAILED.value, tx_hash=tx_hash)
        raise HTTPException(status_code=422, detail=f"Testnet payment could not be verified: {exc}") from exc

    crypto_runtime._update_crypto_state(
        req.order_id,
        state=result.validation.state.value,
        tx_hash=result.tx_hash,
        compliance=result.compliance,
    )
    if result.recorded and result.validation.accepted:
        crypto_runtime._mark_crypto_paid(req.order_id, result.tx_hash, result.compliance)

    return {
        "order_id": req.order_id,
        "network": "Base Sepolia",
        "chain_id": BASE_SEPOLIA_CHAIN_ID,
        "state": "paid" if result.recorded else result.validation.state.value,
        "accepted": result.validation.accepted,
        "reason": result.validation.reason,
        "tx_hash": result.tx_hash,
        "block_number": result.block_number,
        "delivery_ready": False,
        "testnet": True,
        "next_step": "If state is compliance_hold, the on-chain test passed and the separate test compliance transition can be exercised next.",
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
    canary_invoice = None
    testnet_invoice = None
    if _wallet_bool("JAKEAI_CRYPTO_TESTNET_ENABLED"):
        try:
            testnet_invoice = _get_or_create_testnet_invoice()
        except Exception:
            testnet_invoice = None
    elif status["canary_enabled"]:
        try:
            canary_invoice = _get_or_create_canary_invoice()
        except Exception:
            canary_invoice = None
    status_fields = [
        ("Merchant wallet configured", status["merchant_configured"]),
        ("Base RPC configured", status["rpc_configured"]),
        ("Compliance admin configured", status["admin_review_configured"]),
        ("Preview-only lock", status["preview_only_lock"]),
        ("Public crypto payments", status["payments_enabled"]),
        ("Legal activation", status["legal_approved"]),
        ("Mainnet real-money canary", status["canary_enabled"]),
        ("Base Sepolia test mode", _wallet_bool("JAKEAI_CRYPTO_TESTNET_ENABLED")),
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
    if testnet_invoice:
        canary_html = (
            '<div class="label">MODE</div><div class="value"><b>FREE TESTNET — NO REAL MONEY</b></div>'
            '<div class="label">ORDER ID</div><div class="value">' + testnet_invoice["order_id"] + '</div>'
            '<div class="label">EXACT AMOUNT</div><div class="value"><b>' + testnet_invoice["amount_usdc"] + ' test USDC</b></div>'
            '<div class="label">NETWORK</div><div class="value">Base Sepolia · Chain ID 84532</div>'
            '<div class="label">ASSET</div><div class="value">Circle testnet USDC</div>'
            '<div class="label">MERCHANT ADDRESS</div><div class="value">' + testnet_invoice["merchant_address"] + '</div>'
            '<div class="label">TOKEN CONTRACT</div><div class="value">' + BASE_SEPOLIA_USDC_CONTRACT + '</div>'
            '<p class="ok"><b>No real crypto is required.</b> Testnet USDC and gas tokens are free faucet tokens with no monetary value.</p>'
        )
    elif canary_invoice:
        canary_html = (
            '<div class="label">ORDER ID</div><div class="value">' + canary_invoice["order_id"] + '</div>'
            '<div class="label">EXACT AMOUNT</div><div class="value"><b>' + canary_invoice["amount_usdc"] + ' USDC</b></div>'
            '<div class="label">NETWORK</div><div class="value">Base Mainnet · Chain ID 8453</div>'
            '<div class="label">ASSET</div><div class="value">Native USDC</div>'
            '<div class="label">MERCHANT ADDRESS</div><div class="value">' + canary_invoice["merchant_address"] + '</div>'
            '<div class="label">TOKEN CONTRACT</div><div class="value">' + crypto_runtime.BASE_NATIVE_USDC_CONTRACT + '</div>'
            '<p class="warn"><b>STOP HERE until you deliberately send the 0.10 USDC.</b> Creating this invoice moved no money.</p>'
        )
    else:
        canary_html = '<p class="tiny">All canaries are OFF. No invoice exists and no money can move from this console.</p>'
    html = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="robots" content="noindex,nofollow,noarchive"><title>JakeAI Wallet RC2</title><style>:root{color-scheme:dark;--bg:#03070b;--line:#21445a;--cyan:#5ce8ff;--muted:#91abba;--ok:#68efba;--warn:#ffd27e}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 50% 0,#12334c,var(--bg) 48%);color:#eefaff;font:15px/1.45 system-ui,sans-serif}main{max-width:760px;margin:auto;padding:28px 16px 70px}.brand{font-size:28px;font-weight:950}.brand b{color:var(--cyan)}.eyebrow{font-size:10px;letter-spacing:.18em;color:var(--cyan);font-weight:900}h1{font-size:36px;line-height:1;margin:12px 0}p{color:var(--muted)}.panel{margin-top:15px;padding:18px;border:1px solid var(--line);border-radius:18px;background:#07121dcc}.row{display:grid;grid-template-columns:1fr 1fr;gap:8px}.stat{padding:11px;border:1px solid #ffffff16;border-radius:12px;background:#ffffff05;font-size:12px}.ok{color:var(--ok)}.off{color:#ffc267}input,button{width:100%;padding:14px;margin-top:10px;border-radius:12px;font:inherit}input{background:#03080d;border:1px solid #315067;color:#fff}button{border:0;background:#56ddff;color:#00131b;font-weight:900}button.secondary{background:#132535;color:#dffaff;border:1px solid #315067}button:disabled{opacity:.4}pre{white-space:pre-wrap;word-break:break-word;background:#02070b;padding:12px;border-radius:10px;color:#a9efff;min-height:42px}.warn{border-color:#725823}.tiny{font-size:11px}.attest{display:flex;gap:8px;align-items:flex-start;color:var(--muted);font-size:12px}.attest input{width:auto;margin-top:3px}</style></head><body><main><div class="brand">Jake<b>AI</b></div><div class="eyebrow">WALLET RC2 · ISOLATED TEST CONSOLE</div><h1>Base USDC checkout.</h1><p>Merchant-only, non-custodial and fail-closed. The app never holds a customer's wallet and never signs or broadcasts a transaction.</p><section class="panel"><b>Wallet readiness</b><p class="tiny">Loaded automatically from the JakeAI wallet service. No password and no button required.</p>__SUMMARY__<div class="row">__STATUS__</div><p class="tiny">Network: Base Mainnet · Chain ID 8453 · Asset: native USDC · Minimum confirmations: 2</p><p class="tiny">Refresh this page only if you want to re-check the state.</p></section><section class="panel warn"><b>10¢ payment canary</b><p class="tiny">The isolated preview prefers Base Sepolia testnet. The invoice is generated server-side and has no product fulfillment.</p>__CANARY__</section><section class="panel"><b>After you send the test payment</b><p class="tiny">Paste only the public Base transaction hash below. Never paste a seed phrase, private key, recovery phrase, or wallet password.</p><input id="order" value="__CANARY_ORDER__" readonly><input id="tx" placeholder="0x transaction hash"><button class="secondary" id="verify">Verify canary transaction</button><pre id="verifyOut"></pre><p class="tiny">A valid payment should stop at <b>compliance_hold</b> first. JakeAI handles the separate review step after that.</p></section></main><script>
const q=s=>document.querySelector(s);
async function api(path,opt={}){const x=await fetch(path,opt);let j={};try{j=await x.json()}catch{}if(!x.ok)throw new Error(typeof j.detail==='string'?j.detail:JSON.stringify(j.detail||('HTTP '+x.status)));return j}
q('#verify').onclick=async()=>{try{const endpoint='__VERIFY_ENDPOINT__';const j=await api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({order_id:q('#order').value,tx_hash:q('#tx').value})});q('#verifyOut').textContent=JSON.stringify(j,null,2)}catch(e){q('#verifyOut').textContent=e.message}}
</script></body></html>"""
    active_invoice = testnet_invoice or canary_invoice
    verify_endpoint = "/v1/commerce/wallet-preview/verify-testnet-canary" if testnet_invoice else "/v1/commerce/wallet-preview/verify-canary"
    html = (
        html.replace("__STATUS__", status_html)
        .replace("__SUMMARY__", summary)
        .replace("__CANARY__", canary_html)
        .replace("__CANARY_ORDER__", active_invoice["order_id"] if active_invoice else "")
        .replace("__VERIFY_ENDPOINT__", verify_endpoint)
    )
    return _WalletHTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store, max-age=0",
            "X-Robots-Tag": "noindex, nofollow, noarchive",
        },
    )
