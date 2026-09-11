import copy
from pathlib import Path

from tools.change_control import classify_paths, load_policy, required_reviews, validate_change_request


POLICY = load_policy(Path("governance/change_control_policy.json"))


def base_request():
    return {
        "schema_version": "1.0",
        "id": "TEST-1",
        "title": "Test",
        "status": "proposed",
        "baseline_ref": "baseline/master-2026-09-11",
        "purpose": "test",
        "risk_class": "high",
        "scope_categories": [],
        "reviews": {},
        "production_authorized": False,
        "publication_authorized": False,
        "commercial_authorized": False,
        "human_approval_record": "",
        "unresolved_conditions": [],
    }


def test_classifies_governance_and_security_self_modification():
    paths = ["tools/change_control.py", "governance/change_control_policy.json"]
    classified = classify_paths(paths, POLICY)
    assert "governance" in classified
    assert "security" in classified


def test_required_reviews_derived_from_scope():
    reviews = required_reviews({"security", "legal", "commerce"}, POLICY)
    assert {"security", "legal", "commerce", "council"}.issubset(reviews)


def test_self_modification_requires_council_and_human_lanes():
    request = base_request()
    request["scope_categories"] = ["security"]
    request["reviews"] = {"security": "pending"}
    errors = validate_change_request(request, {"security"}, {"tools/change_control.py"}, POLICY)
    assert any("council" in e for e in errors)
    assert any("human" in e for e in errors)


def test_authorization_true_fails_without_approved_status_and_human_record():
    request = base_request()
    request["scope_categories"] = ["documentation"]
    request["production_authorized"] = True
    errors = validate_change_request(request, {"documentation"}, {"README.md"}, POLICY)
    assert any("production_authorized=true requires status=approved" in e for e in errors)
    assert any("production_authorized=true requires a human_approval_record" in e for e in errors)


def test_valid_high_risk_self_modification_declaration_passes():
    request = base_request()
    categories = {"governance", "security", "brand", "documentation", "tests"}
    request["scope_categories"] = sorted(categories)
    request["reviews"] = {
        "architecture": "pending",
        "security": "pending",
        "council": "pending",
        "human": "pending",
    }
    changed = {
        "tools/change_control.py",
        "governance/change_control_policy.json",
        "governance/CHANGE_CONTROL_ENGINE.md",
        "tests/test_change_control.py",
    }
    assert validate_change_request(request, categories, changed, POLICY) == []
