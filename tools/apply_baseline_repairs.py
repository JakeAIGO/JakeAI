#!/usr/bin/env python3
"""Apply deterministic Jake AI Master Baseline repairs.

This script only edits repository files. It does not deploy, call production,
activate checkout, spend money, or touch credentials.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: str, old: str, new: str) -> bool:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if old not in text:
        return False
    text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    changed = []

    checkout_old = '''    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()\n    if not secret_key:\n        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY missing in server variables")\n        \n    stripe.api_key = secret_key\n    \n    # Free Gateway SKU: frictionless 1-click delivery, bypass Stripe minimums\n    if prod_data.get("price", 0) <= 0 or product_id == "prod_make_free_00":\n        return RedirectResponse(url=prod_data.get("download_url", "https://www.jakeaiofficial.com"), status_code=303)\n'''
    checkout_new = '''    # Free Gateway SKU: deliver without requiring Stripe credentials.\n    # This branch intentionally executes before any payment-processor dependency.\n    if prod_data.get("price", 0) <= 0 or product_id == "prod_make_free_00":\n        return RedirectResponse(url=prod_data.get("download_url", "https://www.jakeaiofficial.com"), status_code=303)\n\n    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()\n    if not secret_key:\n        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY missing in server variables")\n\n    stripe.api_key = secret_key\n'''
    if replace_exact("main.py", checkout_old, checkout_new):
        changed.append("main.py: free checkout no longer depends on Stripe")

    replacements = [
        ("main.py", '"title": "PJM Real-Time Energy Tariff & 4CP Peak Forecast API"', '"title": "PJM Demonstration Energy Tariff & 4CP Peak Forecast API"'),
        ("index.html", "● Checkout Active", "Checkout status shown per product"),
        ("index.html", "Authoritative reference guide", "Technical reference guide"),
        ("index.html", "Bots query and transact directly via JSON-LD without human UI, captchas, or browser emulation.", "Designed for autonomous agents to query documented REST interfaces directly; transaction availability is determined per product and deployment state."),
        ("index.html", "Direct REST & JSON-LD execution", "REST interfaces with machine-readable discovery"),
        ("index.html", "Connect your custom software services, APIs, or datasets to the global agent network and monetize machine traffic.", "Developer and vendor onboarding is being prepared around documented, agent-readable interfaces. Commercial activation remains subject to verification and approval gates."),
        ("index.html", "Automated discovery by external agents", "Agent-readable discovery surfaces"),
        ("terms.html", "Transactions initiated by software agents, API keys, or human users are processed securely via Stripe. JakeAI applies a 1.0% (100 basis points) network protocol fee on settled commerce. Users and agents are responsible for maintaining API key confidentiality and setting internal rate caps.", "Where checkout is enabled, payments are handled through the payment provider configured for that product and deployment. Commercial fees and revenue-sharing terms apply only when explicitly presented and supported by the active transaction flow. Users and agents are responsible for protecting their own credentials and authorization controls."),
        (
            "main.py",
            '    system_cost: float = Field(..., example=500000.0, description="Gross Turnkey EPC Cost in USD")',
            '    system_cost: float = Field(..., gt=0.0, example=500000.0, description="Gross Turnkey EPC Cost in USD")',
        ),
        (
            "main.py",
            '    system_kw_dc: float = Field(..., example=400.0, description="System DC Nameplate Rating in kW")',
            '    system_kw_dc: float = Field(..., gt=0.0, example=400.0, description="System DC Nameplate Rating in kW")',
        ),
        (
            "main.py",
            '    peak_demand_kw: float = Field(..., example=450.0)',
            '    peak_demand_kw: float = Field(..., ge=0.0, example=450.0)',
        ),
        (
            "main.py",
            '    monthly_consumption_kwh: float = Field(..., example=180000.0)',
            '    monthly_consumption_kwh: float = Field(..., gt=0.0, example=180000.0)',
        ),
        (
            "main.py",
            '    amount: float\n    take_rate: Optional[float] = 0.01',
            '    amount: float = Field(..., gt=0.0)\n    take_rate: Optional[float] = Field(0.01, ge=0.0, le=1.0)',
        ),
        (
            "main.py",
            "            mode='payment',\n            success_url=success_url,",
            "            mode='payment',\n            metadata={'product_id': product_id},\n            success_url=success_url,",
        ),
        (
            "main.py",
            '''    if session.payment_status != "paid":\n        raise HTTPException(status_code=402, detail="Payment not completed. Delivery withheld.")\n    \n    # Payment verified — redirect to private delivery URL\n    delivery_url = prod_data.get("download_url", "").strip()''',
            '''    if session.payment_status != "paid":\n        raise HTTPException(status_code=402, detail="Payment not completed. Delivery withheld.")\n\n    # Bind the verified Stripe session to the exact product and catalog price.\n    # A paid session for one SKU must never unlock another SKU.\n    session_product_id = (getattr(session, "metadata", None) or {}).get("product_id")\n    if session_product_id != product_id:\n        raise HTTPException(status_code=403, detail="Checkout session product mismatch. Delivery withheld.")\n\n    expected_amount = int(round(float(prod_data["price"]) * 100))\n    if getattr(session, "amount_total", None) != expected_amount:\n        raise HTTPException(status_code=403, detail="Checkout session amount mismatch. Delivery withheld.")\n\n    if str(getattr(session, "currency", "")).lower() != "usd":\n        raise HTTPException(status_code=403, detail="Checkout session currency mismatch. Delivery withheld.")\n    \n    # Payment verified and bound to this product — redirect to private delivery URL\n    delivery_url = prod_data.get("download_url", "").strip()''',
        ),
    ]

    for path, old, new in replacements:
        if replace_exact(path, old, new):
            changed.append(f"{path}: {old[:48]}...")

    if changed:
        print("Applied baseline repairs:")
        for item in changed:
            print(f"- {item}")
    else:
        print("No baseline repairs needed; expected patterns already absent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
