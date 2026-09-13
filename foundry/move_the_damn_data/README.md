# Move the Damn Data™ — Autonomous Admin Relay

**Same Work. Less Bullshit.**

Move the Damn Data™ is a JakeAI administrative workflow engine for the repetitive work between business systems. Its job is simple: take authorized information that arrived somewhere, determine where it belongs, move or transform it safely, prepare the next permitted action, and tell a human when something does not add up.

## Resolved product flow

**Lead Relay → Quote Relay → Job Relay → Invoice Relay → Follow-Up Relay**

### Lead Relay
Captures an opt-in inquiry, validates the minimum identity/contact fields, creates or updates the record, and determines the next permitted action.

### Quote Relay
Builds a draft quote from **verified** customer, scope, and pricing inputs. It does not invent measurements, scope, prices, discounts, warranties, or promises.

### Job Relay
Advances approved work through recognized job states and prepares non-destructive synchronization between approved systems.

### Invoice Relay
Reconciles the invoice against the verified quote and flags unverified differences instead of silently accepting them.

### Follow-Up Relay
Prepares the appropriate authorized communication and stops at human approval before any external send in the current release candidate.

## Core contract

`authorized input → validate → identify → permission check → transform → reconcile → approval gate → prepare next action → audit`

## What the current private release candidate proves

- deterministic fail-closed processing
- missing or contradictory required data routes to human review
- duplicate events/case stages do not perform a second action
- explicit action permissions
- scoped, expiring, single-use approval validation
- tenant/connector boundaries in the synthetic sandbox
- audit/provenance identifiers
- adversarial handling of fake authority and prompt-injection-like payload text
- private end-to-end Lead → Quote → Job → Invoice → Follow-Up chain
- controlled Gmail self-send and external-recipient proofs after explicit user approval

## What it does not claim

The repository reference runtime does not contain production CRM, job-management, accounting, or Gmail connectors. It does not have permission to contact customers, spend money, change prices, delete records, publish anything, or deploy itself. The real Gmail proof-of-concept was performed through connected ChatGPT tools after explicit user approval.

Persistent idempotency, persistent approval-consumption state, production tenant isolation, connector-specific secret handling, outage/retry behavior, rollback, and the final legal/claims review remain production gates.

## Private reference implementation

`engine.py` — generic deterministic relay engine  
`approval_gate.py` — scoped/expiring/single-use approval validator  
`fake_connector.py` — synthetic connector boundary  
`workflow_chain.py` — resolved Lead/Quote/Job/Invoice/Follow-Up product chain  
`product_manifest.json` — machine-readable product/release truth  
`release_readiness.md` — explicit remaining production gates

## Test

From `foundry/move_the_damn_data`:

```bash
python -m pytest -q test_engine.py test_adversarial.py test_integration_sandbox.py test_approval_gate.py test_workflow_chain.py
```

The repository implementation remains private, unmerged, and undeployed until an explicit release decision.
