import sqlite3
import time
import os
import uuid
import json
import stripe
import urllib.request
import re
import ipaddress
import socket
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request, Header, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB_PATH = os.environ.get("DATABASE_PATH", "network.db")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Configurable CORS origins — never wildcard with credentials
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "https://www.jakeaiofficial.com,https://jakeaiofficial.com").split(",") if o.strip()]
NETWORK_FETCH_TOOLS_ENABLED = os.environ.get("NETWORK_FETCH_TOOLS_ENABLED", "false").strip().lower() == "true"

# Categories that require entitlement/metering before they can be sold
API_CREDIT_CATEGORIES = {"ai-utilities", "data-api", "developer-pack", "fintech-api", "robotics-api"}

# Expanded High-Utility Agent Catalog
GENESIS_CATALOG = {
    "prod_grasp_solver_09": {
        "title": "22-DoF Tendon Grasp & Impedance Solver API",
        "description": "Unvalidated educational calculation for hypothetical 5-fingered robotic hands. Outputs are advisory only and must not be used as validated physical-control commands without independent engineering verification.",
        "category": "robotics-api",
        "price": 0.10,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/solve_grasp_v1_robotics_grasp_impedance_solver_post",
        "vendor_did": "did:a2a:jakeai_core",
        "requires_metering": True
    },
    "prod_make_free_00": {
        "title": "Make the Damn Thing for Free™ (Zero-Budget Production Orchestrator)",
        "description": "Flagship gateway Autonomous Workflow Skill. Tell it what you want to make. Starting budget: $0. Find a way. Decomposes goals into micro-tasks, routes to cheapest capable resources, locks successful outputs, and escalates only when necessary.",
        "category": "autonomous-workflow-skills",
        "price": 0.00,
        "download_url": "https://docs.google.com/document/d/14Ayw4pxjnYy5MddTGdLSZEeQGKJGU3CRSmW7384Lfhk/edit?usp=sharing",
        "vendor_did": "did:a2a:jakeai_core",
        "requires_metering": False
    },
    "prod_solar_guide_04": {
        "title": "Commercial Solar & BESS Microgrid Sizing Guide (2026 PDF)",
        "description": "Dense technical reference guide covering C&I electrical string sizing, 4CP peak-shaving dispatch, and IRA tax credit stacking formulas (30% + 10% + 10%).",
        "category": "digital-guide",
        "price": 3.00,
        "download_url": "https://drive.google.com/file/d/1xFpazazGdH2_LGSkvuWgMmR5jhPnq7pv/view?usp=drivesdk",
        "vendor_did": "did:a2a:solutions_energy",
        "requires_metering": False
    },
    "prod_ira_calc_05": {
        "title": "IRA / Section 48 ITC Tax Credit Calculator API",
        "description": "Executable calculator returning statutory cash direct elective pay breakdowns (30% Base + 10% Energy Community + 10% Domestic Content).",
        "category": "fintech-api",
        "price": 1.00,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/calculate_ira_v1_solar_ira_calculator_post",
        "vendor_did": "did:a2a:solutions_energy",
        "requires_metering": True
    },
    "prod_scrape_01": {
        "title": "JakeAI Web-to-Markdown Extraction API (100 Credits)",
        "description": "High-speed clean text & markdown extractor for LLMs and autonomous agents. Bypasses ads, navbars, and bloated HTML.",
        "category": "ai-utilities",
        "price": 5.00,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/extract_markdown_v1_tools_extract_markdown_post",
        "vendor_did": "did:a2a:jakeai_core",
        "requires_metering": True
    },
    "prod_energy_01": {
        "title": "PJM Demonstration Energy Tariff & 4CP Peak Forecast API",
        "description": "Nodal electricity price queries and 4CP transmission peak alerts across PJM & Dominion territories for energy automation bots. Values are demonstration data, not live grid pricing.",
        "category": "data-api",
        "price": 0.25,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/get_tariff_data_v1_energy_tariff_pjm_get",
        "vendor_did": "did:a2a:solutions_energy",
        "requires_metering": True
    },
    "prod_tariff_norm_06": {
        "title": "Utility Tariff Normalizer API (PJM / Dominion / AEP)",
        "description": "Transforms complex non-standard utility rate schedules (GS-1, GS-3, large industrial) into standardized JSON objects for financial modeling.",
        "category": "data-api",
        "price": 0.50,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/normalize_tariff_v1_energy_tariff_normalize_post",
        "vendor_did": "did:a2a:solutions_energy",
        "requires_metering": True
    },
    "prod_audit_pack_10": {
        "title": "Multi-Model Advisory Audit — 10-Audit Developer Pack",
        "description": "Pre-funded developer credit key for 10 automated pre-deployment audits (Claude 3.5 Sonnet + Perplexity Sonar-Pro). Includes CI/CD & MCP execution token.",
        "category": "developer-pack",
        "price": 18.00,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/multi_model_audit_v1_tools_multi_model_audit_post",
        "vendor_did": "did:a2a:jakeai_core",
        "requires_metering": True
    },
    "prod_multi_model_audit_08": {
        "title": "Multi-Model Advisory Council Audit API",
        "description": "Automated dual-model pre-deployment audit combining Claude 3.5 Sonnet (architecture & legal risk) and Perplexity Sonar-Pro (market benchmarks) into a unified Go/No-Go report.",
        "category": "ai-utilities",
        "price": 2.00,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/multi_model_audit_v1_tools_multi_model_audit_post",
        "vendor_did": "did:a2a:jakeai_core",
        "requires_metering": True
    },
    "prod_agent_audit_07": {
        "title": "llms.txt & Agent-Card Readability Auditor API",
        "description": "Automated machine audit testing any domain for /llms.txt compliance, MCP schema compatibility, and AI bot crawlability score.",
        "category": "ai-utilities",
        "price": 0.50,
        "download_url": "https://www.jakeaiofficial.com/docs#/default/audit_agent_card_v1_tools_audit_agent_card_post",
        "vendor_did": "did:a2a:jakeai_core",
        "requires_metering": True
    },
    "prod_game_qa_autopilot_01": {
        "title": "Game QA Autopilot v1.0",
        "description": "Deterministic QA workflow skill for game studios: requirement decomposition, test matrix generation, edge-case coverage, evidence-gated PASS/FAIL, reproducible bug reports, severity/confidence separation, regression queue, and release-readiness reports. Supports Unity, Unreal, Godot, and custom engines. Human release authority by default.",
        "category": "autonomous-workflow-skills",
        "price": 9.99,
        "download_url": os.environ.get("GAME_QA_DELIVERY_URL", ""),
        "vendor_did": "did:a2a:jakeai_core",
        "requires_metering": False,
        "checkout_enabled": bool(os.environ.get("GAME_QA_DELIVERY_URL", "").strip())
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
    description="Digital supply chain and capability exchange for autonomous AI agents.",
    version="2.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "Idempotency-Key"],
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


# --- SECURITY HELPERS ---

def public_product_view(p: dict, product_id: str = None) -> dict:
    """Return a sanitized public view of a product, stripping private delivery URLs."""
    view = {
        "id": product_id,
        "title": p["title"],
        "description": p["description"],
        "category": p["category"],
        "price": p["price"],
        "vendor_did": p["vendor_did"],
    }
    # Never expose download_url in public catalog responses
    return view


def is_product_checkout_enabled(product_id: str) -> bool:
    """Check whether a product's checkout should be enabled."""
    p = GENESIS_CATALOG.get(product_id)
    if not p:
        return False
    # API-credit products fail closed until entitlement/metering exists
    if p.get("requires_metering", False) or p["category"] in API_CREDIT_CATEGORIES:
        return False
    # Products with explicit checkout_enabled flag
    if "checkout_enabled" in p:
        return p["checkout_enabled"]
    # Products without a configured delivery URL fail closed
    delivery_url = p.get("download_url", "").strip()
    if not delivery_url:
        return False
    return True


def is_safe_url(url_str: str) -> bool:
    """SSRF protection: reject non-public network targets."""
    try:
        parsed = urlparse(url_str)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        # Resolve and check IP
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            # Hostname is a domain — resolve it
            try:
                ips = socket.getaddrinfo(hostname, None)
                for family, type_, proto, canonname, sockaddr in ips:
                    ip = ipaddress.ip_address(sockaddr[0])
                    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                        return False
            except socket.gaierror:
                return False
            return True
        # Direct IP address
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
        return True
    except Exception:
        return False


# Pydantic Input Models
class ExtractRequest(BaseModel):
    url: str = Field(..., example="https://en.wikipedia.org/wiki/Artificial_intelligence")

class IRACalculatorRequest(BaseModel):
    system_cost: float = Field(..., gt=0.0, example=500000.0, description="Gross Turnkey EPC Cost in USD")
    system_kw_dc: float = Field(..., gt=0.0, example=400.0, description="System DC Nameplate Rating in kW")
    is_energy_community: bool = Field(False, description="Whether location qualifies for Energy Community +10% adder")
    is_domestic_content: bool = Field(False, description="Whether equipment qualifies for 100% US steel + domestic adder")

class TariffNormalizeRequest(BaseModel):
    utility: str = Field(..., example="Dominion_VA")
    rate_class: str = Field(..., example="GS-3")
    peak_demand_kw: float = Field(..., ge=0.0, example=450.0)
    monthly_consumption_kwh: float = Field(..., gt=0.0, example=180000.0)

class MultiModelAuditRequest(BaseModel):
    content: str = Field(..., max_length=15000, description="Proposal text, code, schema, or product manifest to audit")
    domain: Optional[str] = Field(None, description="Associated website or platform domain")

class AgentAuditRequest(BaseModel):
    domain: str = Field(..., example="github.com")

class SettlementRequest(BaseModel):
    product_id: str
    buyer_did: str
    amount: float = Field(..., gt=0.0)
    take_rate: Optional[float] = Field(0.01, ge=0.0, le=1.0)

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
        "4cp_transmission_exposure_risk": "HIGH" if req.peak_demand_kw > 300 else "MODERATE",
        "data_note": "Rate constants are illustrative demonstration values, not live tariff data."
    }

@app.get("/v1/energy/tariff/pjm")
def get_tariff_data():
    """PJM & Dominion LMP pricing and 4CP status — demonstration data, not live grid pricing"""
    return {
        "region": "PJM_DOMINION",
        "real_time_lmp_mwh": 38.45,
        "day_ahead_lmp_mwh": 41.20,
        "congestion_usd": 1.15,
        "marginal_losses_usd": -0.40,
        "transmission_4cp_peak_alert": False,
        "grid_frequency_hz": 60.00,
        "status": "NORMAL",
        "data_disclaimer": "DEMONSTRATION DATA — not live grid pricing. Values are static placeholders for development and testing."
    }

@app.post("/v1/tools/extract-markdown")
def extract_markdown(req: ExtractRequest):
    """Clean web-to-markdown text extractor for LLMs."""
    if not NETWORK_FETCH_TOOLS_ENABLED:
        raise HTTPException(status_code=503, detail="External network-fetch tools are disabled pending hardened egress controls.")
    # SSRF protection
    if not is_safe_url(req.url):
        raise HTTPException(status_code=400, detail="URL rejected: target is not a publicly accessible resource.")
    try:
        headers = {'User-Agent': 'JakeAIBot/2.3 (+https://www.jakeaiofficial.com)'}
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
        print(f"Extraction provider error: {type(e).__name__}")
        raise HTTPException(status_code=400, detail="Extraction failed for the requested public resource.")


def query_claude_auditor(prompt: str, api_key: Optional[str]) -> Dict[str, Any]:
    if not api_key:
        return {
            "status": "simulation_mode",
            "model": "claude-3-5-sonnet-20241022",
            "verdict": "NOT_RUN",
            "findings": "Server ANTHROPIC_API_KEY not configured. Audit not executed. REVIEW REQUIRED."
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
        print(f"Anthropic audit provider error: {type(e).__name__}")
        return {"status": "error", "model": "claude-3-5-sonnet-20241022", "error": "Provider request failed."}

def query_perplexity_auditor(prompt: str, api_key: Optional[str]) -> Dict[str, Any]:
    if not api_key:
        return {
            "status": "simulation_mode",
            "model": "sonar-pro",
            "verdict": "NOT_RUN",
            "findings": "Server PERPLEXITY_API_KEY not configured. Audit not executed. REVIEW REQUIRED."
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
        print(f"Perplexity audit provider error: {type(e).__name__}")
        return {"status": "error", "model": "sonar-pro", "error": "Provider request failed."}

@app.post("/v1/tools/multi-model-audit")
def multi_model_audit(req: MultiModelAuditRequest, request: Request):
    """Automated pre-deployment dual-model consensus audit (Claude 3.5 Sonnet + Perplexity Sonar-Pro)"""
    # Provider credentials are server-side configuration only; never accept secrets in request headers.
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    perplexity_key = os.environ.get("PERPLEXITY_API_KEY", "").strip()
    
    claude_res = query_claude_auditor(req.content, anthropic_key)
    perplexity_res = query_perplexity_auditor(req.content, perplexity_key)
    
    # Calculate consensus verdict
    claude_v = claude_res.get("verdict", "NOT_RUN")
    perplex_v = perplexity_res.get("verdict", "NOT_RUN")
    if claude_v == "GO" and perplex_v == "GO":
        consensus = "GO"
    elif claude_v == "NOT_RUN" or perplex_v == "NOT_RUN":
        consensus = "REVIEW REQUIRED — one or more models not configured"
    else:
        consensus = "CONDITIONAL REVIEW REQUIRED"
    
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
    """Audits a domain for llms.txt & agent-card readability when hardened egress is enabled."""
    if not NETWORK_FETCH_TOOLS_ENABLED:
        raise HTTPException(status_code=503, detail="External network-fetch tools are disabled pending hardened egress controls.")
    clean_domain = req.domain.replace("https://", "").replace("http://", "").strip("/")
    # Attempt actual checks rather than returning hardcoded pass results
    has_llms_txt = False
    has_agent_card = False
    try:
        llms_url = f"https://{clean_domain}/llms.txt"
        if is_safe_url(llms_url):
            test_req = urllib.request.Request(llms_url, headers={'User-Agent': 'JakeAIBot/2.3'})
            with urllib.request.urlopen(test_req, timeout=5) as resp:
                if resp.status == 200:
                    has_llms_txt = True
    except Exception:
        pass
    try:
        card_url = f"https://{clean_domain}/.well-known/agent.json"
        if is_safe_url(card_url):
            test_req = urllib.request.Request(card_url, headers={'User-Agent': 'JakeAIBot/2.3'})
            with urllib.request.urlopen(test_req, timeout=5) as resp:
                if resp.status == 200:
                    has_agent_card = True
    except Exception:
        pass
    
    grade = "A" if (has_llms_txt and has_agent_card) else ("B" if (has_llms_txt or has_agent_card) else "F")
    
    return {
        "target_domain": clean_domain,
        "agent_readability_grade": grade,
        "has_llms_txt": has_llms_txt,
        "has_mcp_server": "NOT_CHECKED",
        "audit_summary": f"Domain {clean_domain}: llms.txt={'found' if has_llms_txt else 'not found'}, agent.json={'found' if has_agent_card else 'not found'}."
    }

# --- STRIPE CHECKOUT & PAYMENT RAILS WITH IDEMPOTENCY ---

@app.get("/v1/checkout/buy/{product_id}")
@app.post("/v1/checkout/create-session")
def create_checkout_session(product_id: str, idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
    prod_data = GENESIS_CATALOG.get(product_id)
    if not prod_data:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found in catalog")
    
    # Fail closed for products that should not be chargeable
    if not is_product_checkout_enabled(product_id):
        raise HTTPException(
            status_code=503,
            detail=f"Checkout for {product_id} is not available. This product requires configuration before it can be purchased."
        )
        
    # Free Gateway SKU: deliver without requiring Stripe credentials.
    # This branch intentionally executes before any payment-processor dependency.
    if prod_data.get("price", 0) <= 0 or product_id == "prod_make_free_00":
        return RedirectResponse(url=prod_data.get("download_url", "https://www.jakeaiofficial.com"), status_code=303)

    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY missing in server variables")

    stripe.api_key = secret_key

    # Use a verification callback URL instead of direct delivery URL
    # After payment, user hits /v1/checkout/verify which checks Stripe payment status before delivering
    success_url = f"https://agent-commerce-network-production-56e8.up.railway.app/v1/checkout/verify?product_id={product_id}&session_id={{CHECKOUT_SESSION_ID}}"
    
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
            metadata={'product_id': product_id},
            success_url=success_url,
            cancel_url="https://www.jakeaiofficial.com?payment=cancelled",
            **stripe_kwargs
        )
        return RedirectResponse(url=session.url, status_code=303)
    except Exception as e:
        print(f"Checkout provider error: {type(e).__name__}")
        raise HTTPException(status_code=400, detail="Checkout provider could not create a session.")


@app.get("/v1/checkout/verify")
def verify_checkout(product_id: str, session_id: str = Query(...)):
    """Verify Stripe payment status before delivering paid content."""
    prod_data = GENESIS_CATALOG.get(product_id)
    if not prod_data:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found in catalog")
    
    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY missing in server variables")
    
    stripe.api_key = secret_key
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        print(f"Checkout verification provider error: {type(e).__name__}")
        raise HTTPException(status_code=400, detail="Checkout session could not be verified.")
    
    if session.payment_status != "paid":
        raise HTTPException(status_code=402, detail="Payment not completed. Delivery withheld.")

    # Bind the verified Stripe session to the exact product and catalog price.
    # A paid session for one SKU must never unlock another SKU.
    session_product_id = (getattr(session, "metadata", None) or {}).get("product_id")
    if session_product_id != product_id:
        raise HTTPException(status_code=403, detail="Checkout session product mismatch. Delivery withheld.")

    expected_amount = int(round(float(prod_data["price"]) * 100))
    if getattr(session, "amount_total", None) != expected_amount:
        raise HTTPException(status_code=403, detail="Checkout session amount mismatch. Delivery withheld.")

    if str(getattr(session, "currency", "")).lower() != "usd":
        raise HTTPException(status_code=403, detail="Checkout session currency mismatch. Delivery withheld.")
    
    # Payment verified and bound to this product — redirect to private delivery URL
    delivery_url = prod_data.get("download_url", "").strip()
    if not delivery_url:
        raise HTTPException(status_code=503, detail="Delivery URL not configured for this product.")
    
    return RedirectResponse(url=delivery_url, status_code=303)


# Catalog Discovery Endpoints
@app.get("/v1/products/list")
def list_products():
    """Public catalog — excludes private download_url values."""
    return [public_product_view(p, pid) for pid, p in GENESIS_CATALOG.items()]


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
    safety_classification: str
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
        status="advisory_only",
        safety_classification="UNVALIDATED_PHYSICAL_CONTROL_MODEL",
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
        (pid, p) for pid, p in GENESIS_CATALOG.items()
        if q and (q in p["title"].lower() or q in p["description"].lower() or q in p["category"].lower())
    ]
    # Privacy-minimized product-demand telemetry: retain the search term and match count,
    # but do not persist requester IP addresses or user-agent strings.
    background_tasks.add_task(log_unmet_query, q, "not_collected", "not_collected", len(matches))
    
    # Return sanitized public views — never expose download_url
    results = [public_product_view(p, pid) for pid, p in matches] if matches else [public_product_view(p, pid) for pid, p in GENESIS_CATALOG.items()]
    
    return {
        "status": "success" if matches else "no_matches_logged_to_telemetry",
        "count": len(results),
        "results": results
    }

# Machine Specifications
@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    """Machine-readable catalog specification — excludes private delivery URLs."""
    lines = [
        "# JakeAI Network — Agent-to-Agent Machine Specification",
        "> System: Digital supply chain and capability exchange for autonomous AI agents.",
        "> Host: www.jakeaiofficial.com",
        "> Protocol Fee: 1.0% on completed settlements.",
        "> Terms & Policies: https://www.jakeaiofficial.com/terms.html",
        "",
        "## Catalog Products:",
    ]
    for pid, p in GENESIS_CATALOG.items():
        checkout_enabled = is_product_checkout_enabled(pid)
        status = "available" if checkout_enabled else "checkout_disabled"
        lines.extend([
            f"- {p['title']}",
            f"  - Product ID: {pid}",
            f"  - Price: ${p['price']:.2f} USD",
            f"  - Status: {status}",
        ])
    return "\n".join(lines)

@app.get("/.well-known/agent.json", response_class=JSONResponse)
def agent_card():
    return {
        "name": "JakeAI Commerce Network",
        "url": "https://www.jakeaiofficial.com",
        "description": "Digital supply chain and capability exchange for autonomous AI agents.",
        "protocol_version": "2.3.0",
        "fee_structure": {"protocol_fee_percent": 1.0, "currency": "USD"},
        "active_catalog": [public_product_view(p, pid) for pid, p in GENESIS_CATALOG.items()]
    }

@app.get("/health")
def health():
    """Process liveness only; does not assert dependency or commerce readiness."""
    return {"status": "alive", "service": "JakeAI Core v2.3", "scope": "process_liveness_only"}
