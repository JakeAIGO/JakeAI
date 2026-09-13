# JakeAI Dependency Rescue — Autonomous Edition

Status: PRIVATE BUILD / NOT PUBLIC / HUMAN RELEASE APPROVAL REQUIRED
Proposed launch price: $9.99 per autonomous rescue run

## Product outcome
A buyer pays for an outcome, not access to JakeAI staff. After entitlement is confirmed, the buyer submits a supported redacted text/config/code artifact to a controlled intake. The system safety-checks it, scans supported dependency rule packs, produces evidence-backed findings, generates a customer Rescue Report plus machine-readable findings, and makes the result available to the entitled buyer. Normal successful runs require no manual fulfillment.

## Autonomous state machine
1. PURCHASED — payment/entitlement confirmed.
2. INTAKE — accept only supported text/config/code within strict size/count limits.
3. SAFETY_CHECK — reject archives, binaries, symlinks, unsupported encodings/types and potential secrets before dependency analysis.
4. SCAN — run offline Dependency Rescue rule packs. No customer code execution and no credentials.
5. EVIDENCE — attach maintained vendor source, source-check date, vendor date/timing context and confidence classification.
6. REPORT — render customer Markdown report and machine-readable JSON findings.
7. DELIVERED — make outputs available only to the entitled run/customer.
8. EXCEPTION — ambiguous/safety/evidence failures stop rather than guessing and may require human review.
9. RETENTION — delete submitted artifact according to the published retention rule; preserve only minimum non-sensitive operational/audit metadata.

## Customer-visible statuses
- SAFETY_BLOCKED: possible secret or prohibited artifact; no dependency analysis.
- RESCUE_COMPLETE: supported findings produced.
- REVIEW_REQUIRED: one or more candidate findings require verification.
- NO_SUPPORTED_MATCH: no supported signatures found; explicitly not proof of dependency safety.
- SYSTEM_HOLD: evidence/rule/service integrity could not be established; do not produce a confident result.

## Human versus autonomous boundary
Normal path is autonomous. Human review is an exception/safety gate, not fulfillment. Humans may verify or suspend vendor rules, resolve ambiguous findings, investigate system failures, and approve releases. Humans do not need to receive the customer's artifact by email or manually create ordinary reports.

## Security/privacy boundary
- Never request passwords, API keys, private keys, tokens or production credentials.
- Fail closed before scanning when potential secrets are detected.
- Never execute submitted code.
- Never automatically modify production systems, revoke credentials or perform migrations.
- Public intake must not launch until access control, entitlement binding, upload isolation, MIME/content validation, size/rate limits, logging redaction, retention/deletion, abuse handling and failure behavior are implemented and tested.
- Do not expose proprietary rule regexes or internal orchestration in customer reports or machine-facing responses.

## Agent-facing future interface
An authorized agent may invoke the same controlled capability after entitlement. Input is a permitted redacted artifact representation plus metadata. Output is structured status/findings/evidence/remediation/verification. Agent access is scoped and revocable and receives no proprietary source, credentials or unrestricted system access.

## Launch experiment
Price: $9.99 for one autonomous rescue run. Primary metric: first independent stranger payment followed by a successfully delivered autonomous result. Friendly/self/test transactions do not count as market validation.

## Release gate
Do not merge, deploy, publish, activate checkout or enable public upload without explicit human approval for that release. Before requesting approval, demonstrate an end-to-end test of entitlement -> safe intake -> secret rejection -> scan -> report/JSON generation -> access-controlled delivery -> deletion/retention behavior, and complete legal/liability/claims review.