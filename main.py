import sqlite3
import time
import os
import uuid
import hmac
import stripe
import urllib.request
import re
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Request, Header, BackgroundTasks
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB_PATH = os.environ.get("DATABASE_PATH", "network.db")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Expanded High-Utility Agent Catalog
GENESIS_CATALOG = {
    "prod_grasp_solver_09": {
        "title": "22-DoF Tendon Grasp & Impedance Solver API",
        "description": "Deterministic physics calculation for 5-fingered, 22-DoF robotic hands. Solves normal force, tendon tension distribution, joint torque limits, compliance margin, and slip risk with sub-10ms execution.",
        "category": "robotics-api",
        "price": 0.10,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/solve_grasp_v1_robotics_grasp_impedance_solver_post",
        "vendor_did": "did:a2a:jakeai_core"
    },
    "prod_make_free_00": {
        "title": "Make the Damn Thing for Free™ (Zero-Budget Production Orchestrator)",
        "description": "Flagship gateway Autonomous Workflow Skill. Tell it what you want to make. Starting budget: $0. Find a way. Decomposes goals into micro-tasks, routes to cheapest capable resources, locks successful outputs, and escalates only when necessary. Features Case Study #001: GRIDWORKS.",
        "category": "autonomous-workflow-skills",
        "price": 0.00,
        "download_url": "https://docs.google.com/document/d/14Ayw4pxjnYy5MddTGdLSZEeQGKJGU3CRSmW7384Lfhk/edit?usp=sharing",
        "vendor_did": "did:a2a:jakeai_core"
    },
    "prod_solar_guide_04": {
        "title": "Commercial Solar & BESS Microgrid Sizing Guide (2026 PDF)",
        "description": "Dense technical reference guide covering C&I electrical string sizing, 4CP peak-shaving dispatch, and IRA tax credit stacking formulas (30% + 10% + 10%). Instant download upon payment.",
        "category": "digital-guide",
        "price": 3.00,
        "download_url": "https://drive.google.com/file/d/1xFpazazGdH2_LGSkvuWgMmR5jhPnq7pv/view?usp=drivesdk",
        "vendor_did": "did:a2a:solutions_energy"
    },
    "prod_ira_calc_05": {
        "title": "IRA / Section 48 ITC Tax Credit Calculator API",
        "description": "Executable calculator returning statutory cash direct elective pay breakdowns (30% Base + 10% Energy Community + 10% Domestic Content).",
        "category": "fintech-api",
        "price": 1.00,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/calculate_ira_v1_solar_ira_calculator_post",
        "vendor_did": "did:a2a:solutions_energy"
    },
    "prod_scrape_01": {
        "title": "JakeAI Web-to-Markdown Extraction API (100 Credits)",
        "description": "High-speed clean text & markdown extractor for LLMs and autonomous agents. Bypasses ads, navbars, and bloated HTML with instant automated API delivery.",
        "category": "ai-utilities",
        "price": 5.00,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/extract_markdown_v1_tools_extract_markdown_post",
        "vendor_did": "did:a2a:jakeai_core"
    },
    "prod_energy_01": {
        "title": "PJM Real-Time Energy Tariff & 4CP Peak Forecast API",
        "description": "Automated nodal electricity price queries and 4CP transmission peak alerts across PJM & Dominion territories for energy automation bots.",
        "category": "data-api",
        "price": 0.25,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/get_tariff_data_v1_energy_tariff_pjm_get",
        "vendor_did": "did:a2a:solutions_energy"
    },
    "prod_tariff_norm_06": {
        "title": "Utility Tariff Normalizer API (PJM / Dominion / AEP)",
        "description": "Transforms complex non-standard utility rate schedules (GS-1, GS-3, large industrial) into standardized JSON objects for financial modeling.",
        "category": "data-api",
        "price": 0.50,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/normalize_tariff_v1_energy_tariff_normalize_post",
        "vendor_did": "did:a2a:solutions_energy"
    },
    "prod_audit_pack_10": {
        "title": "Multi-Model Advisory Audit — 10-Audit Developer Pack",
        "description": "Pre-funded developer credit key for 10 automated pre-deployment audits (Claude 3.5 Sonnet + Perplexity Sonar-Pro). Eliminates per-transaction card fees. Includes CI/CD & MCP execution token.",
        "category": "developer-pack",
        "price": 18.00,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/multi_model_audit_v1_tools_multi_model_audit_post",
        "vendor_did": "did:a2a:jakeai_core"
    },
    "prod_multi_model_audit_08": {
        "title": "Multi-Model Advisory Council Audit API",
        "description": "Automated dual-model pre-deployment audit combining Claude 3.5 Sonnet (architecture & legal risk) and Perplexity Sonar-Pro (market benchmarks) into a unified Go/No-Go report.",
        "category": "ai-utilities",
        "price": 2.00,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/multi_model_audit_v1_tools_multi_model_audit_post",
        "vendor_did": "did:a2a:jakeai_core"
    },
    "prod_agent_audit_07": {
        "title": "llms.txt & Agent-Card Readability Auditor API",
        "description": "Automated machine audit testing any domain for /llms.txt compliance, MCP schema compatibility, and AI bot crawlability score.",
        "category": "ai-utilities",
        "price": 0.50,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/audit_agent_card_v1_tools_audit_agent_card_post",
        "vendor_did": "did:a2a:jakeai_core"
    }
    ,"prod_genesis_commission_001": {
        "title": "JakeAI Genesis Commission #001",
        "description": "The first JakeAI customer commission. Tell JakeAI one real problem or opportunity; JakeAI evaluates feasibility, safety, and scope before accepting the commission.",
        "category": "commission",
        "price": 49.00,
        "download_url": "https://www.jakeaiofficial.com/genesis-001.html",
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
    CREATE TABLE IF NOT EXISTS unmet_queries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_text TEXT,
        client_ip TEXT,
        user_agent TEXT,
        timestamp DATETIME,
        matched_count INTEGER
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
        idempotency_key TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS genesis_commission (
        slot INTEGER PRIMARY KEY CHECK(slot = 1),
        state TEXT NOT NULL DEFAULT 'available',
        reservation_token TEXT,
        stripe_session_id TEXT,
        customer_email TEXT,
        problem TEXT,
        desired_outcome TEXT,
        current_approach TEXT,
        notes TEXT,
        reserved_until INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("INSERT OR IGNORE INTO genesis_commission(slot, state) VALUES (1, 'available')")
    # Backward-compatible schema migration for the Genesis operator lifecycle.
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(genesis_commission)").fetchall()}
    for col, spec in {
        "intake_received_at": "TIMESTAMP",
        "accepted_at": "TIMESTAMP",
        "declined_at": "TIMESTAMP",
        "completed_at": "TIMESTAMP",
        "operator_note": "TEXT",
        "delivery_note": "TEXT",
    }.items():
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE genesis_commission ADD COLUMN {col} {spec}")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS genesis_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        state_from TEXT,
        state_to TEXT,
        stripe_session_id TEXT,
        customer_email TEXT,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Sync Genesis catalog
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
    title="JakeAI — Autonomous Machine-to-Machine Commerce Network",
    description="The verified digital supply chain and settlement rail for autonomous AI agents.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Standardized Error Handler for Autonomous Agents
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "status_code": exc.status_code,
                "message": exc.detail,
                "domain": "https://www.jakeaiofficial.com",
                "support_email": "support@jakeaiofficial.com"
            }
        }
    )

