# Move the Damn Data™ — Private Release Readiness

This package is a private integration-ready release candidate. This document is not authorization to merge, deploy, publish, connect production systems, spend money, send messages, or expose customer data.

## Product shape now resolved

The product is a reusable autonomous administrative relay with a deterministic business chain:

**Lead Relay → Quote Relay → Job Relay → Invoice Relay → Follow-Up Relay**

The chain is side-effect free in the repository reference implementation. It validates inputs, fails closed on missing or unverified data, preserves idempotency per case stage, records audit provenance, prepares work products, and stops at human approval before external communication.

## Completed gates

- Deterministic fail-closed reference engine
- Required-field validation and human-review routing
- Explicit permission checks
- Scoped, expiring, single-use approval validation
- Human approval gates for external messaging and other gated actions
- Idempotent duplicate-event handling in the reference runtime
- Audit/provenance identifiers
- Unit tests
- Adversarial tests
- Synthetic connector sandbox
- Integration contract
- End-to-end synthetic integration tests
- End-to-end Lead → Quote → Job → Invoice → Follow-Up reference chain
- Quote generation from verified scope and price only
- Job-state validation with approved-quote dependency
- Invoice reconciliation with discrepancy review
- Follow-up preparation that remains `prepared_not_sent`
- Repository guardrail CI includes this package
- Controlled Gmail send-to-self proof with explicit human approval
- Controlled external-recipient Gmail proof with explicit human approval

## Product behavior

### Lead Relay
Requires an opt-in lead plus name, email, and request. Invalid or incomplete contact data routes to human review. No opt-in blocks the workflow.

### Quote Relay
Requires verified customer identity, scope, and price. It does not infer or invent measurements, scope, price, discounts, warranties, or promises. Output is a draft only.

### Job Relay
Requires an approved quote and a recognized job state. Unknown states or missing approved scope route to review.

### Invoice Relay
Compares verified quote and invoice totals. Any unverified difference routes to review rather than being silently accepted.

### Follow-Up Relay
Requires an authorized communication purpose and valid recipient. The repository runtime only prepares the message and stops at `awaiting_approval`; it does not send.

## Still required before production deployment

1. Select the first production connector pair and system of record.
2. Resolve a tenant/principal identity for every action.
3. Scope connector permissions to least privilege.
4. Keep connector credentials in an approved secret store and outside workflow payloads and audit logs.
5. Replace in-memory idempotency with persistent storage and add restart/replay tests.
6. Persist approval-consumption state and support revocation where appropriate.
7. Define retry/backoff, dead-letter, and partial-failure behavior for connector outages.
8. Add conflict handling for ambiguous or duplicate identities across real systems.
9. Complete production tenant-isolation testing.
10. Complete connector-specific security review, audit-log redaction review, and rollback/disconnect plan.
11. Complete claims/legal review for the exact public listing.
12. Obtain explicit user approval for the specific merge/deployment/public release.

## Recommended first production-shaped pilot

**Authorized intake → create/update CRM/job record → prepare follow-up → human approves send → audit result.**

This proves the reusable engine against a real business system without granting autonomous spending, destructive actions, pricing changes, or public publication.

## Verified communication boundary

The connected JakeAI Gmail account has completed both a self-addressed send test and a controlled external-recipient send test after explicit user approval. These tests prove that an approved external communications boundary is technically reachable through connected tools. They do **not** mean the repository runtime contains an autonomous Gmail connector, and they do **not** authorize future sends.

## Non-negotiable stop conditions

Stop and route to review if identity is ambiguous, required data is missing, pricing or scope is unverified, permissions are absent, tenant boundaries do not match, a connector returns contradictory state, an approval is missing/expired/replayed, credentials appear in data payloads, an invoice discrepancy is unverified, or a requested action is outside the configured allowlist.

## Current release state

**PRIVATE / UNMERGED / UNDEPLOYED / NOT PUBLICLY LISTED / PRODUCTION CONNECTORS NOT EMBEDDED / NO PRODUCTION EXECUTION**
