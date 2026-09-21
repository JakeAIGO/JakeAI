import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

import insurance_growth_desk as desk


def _client(tmp_path, monkeypatch):
    db = tmp_path / "insurance-pilot.db"
    monkeypatch.setattr(desk, "_db_path", lambda: str(db))
    monkeypatch.setenv("INSURANCE_PILOT_ACCESS_CODE", "test-only-code")
    monkeypatch.setenv("INSURANCE_BRAND_VERIFIED", "false")
    app = FastAPI()
    desk.register_insurance_growth_routes(app)
    client = TestClient(app, base_url="https://testserver")
    login = client.post("/v1/insurance/login", json={"access_code": "test-only-code"})
    assert login.status_code == 200
    return client


def test_insurance_guardrails_are_explicit(monkeypatch):
    monkeypatch.setenv("INSURANCE_BRAND_VERIFIED", "false")
    text = desk._insurance_instructions("iul_annuity_leads")
    assert "explicit human approval" in text
    assert "Do not provide individualized insurance" in text
    assert "Do not make annuity suitability or best-interest conclusions" in text
    assert "NOT verified" in text
    assert "sensitive traits" in text


def test_contact_approval_requires_verified_opt_in(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    created = client.post(
        "/v1/insurance/leads",
        json={
            "name": "Pilot Lead",
            "product_interest": "iul",
            "source": "manual pilot entry",
            "consent_status": "consent_pending",
        },
    )
    assert created.status_code == 200
    lead_id = created.json()["lead_id"]
    blocked = client.post(f"/v1/insurance/leads/{lead_id}/status", json={"status": "contact_approved"})
    assert blocked.status_code == 409


def test_verified_opt_in_can_reach_contact_approved(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    created = client.post(
        "/v1/insurance/leads",
        json={
            "email": "pilot@example.com",
            "product_interest": "annuity",
            "source": "permission-based test",
            "consent_status": "opt_in_verified",
            "consent_evidence": "Test form opt-in recorded 2026-09-21T14:00:00Z",
        },
    )
    assert created.status_code == 200
    lead_id = created.json()["lead_id"]
    approved = client.post(f"/v1/insurance/leads/{lead_id}/status", json={"status": "contact_approved"})
    assert approved.status_code == 200
