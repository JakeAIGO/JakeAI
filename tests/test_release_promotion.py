import json
from pathlib import Path

from tools.release_promotion import validate_request

POLICY = json.loads(Path("governance/release_promotion_policy.json").read_text())
FINGERPRINT = {"candidate_manifest_sha256": "abc123", "builder_head": "deadbeef"}


def request():
    return {
        "schema_version": "1.0",
        "status": "not_requested",
        "candidate_manifest_sha256": "",
        "candidate_builder_head": "",
        "target": "production",
        "reviews": {lane: "pending" for lane in POLICY["required_approval_states"]},
        "human_approval_record": "",
        "promotion_authorized": False,
        "deployment_authorized": False,
        "publication_authorized": False,
        "commercial_activation_authorized": False,
    }


def test_default_request_is_fail_closed():
    r = request()
    assert validate_request(POLICY, r, FINGERPRINT) == []
    assert r["promotion_authorized"] is False
    assert r["deployment_authorized"] is False


def test_authorization_requires_approved_status():
    r = request(); r["promotion_authorized"] = True
    errors = validate_request(POLICY, r, FINGERPRINT)
    assert any("status=approved" in e for e in errors)


def test_authorization_requires_exact_fingerprint_and_head():
    r = request(); r.update({"status": "approved", "promotion_authorized": True, "human_approval_record": "approved"})
    r["reviews"] = {lane: "approved" for lane in POLICY["required_approval_states"]}
    errors = validate_request(POLICY, r, FINGERPRINT)
    assert any("fingerprint match" in e for e in errors)
    assert any("builder head match" in e for e in errors)


def test_authorization_requires_all_review_lanes_and_human_record():
    r = request(); r.update({
        "status": "approved",
        "candidate_manifest_sha256": "abc123",
        "candidate_builder_head": "deadbeef",
        "promotion_authorized": True,
    })
    errors = validate_request(POLICY, r, FINGERPRINT)
    assert any("human_approval_record" in e for e in errors)
    assert any("architecture review=approved" in e for e in errors)
    assert any("human review=approved" in e for e in errors)


def test_fully_matching_approved_request_validates():
    r = request(); r.update({
        "status": "approved",
        "candidate_manifest_sha256": "abc123",
        "candidate_builder_head": "deadbeef",
        "human_approval_record": "explicit authorized human approval",
        "promotion_authorized": True,
    })
    r["reviews"] = {lane: "approved" for lane in POLICY["required_approval_states"]}
    assert validate_request(POLICY, r, FINGERPRINT) == []


def test_bad_target_is_rejected():
    r = request(); r["target"] = "somewhere-else"
    assert any("target" in e for e in validate_request(POLICY, r, FINGERPRINT))
