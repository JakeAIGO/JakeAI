import sqlite3
import os
import uuid
import stripe
import urllib.request
import re
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
    
    # Seed Products if empty or update featured
    cursor.execute("SELECT COUNT(*) FROM products WHERE id = 'prod_scrape_01'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO products (id, title, description, category, price, endpoint_url, vendor_did)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "prod_scrape_01",
            "JakeAI Web-to-Markdown Extraction API (100 Credits)",
            "High-speed clean text & markdown extractor for LLMs and autonomous agents. Bypasses ads, navigation, and bloated HTML.",
            "ai-utilities",
            5.00,
            "https://agent-commerce-network-production-56e8.up.railway.app/v1/tools/extract-markdown",
            "did:a2a:jakeai_core"
        ))
    conn.commit()
    conn.close()

init_db()

app = FastAPI(
    title="JakeAI — Autonomous Commerce Network",
    description="Machine-Native Registry, Discovery & Settlement for Autonomous AI Agents.",
    version="1.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class ExtractRequest(BaseModel):
    url: str = Field(..., example="https://en.wikipedia.org/wiki/Artificial_intelligence")

class ProductManifest(BaseModel):
    title: str
    description: str
    category: str
    price: float
    endpoint_url: str
    vendor_did: str

class SearchQuery(BaseModel):
    query: Optional[str] = ""
    category: Optional[str] = None
    max_price: Optional[float] = None
    limit: Optional[int] = 10

# Working AI Tool Endpoint
@app.post("/v1/tools/extract-markdown")
def extract_markdown(req: ExtractRequest):
    """Real functioning utility that extracts clean text from any webpage for AI agents"""
    try:
        headers = {'User-Agent': 'JakeAIBot/1.0 (+https://www.jakeaiofficial.com)'}
        request_obj = urllib.request.Request(req.url, headers=headers)
        with urllib.request.urlopen(request_obj, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        # Clean HTML tags to extract raw content
        cleaned = re.sub(r'<(script|style).*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^<]+?>', ' ', cleaned)
        text = re.sub(r'\s+', ' ', text).strip()
        
        return {
            "status": "success",
            "source_url": req.url,
            "word_count": len(text.split()),
            "markdown_content": text[:4000] # preview first 4000 characters
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Extraction failed: {str(e)}")

# Machine Discovery & Specifications
@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    return """# JakeAI Network — Agent-to-Agent Machine Specification
> System: Decentralized commerce and capability exchange for autonomous AI agents.
> Host: www.jakeaiofficial.com
> Protocol Fee: 1.0% (100 basis points) on completed settlements.

## Available Products & Tools for AI Agents:
1. Web-to-Markdown Extraction API (100 Credits)
   - Product ID: prod_scrape_01
   - Price: $5.00 USD
   - Direct Stripe Checkout: https://agent-commerce-network-production-56e8.up.railway.app/v1/checkout/buy/prod_scrape_01
   - API Tool Endpoint: POST /v1/tools/extract-markdown
   - Payload: {"url": "https://example.com"}

2. Discovery & Search: POST /v1/products/search
   - Accepts: {"query": "ai-utilities"}
"""

@app.get("/.well-known/agent.json", response_class=JSONResponse)
def agent_card():
    return {
        "name": "JakeAI Commerce Network",
        "url": "https://www.jakeaiofficial.com",
        "description": "Zero-friction tool registry for autonomous AI agents.",
        "featured_tool": {
            "name": "Web-to-Markdown Extractor",
            "id": "prod_scrape_01",
            "endpoint": "https://agent-commerce-network-production-56e8.up.railway.app/v1/tools/extract-markdown",
            "price_usd": 5.00,
            "checkout_url": "https://agent-commerce-network-production-56e8.up.railway.app/v1/checkout/buy/prod_scrape_01"
        }
    }

# Stripe Checkout Session
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
                    'unit_amount': int(prod[3] * 100),
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
    cursor.execute("SELECT id, title, description, category, price, endpoint_url, vendor_did FROM products")
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": r[0], "title": r[1], "description": r[2], "category": r[3], "price": r[4], "endpoint_url": r[5], "vendor_did": r[6]}
        for r in rows
    ]

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
