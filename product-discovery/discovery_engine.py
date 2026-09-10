"""
JakeAI Autonomous Product Discovery Engine v0.1

Purpose:
Turn observed real-world signals into structured candidates
for JakeAI Autonomous Workflow Skills.

SAFETY MODE:
- No autonomous publishing
- No autonomous spending
- No website modification
- No fabricated evidence
- Human approval required
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import os
import sys


CANDIDATE_THRESHOLD = 70

STATUS_REJECTED = "REJECTED"
STATUS_WATCH = "WATCH"
STATUS_CANDIDATE = "CANDIDATE"


@dataclass
class Opportunity:
    title: str
    problem: str
    industry: str
    target_buyer: str

    evidence: list
    source_urls: list

    existing_alternatives: str
    identified_gap: str
    proposed_skill: str
    workflow_description: str

    required_capabilities: list
    feasibility_notes: str

    estimated_prototype_cost: float
    estimated_operating_cost: float

    pain_urgency: int
    evidence_strength: int
    buyer_clarity: int
    repeatability: int
    workflow_feasibility: int
    competitive_gap: int
    economic_value: int
    jakeai_fit: int

    risks: list
    validation_experiment: str

    def score(self):
        components = {
            "pain_urgency": (self.pain_urgency, 20),
            "evidence_strength": (self.evidence_strength, 15),
            "buyer_clarity": (self.buyer_clarity, 15),
            "repeatability": (self.repeatability, 10),
            "workflow_feasibility": (self.workflow_feasibility, 15),
            "competitive_gap": (self.competitive_gap, 10),
            "economic_value": (self.economic_value, 10),
            "jakeai_fit": (self.jakeai_fit, 5),
        }

        total = 0

        for name, (value, maximum) in components.items():
            if value < 0 or value > maximum:
                raise ValueError(
                    f"{name} must be between 0 and {maximum}. "
                    f"Received {value}."
                )
            total += value

        return total

    def status(self):
        score = self.score()

        if score >= CANDIDATE_THRESHOLD:
            return STATUS_CANDIDATE

        if score >= 50:
            return STATUS_WATCH

        return STATUS_REJECTED

    def validate_evidence(self):
        """
        Evidence-backed candidates require both evidence statements
        and source URLs. This does NOT prove market demand; it only
        verifies that evidence was supplied.
        """
        if not self.evidence:
            return False

        if not self.source_urls:
            return False

        return True

    def to_record(self):
        record = asdict(self)

        record["score"] = self.score()
        record["status"] = self.status()
        record["evidence_supplied"] = self.validate_evidence()

        record["generated_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        record["publication_authorized"] = False
        record["spending_authorized"] = False
        record["human_approval_required"] = True

        return record


def evaluate_opportunity(data):
    """
    Convert structured discovery input into a scored JakeAI candidate.
    """

    opportunity = Opportunity(**data)
    record = opportunity.to_record()

    # Evidence is mandatory for candidate status.
    if not record["evidence_supplied"]:
        record["status"] = STATUS_REJECTED
        record["score_adjustment_reason"] = (
            "Candidate rejected because supporting evidence "
            "and source URLs were not supplied."
        )

    return record


def save_candidate(record, output_directory="product-discovery/candidates"):
    """
    Save the candidate as JSON for later human review.
    """

    os.makedirs(output_directory, exist_ok=True)

    safe_title = "".join(
        character.lower()
        if character.isalnum()
        else "-"
        for character in record["title"]
    )

    safe_title = "-".join(
        part for part in safe_title.split("-") if part
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d-%H%M%S")

    filename = f"{timestamp}-{safe_title}.json"
    filepath = os.path.join(output_directory, filename)

    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(record, file, indent=2)

    return filepath


def print_report(record):
    print()
    print("=" * 72)
    print("JAKEAI AUTONOMOUS PRODUCT DISCOVERY ENGINE")
    print("=" * 72)

    print(f"Opportunity: {record['title']}")
    print(f"Industry: {record['industry']}")
    print(f"Target buyer: {record['target_buyer']}")

    print()
    print(f"SCORE: {record['score']} / 100")
    print(f"STATUS: {record['status']}")

    print()
    print("PROBLEM")
    print(record["problem"])

    print()
    print("PROPOSED AUTONOMOUS WORKFLOW SKILL")
    print(record["proposed_skill"])

    print()
    print("IDENTIFIED GAP")
    print(record["identified_gap"])

    print()
    print("VALIDATION EXPERIMENT")
    print(record["validation_experiment"])

    print()
    print("CONTROL STATUS")
    print("Autonomous publication: DISABLED")
    print("Autonomous spending: DISABLED")
    print("Human approval: REQUIRED")

    print("=" * 72)
    print()


def load_input(filepath):
    with open(filepath, "r", encoding="utf-8") as file:
        return json.load(file)


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python product-discovery/discovery_engine.py "
            "<opportunity.json>"
        )
        sys.exit(1)

    input_file = sys.argv[1]

    try:
        data = load_input(input_file)
        record = evaluate_opportunity(data)
        saved_file = save_candidate(record)

        print_report(record)
        print(f"Candidate record saved to: {saved_file}")

    except Exception as error:
        print(f"Discovery evaluation failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
