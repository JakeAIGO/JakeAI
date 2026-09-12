from __future__ import annotations

import os
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .matching import match_contractor
from .models import ContractorCapabilityFingerprint, MatchResult, OpportunityRequirementFingerprint

router = APIRouter(prefix="/v1/opportunity-to-award", tags=["opportunity-to-award"])


class MatchRequest(BaseModel):
    opportunity: OpportunityRequirementFingerprint
    contractors: List[ContractorCapabilityFingerprint]
    cohort_limit: int = 5


def _enabled() -> bool:
    return os.environ.get("OPPORTUNITY_TO_AWARD_ENABLED", "false").strip().lower() == "true"


@router.get("/health")
def health():
    return {
        "module": "opportunity-to-award",
        "enabled": _enabled(),
        "human_approval_required": True,
        "contingent_fee_status": "PENDING_LEGAL_REVIEW",
    }


@router.post("/match", response_model=List[MatchResult])
def match(req: MatchRequest):
    if not _enabled():
        raise HTTPException(
            status_code=503,
            detail="Opportunity-to-Award module is staged but disabled pending explicit activation approval.",
        )
    limit = min(max(req.cohort_limit, 1), 5)
    results = [match_contractor(req.opportunity, c) for c in req.contractors]
    eligible = [r for r in results if r.eligible]
    eligible.sort(key=lambda r: (-r.soft_score, r.contractor_id))
    return eligible[:limit]
