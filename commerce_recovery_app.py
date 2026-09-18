import os
from datetime import datetime, timezone

import stripe
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse

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


@app.get("/", response_class=HTMLResponse)
def private_commerce_preview():
    if os.environ.get("JAKEAI_COMMERCE_DRY_RUN_ENABLED","").strip().lower() not in {"1","true","yes","on"}:
        raise HTTPException(404,"Not Found")
    return """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>JakeAI Commerce — Isolated Preview</title><style>:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#05070c;color:#eef5ff;font:16px/1.5 system-ui,sans-serif}main{max-width:720px;margin:auto;padding:28px 18px}.brand{font-weight:900;font-size:30px}.brand b{color:#62e7ff}.eyebrow{letter-spacing:.16em;text-transform:uppercase;color:#8fa8bf;font-size:12px}.panel{margin-top:22px;padding:22px;border:1px solid #203047;border-radius:20px;background:#0c1320}h1{font-size:34px;line-height:1.08}p{color:#b8c7d8}.notice{margin-top:16px;padding:13px;border:1px solid #263b51;border-radius:12px;color:#9fb4c8}.action,input{width:100%;margin-top:12px;padding:15px;border-radius:14px;font:inherit}.action{border:0;background:#eef5ff;color:#07101a;font-weight:850}.action:disabled{opacity:.45}input{border:1px solid #2b405a;background:#080b12;color:#eef5ff}pre{white-space:pre-wrap;word-break:break-word;color:#a8efff}</style></head><body><main><div class="brand">Jake<b>AI</b></div><div class="eyebrow">Commerce · Isolated Railway Preview</div><section class="panel"><h1>Zero-money commerce simulation.</h1><p>This surface exercises JakeAI order → entitlement → receipt. Card, USDC, Stripe and blockchain execution are not available here.</p><div class="notice"><strong>Private preview authorization</strong><input id="key" type="password" autocomplete="off" placeholder="Paste temporary preview password"><button class="action" id="run">Run zero-money simulation</button><pre id="out"></pre></div><div class="notice">SIMULATION ONLY — money moved: false. External payment processors contacted: false. Blockchain contacted: false.</div></section><script>const run=document.getElementById('run'),out=document.getElementById('out'),key=document.getElementById('key');run.onclick=async()=>{run.disabled=true;out.textContent='Running isolated simulation…';try{const r=await fetch('/v1/commerce/dry-run/prod_where_the_hell_are_my_glasses_01',{method:'POST',headers:{'X-JakeAI-Preview-Key':key.value}});const j=await r.json();if(!r.ok)throw new Error(j.detail||'Simulation unavailable');out.textContent=JSON.stringify(j,null,2)}catch(e){out.textContent=e.message}finally{run.disabled=false}};</script></main></body></html>"""
