from pathlib import Path

import private_connector_service as service
from google_workspace_adapter import GoogleWorkspaceAdapter


def configure(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(service, "OPERATOR_TOKEN", "test-operator-token")
    monkeypatch.setattr(service, "STATE_PATH", str(tmp_path / "state.json"))


def row(**overrides):
    data = {
        "event_id": "sheet-001",
        "name": "Ada Example",
        "email": "ada@example.com",
        "request": "Please contact me about a project.",
        "opt_in": True,
    }
    data.update(overrides)
    return data


def test_valid_row_produces_draft_request_only(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    adapter = GoogleWorkspaceAdapter(operator_token="test-operator-token")
    result = adapter.prepare_from_sheet_row(row())
    assert result.status == "draft_ready"
    assert result.draft_request["operation"] == "gmail.create_draft"
    assert result.draft_request["send"] is False
    assert result.draft_request["human_approval_required_before_send"] is True


def test_missing_column_routes_to_review(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    adapter = GoogleWorkspaceAdapter(operator_token="test-operator-token")
    data = row()
    del data["email"]
    result = adapter.prepare_from_sheet_row(data)
    assert result.status == "human_review"


def test_invalid_email_routes_to_review(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    adapter = GoogleWorkspaceAdapter(operator_token="test-operator-token")
    result = adapter.prepare_from_sheet_row(row(email="bad-address"))
    assert result.status == "human_review"


def test_opt_in_must_be_explicit_boolean(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    adapter = GoogleWorkspaceAdapter(operator_token="test-operator-token")
    result = adapter.prepare_from_sheet_row(row(opt_in="yes"))
    assert result.status == "human_review"


def test_no_opt_in_is_blocked(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    adapter = GoogleWorkspaceAdapter(operator_token="test-operator-token")
    result = adapter.prepare_from_sheet_row(row(opt_in=False))
    assert result.status == "blocked"
    assert result.draft_request is None


def test_duplicate_sheet_event_does_not_prepare_second_draft(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    adapter = GoogleWorkspaceAdapter(operator_token="test-operator-token")
    first = adapter.prepare_from_sheet_row(row())
    second = adapter.prepare_from_sheet_row(row())
    assert first.status == "draft_ready"
    assert second.status == "duplicate"
    assert second.draft_request is None


def test_adapter_requires_operator_token():
    try:
        GoogleWorkspaceAdapter(operator_token="")
    except ValueError as exc:
        assert "operator_token" in str(exc)
    else:
        raise AssertionError("missing operator token should fail closed")
