from datetime import datetime, timedelta, timezone
from pathlib import Path

from approval_gate import ApprovalGate, ApprovalGrant
from durable_state import DurableState
from recovery import RecoveryCoordinator


def grant(event_id: str = "evt-1") -> ApprovalGrant:
    return ApprovalGrant(
        grant_id="grant-1",
        principal_id="principal-1",
        event_id=event_id,
        allowed_actions=frozenset({"send_external_message"}),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        nonce="nonce-1",
    )


def test_consumed_approval_is_rejected_after_restart(tmp_path: Path):
    path = tmp_path / "state.json"
    first_gate = ApprovalGate(durable_state=DurableState(path))
    first = first_gate.validate(
        grant=grant(),
        principal_id="principal-1",
        event_id="evt-1",
        action="send_external_message",
    )
    assert first.allowed is True

    restarted_gate = ApprovalGate(durable_state=DurableState(path))
    replay = restarted_gate.validate(
        grant=grant(),
        principal_id="principal-1",
        event_id="evt-1",
        action="send_external_message",
    )
    assert replay.allowed is False
    assert replay.reason == "approval_replayed"


def test_unknown_delivery_remains_quarantined_after_restart(tmp_path: Path):
    path = tmp_path / "state.json"
    first = RecoveryCoordinator(durable_state=DurableState(path))
    assert first.begin(event_id="evt-2", action="send_external_message").decision == "execute"
    first.record_attempt(event_id="evt-2", action="send_external_message", outcome="unknown")

    restarted = RecoveryCoordinator(durable_state=DurableState(path))
    decision = restarted.begin(event_id="evt-2", action="send_external_message")
    assert decision.decision == "quarantine"


def test_confirmed_success_remains_complete_after_restart(tmp_path: Path):
    path = tmp_path / "state.json"
    first = RecoveryCoordinator(durable_state=DurableState(path))
    first.begin(event_id="evt-3", action="send_external_message")
    first.record_attempt(
        event_id="evt-3",
        action="send_external_message",
        outcome="confirmed_success",
        external_reference="msg-123",
    )

    restarted = RecoveryCoordinator(durable_state=DurableState(path))
    decision = restarted.begin(event_id="evt-3", action="send_external_message")
    assert decision.decision == "complete"
    assert restarted.state("evt-3").external_reference == "msg-123"


def test_confirmed_failure_can_retry_after_restart(tmp_path: Path):
    path = tmp_path / "state.json"
    first = RecoveryCoordinator(durable_state=DurableState(path), max_attempts=3)
    first.begin(event_id="evt-4", action="send_external_message")
    first.record_attempt(event_id="evt-4", action="send_external_message", outcome="confirmed_failure")

    restarted = RecoveryCoordinator(durable_state=DurableState(path), max_attempts=3)
    assert restarted.begin(event_id="evt-4", action="send_external_message").decision == "retry"


def test_reconciled_success_survives_restart(tmp_path: Path):
    path = tmp_path / "state.json"
    first = RecoveryCoordinator(durable_state=DurableState(path))
    first.begin(event_id="evt-5", action="send_external_message")
    first.record_attempt(event_id="evt-5", action="send_external_message", outcome="unknown")
    first.reconcile_success(event_id="evt-5", external_reference="msg-456")

    restarted = RecoveryCoordinator(durable_state=DurableState(path))
    assert restarted.begin(event_id="evt-5", action="send_external_message").decision == "complete"
