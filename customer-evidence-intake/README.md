# JakeAI Customer Evidence Intake v1

Status: PRIVATE RELEASE CANDIDATE — NOT PUBLICLY RELEASED

## Purpose
Convert a real outsider's recurring human workaround into a safe, structured Product Factory evidence packet without requesting credentials or production access.

## v1 boundary
Text-only intake. No file uploads, URLs fetched on behalf of submitters, credentials, API keys, access tokens, private keys, financial account credentials, medical records, government identifiers, payment-card data, or other unnecessary sensitive data.

No production-system access or changes. No automatic consequential financial, medical, legal, employment, safety-critical, destructive, or irreversible action.

## Intake fields
- What software or AI is involved?
- What does it normally automate?
- When it fails or needs help, what does a person still have to fix, check, copy, chase, or redo?
- How often does that happen?
- Roughly how many human minutes does one occurrence take?
- What happens if the person does nothing?
- What non-sensitive evidence tells the person what to do?
- Optional contact method for follow-up.

## Pre-processing safety gate
1. Enforce bounded text length and rate limits.
2. Normalize text without executing or rendering submitted markup/code.
3. Scan for likely secrets, credentials, high-risk personal/sensitive data, and prohibited content classes.
4. If suspected secret/credential appears: fail closed, do not send content into downstream Product Factory processing, and instruct submitter to remove it.
5. High-consequence domain or requested autonomous consequential action routes to HUMAN_REVIEW or REJECTED_SCOPE.
6. Do not fetch links or connect to customer systems in v1.

## Evidence packet
Each accepted submission becomes a private structured packet:
- submission_id
- received_at
- software_or_ai
- normal_automation
- residual_human_intervention
- trigger_or_exception
- frequency
- minutes_per_occurrence
- consequence_if_unhandled
- evidence_used_by_human
- estimated_monthly_human_minutes
- dollarized_pain_inputs (only when supplied or explicitly estimated with labeled assumptions)
- safety_class
- recurrence_signature
- product_factory_status

## Product Factory states
RECEIVED -> SAFETY_SCREENED -> EVIDENCE_PACKETED -> PAIN_GATE -> COMPETITOR_GATE -> FREE_ALTERNATIVE_GATE -> SAFETY_LEGAL_GATE -> RESCUE_CANDIDATE

Any gate may terminate in KILLED or HUMAN_REVIEW. Unknown/ambiguous safety state fails closed.

## Graduation rule
One submission is evidence, not a product. A reusable skill may be proposed only after materially equivalent residual work recurs across independent customers and survives the Product Factory gates. Acceptance requires both reduced human intervention and escaped/false-accept errors at or below the frozen baseline/tolerance.

## Data handling principles
Collect the minimum necessary. Separate customer-specific raw text from derived non-sensitive recurrence signatures. Raw prototype evidence is bounded by configurable retention (default 30 days in the local store). Do not silently publish customer material, expose it in marketplace listings, or treat it as permission to train/publicize. Access must be scoped and auditable.

## Private HTTP boundary
The unreleased HTTP boundary now includes strict origin allowlisting, Bearer authentication, JSON-only input, bounded request size, explicit processing consent, explicit no-secrets/sensitive-data acknowledgement, rate limiting, and non-payload audit metadata. Rejected/high-risk input is not persisted through the service boundary.

## Production-adapter hardening completed privately
- Secrets are required from deploy-time environment configuration; no production secret is stored in source.
- Public origins must be explicit HTTPS origins; wildcard and plain HTTP origins fail closed.
- Forwarded client addresses are trusted only when the immediate peer belongs to an explicitly configured trusted-proxy CIDR.
- A durable SQLite-backed rate limiter prototype persists hashed actor identifiers rather than plaintext client IDs.
- A durable audit prototype stores only event type, actor fingerprint, outcome, and timestamp — not request bodies, authorization headers, contact text, or evidence payloads.
- In-memory databases are rejected by the production configuration adapter.
- No network socket, route, deployment, checkout, or public intake is activated by these modules.

## Remaining public-launch blockers
Before any public intake endpoint is enabled, still implement/verify: production-grade encrypted and access-isolated evidence storage; authenticated deletion/data-subject controls; secret rotation/operational key management; production-grade shared rate limiting if horizontally scaled; real reverse-proxy integration tests; abuse/incident handling; privacy notice/consent language and legal/privacy review; monitoring without sensitive payloads; backup/restore and retention guarantees; rollback procedure; deployment configuration review; and a final security review of the concrete hosting adapter.

## Release gate
This specification may be built and tested privately. No merge to main, production deployment, public intake, checkout activation, or public release without explicit human approval for that specific release.
