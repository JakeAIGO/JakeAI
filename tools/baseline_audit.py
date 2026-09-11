#!/usr/bin/env python3
"""Jake AI Master Baseline repository auditor.

Offline/static checks only. No production calls, credentials, spending, checkout activation,
or deployment changes are performed by this script.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_FILES = {
    "main.py",
    "index.html",
    "terms.html",
    "privacy.html",
    "refunds.html",
    "netlify.toml",
    "requirements.txt",
    "AGENTS.md",
    "governance/MASTER_BASELINE_ENGINE.md",
    "tests/test_master_baseline_invariants.py",
}


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def check_expected_files(failures: list[str]) -> None:
    for rel in sorted(EXPECTED_FILES):
        if not (ROOT / rel).is_file():
            fail(f"missing required baseline file: {rel}", failures)


def check_python_syntax(failures: list[str]) -> None:
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in {".git", ".venv", "venv"} for part in path.parts):
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            fail(f"python syntax error in {path.relative_to(ROOT)}: {exc}", failures)


def html_internal_links() -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    href_re = re.compile(r'href=["\']([^"\']+)["\']', re.I)
    for html in sorted(ROOT.glob("*.html")):
        text = html.read_text(encoding="utf-8")
        for href in href_re.findall(text):
            links.append((html.name, href.strip()))
    return links


def check_internal_html_links(failures: list[str]) -> None:
    # Dynamic/proxied routes are validated separately.
    dynamic_prefixes = ("/api/", "/v1/", "/docs", "/openapi.json", "/health", "/llms.txt", "/.well-known/")
    for source, href in html_internal_links():
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        parsed = urlparse(href)
        if parsed.scheme in {"http", "https"}:
            continue
        path = parsed.path
        if path == "/":
            target = ROOT / "index.html"
        elif path.startswith(dynamic_prefixes):
            continue
        elif path.startswith("/"):
            target = ROOT / path.lstrip("/")
        else:
            target = ROOT / path
        if not target.is_file():
            fail(f"broken internal link in {source}: {href} -> missing {target.relative_to(ROOT)}", failures)


def check_proxy_contract(failures: list[str]) -> None:
    cfg = read("netlify.toml")
    required = {
        'from = "/api/v1/*"': "website-facing API proxy",
        'from = "/llms.txt"': "machine-readable catalog proxy",
        'from = "/.well-known/*"': "agent-card proxy",
        'from = "/docs"': "docs proxy",
        'from = "/openapi.json"': "OpenAPI proxy",
        'from = "/health"': "health proxy",
    }
    for needle, label in required.items():
        if needle not in cfg:
            fail(f"missing {label}: {needle}", failures)


def check_claims(failures: list[str]) -> None:
    index = read("index.html")
    readme = read("README.md")
    main = read("main.py")

    banned = {
        "● Checkout Active": "global checkout state overclaims mixed per-product availability",
        "Authoritative reference guide": "unsupported authority claim",
        "publish, discover, and settle commercial transactions without human intervention": "unbounded autonomy claim",
    }
    corpus = "\n".join([index, readme])
    for phrase, reason in banned.items():
        if phrase in corpus:
            fail(f"claim gate failed: {reason}: {phrase!r}", failures)

    # Products explicitly described as demonstration data may not carry Real-Time in their title.
    if '"prod_energy_01"' in main and '"title": "PJM Real-Time Energy Tariff' in main:
        fail("claim gate failed: demonstration energy product title still says Real-Time", failures)


def check_commerce_invariants(failures: list[str]) -> None:
    main = read("main.py")
    start = main.find("def create_checkout_session")
    if start < 0:
        fail("checkout handler missing", failures)
        return
    section = main[start:]
    free_gate = 'if prod_data.get("price", 0) <= 0 or product_id == "prod_make_free_00"'
    secret_gate = 'secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()'
    if free_gate not in section or secret_gate not in section:
        fail("checkout handler missing expected free/Stripe gates", failures)
    elif section.index(free_gate) > section.index(secret_gate):
        fail("free product incorrectly depends on STRIPE_SECRET_KEY", failures)

    verify = main.find("def verify_checkout")
    if verify < 0:
        fail("payment verification handler missing", failures)
    else:
        v = main[verify:]
        paid = 'session.payment_status != "paid"'
        delivery = 'delivery_url = prod_data.get("download_url"'
        if paid not in v or delivery not in v or v.index(paid) > v.index(delivery):
            fail("paid delivery is not clearly gated behind payment verification", failures)

    helper = main[main.find("def public_product_view"):main.find("def is_product_checkout_enabled")]
    if '"download_url"' in helper:
        fail("public product view exposes private delivery URL", failures)


def main() -> int:
    failures: list[str] = []
    check_expected_files(failures)
    check_python_syntax(failures)
    check_internal_html_links(failures)
    check_proxy_contract(failures)
    check_claims(failures)
    check_commerce_invariants(failures)

    if failures:
        print("MASTER BASELINE AUDIT: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    print("MASTER BASELINE AUDIT: PASS")
    print("Static repository gates passed. Runtime/deployment/Council verification is still required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
