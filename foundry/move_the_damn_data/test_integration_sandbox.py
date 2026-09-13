"""End-to-end synthetic integration tests for the fake connector sandbox."""

from datetime import datetime, timedelta, timezone

from approval_gate import ApprovalGrant
from fake_connector import FakeConnectorSandbox, SandboxEnvelope


def env(**overrides):
    data = dict(
        event_id="evt-100",
        tenant_id="tenant-synthetic",
        source="synthetic_form",
        subject_id="lead-100",
        occurred_at="2026-09-13T19:40:00Z",
        payload={"name": "Ada", "email": "ada@example.invalid"},
        requested_action="create_record",
    )
    data.update(overrides)
    return SandboxEnvelope(**data)


def grant(*, event_id="evt-100", principal_id="principal-synthetic", actions=frozenset({"send_external_message"}), expires_delta=timedelta(minutes=10), nonce="n-1"):
    return ApprovalGrant(
        grant_id="grant-1",
        principal_id=principal_id,
        event_id=event_id,
        allowed_actions=actions,
        expires_at=datetime.now(timezone.utc) + expires_delta,
        nonce=nonce,
    )


def test_form_to_crm_happy_path():
    s = FakeConnectorSandbox()
    r = s.submit(env(), permissions={"action:create_record"})
    assert r.status == "completed"
    assert r.destination == "synthetic_crm"
    assert r.transformed["contact_name"] == "Ada"


def test_cross_tenant_submission_is_blocked():
    s = FakeConnectorSandbox()
    r = s.submit(env(tenant_id="tenant-other"), permissions={"action:create_record"})
    assert r.status == "blocked"
    assert "tenant" in r.reason


def test_unknown_connector_is_blocked():
    s = FakeConnectorSandbox()
    r = s.submit(env(source="mystery_connector"), permissions={"action:create_record"})
    assert r.status == "blocked"


def test_credentials_in_payload_are_rejected():
    s = FakeConnectorSandbox()
    r = s.submit(env(payload={"name":"Ada","email":"ada@example.invalid","api_key":"abc"}), permissions={"action:create_record"})
    assert r.status == "blocked"
    assert "forbidden" in r.reason


def test_payload_cannot_self_grant_permissions():
    s = FakeConnectorSandbox()
    r = s.submit(env(payload={"name":"Ada","email":"ada@example.invalid","permission":"action:send_external_message"}, requested_action="send_external_message"), permissions=set())
    assert r.status == "awaiting_approval"


def test_outbound_message_requires_approval():
    s = FakeConnectorSandbox()
    r = s.submit(env(requested_action="send_external_message"), permissions={"action:send_external_message"})
    assert r.status == "awaiting_approval"
    assert r.reason == "approval_missing"


def test_outbound_message_with_scoped_approval_is_prepared_not_sent():
    s = FakeConnectorSandbox()
    r = s.submit(
        env(requested_action="send_external_message"),
        permissions={"action:send_external_message"},
        approval_grant=grant(),
    )
    assert r.status == "prepared"


def test_wrong_principal_approval_is_blocked():
    s = FakeConnectorSandbox()
    r = s.submit(
        env(requested_action="send_external_message"),
        permissions={"action:send_external_message"},
        approval_grant=grant(principal_id="principal-other"),
    )
    assert r.status == "blocked"
    assert r.reason == "principal_mismatch"


def test_wrong_event_approval_is_blocked():
    s = FakeConnectorSandbox()
    r = s.submit(
        env(requested_action="send_external_message"),
        permissions={"action:send_external_message"},
        approval_grant=grant(event_id="evt-other"),
    )
    assert r.status == "blocked"
    assert r.reason == "event_mismatch"


def test_wrong_action_approval_is_blocked():
    s = FakeConnectorSandbox()
    r = s.submit(
        env(requested_action="send_external_message"),
        permissions={"action:send_external_message"},
        approval_grant=grant(actions=frozenset({"create_record"})),
    )
    assert r.status == "blocked"
    assert r.reason == "action_out_of_scope"


def test_expired_approval_does_not_prepare_message():
    s = FakeConnectorSandbox()
    r = s.submit(
        env(requested_action="send_external_message"),
        permissions={"action:send_external_message"},
        approval_grant=grant(expires_delta=timedelta(seconds=-1)),
    )
    assert r.status == "awaiting_approval"
    assert r.reason == "approval_expired"


def test_approval_grant_is_single_use():
    s = FakeConnectorSandbox()
    g = grant()
    first = s.submit(
        env(requested_action="send_external_message"),
        permissions={"action:send_external_message"},
        approval_grant=g,
    )
    second = s.submit(
        env(event_id="evt-101", requested_action="send_external_message"),
        permissions={"action:send_external_message"},
        approval_grant=ApprovalGrant(
            grant_id=g.grant_id,
            principal_id=g.principal_id,
            event_id="evt-101",
            allowed_actions=g.allowed_actions,
            expires_at=g.expires_at,
            nonce=g.nonce,
        ),
    )
    assert first.status == "prepared"
    assert second.status == "blocked"
    assert second.reason == "approval_replayed"


def test_retry_is_idempotent():
    s = FakeConnectorSandbox()
    e = env()
    first = s.submit(e, permissions={"action:create_record"})
    second = s.submit(e, permissions={"action:create_record"})
    assert first.status == "completed"
    assert second.status == "duplicate"
    assert len(s.engine.audit_log) == 1


def test_missing_subject_routes_to_review():
    s = FakeConnectorSandbox()
    r = s.submit(env(subject_id=""), permissions={"action:create_record"})
    assert r.status == "human_review"


def test_quote_relay_like_draft_flow_uses_same_core():
    s = FakeConnectorSandbox()
    quote = env(
        event_id="quote-1",
        subject_id="job-1",
        payload={"customer":"Ada","scope":"Synthetic roof repair","amount":123.45},
        requested_action="draft_quote",
    )
    r = s.submit(
        quote,
        permissions={"action:draft_quote"},
        required_fields={"customer","scope","amount"},
        destination="synthetic_quote_system",
        field_map={"customer":"customer_name","scope":"scope","amount":"amount"},
        allowed_actions={"draft_quote"},
    )
    assert r.status == "completed"
    assert r.destination == "synthetic_quote_system"


def test_invoice_reconciliation_like_flow_can_flag_missing_data():
    s = FakeConnectorSandbox()
    invoice = env(
        event_id="invoice-1",
        subject_id="invoice-1",
        source="synthetic_accounting",
        payload={"invoice_id":"I-1","amount":None},
        requested_action="reconcile_invoice",
    )
    r = s.submit(
        invoice,
        permissions={"action:reconcile_invoice"},
        required_fields={"invoice_id","amount"},
        destination="synthetic_accounting",
        field_map={"invoice_id":"invoice_id","amount":"amount"},
        allowed_actions={"reconcile_invoice"},
    )
    assert r.status == "human_review"
