"""Static regression gates for Jake AI Master Baseline candidate.

These tests intentionally require no production credentials and make no network calls.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
NETLIFY = (ROOT / "netlify.toml").read_text(encoding="utf-8")


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


def test_homepage_does_not_make_global_checkout_active_claim():
    assert "● Checkout Active" not in INDEX


def test_homepage_does_not_call_solar_guide_authoritative():
    assert "Authoritative reference guide" not in INDEX
