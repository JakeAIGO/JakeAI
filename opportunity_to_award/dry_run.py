from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from .matching import match_contractor
from .models import ContractorCapabilityFingerprint, MatchResult, OpportunityRequirementFingerprint

FIXTURE_PATH = Path(__file__).with_name("fixtures") / "fcps_phase1_opportunities.json"


def load_phase1_opportunities() -> List[OpportunityRequirementFingerprint]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [OpportunityRequirementFingerprint.model_validate(item) for item in payload["opportunities"]]


def run_dry_match(
    contractors: Iterable[ContractorCapabilityFingerprint],
) -> dict[str, List[MatchResult]]:
    """Run deterministic matches without contact, release, persistence, or invoicing.

    Missing source facts intentionally remain missing. In particular, an unverified
    project value causes the bonding hard gate to fail closed rather than guessing.
    """
    contractor_list = list(contractors)
    return {
        opportunity.project_id: [
            match_contractor(opportunity, contractor) for contractor in contractor_list
        ]
        for opportunity in load_phase1_opportunities()
    }
