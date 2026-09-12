import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode, urlparse

import stripe
from fastapi import Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

import main

app = main.app
DB_PATH = main.DB_PATH
SECURE_DELIVERY_URL = "https://jakeai-secure-delivery-z0syg0.v2.appdeploy.ai/"

GAME_QA_PRODUCT_ID = "prod_game_qa_autopilot_01"
GAME_QA_PRODUCT = {"title":"Game QA Autopilot v1.0","description":"Practical game QA workflow kit for build fingerprinting, smoke tests, test matrices, edge cases, reproducible bug reports, regression queues, and release-readiness review. Human testing remains required.","category":"gaming-qa-workflow","price":9.99,"download_url":SECURE_DELIVERY_URL,"delivery_mode":"protected_order","vendor_did":"did:a2a:jakeai_core"}
BOSS_FIGHT_PRODUCT_ID = "prod_boss_fight_lab_01"
BOSS_FIGHT_PRODUCT = {"title":"Boss Fight Lab v1.0","description":"Original boss-encounter design workflow with arena mechanics, readable phases, telegraphs, counterplay, difficulty scaling, rewards, implementation notes, and accessibility/frustration-risk review.","category":"games-creative-workflow","price":3.99,"download_url":SECURE_DELIVERY_URL,"delivery_mode":"protected_order","vendor_did":"did:a2a:jakeai_core"}
INVENTORY_PRODUCT_ID = "prod_inventory_replenishment_01"
INVENTORY_PRODUCT = {"title":"JakeAI Inventory & Replenishment Intelligence Autopilot — Founding Pilot","description":"CSV-based inventory decision-support workflow that identifies stockout risk, reorder candidates, excess or possible-obsolete inventory, and suggested replenishment quantities for authorized buyer review. No purchase orders are placed autonomously.","category":"inventory-replenishment-workflow","price":49.00,"download_url":SECURE_DELIVERY_URL,"delivery_mode":"protected_order","vendor_did":"did:a2a:jakeai_core"}
POOL_PRODUCT_ID = "prod_pool_coach_autopilot_01"
POOL_PRODUCT = {"title":"JakeAI Pool Coach Autopilot v1.0","description":"A lightweight pool-practice companion that turns plain-language session notes into recurring-pattern tracking and a focused next-session warmup. Recreational training aid; no wagering, guaranteed shot prediction, or camera analysis in v1.0.","category":"sports-practice-workflow","price":1.00,"download_url":SECURE_DELIVERY_URL,"delivery_mode":"protected_order","vendor_did":"did:a2a:jakeai_core"}

PROMOTED_PRODUCTS={GAME_QA_PRODUCT_ID:GAME_QA_PRODUCT,BOSS_FIGHT_PRODUCT_ID:BOSS_FIGHT_PRODUCT,INVENTORY_PRODUCT_ID:INVENTORY_PRODUCT,POOL_PRODUCT_ID:POOL_PRODUCT}
main.GENESIS_CATALOG.update(PROMOTED_PRODUCTS)
COMMERCE_ENABLED={"prod_make_free_00","prod_solar_guide_04",GAME_QA_PRODUCT_ID,BOSS_FIGHT_PRODUCT_ID,INVENTORY_PRODUCT_ID,POOL_PRODUCT_ID}

app.user_middleware=[m for m in app.user_middleware if m.cls is not CORSMiddleware]
app.add_middleware(CORSMiddleware,allow_origins=["https://jakeaiofficial.com","https://www.jakeaiofficial.com"],allow_credentials=False,allow_methods=["GET","POST","OPTIONS"],allow_headers=["Content-Type","Idempotency-Key"])

def is_safe_url(url:str)->bool:
    try: parsed=urlparse(url)
    except Exception:return False
    return parsed.scheme=="https" and (parsed.hostname or "").lower() in {"jakeaiofficial.com","www.jakeaiofficial.com","docs.google.com","drive.google.com","jakeai-secure-delivery-z0syg0.v2.appdeploy.ai"}

def is_product_checkout_enabled(product_id:str)->bool:
    p=main.GENESIS_CATALOG.get(product_id)
    return bool(p and not p.get("requires_metering",False) and product_id in COMMERCE_ENABLED and p.get("download_url") and is_safe_url(p["download_url"]))

def _delivery_target(product_id,product,order_id):
    url=product["download_url"]
    if product.get("delivery_mode")!="protected_order":return url
    return f"{url}{'&' if '?' in url else '?'}{urlencode({'order_id':order_id,'product_id':product_id})}"

def _init_commerce_tables():
    conn=sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS commerce_orders (id TEXT PRIMARY KEY,product_id TEXT NOT NULL,amount_cents INTEGER NOT NULL,status TEXT NOT NULL,stripe_session_id TEXT,source TEXT,created_at TEXT NOT NULL,completed_at TEXT)")
    for product_id,p in PROMOTED_PRODUCTS.items(): conn.execute("INSERT OR REPLACE INTO products (id,title,description,category,price,endpoint_url,vendor_did) VALUES (?,?,?,?,?,?,?)",(product_id,p["title"],p["description"],p["category"],p["price"],p["download_url"],p["vendor_did"]))
    conn.commit();conn.close()