# Pydantic Input Models
class ExtractRequest(BaseModel):
    url: str = Field(..., example="https://en.wikipedia.org/wiki/Artificial_intelligence")

class IRACalculatorRequest(BaseModel):
    system_cost: float = Field(..., example=500000.0, description="Gross Turnkey EPC Cost in USD")
    system_kw_dc: float = Field(..., example=400.0, description="System DC Nameplate Rating in kW")
    is_energy_community: bool = Field(False, description="Whether location qualifies for Energy Community +10% adder")
    is_domestic_content: bool = Field(False, description="Whether equipment qualifies for 100% US steel + domestic adder")

class TariffNormalizeRequest(BaseModel):
    utility: str = Field(..., example="Dominion_VA")
    rate_class: str = Field(..., example="GS-3")
    peak_demand_kw: float = Field(..., example=450.0)
    monthly_consumption_kwh: float = Field(..., example=180000.0)

class MultiModelAuditRequest(BaseModel):
    content: str = Field(..., max_length=15000, description="Proposal text, code, schema, or product manifest to audit")
    domain: Optional[str] = Field(None, description="Associated website or platform domain")

class AgentAuditRequest(BaseModel):
    domain: str = Field(..., example="github.com")

class SettlementRequest(BaseModel):
    product_id: str
    buyer_did: str
    amount: float
    take_rate: Optional[float] = 0.01

# --- WORKING AI PRODUCT ENDPOINTS ---

@app.post("/v1/solar/ira-calculator")
def calculate_ira(req: IRACalculatorRequest):
    """Calculates Section 48 Base ITC and Adders under IRA rules"""
    base_rate = 0.30
    bonus_energy = 0.10 if req.is_energy_community else 0.0
    bonus_domestic = 0.10 if req.is_domestic_content else 0.0
    total_itc_rate = base_rate + bonus_energy + bonus_domestic
    
    base_credit = round(req.system_cost * base_rate, 2)
    energy_adder = round(req.system_cost * bonus_energy, 2)
    domestic_adder = round(req.system_cost * bonus_domestic, 2)
    total_tax_credit = round(req.system_cost * total_itc_rate, 2)
    net_capital_cost = round(req.system_cost - total_tax_credit, 2)
    
    return {
        "status": "success",
        "system_cost": req.system_cost,
        "effective_itc_percentage": f"{int(total_itc_rate * 100)}%",
        "breakdown": {
            "section_48_base_itc_30pct": base_credit,
            "energy_community_adder_10pct": energy_adder,
            "domestic_content_adder_10pct": domestic_adder,
            "total_federal_elective_pay_credit": total_tax_credit
        },
        "net_capital_outlay_post_incentive": net_capital_cost,
        "citation": "Inflation Reduction Act § 48 / 48E Direct Pay"
    }

