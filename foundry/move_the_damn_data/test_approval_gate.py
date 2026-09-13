from datetime import datetime, timedelta, timezone

from approval_gate import ApprovalGate, ApprovalGrant

NOW = datetime(2026, 9, 13, 20, 0, tzinfo=timezone.utc)


def grant(**overrides):
    data = {
        "grant_id": "grant-001",
        "principal_id": "principal-jakeai",
        "event_id": "pilot-001",
        "allowed_actions": frozenset({"send_external_message"}),
        "expires_at": NOW + timedelta(minutes=10),
        "nonce": "nonce-001",
    }
    data.update(overrides)
    return ApprovalGrant(**data)


def test_valid_approval_allows_preparation_only():
    gate = ApprovalGate()
    decision = gate.validate(
        grant=grant(),
        principal_id="principal-jakeai",
        event_id="pilot-001",
        action="send_external_message",
        now=NOW,
    )
    assert decision.allowed is True
    assert decision.reason == "approved_for_preparation"


def test_missing_approval_blocks():
    gate = ApprovalGate()
    decision = gate.validate(
        grant=None,
        principal_id="principal-jakeai",
        event_id="pilot-001",
        action="send_external_message",
        now=NOW,
    )
    assert decision.allowed is False
    assert decision.reason == "approval_missing"


def test_expired_approval_blocks():
    gate = ApprovalGate()
    decision = gate.validate(
        grant=grant(expires_at=NOW - timedelta(seconds=1)),
        principal_id="principal-jakeai",
        event_id="pilot-001",
        action="send_external_message",
        now=NOW,
    )
    assert decision.allowed is False
    assert decision.reason == "approval_expired"


def test_wrong_principal_blocks():
    gate = ApprovalGate()
    decision = gate.validate(
        grant=grant(),
        principal_id="other-principal",
        event_id="pilot-001",
        action="send_external_message",
        now=NOW,
    )
    assert decision.allowed is False
    assert decision.reason == "principal_mismatch"


def test_wrong_event_blocks():
    gate = ApprovalGate()
    decision = gate.validate(
        grant=grant(),
        principal_id="principal-jakeai",
        event_id="pilot-999",
        action="send_external_message",
        now=NOW,
    )
    assert decision.allowed is False
    assert decision.reason == "event_mismatch"


def test_out_of_scope_action_blocks():
    gate = ApprovalGate()
    decision = gate.validate(
        grant=grant(),
        principal_id="principal-jakeai",
        event_id="pilot-001",
        action="publish_publicly",
        now=NOW,
    )
    assert decision.allowed is False
    assert decision.reason == "action_out_of_scope"


def test_approval_is_single_use():
    gate = ApprovalGate()
    g = grant()
    first = gate.validate(
        grant=g,
        principal_id="principal-jakeai",
        event_id="pilot-001",
        action="send_external_message",
        now=NOW,
    )
    second = gate.validate(
        grant=g,
        principal_id="principal-jakeai",
        event_id="pilot-001",
        action="send_external_message",
        now=NOW,
    )
    assert first.allowed is True
    assert second.allowed is False
    assert second.reason == "approval_replayed"


def test_naive_expiration_timestamp_fails_closed():
    gate = ApprovalGate()
    decision = gate.validate(
        grant=grant(expires_at=datetime(2026, 9, 13, 20, 10)),
        principal_id="principal-jakeai",
        event_id="pilot-001",
        action="send_external_message",
        now=NOW,
    )
    assert decision.allowed is False
    assert decision.reason == "approval_malformed"
