# Biotech & Life Sciences Risk Router

## Purpose
This document defines how the Jake AI Autonomous Product Factory evaluates biotech and life-sciences opportunities before build, publication, or activation.

The goal is to pursue commercially useful workflow automation while preventing the platform from becoming an autonomous biological decision-maker or wet-lab experimentation system.

## Core rule
Jake AI may automate efficiency, coordination, documentation, evidence handling, provenance, compliance support, scheduling, inventory, QA, and human-approval routing.

Jake AI must not autonomously decide what biological modification to make, design or optimize biological experiments intended to create a biological effect, execute wet-lab procedures, bypass required biosafety or institutional review, or substitute for qualified scientific/regulatory judgment.

## Risk routing

### GREEN — Normal
Examples: benign creative, educational, documentation, citation management, non-sensitive project organization.

Controls:
- standard QA
- basic legal/IP review
- normal publication authorization

### YELLOW — Consequential
Examples: research data handling, inventory workflows, laboratory scheduling, operational coordination, non-clinical analytics support.

Controls:
- enhanced QA
- permissions and audit logging
- human confirmation for consequential actions
- targeted legal/privacy review

### RED — High consequence
Examples: workflows touching gene editing, gene therapy, synthetic biology, biosafety, regulated biomanufacturing, clinical development, or safety-critical laboratory operations.

Controls:
- Council review before build authorization
- What-If / Consequence Simulation
- misuse and dual-use assessment
- regulatory applicability review
- human-in-the-loop approval gates
- fail-closed behavior
- strict audit/provenance requirements
- no autonomous wet-lab execution

### BLACK — Unacceptable
Any product whose foreseeable biological, environmental, clinical, legal, or public-safety risk cannot be reduced to an acceptable level with practical safeguards.

Action: do not build, publish, sell, or activate.

## What-If / Consequence Simulation Gate
For YELLOW and RED products, evaluate:
1. intended outcome
2. likely second- and third-order effects
3. user error
4. automation/model error
5. bad, incomplete, stale, or adversarial data
6. misuse and foreseeable dual use
7. interactions with other tools and downstream systems
8. impact at scale
9. regulatory and contractual consequences
10. worst credible outcome
11. detectability of failure
12. reversibility / rollback
13. uncertainty and unknowns
14. capability amplification — what later actions this workflow makes materially easier

Scoring dimensions:
- probability
- severity
- detectability
- reversibility
- uncertainty
- scale
- capability amplification

Unknowns are risk. Low probability does not automatically permit a product when potential severity is extreme.

## Council decision states
- GREENLIGHT: proceed to normal build/QA
- REDESIGN: safeguards required before re-review
- HOLD: insufficient evidence or unresolved regulatory/safety question
- REJECT: unacceptable residual risk

## Initial commercially promising, lower-biological-risk opportunity classes
- scientific literature and evidence monitoring
- regulatory intelligence and change tracking
- laboratory documentation and record completeness
- audit-readiness and QA evidence collection
- data provenance and metadata completeness
- research project orchestration
- reagent/inventory/lot/expiry tracking
- human approval and escalation routing
- approved computational-job orchestration with logging and reproducibility checks
- interoperability monitoring across laboratory software/data systems

## Explicit exclusions for autonomous operation
- selecting genetic targets or edits
- designing or optimizing gene-editing constructs for real-world use
- choosing experimental biological conditions intended to achieve a biological effect
- autonomous experimental execution in wet labs
- bypassing IBC, biosafety, clinical, regulatory, or institutional approvals
- autonomous release of modified organisms or biological agents
- claims that Jake AI provides legal, medical, regulatory, or biosafety approval

## Product Factory integration target
Risk routing should occur after Product Discovery and before Build Authorization. A RED classification inserts the Council + Consequence Simulation Gate before construction. Publication remains a separate permission gate.

Recommended stage flow:
Signal Discovery -> Evidence Enrichment -> Opportunity Scoring -> Product Discovery -> Risk Classification -> [Council/What-If if required] -> Independent Validation -> Build Authorization -> Construction -> Technical QA -> Security Review -> Legal/Liability Review -> Pricing/Packaging -> Publication Authorization -> Deployment -> Monitoring/Rollback

## Current biotech thesis
The strongest near-term Jake AI opportunities are not autonomous biology. They are workflow infrastructure around modern biotech: provenance, interoperability, documentation, compliance support, data quality, reproducibility, scheduling, inventory, regulatory intelligence, and human oversight.