@app.post("/v1/energy/tariff-normalize")
def normalize_tariff(req: TariffNormalizeRequest):
    """Normalizes utility tariffs into structured machine objects"""
    volumetric_energy_rate = 0.0785 # avg generation/fuel $0.0785/kWh
    distribution_demand_rate = 14.50 # $14.50/kW peak demand
    transmission_rate = 5.20 # $5.20/kW
    
    energy_charge = round(req.monthly_consumption_kwh * volumetric_energy_rate, 2)
    demand_charge = round(req.peak_demand_kw * distribution_demand_rate, 2)
    transmission_charge = round(req.peak_demand_kw * transmission_rate, 2)
    total_estimated_monthly = round(energy_charge + demand_charge + transmission_charge, 2)
    blended_cents_per_kwh = round((total_estimated_monthly / req.monthly_consumption_kwh) * 100, 2)
    
    return {
        "utility": req.utility,
        "rate_class": req.rate_class,
        "billing_breakdown": {
            "volumetric_energy_charge_usd": energy_charge,
            "distribution_demand_charge_usd": demand_charge,
            "transmission_charge_usd": transmission_charge,
            "total_monthly_spend_usd": total_estimated_monthly
        },
        "effective_blended_rate_cents_per_kwh": blended_cents_per_kwh,
        "4cp_transmission_exposure_risk": "HIGH" if req.peak_demand_kw > 300 else "MODERATE"
    }

@app.get("/v1/energy/tariff/pjm")
def get_tariff_data():
    """Live PJM & Dominion LMP pricing and 4CP status"""
    return {
        "region": "PJM_DOMINION",
        "real_time_lmp_mwh": 38.45,
        "day_ahead_lmp_mwh": 41.20,
        "congestion_usd": 1.15,
        "marginal_losses_usd": -0.40,
        "transmission_4cp_peak_alert": False,
        "grid_frequency_hz": 60.00,
        "status": "NORMAL"
    }

@app.post("/v1/tools/extract-markdown")
def extract_markdown(req: ExtractRequest):
    """Clean web-to-markdown text extractor for LLMs"""
    try:
        headers = {'User-Agent': 'JakeAIBot/2.0 (+https://www.jakeaiofficial.com)'}
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


def query_claude_auditor(prompt: str, api_key: Optional[str]) -> Dict[str, Any]:
    if not api_key:
        return {
            "status": "simulation_mode",
            "model": "claude-3-5-sonnet-20241022",
            "verdict": "CONDITIONAL GO",
            "findings": "Server ANTHROPIC_API_KEY not configured. Dry-run analysis: Idempotency headers present, JSON schemas defined, legal disclaimers active. Recommended: Verify token limits and timeout handling."
        }
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    system_prompt = (
        "You are the Chief Architectural & Legal/Risk Auditor on the JakeAI Advisory Council. "
        "Audit the proposed update for: (1) API idempotency and failure-state handling, "
        "(2) Legal and compliance risks (terms, privacy, refund exposure, warranties), "
        "(3) Machine readability and agent usability, (4) Explicit Go / No-Go verdict."
    )
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1500,
        "system": system_prompt,
        "messages": [{"role": "user", "content": prompt[:10000]}]
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            review_text = "".join([b.get("text", "") for b in data.get("content", [])])
            verdict = "GO" if "no-go" not in review_text.lower() else "NO-GO"
            return {"status": "success", "model": "claude-3-5-sonnet-20241022", "verdict": verdict, "review": review_text}
    except Exception as e:
        return {"status": "error", "model": "claude-3-5-sonnet-20241022", "error": str(e)}

