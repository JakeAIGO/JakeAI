from recovery import RecoveryCoordinator


def test_first_attempt_is_permitted():
    c = RecoveryCoordinator()
    d = c.begin(event_id="e1", action="send_external_message")
    assert d.decision == "execute"


def test_confirmed_success_is_never_retried():
    c = RecoveryCoordinator()
    c.begin(event_id="e1", action="send_external_message")
    c.record_attempt(event_id="e1", action="send_external_message", outcome="confirmed_success", external_reference="m1")
    d = c.begin(event_id="e1", action="send_external_message")
    assert d.decision == "complete"


def test_unknown_outcome_is_quarantined_not_retried():
    c = RecoveryCoordinator()
    c.begin(event_id="e1", action="send_external_message")
    c.record_attempt(event_id="e1", action="send_external_message", outcome="unknown")
    d = c.begin(event_id="e1", action="send_external_message")
    assert d.decision == "quarantine"


def test_unknown_can_reconcile_to_success_without_retry():
    c = RecoveryCoordinator()
    c.begin(event_id="e1", action="send_external_message")
    c.record_attempt(event_id="e1", action="send_external_message", outcome="unknown")
    state = c.reconcile_success(event_id="e1", external_reference="m1")
    assert state.outcome == "confirmed_success"
    assert c.begin(event_id="e1", action="send_external_message").decision == "complete"


def test_unknown_can_reconcile_to_failure_then_retry():
    c = RecoveryCoordinator()
    c.begin(event_id="e1", action="send_external_message")
    c.record_attempt(event_id="e1", action="send_external_message", outcome="unknown")
    c.reconcile_failure(event_id="e1")
    assert c.begin(event_id="e1", action="send_external_message").decision == "retry"


def test_retry_budget_exhaustion_quarantines():
    c = RecoveryCoordinator(max_attempts=2)
    c.begin(event_id="e1", action="update_job_state")
    c.record_attempt(event_id="e1", action="update_job_state", outcome="confirmed_failure")
    assert c.begin(event_id="e1", action="update_job_state").decision == "retry"
    c.record_attempt(event_id="e1", action="update_job_state", outcome="confirmed_failure")
    assert c.begin(event_id="e1", action="update_job_state").decision == "quarantine"


def test_event_cannot_change_action():
    c = RecoveryCoordinator()
    c.begin(event_id="e1", action="create_record")
    assert c.begin(event_id="e1", action="delete_record").decision == "blocked"


def test_success_state_is_immutable():
    c = RecoveryCoordinator()
    c.begin(event_id="e1", action="create_record")
    c.record_attempt(event_id="e1", action="create_record", outcome="confirmed_success")
    try:
        c.record_attempt(event_id="e1", action="create_record", outcome="confirmed_failure")
    except ValueError as exc:
        assert "immutable" in str(exc)
    else:
        raise AssertionError("successful state must not be overwritten")


def test_cannot_record_without_begin():
    c = RecoveryCoordinator()
    try:
        c.record_attempt(event_id="e1", action="create_record", outcome="confirmed_failure")
    except ValueError as exc:
        assert "begin" in str(exc)
    else:
        raise AssertionError("record_attempt should fail without begin")


def test_invalid_attempt_budget_is_rejected():
    try:
        RecoveryCoordinator(max_attempts=0)
    except ValueError as exc:
        assert "at least 1" in str(exc)
    else:
        raise AssertionError("invalid retry budget should fail")
