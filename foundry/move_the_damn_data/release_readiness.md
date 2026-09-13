# Move the Damn Data™ — Private Release Readiness

This package is a private integration-ready release candidate. This document is not authorization to merge, deploy, publish, connect production systems, spend money, send messages, or expose customer data.

## Completed gates

- Deterministic fail-closed reference engine
- Required-field validation and human-review routing
- Explicit permission checks
- Human approval gates for external messaging and other gated actions
- Idempotent duplicate-event handling
- Audit/provenance identifiers
- Unit tests
- Adversarial tests
- Synthetic connector sandbox
- Integration contract
- End-to-end synthetic integration tests
- Repository guardrail CI includes this package

## Still required before any real-system pilot

1. Select one narrow first use case.
2. Identify the input and output systems.
3. Define the system of record.
4. Resolve a tenant/principal identity for every action.
5. Scope connector permissions to least privilege.
6. Keep connector credentials outside workflow payloads and audit logs.
7. Add persistent idempotency storage appropriate to the deployment environment.
8. Define retry/backoff and dead-letter behavior for connector outages.
9. Define approval-token scope, expiry, revocation, and replay protection.
10. Add conflict handling for ambiguous or duplicate identities.
11. Test with synthetic or non-sensitive records in an isolated pilot where practical.
12. Verify outbound actions remain draft/prepared until the required human approval.
13. Obtain explicit user approval for the specific live pilot.

## Recommended first pilot

**Authorized intake → create/update CRM record → prepare follow-up draft → human approves send.**

This proves real integration, identity, mapping, retry, idempotency, audit, and approval behavior while avoiding autonomous spending, destructive actions, pricing changes, and public publication.

## Non-negotiable stop conditions

Stop and route to review if identity is ambiguous, required data is missing, permissions are absent, tenant boundaries do not match, a connector returns contradictory state, an approval is missing or expired, credentials appear in data payloads, or a requested action is outside the configured allowlist.

## Current release state

**PRIVATE / UNMERGED / UNDEPLOYED / NOT PUBLICLY LISTED / NO REAL CONNECTORS / NO PRODUCTION EXECUTION**