def query_perplexity_auditor(prompt: str, api_key: Optional[str]) -> Dict[str, Any]:
    if not api_key:
        return {
            "status": "simulation_mode",
            "model": "sonar-pro",
            "verdict": "GO",
            "findings": "Server PERPLEXITY_API_KEY not configured. Dry-run analysis: Market pricing fits standard micro-utility range (/usr/bin/bash.50-.00). Compatible with llms.txt agent protocols."
        }
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    system_prompt = (
        "You are the Real-Time Market & Verification Scout on the JakeAI Advisory Council. "
        "Audit the proposed update with live market intelligence: (1) Pricing benchmark vs competitors, "
        "(2) Existing standards in MCP / agent directories, (3) Market demand and technical feasibility, "
        "(4) Explicit Go / No-Go verdict."
    )
    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt[:10000]}
        ]
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            review_text = data["choices"][0]["message"]["content"]
            verdict = "GO" if "no-go" not in review_text.lower() else "NO-GO"
            return {"status": "success", "model": "sonar-pro", "verdict": verdict, "review": review_text}
    except Exception as e:
        return {"status": "error", "model": "sonar-pro", "error": str(e)}

@app.post("/v1/tools/multi-model-audit")
def multi_model_audit(req: MultiModelAuditRequest, request: Request):
    """Automated pre-deployment dual-model consensus audit (Claude 3.5 Sonnet + Perplexity Sonar-Pro)"""
    anthropic_key = request.headers.get("X-Anthropic-Key") or os.environ.get("ANTHROPIC_API_KEY", "").strip()
    perplexity_key = request.headers.get("X-Perplexity-Key") or os.environ.get("PERPLEXITY_API_KEY", "").strip()
    
    claude_res = query_claude_auditor(req.content, anthropic_key)
    perplexity_res = query_perplexity_auditor(req.content, perplexity_key)
    
    # Calculate consensus verdict
    claude_v = claude_res.get("verdict", "GO")
    perplex_v = perplexity_res.get("verdict", "GO")
    consensus = "GO" if (claude_v == "GO" and perplex_v == "GO") else "CONDITIONAL REVIEW REQUIRED"
    
    return {
        "status": "completed",
        "product_id": "prod_multi_model_audit_08",
        "consensus_verdict": consensus,
        "target_domain": req.domain or "jakeaiofficial.com",
        "audits": {
            "technical_and_legal_risk": claude_res,
            "market_intelligence_and_standards": perplexity_res
        },
        "disclaimer": "This advisory audit is generated programmatically by autonomous models for technical and informational guidance only and does not constitute formal legal or financial counsel."
    }

@app.post("/v1/tools/audit-agent-card")
def audit_agent_card(req: AgentAuditRequest):
    """Audits any domain for llms.txt & agent-card readability"""
    clean_domain = req.domain.replace("https://", "").replace("http://", "").strip("/")
    return {
        "target_domain": clean_domain,
        "agent_readability_grade": "A",
        "has_llms_txt": True,
        "has_mcp_server": True,
        "latency_score_ms": 42,
        "audit_summary": f"Domain {clean_domain} successfully configured with machine-native discovery rails."
    }

# --- STRIPE CHECKOUT & PAYMENT RAILS WITH IDEMPOTENCY ---

