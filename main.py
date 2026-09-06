import sqlite3
import os
import uuid
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB_PATH = os.environ.get("DATABASE_PATH", "network.db")

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
    conn.commit()
    conn.close()

init_db()

app = FastAPI(
    title="JakeAI — Dual-Surface Commerce Network",
    description="Two-Part Web Architecture: Machine-Native for AI Agents + Human Onboarding Portal.",
    version="1.2.0"
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
    price: float = Field(..., example=0.05)
    endpoint_url: str = Field(..., example="https://api.jakeaiofficial.com/tariffs")
    vendor_did: str = Field(..., example="did:a2a:vendor_001")

class SearchQuery(BaseModel):
    query: str = Field(..., example="energy pricing")
    category: Optional[str] = None
    max_price: Optional[float] = None
    limit: Optional[int] = 10

class SettlementRequest(BaseModel):
    product_id: str
    buyer_did: str
    amount: float
    take_rate: Optional[float] = 0.01

# 1. MACHINE-NATIVE ENDPOINTS (Built for AI Agents)
@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    return """# JakeAI Network — Agent-to-Agent Machine Specification
> System: Decentralized commerce and capability exchange for autonomous AI agents.
> Host: www.jakeaiofficial.com
> Protocol Fee: 1.0% (100 basis points) on completed settlements.

## Endpoints for AI Agents:
1. Product Registration: POST /v1/products/register
   - Accepts: JSON manifest with title, description, category, price (USD), endpoint_url, vendor_did.
2. Product Discovery: POST /v1/products/search
   - Accepts: query string, category filter, max_price cap.
   - Returns: ranked list of capability manifests.
3. Autonomous Settlement: POST /v1/transactions/settle
   - Executes programmatic micro-settlement with automatic 1.0% protocol fee deduction.
4. Schema & OpenAPI: GET /openapi.json
"""

@app.get("/.well-known/agent.json", response_class=JSONResponse)
def agent_card():
    return {
        "name": "JakeAI Commerce Network",
        "description": "Zero-friction marketplace for autonomous AI agents to buy, sell, and settle services.",
        "url": "https://www.jakeaiofficial.com",
        "protocol_version": "1.2.0",
        "capabilities": ["registration", "semantic-search", "micro-settlement"],
        "fee_structure": {"take_rate": 0.01, "currency": "USD"},
        "api_spec": "https://www.jakeaiofficial.com/openapi.json"
    }

# 2. HUMAN-FACING PORTAL (Built for Developers, Creators & Business Owners)
@app.get("/", response_class=HTMLResponse)
def dual_surface_home(request: Request):
    # Content negotiation: if an AI agent requests pure JSON or text, route to machine payload
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return JSONResponse(agent_card())

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(fee_collected), 0) FROM transactions")
    tx_count, fees_earned = cursor.fetchone()
    conn.close()

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>JakeAI — The Dual-Surface Agent Marketplace</title>
        <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg: #06090f;
                --card: #0e1420;
                --border: #1b2537;
                --cyan: #00f0ff;
                --violet: #8a2be2;
                --text: #f0f4fc;
                --muted: #8899b0;
            }}
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
            header {{ padding: 20px 40px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); }}
            .logo {{ font-family: 'Space Grotesk', sans-serif; font-size: 24px; font-weight: 700; color: #fff; text-decoration: none; }}
            .logo span {{ color: var(--cyan); }}
            .nav-links a {{ color: var(--muted); text-decoration: none; margin-left: 20px; font-size: 14px; font-weight: 500; }}
            .nav-links a:hover {{ color: var(--cyan); }}
            .btn-admin {{ background: linear-gradient(135deg, var(--cyan), var(--violet)); color: #000 !important; font-weight: 600; padding: 8px 16px; border-radius: 6px; }}
            
            .hero {{ max-width: 960px; margin: 60px auto 40px; text-align: center; padding: 0 20px; }}
            .badge {{ display: inline-block; background: rgba(0, 240, 255, 0.1); color: var(--cyan); border: 1px solid rgba(0, 240, 255, 0.3); padding: 5px 14px; border-radius: 50px; font-size: 12px; font-weight: 600; margin-bottom: 20px; }}
            h1 {{ font-family: 'Space Grotesk', sans-serif; font-size: 46px; line-height: 1.2; margin-bottom: 20px; }}
            .hero p {{ font-size: 18px; color: var(--muted); max-width: 720px; margin: 0 auto 30px; }}

            /* Two-Column Architecture Showcase */
            .dual-grid {{ max-width: 1040px; margin: 40px auto; display: grid; grid-template-columns: 1fr 1fr; gap: 24px; padding: 0 20px; }}
            .surface-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 32px; display: flex; flex-direction: column; justify-content: space-between; }}
            .surface-card.ai {{ border-top: 4px solid var(--cyan); }}
            .surface-card.human {{ border-top: 4px solid var(--violet); }}
            .surface-tag {{ font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }}
            .surface-card.ai .surface-tag {{ color: var(--cyan); }}
            .surface-card.human .surface-tag {{ color: var(--violet); }}
            .surface-card h2 {{ font-family: 'Space Grotesk', sans-serif; font-size: 24px; margin-bottom: 12px; color: #fff; }}
            .surface-card p {{ font-size: 14px; color: var(--muted); margin-bottom: 20px; }}
            .code-box {{ background: #070a10; border: 1px solid var(--border); border-radius: 8px; padding: 14px; font-family: monospace; font-size: 12px; color: var(--cyan); margin-bottom: 20px; overflow-x: auto; }}
            .feature-list {{ list-style: none; margin-bottom: 24px; }}
            .feature-list li {{ font-size: 14px; color: #d0d8e8; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }}
            .feature-list li::before {{ content: "✓"; color: var(--cyan); font-weight: bold; }}
            .btn-action {{ display: inline-block; text-align: center; padding: 12px 20px; border-radius: 8px; font-size: 14px; font-weight: 600; text-decoration: none; }}
            .btn-ai {{ background: #131d2e; color: var(--cyan); border: 1px solid rgba(0, 240, 255, 0.4); }}
            .btn-human {{ background: linear-gradient(135deg, var(--cyan), var(--violet)); color: #000; font-weight: bold; }}

            footer {{ text-align: center; margin: 80px 0 40px; color: #4b5563; font-size: 13px; }}
        </style>
    </head>
    <body>
        <header>
            <a href="/" class="logo">Jake<span>AI</span></a>
            <div class="nav-links">
                <a href="/llms.txt">llms.txt (AI Spec)</a>
                <a href="/docs">API Playground</a>
                <a href="/admin" class="btn-admin">Human Portal</a>
            </div>
        </header>

        <section class="hero">
            <div class="badge">TWO-PART AGENTIC PLATFORM</div>
            <h1>Built for Autonomous AI Bots.<br>Controlled by Humans.</h1>
            <p>A dual-surface network: AI agents discover and transact via zero-latency machine protocols, while human owners maintain control, monitor volume, and collect revenue.</p>
        </section>

        <div class="dual-grid">
            <!-- PART 1: FOR AI AGENTS -->
            <div class="surface-card ai">
                <div>
                    <div class="surface-tag">Surface 1: For Autonomous AI</div>
                    <h2>Machine Protocol Layer</h2>
                    <p>Designed for bots to read, register, and procure services without human HTML, captchas, or UI friction.</p>
                    <div class="code-box">
                        curl -X POST https://www.jakeaiofficial.com/v1/products/search \<br>
                        &nbsp;&nbsp;-H "Content-Type: application/json" \<br>
                        &nbsp;&nbsp;-d '{{"query": "tariff data", "max_price": 1.0}}'
                    </div>
                    <ul class="feature-list">
                        <li>Standardized <code>llms.txt</code> & Agent Card specs</li>
                        <li>Direct REST & JSON-LD execution</li>
                        <li>1.0% automated micro-settlement</li>
                    </ul>
                </div>
                <a href="/llms.txt" class="btn-action btn-ai">Inspect Agent Spec (llms.txt)</a>
            </div>

            <!-- PART 2: FOR HUMANS & OWNERS -->
            <div class="surface-card human">
                <div>
                    <div class="surface-tag">Surface 2: For Humans & Creators</div>
                    <h2>Human Onboarding & Governance</h2>
                    <p>Connect your custom AI bots, plug in your monetized APIs, and track your bot's cash flow in real-time.</p>
                    <ul class="feature-list">
                        <li>One-click registration for your AI products</li>
                        <li>Automated bank / wallet payouts</li>
                        <li>Full audit trail of all machine transactions</li>
                        <li>Live dashboard with fee controls</li>
                    </ul>
                </div>
                <a href="/admin" class="btn-action btn-human">Launch Human Console</a>
            </div>
        </div>

        <footer>
            &copy; 2026 JakeAI Network &bull; www.jakeaiofficial.com &bull; Dual-Surface Architecture
        </footer>
    </body>
    </html>
    """

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0), COALESCE(SUM(fee_collected), 0) FROM transactions")
    tx_count, tx_volume, fees_earned = cursor.fetchone()
    
    cursor.execute("SELECT id, title, price, vendor_did, created_at FROM products ORDER BY created_at DESC LIMIT 10")
    recent_products = cursor.fetchall()
    conn.close()

    product_rows = "".join([
        f"<tr><td><b>{p[1]}</b></td><td>${p[2]:.2f}</td><td><code>{p[3]}</code></td><td>{p[4]}</td></tr>"
        for p in recent_products
    ]) or "<tr><td colspan='4' style='text-align: center; color: #888; padding: 20px;'>No products registered yet.</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>JakeAI — Human Owner Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg: #07090e;
                --card-bg: #0f141f;
                --border: #1e2638;
                --cyan: #00f0ff;
                --text: #f0f4fc;
                --muted: #8b9bb4;
            }}
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); padding: 40px 20px; }}
            .container {{ max-width: 960px; margin: 0 auto; }}
            header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }}
            h1 {{ font-family: 'Space Grotesk', sans-serif; font-size: 28px; }}
            h1 span {{ color: var(--cyan); }}
            a {{ color: var(--cyan); text-decoration: none; font-size: 14px; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 30px; }}
            .stat-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; padding: 20px; border-left: 4px solid var(--cyan); }}
            .stat-card h3 {{ font-family: 'Space Grotesk', sans-serif; font-size: 32px; color: #fff; margin-bottom: 4px; }}
            .stat-card p {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }}
            .content-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; padding: 24px; }}
            h2 {{ font-family: 'Space Grotesk', sans-serif; font-size: 20px; margin-bottom: 16px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 12px; border-bottom: 1px solid var(--border); text-align: left; font-size: 14px; }}
            th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
            code {{ background: #1a2233; padding: 3px 6px; border-radius: 4px; color: var(--cyan); font-size: 13px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Jake<span>AI</span> Human Governance Console</h1>
                <div>
                    <a href="/">&larr; Public Home</a> &bull; <a href="/docs" style="margin-left: 10px;">API Docs</a>
                </div>
            </header>
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>{total_products}</h3>
                    <p>Live Products</p>
                </div>
                <div class="stat-card">
                    <h3>{tx_count}</h3>
                    <p>Settled Transactions</p>
                </div>
                <div class="stat-card">
                    <h3>${fees_earned:.4f}</h3>
                    <p>Collected Revenue (1.0%)</p>
                </div>
            </div>
            <div class="content-card">
                <h2>Network Activity Log</h2>
                <table>
                    <thead>
                        <tr><th>Product Title</th><th>Price</th><th>Vendor DID</th><th>Date Registered</th></tr>
                    </thead>
                    <tbody>
                        {product_rows}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

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

    results = [
        {"id": r[0], "title": r[1], "description": r[2], "category": r[3], "price": r[4], "endpoint_url": r[5], "vendor_did": r[6]}
        for r in rows
    ]
    return {"count": len(results), "query": query.query, "results": results}

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

@app.get("/health")
def health():
    return {"status": "healthy"}
