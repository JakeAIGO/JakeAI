from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import private_connector_service as service


def configure(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(service, "OPERATOR_TOKEN", "test-operator-token")
    monkeypatch.setattr(service, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(service, "LIVE_CONNECTORS_ENABLED", False)


def valid_payload(**overrides):
    data = {
        "event_id": "lead-001",
        "name": "Ada Example",
        "email": "ada@example.com",
        "request": "Please contact me about a project.",
        "opt_in": True,
    }
    data.update(overrides)
    return data


def make_intake(**overrides):
    return service.LeadIntake(**valid_payload(**overrides))


def test_health_discloses_external_send_disabled(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    body = service.health()
    assert body["external_send_enabled"] is False
    assert body["human_approval_required"] is True


def test_operator_auth_required(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as exc:
        service.prepare_lead(make_intake(), x_jakeai_operator_token=None)
    assert exc.value.status_code == 401


def test_valid_opt_in_lead_prepares_draft_only(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    body = service.prepare_lead(make_intake(), x_jakeai_operator_token="test-operator-token")
    assert body.status == "awaiting_approval"
    assert body.connector_execution == "none"
    assert body.prepared_draft["delivery_state"] == "prepared_not_sent"
    assert body.prepared_draft["human_approval_required"] is True


def test_duplicate_event_is_not_prepared_twice(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    first = service.prepare_lead(make_intake(), x_jakeai_operator_token="test-operator-token")
    second = service.prepare_lead(make_intake(), x_jakeai_operator_token="test-operator-token")
    assert first.status == "awaiting_approval"
    assert second.status == "duplicate"
    assert second.prepared_draft is None


def test_no_opt_in_blocks_preparation(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    body = service.prepare_lead(make_intake(opt_in=False), x_jakeai_operator_token="test-operator-token")
    assert body.status == "blocked"
    assert body.prepared_draft is None


def test_invalid_email_routes_to_review(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    body = service.prepare_lead(make_intake(email="not-an-email"), x_jakeai_operator_token="test-operator-token")
    assert body.status == "human_review"
    assert body.prepared_draft is None


def test_extra_payload_authority_is_rejected():
    payload = valid_payload(permissions=["send_external_message"], approval_token="fake")
    with pytest.raises(ValidationError):
        service.LeadIntake(**payload)


def test_live_execute_endpoint_remains_fail_closed(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as exc:
        service.execute_connector(x_jakeai_operator_token="test-operator-token")
    assert exc.value.status_code == 503
    assert "external action remains disabled" in exc.value.detail


def test_restart_preserves_duplicate_detection(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    first = service.prepare_lead(make_intake(), x_jakeai_operator_token="test-operator-token")
    assert first.status == "awaiting_approval"
    second = service.prepare_lead(make_intake(), x_jakeai_operator_token="test-operator-token")
    assert second.status == "duplicate"