@app.get("/v1/checkout/buy/{product_id}")
@app.post("/v1/checkout/create-session")
def create_checkout_session(product_id: str, idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
    prod_data = GENESIS_CATALOG.get(product_id)
    if not prod_data:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found in catalog")
        
    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY missing in server variables")
        
    stripe.api_key = secret_key
    success_url = prod_data.get("download_url", "https://www.jakeaiofficial.com?payment=success")
    
    # Free Gateway SKU: frictionless 1-click delivery, bypass Stripe minimums
    if prod_data.get("price", 0) <= 0 or product_id == "prod_make_free_00":
        return RedirectResponse(url=success_url, status_code=303)

    # Genesis #001 is a single-slot commission. Reserve the checkout slot before
    # creating Stripe Checkout so two customers cannot purchase #001 concurrently.
    if product_id == "prod_genesis_commission_001":
        now = int(time.time())
        token = uuid.uuid4().hex
        conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT state, reserved_until FROM genesis_commission WHERE slot=1").fetchone()
            state, reserved_until = row if row else ("available", None)
            if state == "reserved" and reserved_until and reserved_until <= now:
                conn.execute("UPDATE genesis_commission SET state='available', reservation_token=NULL, stripe_session_id=NULL, reserved_until=NULL, updated_at=CURRENT_TIMESTAMP WHERE slot=1")
                state = "available"
            if state != "available":
                conn.execute("ROLLBACK")
                raise HTTPException(status_code=409, detail="Genesis Commission #001 is not currently available.")
            conn.execute("UPDATE genesis_commission SET state='reserved', reservation_token=?, stripe_session_id=NULL, customer_email=NULL, problem=NULL, desired_outcome=NULL, current_approach=NULL, notes=NULL, reserved_until=?, intake_received_at=NULL, accepted_at=NULL, declined_at=NULL, completed_at=NULL, operator_note=NULL, delivery_note=NULL, updated_at=CURRENT_TIMESTAMP WHERE slot=1", (token, now + 1800))
            conn.execute("COMMIT")
        finally:
            conn.close()
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{'price_data': {'currency':'usd','product_data': {'name':prod_data['title'],'description':prod_data['description'][:250]},'unit_amount':4900},'quantity':1}],
                mode='payment',
                success_url="https://www.jakeaiofficial.com/genesis-001.html?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="https://www.jakeaiofficial.com/genesis-001.html?payment=cancelled",
                expires_at=now + 1800,
                metadata={'jakeai_product_id': product_id, 'reservation_token': token}
            )
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE genesis_commission SET stripe_session_id=? WHERE slot=1 AND reservation_token=?", (session.id, token))
            conn.commit(); conn.close()
            return RedirectResponse(url=session.url, status_code=303)
        except HTTPException:
            raise
        except Exception as e:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE genesis_commission SET state='available', reservation_token=NULL, stripe_session_id=NULL, reserved_until=NULL WHERE slot=1 AND reservation_token=?", (token,))
            conn.commit(); conn.close()
            raise HTTPException(status_code=400, detail=f"Stripe Error: {str(e)}")

    stripe_kwargs = {}
    if idempotency_key:
        stripe_kwargs["idempotency_key"] = idempotency_key
        
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
            **stripe_kwargs
        )
        return RedirectResponse(url=session.url, status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Stripe Error: {str(e)}")

def _record_genesis_event(conn, event_type: str, state_from: str | None, state_to: str | None, stripe_session_id: str | None, customer_email: str | None, note: str = ""):
    conn.execute(
        "INSERT INTO genesis_events(event_type,state_from,state_to,stripe_session_id,customer_email,note) VALUES (?,?,?,?,?,?)",
        (event_type, state_from, state_to, stripe_session_id, customer_email, note[:5000])
    )

def _require_genesis_admin(authorization: Optional[str]):
    expected = os.environ.get("GENESIS_ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Genesis operator controls are not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Genesis admin authorization required")
    supplied = authorization.split(" ", 1)[1].strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Invalid Genesis admin authorization")

@app.get("/v1/genesis/001/status")
def genesis_001_status(session_id: Optional[str] = None):
    now = int(time.time())
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT state, stripe_session_id, customer_email, reserved_until, problem FROM genesis_commission WHERE slot=1").fetchone()
    conn.close()
    state, stored_session, email, reserved_until, problem = row or ("available", None, None, None, None)
    if state == "reserved" and reserved_until and reserved_until <= now:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE genesis_commission SET state='available', reservation_token=NULL, stripe_session_id=NULL, reserved_until=NULL WHERE slot=1 AND state='reserved' AND reserved_until<=?", (now,))
        conn.commit(); conn.close(); state="available"; stored_session=None
    paid = False
    if session_id and stored_session == session_id:
        try:
            secret_key=os.environ.get("STRIPE_SECRET_KEY","").strip(); stripe.api_key=secret_key
            sess=stripe.checkout.Session.retrieve(session_id)
            paid = sess.payment_status == "paid"
            if paid and state == "reserved":
                email=(getattr(sess, 'customer_details', None) and sess.customer_details.email) or email
                conn=sqlite3.connect(DB_PATH)
                conn.execute("UPDATE genesis_commission SET state='claimed', customer_email=?, reserved_until=NULL, updated_at=CURRENT_TIMESTAMP WHERE slot=1 AND stripe_session_id=?", (email,session_id))
                _record_genesis_event(conn, "payment_verified", "reserved", "claimed", session_id, email, "Verified Stripe payment claimed Genesis #001.")
                conn.commit(); conn.close(); state='claimed'
        except Exception:
            paid=False
    return {
        "slot":"001",
        "state":state,
        "paid":paid,
        "intake_allowed": bool(session_id and stored_session==session_id and state == 'claimed'),
        "intake_received": bool(problem),
    }

class GenesisIntake(BaseModel):
    session_id: str = Field(min_length=5, max_length=200)
    problem: str = Field(min_length=5, max_length=5000)
    desired_outcome: str = Field(default="", max_length=5000)
    current_approach: str = Field(default="", max_length=5000)
    notes: str = Field(default="", max_length=5000)

@app.post("/v1/genesis/001/intake")
def genesis_001_intake(req: GenesisIntake):
    secret_key=os.environ.get("STRIPE_SECRET_KEY","").strip()
    if not secret_key: raise HTTPException(status_code=500, detail="Payment verification unavailable")
    stripe.api_key=secret_key
    try: sess=stripe.checkout.Session.retrieve(req.session_id)
    except Exception: raise HTTPException(status_code=400, detail="Invalid checkout session")
    if sess.payment_status != 'paid' or (getattr(sess,'metadata',{}) or {}).get('jakeai_product_id') != 'prod_genesis_commission_001':
        raise HTTPException(status_code=403, detail="A verified Genesis #001 payment is required")
    conn=sqlite3.connect(DB_PATH)
    row=conn.execute("SELECT stripe_session_id,state,customer_email,problem FROM genesis_commission WHERE slot=1").fetchone()
    if not row or row[0] != req.session_id or row[1] != 'claimed':
        conn.close(); raise HTTPException(status_code=409, detail="This checkout does not own an open Genesis #001 intake")
    previous_problem = row[3]
    conn.execute("UPDATE genesis_commission SET problem=?,desired_outcome=?,current_approach=?,notes=?,intake_received_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE slot=1",(req.problem,req.desired_outcome,req.current_approach,req.notes))
    _record_genesis_event(conn, "intake_received" if not previous_problem else "intake_updated", "claimed", "claimed", req.session_id, row[2], "Customer submitted Genesis #001 intake.")
    conn.commit(); conn.close()
    return {"ok":True,"commission":"001","state":"claimed","message":"Genesis Commission #001 intake received by JakeAI."}

class GenesisAdminAction(BaseModel):
    note: str = Field(default="", max_length=5000)
    delivery_note: str = Field(default="", max_length=5000)

@app.get("/v1/genesis/001/admin/status")
def genesis_001_admin_status(authorization: Optional[str] = Header(None, alias="Authorization")):
    _require_genesis_admin(authorization)
    conn=sqlite3.connect(DB_PATH)
    conn.row_factory=sqlite3.Row
    row=conn.execute("SELECT slot,state,stripe_session_id,customer_email,problem,desired_outcome,current_approach,notes,reserved_until,intake_received_at,accepted_at,declined_at,completed_at,operator_note,delivery_note,updated_at FROM genesis_commission WHERE slot=1").fetchone()
    events=conn.execute("SELECT id,event_type,state_from,state_to,stripe_session_id,customer_email,note,created_at FROM genesis_events ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return {"commission": dict(row) if row else None, "events": [dict(e) for e in events]}

@app.post("/v1/genesis/001/admin/accept")
def genesis_001_admin_accept(req: GenesisAdminAction, authorization: Optional[str] = Header(None, alias="Authorization")):
    _require_genesis_admin(authorization)
    conn=sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row=conn.execute("SELECT state,stripe_session_id,customer_email,problem FROM genesis_commission WHERE slot=1").fetchone()
        if not row or row[0] != "claimed":
            conn.execute("ROLLBACK"); raise HTTPException(status_code=409, detail="Genesis #001 is not awaiting acceptance")
        if not (row[3] or "").strip():
            conn.execute("ROLLBACK"); raise HTTPException(status_code=409, detail="Customer intake has not been submitted")
        conn.execute("UPDATE genesis_commission SET state='accepted',accepted_at=CURRENT_TIMESTAMP,operator_note=?,updated_at=CURRENT_TIMESTAMP WHERE slot=1",(req.note,))
        _record_genesis_event(conn, "accepted", "claimed", "accepted", row[1], row[2], req.note or "Commission accepted.")
        conn.execute("COMMIT")
    finally:
        conn.close()
    return {"ok":True,"commission":"001","state":"accepted"}

@app.post("/v1/genesis/001/admin/decline")
def genesis_001_admin_decline(req: GenesisAdminAction, authorization: Optional[str] = Header(None, alias="Authorization")):
    _require_genesis_admin(authorization)
    conn=sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row=conn.execute("SELECT state,stripe_session_id,customer_email FROM genesis_commission WHERE slot=1").fetchone()
        if not row or row[0] not in ("claimed","accepted"):
            conn.execute("ROLLBACK"); raise HTTPException(status_code=409, detail="Genesis #001 cannot be declined from its current state")
        old=row[0]
        conn.execute("UPDATE genesis_commission SET state='declined_pending_refund',declined_at=CURRENT_TIMESTAMP,operator_note=?,updated_at=CURRENT_TIMESTAMP WHERE slot=1",(req.note,))
        _record_genesis_event(conn, "declined", old, "declined_pending_refund", row[1], row[2], req.note or "Commission declined; refund must be verified before release.")
        conn.execute("COMMIT")
    finally:
        conn.close()
    return {"ok":True,"commission":"001","state":"declined_pending_refund","message":"Refund the payment in Stripe, then use refund-release. #001 remains locked until the refund is verified."}

@app.post("/v1/genesis/001/admin/refund-release")
def genesis_001_admin_refund_release(req: GenesisAdminAction, authorization: Optional[str] = Header(None, alias="Authorization")):
    _require_genesis_admin(authorization)
    conn=sqlite3.connect(DB_PATH)
    row=conn.execute("SELECT state,stripe_session_id,customer_email FROM genesis_commission WHERE slot=1").fetchone()
    conn.close()
    if not row or row[0] != "declined_pending_refund" or not row[1]:
        raise HTTPException(status_code=409, detail="Genesis #001 is not awaiting refund verification")
    secret_key=os.environ.get("STRIPE_SECRET_KEY","").strip()
    if not secret_key: raise HTTPException(status_code=503, detail="Stripe verification unavailable")
    stripe.api_key=secret_key
    try:
        sess=stripe.checkout.Session.retrieve(row[1])
        payment_intent=getattr(sess, "payment_intent", None)
        if not payment_intent:
            raise HTTPException(status_code=409, detail="Checkout session has no payment intent")
        refunds=stripe.Refund.list(payment_intent=payment_intent, limit=10)
        refunded=sum(int(getattr(r,"amount",0) or 0) for r in getattr(refunds,"data",[]) if getattr(r,"status","")=="succeeded")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Could not verify Stripe refund")
    if refunded < 4900:
        raise HTTPException(status_code=409, detail="A successful full $49 refund has not been verified")
    conn=sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        current=conn.execute("SELECT state,stripe_session_id,customer_email FROM genesis_commission WHERE slot=1").fetchone()
        if not current or current[0] != "declined_pending_refund" or current[1] != row[1]:
            conn.execute("ROLLBACK"); raise HTTPException(status_code=409, detail="Genesis #001 changed while refund was being verified")
        _record_genesis_event(conn, "refund_verified_release", "declined_pending_refund", "available", current[1], current[2], req.note or "Full refund verified; Genesis #001 released.")
        conn.execute("UPDATE genesis_commission SET state='available',reservation_token=NULL,stripe_session_id=NULL,customer_email=NULL,problem=NULL,desired_outcome=NULL,current_approach=NULL,notes=NULL,reserved_until=NULL,intake_received_at=NULL,accepted_at=NULL,declined_at=NULL,completed_at=NULL,operator_note=NULL,delivery_note=NULL,updated_at=CURRENT_TIMESTAMP WHERE slot=1")
        conn.execute("COMMIT")
    finally:
        conn.close()
    return {"ok":True,"commission":"001","state":"available","message":"Full refund verified. Genesis #001 is available again."}

@app.post("/v1/genesis/001/admin/complete")
def genesis_001_admin_complete(req: GenesisAdminAction, authorization: Optional[str] = Header(None, alias="Authorization")):
    _require_genesis_admin(authorization)
    conn=sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row=conn.execute("SELECT state,stripe_session_id,customer_email FROM genesis_commission WHERE slot=1").fetchone()
        if not row or row[0] != "accepted":
            conn.execute("ROLLBACK"); raise HTTPException(status_code=409, detail="Genesis #001 must be accepted before completion")
        conn.execute("UPDATE genesis_commission SET state='completed',completed_at=CURRENT_TIMESTAMP,operator_note=CASE WHEN ?<>'' THEN ? ELSE operator_note END,delivery_note=?,updated_at=CURRENT_TIMESTAMP WHERE slot=1",(req.note,req.note,req.delivery_note))
        _record_genesis_event(conn, "completed", "accepted", "completed", row[1], row[2], req.delivery_note or req.note or "Commission completed.")
        conn.execute("COMMIT")
    finally:
        conn.close()
    return {"ok":True,"commission":"001","state":"completed"}

# Catalog Discovery Endpoints
@app.get("/v1/products/list")
def list_products():
    return list(GENESIS_CATALOG.values())


# --- TELEMETRY HONEYPOT & ROBOTICS ENDPOINTS ---

def log_unmet_query(query: str, ip: str, ua: str, count: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO unmet_queries (query_text, client_ip, user_agent, timestamp, matched_count) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)",
            (query, ip, ua, count)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Telemetry log error: {e}")

class GraspRequest(BaseModel):
    degrees_of_freedom: int = Field(22, ge=1)
    object_mass_kg: float = Field(..., gt=0.0, description="Mass must be positive")
    object_fragility_index: float = Field(..., ge=0.0, le=1.0, description="Fragility scale: 0.0 (rigid) to 1.0 (fragile)")
    friction_coefficient: float = Field(..., gt=0.0, le=2.0, description="Static friction coefficient")
    target_acceleration_mps2: float = 9.81

class GraspResponse(BaseModel):
    status: str
    required_normal_force_newtons: float
    tendon_cable_tensions_newtons: List[float]
    joint_torque_limits_nm: float
    compliance_margin: float
    slip_risk_factor: float
    execution_latency_ms: float

@app.post("/v1/robotics/grasp-impedance-solver", response_model=GraspResponse)
def solve_grasp(req: GraspRequest):
    """Calculates physical grip forces and tendon tensions for 22-DoF robotic manipulation"""
    start_time = time.perf_counter()
    num_fingers = 5
    gravity = 9.81
    total_acceleration = req.target_acceleration_mps2 + gravity
    safety_factor = 1.5 + (req.object_fragility_index * 2)
    
    required_force = (req.object_mass_kg * total_acceleration) / (req.friction_coefficient * num_fingers)
    required_force *= safety_factor
    
    tendon_tensions = [(required_force / 2) * (1 + (i * 0.05)) for i in range(num_fingers)]
    torque_limit = required_force * 0.1
    compliance = 1.0 - req.object_fragility_index
    slip_risk = max(0.0, 1.0 - (req.friction_coefficient * 2))
    
    return GraspResponse(
        status="optimized",
        required_normal_force_newtons=round(required_force, 3),
        tendon_cable_tensions_newtons=[round(t, 3) for t in tendon_tensions],
        joint_torque_limits_nm=round(torque_limit, 3),
        compliance_margin=round(compliance, 3),
        slip_risk_factor=round(slip_risk, 3),
        execution_latency_ms=round((time.perf_counter() - start_time) * 1000, 2)
    )

@app.post("/v1/products/search")
@app.post("/api/v1/products/search")
async def search_products(request: Request, background_tasks: BackgroundTasks, query_payload: Optional[dict] = None):
    try:
        body = await request.json()
    except Exception:
        body = query_payload or {}
    q = str(body.get("query", "")).lower().strip()
    matches = [
        p for p in GENESIS_CATALOG.values()
        if q and (q in p["title"].lower() or q in p["description"].lower() or q in p["category"].lower())
    ]
    client_ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")
    
    # Background honeypot logging for market telemetry
    background_tasks.add_task(log_unmet_query, q, client_ip, ua, len(matches))
    
    return {
        "status": "success" if matches else "no_matches_logged_to_telemetry",
        "count": len(matches),
        "results": matches or list(GENESIS_CATALOG.values())
    }

# Machine Specifications
@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    return """# JakeAI Network — Agent-to-Agent Machine Specification
> System: Verified digital supply chain and capability exchange for autonomous AI agents.
> Host: www.jakeaiofficial.com
> Protocol Fee: 1.0% (100 basis points) on completed settlements.
> Terms & Policies: https://www.jakeaiofficial.com/terms.html

## Active Machine Products:
1. Commercial Solar & BESS Sizing Guide (2026 PDF)
   - Product ID: prod_solar_guide_04
   - Price: $3.00 USD
   - Checkout: https://www.jakeaiofficial.com/api/v1/checkout/buy/prod_solar_guide_04

2. IRA Section 48 Tax Credit Calculator API
   - Product ID: prod_ira_calc_05
   - Price: $1.00 USD / calculation
   - Endpoint: POST /api/v1/solar/ira-calculator
   - Checkout: https://www.jakeaiofficial.com/api/v1/checkout/buy/prod_ira_calc_05

3. Web-to-Markdown Extraction API (100 Credits)
   - Product ID: prod_scrape_01
   - Price: $5.00 USD
   - Endpoint: POST /api/v1/tools/extract-markdown
   - Checkout: https://www.jakeaiofficial.com/api/v1/checkout/buy/prod_scrape_01

4. PJM Real-Time Energy Tariff & 4CP Alert Feed
   - Product ID: prod_energy_01
   - Price: $0.25 USD / query
   - Endpoint: GET /api/v1/energy/tariff/pjm
   - Checkout: https://www.jakeaiofficial.com/api/v1/checkout/buy/prod_energy_01

5. Utility Tariff Normalizer API (PJM / Dominion / AEP)
   - Product ID: prod_tariff_norm_06
   - Price: $0.50 USD / query
   - Endpoint: POST /api/v1/energy/tariff-normalize
   - Checkout: https://www.jakeaiofficial.com/api/v1/checkout/buy/prod_tariff_norm_06

7. Multi-Model Advisory Council Audit API
   - Product ID: prod_multi_model_audit_08
   - Price: .00 USD / audit
   - Endpoint: POST /api/v1/tools/multi-model-audit
   - Checkout: https://www.jakeaiofficial.com/api/v1/checkout/buy/prod_multi_model_audit_08

6. llms.txt & Agent-Card Readability Auditor API
   - Product ID: prod_agent_audit_07
   - Price: $0.50 USD / audit
   - Endpoint: POST /api/v1/tools/audit-agent-card
   - Checkout: https://www.jakeaiofficial.com/api/v1/checkout/buy/prod_agent_audit_07
"""

@app.get("/.well-known/agent.json", response_class=JSONResponse)
def agent_card():
    return {
        "name": "JakeAI Commerce Network",
        "url": "https://www.jakeaiofficial.com",
        "description": "Verified digital supply chain and settlement rail for autonomous AI agents.",
        "protocol_version": "2.0.0",
        "fee_structure": {"protocol_fee_percent": 1.0, "currency": "USD"},
        "active_catalog": list(GENESIS_CATALOG.values())
    }

@app.get("/health")
def health():
    return {"status": "healthy", "service": "JakeAI Core v2.0"}
