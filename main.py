import sqlite3
import os
import uuid
import stripe
import urllib.request
import re
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB_PATH = os.environ.get("DATABASE_PATH", "network.db")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# 100% Hands-Off Autonomous Digital Products (Zero Physical Shipping)
GENESIS_CATALOG = {
    "prod_solar_guide_04": {
        "title": "Commercial Solar & BESS Microgrid Sizing Guide (2026 PDF)",
        "description": "Dense reference guide covering C&I electrical string sizing, 4CP peak-shaving dispatch, and IRA tax credit stacking formulas.",
        "category": "digital-guide",
        "price": 3.00,
        "download_url": "https://drive.google.com/file/d/1xFpazazGdH2_LGSkvuWgMmR5jhPnq7pv/view?usp=drivesdk",
        "vendor_did": "did:a2a:solutions_energy"
    },
    "prod_scrape_01": {
        "title": "JakeAI Web-to-Markdown Extraction API (100 Credits)",
        "description": "High-speed clean text & markdown extractor for LLMs and autonomous agents. Zero human interaction, instant digital delivery.",
        "category": "ai-utilities",
        "price": 5.00,
        "download_url": "https://agent-commerce-network-production-56e8.up.railway.app/v1/tools/extract-markdown",
        "vendor_did": "did:a2a:jakeai_core"
    },
    "prod_energy_01": {
        "title": "PJM Real-Time Energy Tariff & 4CP Peak Forecast API",
        "description": "Automated nodal electricity price queries and 4CP transmission peak alerts across PJM & Dominion territories.",
        "category": "data-api",
        "price": 0.25,
        "download_url": "https://api.solutionsenergy.com/tariffs",
        "vendor_did": "did:a2a:solutions_energy"
    },
    "prod_ai_03": {
        "title": "Autonomous Architectural Spec & MTO Extractor",
        "description": "Machine-readable parser extracting bill of materials and equipment specs from architectural PDFs into JSON.",
        "category": "ai-utilities",
        "price": 5.00,
        "download_url": "https://tools.jakeaiofficial.com/extract-mto",
        "vendor_did": "did:a2a:jakeai_core"
    }
}

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
    for pid, p in GENESIS_CATALOG.items():
        cursor.execute("SELECT id FROM products WHERE id = ?", (pid,))
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO products (id, title, description, category, price, endpoint_url, vendor_did)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pid, p["title"], p["description"], p["category"], p["price"], p["download_url"], p["vendor_did"]))
    conn.commit()
    conn.close()

init_db()

app = FastAPI(
    title="JakeAI — Autonomous Commerce Network",
    description="100% Hands-Off Machine Registry & Settlement Rails.",
    version="1.7.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExtractRequest(BaseModel):
    url: str

@app.post("/v1/tools/extract-markdown")
def extract_markdown(req: ExtractRequest):
    try:
        headers = {'User-Agent': 'JakeAIBot/1.0 (+https://www.jakeaiofficial.com)'}
        request_obj = urllib.request.Request(req.url, headers=headers)
        with urllib.request.urlopen(request_obj, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
        cleaned = re.sub(r'<(script|style).*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^<]+?>', ' ', cleaned)
        text = re.sub(r'\s+', ' ', text).strip()
        return {
            "status": "success",
            "source_url": req.url,
            "word_count": len(text.split()),
            "markdown_content": text[:4000]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Extraction failed: {str(e)}")

@app.get("/v1/checkout/buy/{product_id}")
@app.post("/v1/checkout/create-session")
def create_checkout_session(product_id: str):
    prod_data = GENESIS_CATALOG.get(product_id)
    if not prod_data:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
        
    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY missing in Railway variables")
        
    stripe.api_key = secret_key
    success_url = prod_data.get("download_url", "https://www.jakeaiofficial.com?payment=success")
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': prod_data["title"],
                        'description': prod_data["description"][:250],
                    },
                    'unit_amount': int(prod_data["price"] * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url="https://www.jakeaiofficial.com?payment=cancelled",
        )
        return RedirectResponse(url=session.url, status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Stripe Error: {str(e)}")

@app.get("/v1/products/list")
def list_products():
    return list(GENESIS_CATALOG.values())

@app.get("/health")
def health():
    return {"status": "healthy", "service": "JakeAI"}
