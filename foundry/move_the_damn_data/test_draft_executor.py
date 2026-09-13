from draft_executor import DraftOnlyExecutor


class FakeDraftProvider:
    def __init__(self):
        self.calls = []

    def create_draft(self, *, to, subject, body, idempotency_key):
        self.calls.append((to, subject, body, idempotency_key))
        return "draft-ref-1"


def request(**overrides):
    value = {
        "operation": "gmail.create_draft",
        "to": "ada@example.com",
        "subject": "Hello",
        "body": "Prepared, not sent.",
        "send": False,
        "human_approval_required_before_send": True,
    }
    value.update(overrides)
    return value


def test_creates_draft_only():
    provider = FakeDraftProvider()
    result = DraftOnlyExecutor(provider).execute(event_id="e1", request=request())
    assert result.status == "draft_created"
    assert result.provider_reference == "draft-ref-1"
    assert provider.calls == [("ada@example.com", "Hello", "Prepared, not sent.", "e1")]


def test_duplicate_does_not_call_provider_twice():
    provider = FakeDraftProvider()
    executor = DraftOnlyExecutor(provider)
    assert executor.execute(event_id="e1", request=request()).status == "draft_created"
    duplicate = executor.execute(event_id="e1", request=request())
    assert duplicate.status == "duplicate"
    assert len(provider.calls) == 1


def test_send_true_is_blocked():
    provider = FakeDraftProvider()
    result = DraftOnlyExecutor(provider).execute(event_id="e1", request=request(send=True))
    assert result.status == "blocked"
    assert provider.calls == []


def test_wrong_operation_is_blocked():
    provider = FakeDraftProvider()
    result = DraftOnlyExecutor(provider).execute(event_id="e1", request=request(operation="gmail.send"))
    assert result.status == "blocked"
    assert provider.calls == []


def test_missing_human_approval_invariant_is_blocked():
    provider = FakeDraftProvider()
    result = DraftOnlyExecutor(provider).execute(
        event_id="e1", request=request(human_approval_required_before_send=False)
    )
    assert result.status == "blocked"
    assert provider.calls == []


def test_missing_fields_route_to_review():
    provider = FakeDraftProvider()
    result = DraftOnlyExecutor(provider).execute(event_id="e1", request=request(body=""))
    assert result.status == "human_review"
    assert provider.calls == []


def test_provider_without_reference_quarantines():
    class BadProvider:
        def create_draft(self, **kwargs):
            return ""

    result = DraftOnlyExecutor(BadProvider()).execute(event_id="e1", request=request())
    assert result.status == "quarantine"
