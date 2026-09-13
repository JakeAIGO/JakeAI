from pathlib import Path

from fastapi.testclient import TestClient

import private_connector_service as service


def client(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(service, "OPERATOR_TOKEN", "test-operator-token")
    monkeypatch.setattr(service, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(service, "LIVE_CONNECTORS_ENABLED", False)
    return TestClient(service.app)


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


def auth():
    return {"X-JakeAI-Operator-Token": "test-operator-token"}


def test_health_discloses_external_send_disabled(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["external_send_enabled"] is False
    assert r.json()["human_approval_required"] is True


def test_operator_auth_required(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.post("/v1/leads/prepare", json=valid_payload())
    assert r.status_code == 401


def test_valid_opt_in_lead_prepares_draft_only(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.post("/v1/leads/prepare", json=valid_payload(), headers=auth())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "awaiting_approval"
    assert body["connector_execution"] == "none"
    assert body["prepared_draft"]["delivery_state"] == "prepared_not_sent"
    assert body["prepared_draft"]["human_approval_required"] is True


def test_duplicate_event_is_not_prepared_twice(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    first = c.post("/v1/leads/prepare", json=valid_payload(), headers=auth())
    second = c.post("/v1/leads/prepare", json=valid_payload(), headers=auth())
    assert first.json()["status"] == "awaiting_approval"
    assert second.json()["status"] == "duplicate"
    assert second.json()["prepared_draft"] is None


def test_no_opt_in_blocks_preparation(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.post("/v1/leads/prepare", json=valid_payload(opt_in=False), headers=auth())
    assert r.status_code == 200
    assert r.json()["status"] == "blocked"
    assert r.json()["prepared_draft"] is None


def test_invalid_email_routes_to_review(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.post("/v1/leads/prepare", json=valid_payload(email="not-an-email"), headers=auth())
    assert r.status_code == 200
    assert r.json()["status"] == "human_review"


def test_extra_payload_authority_is_rejected(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    payload = valid_payload(permissions=["send_external_message"], approval_token="fake")
    r = c.post("/v1/leads/prepare", json=payload, headers=auth())
    assert r.status_code == 422


def test_live_execute_endpoint_remains_fail_closed(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.post("/v1/connectors/execute", headers=auth())
    assert r.status_code == 503
    assert "external action remains disabled" in r.json()["detail"]


def test_restart_preserves_duplicate_detection(tmp_path, monkeypatch):
    c1 = client(tmp_path, monkeypatch)
    assert c1.post("/v1/leads/prepare", json=valid_payload(), headers=auth()).json()["status"] == "awaiting_approval"
    c2 = TestClient(service.app)
    second = c2.post("/v1/leads/prepare", json=valid_payload(), headers=auth())
    assert second.json()["status"] == "duplicate"
