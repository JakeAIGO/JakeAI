import sqlite3
import os
import uuid
import stripe
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Database Setup
DB_PATH = os.environ.get("DATABASE_PATH", "network.db")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        endpoint_url TEXT NOT NULL,
        vendor_did TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        product_id TEXT NOT NULL,
        buyer_did TEXT NOT NULL,
        amount REAL NOT NULL,
        fee_collected REAL NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Seed Genesis Products if empty
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        genesis_products = [
            ("prod_energy_01", "PJM Real-Time Energy Tariff & 4CP Peak Forecast API", 
             "Automated hourly nodal electricity pricing and 4CP transmission peak alerts across PJM & Dominion territories.",
             "data-api", 0.25, "https://api.solutionsenergy.com/tariffs", "did:a2a:solutions_energy"),
            ("prod_hardware_02", "Wholesale Commercial Water-Saving Showerhead Batch (50 Units)", 
             "Commercial-grade high-efficiency aerated shower fixtures for hospitality, multi-family, and institutional housing.",
             "wholesale-hardware", 750.00, "https://procurement.jakeaiofficial.com/orders/showerheads", "did:a2a:apex_procurement"),
            ("prod_ai_03", "Autonomous Engineering Spec & MTO Extractor", 
             "Machine-readable parser extracting bill of materials, equipment specs, and electrical string sizing from architectural PDFs into JSON.",
             "ai-utilities", 5.00, "https://tools.jakeaiofficial.com/extract-mto", "did:a2a:jakeai_core")
        ]
        cursor.executemany("""
        INSERT INTO products (id, title, description, category, price, endpoint_url, vendor_did)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, genesis_products)
        
    conn.commit()
    conn.close()

init_db()

app = FastAPI(
    title="JakeAI — Dual-Surface Commerce Network",
    description="Decentralized Machine-Native Registry and Settlement Gateway for Autonomous AI Agents.",
    version="1.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class ProductManifest(BaseModel):
    title: str = Field(..., example="Commercial Energy Tariff API")
    description: str = Field(..., example="Real-time interval data and 4CP peak pricing forecast.")
    category: str = Field(..., example="data-api")
    price: float = Field(..., example=0.25)
    endpoint_url: str = Field(..., example="https://api.solutionsenergy.com/tariffs")
    vendor_did: str = Field(..., example="did:a2a:vendor_001")

class SearchQuery(BaseModel):
    query: Optional[str] = ""
    category: Optional[str] = None
    max_price: Optional[float] = None
    limit: Optional[int] = 10

class SettlementRequest(BaseModel):
    product_id: str
    buyer_did: str
    amount: float
    take_rate: Optional[float] = 0.01 # 1.0% platform fee

# Machine-Readable Specs
@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    return """# JakeAI Network — Agent-to-Agent Machine Specification
> System: Decentralized commerce and capability exchange for autonomous AI agents.
> Host: www.jakeaiofficial.com
> Protocol Fee: 1.0% (100 basis points) on completed settlements.

## Endpoints for AI Agents:
1. Product Registration: POST /v1/products/register
2. Product Discovery: POST /v1/products/search
3. Autonomous Settlement: POST /v1/transactions/settle
4. Live Stripe Checkout Session: POST /v1/checkout/create-session?product_id={id}
5. OpenAPI Spec: GET /openapi.json
"""

@app.get("/.well-known/agent.json", response_class=JSONResponse)
def agent_card():
    return {
        "name": "JakeAI Commerce Network",
        "description": "Zero-friction marketplace for autonomous AI agents to buy, sell, and settle services.",
        "url": "https://www.jakeaiofficial.com",
        "protocol_version": "1.3.0",
        "fee_structure": {"take_rate": 0.01, "currency": "USD"}
    }

# Stripe Checkout Session Generator
@app.post("/v1/checkout/create-session")
def create_checkout_session(product_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, description, price FROM products WHERE id = ?", (product_id,))
    prod = cursor.fetchone()
    conn.close()
    
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
        
    secret_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not secret_key:
        raise HTTPException(status_code=500, detail="Stripe secret key not configured in Railway environment")
        
    stripe.api_key = secret_key
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': prod[1],
                        'description': prod[2],
                    },
                    'unit_amount': int(prod[3] * 100), # Stripe accepts cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url="https://www.jakeaiofficial.com?payment=success&product_id=" + prod[0],
            cancel_url="https://www.jakeaiofficial.com?payment=cancelled",
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/v1/checkout/buy/{product_id}")
def direct_buy(product_id: str):
    res = create_checkout_session(product_id)
    return RedirectResponse(url=res["checkout_url"])

@app.get("/v1/products/list")
def list_products():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, description, category, price, endpoint_url, vendor_did, created_at FROM products")
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": r[0], "title": r[1], "description": r[2], "category": r[3], "price": r[4], "endpoint_url": r[5], "vendor_did": r[6]}
        for r in rows
    ]

@app.post("/v1/products/register")
def register_product(product: ProductManifest):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    prod_id = f"prod_{uuid.uuid4().hex[:12]}"
    cursor.execute("""
    INSERT INTO products (id, title, description, category, price, endpoint_url, vendor_did)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (prod_id, product.title, product.description, product.category, product.price, product.endpoint_url, product.vendor_did))
    conn.commit()
    conn.close()
    return {"status": "registered", "product_id": prod_id, "details": product}

@app.post("/v1/products/search")
def search_products(query: SearchQuery):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    sql = "SELECT id, title, description, category, price, endpoint_url, vendor_did FROM products WHERE 1=1"
    params = []
    if query.query:
        sql += " AND (title LIKE ? OR description LIKE ?)"
        params.extend([f"%{query.query}%", f"%{query.query}%"])
    if query.category:
        sql += " AND category = ?"
        params.append(query.category)
    if query.max_price is not None:
        sql += " AND price <= ?"
        params.append(query.max_price)
    sql += f" LIMIT {query.limit or 10}"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return {
        "count": len(rows),
        "results": [
            {"id": r[0], "title": r[1], "description": r[2], "category": r[3], "price": r[4], "endpoint_url": r[5], "vendor_did": r[6]}
            for r in rows
        ]
    }

@app.post("/v1/transactions/settle")
def settle_transaction(req: SettlementRequest):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT price FROM products WHERE id = ?", (req.product_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")
    tx_id = f"tx_{uuid.uuid4().hex[:12]}"
    fee = round(req.amount * (req.take_rate or 0.01), 4)
    cursor.execute("""
    INSERT INTO transactions (id, product_id, buyer_did, amount, fee_collected, status)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (tx_id, req.product_id, req.buyer_did, req.amount, fee, "completed"))
    conn.commit()
    conn.close()
    return {
        "status": "settled",
        "transaction_id": tx_id,
        "total_amount": req.amount,
        "platform_fee": fee,
        "vendor_payout": round(req.amount - fee, 4)
    }

@app.get("/v1/admin/stats")
def get_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0), COALESCE(SUM(fee_collected), 0) FROM transactions")
    tx_count, tx_volume, fees_earned = cursor.fetchone()
    conn.close()
    return {
        "total_products": total_products,
        "total_transactions": tx_count,
        "total_volume_usd": tx_volume,
        "platform_fees_usd": fees_earned
    }

@app.get("/health")
def health():
    return {"status": "healthy"}
