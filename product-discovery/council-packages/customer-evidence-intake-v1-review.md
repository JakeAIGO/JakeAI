# JakeAI Council Review Packet — Customer Evidence Intake v1

Packet status: FROZEN FOR INDEPENDENT COUNCIL REVIEW

## Decision requested
Return exactly one verdict: PASS_WITH_GATES, HOLD, or REJECT. Do not treat this review as legal approval. Identify material risks, missing evidence, mitigations, and questions requiring qualified counsel or operator verification.

## Product
Customer Evidence Intake v1 is a free diagnostic entry point. A user describes one recurring low-risk operational task that existing software or AI still makes a person fix, check, copy, chase, or redo. JakeAI screens the submission, creates a structured evidence packet, estimates human intervention cost when sufficient inputs exist, applies Product Factory gates, and offers a paid bounded Rescue only when the problem survives those gates and an objective completion test can be defined.

## Proposed public experience
Headline: “Show JakeAI the work your software still makes a human do.”

Fields: software/AI involved; what it normally automates; residual human intervention; frequency; minutes per occurrence; consequence if unhandled; non-sensitive evidence used by the human; optional contact method.

Required acknowledgements: user understands automation is not guaranteed; confirms prohibited secrets/sensitive data are not included; consents to processing for evaluation.

## Scope
- Initial launch: United States only.
- Adults/business users only.
- Low-risk business and operational workflows only.
- No consequential financial, medical, legal, employment, safety-critical, destructive, or irreversible automation.
- No production-system credentials or access required.
- Text only; no file uploads and no URL fetching in v1.

## Data controls
- Proposed raw-evidence retention: 30 days, with authenticated deletion available sooner.
- Minimum-necessary collection.
- Raw customer evidence separated from derived recurrence signatures.
- Suspected credentials/secrets fail closed and are not persisted through the intake service boundary.
- Prohibited: passwords, API keys, access tokens, private keys, financial-account credentials, medical records, government identifiers, payment-card data, and unnecessary sensitive information.
- Customer material is not publicized, used as a marketplace example, or reused for public training/marketing without separate explicit permission.

## Production architecture
- Public intake disabled by default.
- Existing Railway production service remains pinned to main and commerce_guard:app.
- Intake activation requires isolated PostgreSQL evidence storage, an external reviewed authenticated-encryption provider/key ID, strong API authentication secret, durable deletion-token authority using HMAC digests with secret pepper stored outside the database, payload-free audit logging, bounded/rate-limited requests, explicit HTTPS origin allowlist, and verified proxy handling.
- Missing storage/encryption/auth/deletion configuration fails closed.
- No production resource has been created or changed by the release-candidate work.

## Product Factory gates
Submission → secret/sensitive-data screen → Evidence Packet → dollarized-pain gate → incumbent-residual check → exact-competitor gate → free-alternative gate → safety/legal/liability gate → Rescue Candidate or KILL.

One submission is evidence, not a reusable product. Reusable-product graduation requires recurrence across independent customers and acceptance based on both reduced human intervention and escaped/false-accept errors staying at or below the frozen baseline/tolerance.

## Commercial model
- Intake/diagnosis is free.
- No checkout at intake.
- A paid Rescue is offered only after a bounded deliverable and objective completion test are defined.
- Current verified outside paying customers: 0.

## Human release gate
No merge to main, production deployment, public endpoint, checkout activation, or public release without explicit human approval for that specific release after review of the final evidence package.

## Engineering evidence
The Customer Evidence Intake release candidate, Railway topology/storage/deletion contracts, fail-closed production composition, attack/rollback rehearsal, and privacy/consent draft have passed their dedicated repository CI and JakeAI PR guardrails on their verified candidate heads. Real-host provisioning, key lifecycle, host-specific rollback, final privacy/legal review, and release approval remain unresolved.

## Council focus
Attack the concept rather than endorse it. Specifically test: whether the offer is materially differentiated; whether free diagnosis can convert without becoming consulting; whether data minimization/retention/deletion controls are credible; whether prohibited-data screening creates false confidence; whether U.S.-only/low-risk scope is sufficiently bounded; whether proposed claims create consumer/privacy/liability risk; whether production architecture has dangerous gaps; whether a simpler/free incumbent solution kills the offer; and what evidence must exist before launch.
