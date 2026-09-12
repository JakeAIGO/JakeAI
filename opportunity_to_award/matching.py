from __future__ import annotations

from .models import (
    ContractorCapabilityFingerprint,
    GateResult,
    MatchResult,
    OpportunityRequirementFingerprint,
)


def _active_prequal_status(status: str | None) -> bool:
    return (status or "").upper() == "APPROVED"


def match_contractor(
    opportunity: OpportunityRequirementFingerprint,
    contractor: ContractorCapabilityFingerprint,
) -> MatchResult:
    """Deterministic ORF->CCF match using the Phase 1 Council schema."""
    state = opportunity.project_state.upper()
    license_ok = contractor.license_active and state in {s.upper() for s in contractor.license_states}
    prequal_status = contractor.agency_prequalifications.get(opportunity.agency_name)
    prequal_ok = (not opportunity.mandatory_prequalification) or _active_prequal_status(prequal_status)

    if opportunity.estimated_value is None:
        bond_ok = False
        bond_reason = "Estimated project value is unverified; bonding gate cannot be satisfied"
    else:
        bond_ok = contractor.single_project_bonding_limit >= opportunity.estimated_value
        bond_reason = (
            "Bonding capacity covers estimated value"
            if bond_ok
            else "Bonding capacity below estimated value"
        )

    hard_gates = [
        GateResult(
            gate="STATUTORY_LICENSE",
            passed=license_ok,
            reason=("Active license in project state" if license_ok else "No verified active license in project state"),
        ),
        GateResult(
            gate="AGENCY_PREQUALIFICATION",
            passed=prequal_ok,
            reason=("Agency prequalification satisfied" if prequal_ok else "Required agency prequalification not approved"),
        ),
        GateResult(
            gate="SINGLE_PROJECT_BONDING",
            passed=bond_ok,
            reason=bond_reason,
        ),
    ]

    eligible = all(g.passed for g in hard_gates)
    score = 0.0

    if opportunity.mandatory_prebid_meeting:
        if contractor.prebid_rsvp_confirmed:
            score += 25.0
    else:
        score += 25.0

    if opportunity.required_manufacturer:
        credentials = {c.casefold() for c in contractor.manufacturer_credentials}
        if opportunity.required_manufacturer.casefold() in credentials:
            score += 25.0
    else:
        score += 25.0

    if contractor.k12_public_track_record:
        score += 20.0
    if contractor.available_uncommitted_crews > 0:
        score += 15.0

    terms = contractor.commercial_terms_status.upper()
    if terms == "ACTIVE":
        score += 15.0
        legal_fee_gate = "ACTIVE_TERMS_PRESENT"
    else:
        legal_fee_gate = "PENDING_LEGAL_REVIEW"

    return MatchResult(
        contractor_id=contractor.contractor_id,
        company_name=contractor.company_name,
        eligible=eligible,
        hard_gates=hard_gates,
        soft_score=score,
        legal_fee_gate=legal_fee_gate,
        human_approval_required=True,
        release_status="HOLD_FOR_HUMAN_APPROVAL",
    )
