import copy
import json
from pathlib import Path

from tools.commercial_rules import validate

REGISTRY = json.loads(Path("governance/commercial_rules_registry.json").read_text())
MASTER = json.loads(Path("governance/master_manifest.json").read_text())


def test_registry_matches_master_and_is_fail_closed():
    assert validate(REGISTRY, MASTER) == []


def test_price_drift_fails():
    registry = copy.deepcopy(REGISTRY)
    registry["products"]["prod_game_qa_autopilot_01"]["price_usd"] = 19.99
    assert any("price does not match" in e for e in validate(registry, MASTER))


def test_product_cannot_self_authorize():
    registry = copy.deepcopy(REGISTRY)
    registry["products"]["prod_solar_guide_04"]["commercial_authorized"] = True
    assert any("commercial_authorized must remain false" in e for e in validate(registry, MASTER))


def test_checkout_cannot_pre_authorize():
    registry = copy.deepcopy(REGISTRY)
    registry["products"]["prod_solar_guide_04"]["checkout_authorized"] = True
    assert any("checkout_authorized must remain false" in e for e in validate(registry, MASTER))


def test_public_fee_claim_cannot_be_preapproved():
    registry = copy.deepcopy(REGISTRY)
    registry["platform_terms"]["protocol_fee"]["public_claim_authorized"] = True
    assert any("public claim must remain unauthorized" in e for e in validate(registry, MASTER))


def test_creator_split_must_sum_to_one():
    registry = copy.deepcopy(REGISTRY)
    registry["platform_terms"]["creator_revenue_split"]["creator_share"] = 0.75
    assert any("split must sum to 1.0" in e for e in validate(registry, MASTER))


def test_metered_products_cannot_be_marked_verified_without_baseline_evidence():
    registry = copy.deepcopy(REGISTRY)
    registry["products"]["prod_energy_01"]["metering_verified"] = True
    assert any("metering cannot be pre-verified" in e for e in validate(registry, MASTER))
