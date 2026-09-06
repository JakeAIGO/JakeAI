import sqlite3
import os
import uuid
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Database Setup
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
    title="Agent-to-Agent (A2A) Commerce Network",
    description="Decentralized Machine-Native Registry and Settlement Gateway for Autonomous AI Agents.",
    version="1.0.0"
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
    endpoint_url: str = Field(..., example="https://api.solutionsenergy.com/tariffs")
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
    take_rate: Optional[float] = 0.005 # 0.5% default platform fee

# Routes
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "A2A Agent Network"}

@app.get("/", response_class=HTMLResponse)
def index_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>A2A Network — Agent Commerce Gateway</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #222; }
            h1 { color: #0056b3; }
            .card { background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
            a.btn { display: inline-block; background: #0056b3; color: #fff; padding: 10px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; margin-right: 10px; }
            a.btn-secondary { background: #6c757d; }
            code { background: #eee; padding: 2px 6px; border-radius: 4px; }
        </style>
    </head>
    <body>
        <h1>Agent-to-Agent (A2A) Commerce Network</h1>
        <p>This server is active and accessible to autonomous AI agents worldwide.</p>
        <div class="card">
            <h3>Quick Links:</h3>
            <a href="/docs" class="btn">Interactive API Docs (Swagger)</a>
            <a href="/admin" class="btn btn-secondary">Admin Dashboard</a>
        </div>
        <div class="card">
            <h3>Active Endpoints for Bots:</h3>
            <ul>
                <li><code>POST /v1/products/register</code> — Register a product manifest</li>
                <li><code>POST /v1/products/search</code> — Semantic/keyword discovery</li>
                <li><code>POST /v1/transactions/settle</code> — Micro-settlement with platform fee deduction</li>
            </ul>
        </div>
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
        f"<tr><td>{p[1]}</td><td>${p[2]:.2f}</td><td><code>{p[3]}</code></td><td>{p[4]}</td></tr>"
        for p in recent_products
    ]) or "<tr><td colspan='4'>No products registered yet.</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>A2A Network — Admin Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #222; }}
            .stats {{ display: flex; gap: 20px; margin-bottom: 30px; }}
            .stat-box {{ flex: 1; background: #f0f4f8; padding: 20px; border-radius: 8px; border-left: 4px solid #0056b3; }}
            .stat-box h2 {{ margin: 0 0 5px 0; font-size: 28px; color: #0056b3; }}
            .stat-box p {{ margin: 0; color: #666; font-size: 14px; text-transform: uppercase; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; border-bottom: 1px solid #ddd; text-align: left; }}
            th {{ background: #f8f9fa; }}
            a {{ color: #0056b3; text-decoration: none; }}
        </style>
    </head>
    <body>
        <h1>A2A Network Admin Dashboard</h1>
        <p><a href="/">&larr; Back to Home</a> | <a href="/docs">API Documentation</a></p>
        <div class="stats">
            <div class="stat-box">
                <h2>{total_products}</h2>
                <p>Registered Products</p>
            </div>
            <div class="stat-box">
                <h2>{tx_count}</h2>
                <p>Total Transactions</p>
            </div>
            <div class="stat-box">
                <h2>${fees_earned:.4f}</h2>
                <p>Platform Fees Earned (0.5%)</p>
            </div>
        </div>
        <h3>Recently Registered Products</h3>
        <table>
            <thead><tr><th>Title</th><th>Price</th><th>Vendor DID</th><th>Date</th></tr></thead>
            <tbody>{product_rows}</tbody>
        </table>
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
        {
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "category": r[3],
            "price": r[4],
            "endpoint_url": r[5],
            "vendor_did": r[6]
        }
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
    fee = round(req.amount * (req.take_rate or 0.005), 4)
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
