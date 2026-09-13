from pathlib import Path

import pytest

from durable_state import DurableState, DurableStateError


def test_consumed_approval_survives_restart(tmp_path: Path):
    path = tmp_path / "state.json"
    first = DurableState(path)
    assert first.consume_approval("grant-1", "nonce-1") is True
    second = DurableState(path)
    assert second.approval_consumed("grant-1", "nonce-1") is True
    assert second.consume_approval("grant-1", "nonce-1") is False


def test_recovery_quarantine_survives_restart(tmp_path: Path):
    path = tmp_path / "state.json"
    first = DurableState(path)
    first.put_recovery("event-1", {"action": "send_external_message", "outcome": "unknown", "attempt_count": 1})
    second = DurableState(path)
    assert second.recovery("event-1") == {"action": "send_external_message", "outcome": "unknown", "attempt_count": 1}


def test_success_recovery_survives_restart(tmp_path: Path):
    path = tmp_path / "state.json"
    state = DurableState(path)
    state.put_recovery("event-2", {"action": "send_external_message", "outcome": "confirmed_success", "attempt_count": 1, "external_reference": "msg-1"})
    restarted = DurableState(path)
    assert restarted.recovery("event-2")["outcome"] == "confirmed_success"
    assert restarted.recovery("event-2")["external_reference"] == "msg-1"


def test_corrupt_state_fails_closed(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(DurableStateError):
        DurableState(path)


def test_wrong_schema_fails_closed(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text('{"version":999,"consumed_approvals":[],"recoveries":{}}', encoding="utf-8")
    with pytest.raises(DurableStateError):
        DurableState(path)


def test_missing_approval_identity_fails_closed(tmp_path: Path):
    state = DurableState(tmp_path / "state.json")
    with pytest.raises(DurableStateError):
        state.consume_approval("", "nonce")
