import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from opportunity_to_award.matching import match_contractor
from opportunity_to_award.models import ContractorCapabilityFingerprint, OpportunityRequirementFingerprint
from opportunity_to_award.router import router


def _orf():
    return OpportunityRequirementFingerprint(
        project_id="MMB-006-27",
        project_state="VA",
        agency_name="Fairfax County Public Schools (FCPS)",
        estimated_value=1_000_000,
        mandatory_prequalification=True,
        mandatory_prebid_meeting=True,
        required_manufacturer="Carlisle",
        facility_type="K-12",
    )


def _ccf(**overrides):
    data = dict(
        contractor_id="c-1",
        company_name="Example Roofing",
        license_states=["VA"],
        license_active=True,
        agency_prequalifications={"Fairfax County Public Schools (FCPS)": "APPROVED"},
        single_project_bonding_limit=2_000_000,
        prebid_rsvp_confirmed=True,
        manufacturer_credentials=["Carlisle"],
        k12_public_track_record=True,
        available_uncommitted_crews=2,
        commercial_terms_status="PENDING_LEGAL_REVIEW",
    )
    data.update(overrides)
    return ContractorCapabilityFingerprint(**data)


def test_hard_gate_fail_closed_on_bonding():
    result = match_contractor(_orf(), _ccf(single_project_bonding_limit=500_000))
    assert result.eligible is False
    assert any(g.gate == "SINGLE_PROJECT_BONDING" and not g.passed for g in result.hard_gates)


def test_fee_terms_do_not_activate_while_pending_legal_review():
    result = match_contractor(_orf(), _ccf())
    assert result.eligible is True
    assert result.soft_score == 85.0
    assert result.legal_fee_gate == "PENDING_LEGAL_REVIEW"
    assert result.human_approval_required is True
    assert result.release_status == "HOLD_FOR_HUMAN_APPROVAL"


def test_active_terms_add_only_the_canonical_15_percent_operational_factor():
    result = match_contractor(_orf(), _ccf(commercial_terms_status="ACTIVE"))
    assert result.soft_score == 100.0
    assert result.legal_fee_gate == "ACTIVE_TERMS_PRESENT"


def test_router_stays_disabled_by_default():
    os.environ.pop("OPPORTUNITY_TO_AWARD_ENABLED", None)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.post(
        "/v1/opportunity-to-award/match",
        json={"opportunity": _orf().model_dump(), "contractors": [_ccf().model_dump()]},
    )
    assert response.status_code == 503
