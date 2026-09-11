"""Static regression gates for the Jake AI Master Baseline candidate.

These tests intentionally require no production credentials and make no network calls.
They are guardrails, not proof of deployed runtime behavior.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
NETLIFY = (ROOT / "netlify.toml").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_free_checkout_precedes_stripe_secret_requirement():
    free_gate = 'if prod_data.get("price", 0) <= 0 or product_id == "prod_make_free_00"'
    secret_gate = 'secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()'
    checkout_start = MAIN.index('def create_checkout_session')
    section = MAIN[checkout_start:]
    assert free_gate in section
    assert section.index(free_gate) < section.index(secret_gate), (
        "Free gateway must bypass Stripe before STRIPE_SECRET_KEY is required"
    )


def test_public_catalog_strips_delivery_url():
    helper_start = MAIN.index("def public_product_view")
    helper_end = MAIN.index("def is_product_checkout_enabled", helper_start)
    helper = MAIN[helper_start:helper_end]
    assert '"download_url"' not in helper


def test_paid_checkout_verifies_payment_before_delivery():
    verify_start = MAIN.index("def verify_checkout")
    section = MAIN[verify_start:]
    paid_check = 'session.payment_status != "paid"'
    delivery = 'delivery_url = prod_data.get("download_url"'
    assert paid_check in section and delivery in section
    assert section.index(paid_check) < section.index(delivery)


def test_machine_discovery_is_proxied_to_backend():
    assert 'from = "/llms.txt"' in NETLIFY
    assert 'from = "/.well-known/*"' in NETLIFY


def test_canonical_public_api_proxy_exists():
    assert 'from = "/api/v1/*"' in NETLIFY
    assert '/v1/:splat' in NETLIFY


def test_homepage_does_not_make_global_checkout_active_claim():
    assert "● Checkout Active" not in INDEX


def test_homepage_does_not_call_solar_guide_authoritative():
    assert "Authoritative reference guide" not in INDEX


def test_demo_energy_product_title_does_not_imply_unqualified_realtime_data():
    assert '"PJM Real-Time Energy Tariff & 4CP Peak Forecast API"' not in MAIN


def test_readme_does_not_claim_unbounded_human_free_commerce():
    assert "without human intervention" not in README.lower()


def test_readme_does_not_document_removed_register_or_settle_routes():
    assert "/v1/products/register" not in README
    assert "/v1/transactions/settle" not in README


def test_readme_does_not_call_admin_private_without_verified_access_control():
    assert "Private Web Admin Dashboard" not in README


def test_readme_documents_master_baseline_gate():
    assert "MASTER BASELINE -> WORKING BRANCH -> AUTOMATED TESTS" in README
