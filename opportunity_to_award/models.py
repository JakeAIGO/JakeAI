from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class OpportunityRequirementFingerprint(BaseModel):
    project_id: str
    project_state: str = Field(min_length=2, max_length=2)
    agency_name: str
    estimated_value: Optional[float] = Field(default=None, gt=0)
    mandatory_prequalification: bool = True
    mandatory_prebid_meeting: bool = False
    required_manufacturer: Optional[str] = None
    facility_type: Optional[str] = None
    construction_window: Optional[str] = None
    source_notes: List[str] = Field(default_factory=list)


class ContractorCapabilityFingerprint(BaseModel):
    contractor_id: str
    company_name: str
    license_states: List[str] = Field(default_factory=list)
    license_active: bool = False
    agency_prequalifications: Dict[str, str] = Field(default_factory=dict)
    single_project_bonding_limit: float = Field(ge=0)
    service_radius_miles: int = Field(ge=0, default=100)
    prebid_rsvp_confirmed: bool = False
    manufacturer_credentials: List[str] = Field(default_factory=list)
    k12_public_track_record: bool = False
    available_uncommitted_crews: int = Field(ge=0, default=0)
    commercial_terms_status: str = "PENDING_LEGAL_REVIEW"


class GateResult(BaseModel):
    gate: str
    passed: bool
    reason: str


class MatchResult(BaseModel):
    contractor_id: str
    company_name: str
    eligible: bool
    hard_gates: List[GateResult]
    soft_score: float = Field(ge=0, le=100)
    legal_fee_gate: str
    human_approval_required: bool = True
    release_status: str = "HOLD_FOR_HUMAN_APPROVAL"