def _create_order(product_id,amount_cents,status,source=None):
    oid=f"ord_{uuid.uuid4().hex}"; now=datetime.now(timezone.utc).isoformat();conn=sqlite3.connect(DB_PATH);conn.execute("INSERT INTO commerce_orders (id,product_id,amount_cents,status,source,created_at) VALUES (?,?,?,?,?,?)",(oid,product_id,amount_cents,status,source,now));conn.commit();conn.close();return oid

def _mark_order_paid(order_id,session_id):
    conn=sqlite3.connect(DB_PATH);conn.execute("UPDATE commerce_orders SET status='paid',stripe_session_id=?,completed_at=? WHERE id=?",(session_id,datetime.now(timezone.utc).isoformat(),order_id));conn.commit();conn.close()

def _get_order(order_id):
    conn=sqlite3.connect(DB_PATH);conn.row_factory=sqlite3.Row;row=conn.execute("SELECT * FROM commerce_orders WHERE id=?",(order_id,)).fetchone();conn.close();return dict(row) if row else None

_init_commerce_tables()
_legacy_paths={"/v1/checkout/buy/{product_id}","/v1/checkout/create-session"}
app.router.routes[:]=[r for r in app.router.routes if getattr(r,"path",None) not in _legacy_paths]

@app.get("/v1/checkout/buy/{product_id}")
async def buy_product(product_id:str,request:Request,source:Optional[str]=None,idempotency_key:Optional[str]=Header(None,alias="Idempotency-Key")):
    product=main.GENESIS_CATALOG.get(product_id)
    if not product:raise HTTPException(404,"Product not found")
    if not is_product_checkout_enabled(product_id):raise HTTPException(409,"Checkout is not active for this product yet")
    amount_cents=int(round(float(product.get("price",0))*100));delivery_url=product.get("download_url")
    if not delivery_url or not is_safe_url(delivery_url):raise HTTPException(409,"Product delivery is not configured safely")
    if amount_cents<=0:
        oid=_create_order(product_id,0,"free_claim_complete",source or "direct");return RedirectResponse(_delivery_target(product_id,product,oid),303)
    secret=os.environ.get("STRIPE_SECRET_KEY","").strip()
    if not secret:raise HTTPException(503,"Payment processor is temporarily unavailable")
    stripe.api_key=secret;oid=_create_order(product_id,amount_cents,"pending_payment",source or "direct");base=str(request.base_url).rstrip("/")
    try:
        session=stripe.checkout.Session.create(payment_method_types=["card"],line_items=[{"price_data":{"currency":"usd","product_data":{"name":product["title"],"description":product["description"][:250]},"unit_amount":amount_cents},"quantity":1}],mode="payment",success_url=f"{base}/v1/checkout/complete?session_id={{CHECKOUT_SESSION_ID}}&order_id={oid}",cancel_url="https://www.jakeaiofficial.com/?payment=cancelled",metadata={"jakeai_order_id":oid,"product_id":product_id},**({"idempotency_key":idempotency_key} if idempotency_key else {}))
    except Exception as exc:raise HTTPException(400,f"Checkout could not be created: {exc}")
    conn=sqlite3.connect(DB_PATH);conn.execute("UPDATE commerce_orders SET stripe_session_id=? WHERE id=?",(session.id,oid));conn.commit();conn.close();return RedirectResponse(session.url,303)

@app.get("/v1/checkout/complete")
def complete_checkout(session_id:str,order_id:str):
    order=_get_order(order_id)
    if not order:raise HTTPException(404,"Order not found")
    if not is_product_checkout_enabled(order["product_id"]):raise HTTPException(409,"Product is not enabled for commerce")
    product=main.GENESIS_CATALOG.get(order["product_id"]);target=_delivery_target(order["product_id"],product,order_id)
    if order["status"]=="paid" and order.get("stripe_session_id")==session_id:return RedirectResponse(target,303)
    secret=os.environ.get("STRIPE_SECRET_KEY","").strip()
    if not secret:raise HTTPException(503,"Payment verification is temporarily unavailable")
    stripe.api_key=secret
    try:session=stripe.checkout.Session.retrieve(session_id)
    except Exception as exc:raise HTTPException(400,f"Payment verification failed: {exc}")
    md=getattr(session,"metadata",{}) or {}
    if getattr(session,"payment_status",None)!="paid" or md.get("jakeai_order_id")!=order_id or md.get("product_id")!=order["product_id"] or int(getattr(session,"amount_total",-1) or -1)!=int(order["amount_cents"]) or str(getattr(session,"currency","")).lower()!="usd":raise HTTPException(402,"Payment has not been verified for this order")
    _mark_order_paid(order_id,session_id);return RedirectResponse(target,303)

@app.get("/v1/commerce/status/{order_id}")
def commerce_status(order_id:str):
    order=_get_order(order_id)
    if not order:raise HTTPException(404,"Order not found")
    return {k:order[k] for k in ["id","product_id","amount_cents","status","created_at","completed_at"]}
