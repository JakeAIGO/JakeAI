import json
from pathlib import Path

import pytest

from tools.production_candidate_builder import approved_platform_terms, approved_products


def test_unapproved_products_are_excluded():
    registry = {"products": {"p1": {"price_usd": 1.0, "commercial_authorized": False, "checkout_authorized": False}}}
    assert approved_products(registry) == []


def test_authorized_product_requires_fulfillment_and_legal_review():
    registry = {"products": {"p1": {"price_usd": 1.0, "commercial_authorized": True, "checkout_authorized": True, "fulfillment_verified": False, "legal_review_complete": True}}}
    with pytest.raises(ValueError):
        approved_products(registry)


def test_fully_verified_authorized_product_is_included():
    registry = {"products": {"p1": {"price_usd": 1.0, "commercial_authorized": True, "checkout_authorized": True, "fulfillment_verified": True, "legal_review_complete": True}}}
    assert approved_products(registry) == [{"product_id": "p1", "price_usd": 1.0}]


def test_unapproved_platform_terms_are_excluded():
    registry = {"platform_terms": {"creator_revenue_split": {"approved": False, "public_claim_authorized": False, "creator_share": 0.5}}}
    assert approved_platform_terms(registry) == {}


def test_approved_public_terms_can_be_included():
    term = {"approved": True, "public_claim_authorized": True, "rate": 0.01}
    registry = {"platform_terms": {"protocol_fee": term}}
    assert approved_platform_terms(registry) == {"protocol_fee": term}


def test_current_registry_builds_empty_commercial_candidate():
    registry = json.loads(Path("governance/commercial_rules_registry.json").read_text())
    assert approved_products(registry) == []
    assert approved_platform_terms(registry) == {}
