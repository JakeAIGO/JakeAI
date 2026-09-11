# JakeAI Baseline Change-Control Engine

Status: CANDIDATE ENGINE — NOT PRODUCTION AUTHORIZATION
Date: 2026-09-11
Canonical comparison anchor: `baseline/master-2026-09-11`

## Purpose
The Baseline Change-Control Engine makes future JakeAI changes prove what they alter before they can be considered for promotion. Repository evidence, not chat memory, carries the rules forward.

## Operating rule
Every working branch must be descended from the canonical baseline anchor, declare its purpose and risk in a machine-readable change request, and pass the same static, regression, truth, security, privacy, and continuity checks before review.

## Pipeline
`MASTER BASELINE -> WORKING BRANCH -> CHANGE DECLARATION -> DIFF CLASSIFICATION -> CHANGE-CONTROL GATE -> FULL BASELINE GATE -> COUNCIL/HUMAN REVIEW WHEN REQUIRED -> NEW BASELINE CANDIDATE -> EXPLICIT PRODUCTION DECISION`

No step in this engine authorizes deployment, publication, checkout activation, spending, or commercial activation.

## What the engine enforces
- A working branch must descend from the designated baseline ref.
- Every non-empty baseline diff requires at least one changed `governance/change_requests/*.json` declaration.
- Changed files are classified into governance, runtime, commerce, security, privacy, legal, safety, brand, dependencies, tests, and documentation scopes.
- High-risk scopes automatically require corresponding review lanes.
- Changes to the change-control engine itself are treated as high-risk self-modification.
- Commercial, publication, and production authorization default to false.
- Any authorization flag may be true only when the change request is explicitly approved and records human approval; the engine does not itself grant that approval.
- `governance/master_manifest.json` must continue to keep production/publication authorization false unless a separately reviewed promotion process deliberately changes that rule.
- The ordinary full baseline audit and regression suite still run after change-control checks.

## Change request contract
Each change request records:
- stable change ID and title;
- exact baseline ref;
- purpose;
- risk class;
- scope categories expected to change;
- required review lanes and their status;
- production/publication/commercial authorization flags;
- human approval record, if any;
- unresolved conditions and evidence notes.

## Self-modification rule
Changing `tools/change_control.py`, `governance/change_control_policy.json`, or `.github/workflows/change-control-gate.yml` is never considered a routine edit. It must be declared at high or critical risk and routed through Council and human review before it can become a later canonical baseline.

## Baseline immutability
`baseline/master-2026-09-11` is a historical anchor. This engine is being developed on a separate working branch. If accepted, it should become part of a new baseline version/anchor rather than silently rewriting the historical anchor.
