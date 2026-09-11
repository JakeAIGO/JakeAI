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
