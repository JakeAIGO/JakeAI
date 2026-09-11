from pathlib import Path

from tools.change_control import (
    classify_paths,
    load_policy,
    minimum_required_risk,
    required_reviews,
    validate_change_request,
    validate_change_request_set,
)


POLICY = load_policy(Path("governance/change_control_policy.json"))


def base_request(change_id="TEST-1"):
    return {
        "schema_version": "1.1",
        "id": change_id,
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


def test_classifies_module_paths():
    classified = classify_paths(["modules/demo/module.json"], POLICY)
    assert "modules" in classified


def test_required_reviews_derived_from_scope():
    reviews = required_reviews({"security", "legal", "commerce"}, POLICY)
    assert {"security", "legal", "commerce", "council"}.issubset(reviews)


def test_minimum_risk_is_critical_for_safety():
    risk = minimum_required_risk({"safety", "runtime"}, {"main.py"}, POLICY)
    assert risk == "critical"


def test_low_risk_cannot_underdeclare_security_change():
    request = base_request()
    request["risk_class"] = "low"
    request["scope_categories"] = ["security"]
    request["reviews"] = {"security": "pending"}
    errors = validate_change_request(request, {"security"}, {"tools/helper.py"}, POLICY)
    assert any("below required minimum high" in e for e in errors)


def test_self_modification_requires_council_and_human_lanes():
    request = base_request()
    request["scope_categories"] = ["security"]
    request["reviews"] = {"security": "pending"}
    errors = validate_change_request(request, {"security"}, {"tools/change_control.py"}, POLICY)
    assert any("council" in e for e in errors)
    assert any("human" in e for e in errors)


def test_authorization_true_requires_approved_status_human_record_and_reviews():
    request = base_request()
    request["scope_categories"] = ["governance"]
    request["reviews"] = {"architecture": "pending", "human": "pending"}
    request["production_authorized"] = True
    errors = validate_change_request(request, {"governance"}, {"governance/example.json"}, POLICY)
    assert any("production_authorized=true requires status=approved" in e for e in errors)
    assert any("production_authorized=true requires a human_approval_record" in e for e in errors)
    assert any("authorization requires architecture review=approved" in e for e in errors)
    assert any("authorization requires human review=approved" in e for e in errors)


def test_valid_high_risk_self_modification_declaration_passes_while_reviews_pending():
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


def test_authorized_self_modification_requires_all_reviews_approved():
    request = base_request()
    categories = {"governance", "security"}
    request["scope_categories"] = sorted(categories)
    request["status"] = "approved"
    request["human_approval_record"] = "approved by authorized human"
    request["production_authorized"] = True
    request["reviews"] = {
        "architecture": "approved",
        "security": "approved",
        "council": "pending",
        "human": "approved",
    }
    errors = validate_change_request(request, categories, {"tools/change_control.py"}, POLICY)
    assert any("authorization requires council review=approved" in e for e in errors)


def test_cumulative_change_requests_can_split_scopes_without_rewriting_history():
    first = base_request("OLD")
    first["scope_categories"] = ["governance", "security"]
    first["reviews"] = {"architecture": "pending", "security": "pending", "council": "pending", "human": "pending"}
    second = base_request("NEW")
    second["scope_categories"] = ["modules"]
    second["reviews"] = {"architecture": "pending", "security": "pending", "council": "pending", "human": "pending"}
    errors = validate_change_request_set(
        [first, second],
        {"governance", "security", "modules"},
        {"tools/change_control.py", "modules/demo/module.json"},
        POLICY,
    )
    assert errors == []
