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
Collect the minimum necessary. Separate customer-specific raw text from derived non-sensitive recurrence signatures. Define and enforce retention/deletion before public launch. Do not silently publish customer material, expose it in marketplace listings, or treat it as permission to train/publicize. Access must be scoped and auditable.

## Public-launch blockers
Before any public intake endpoint is enabled, implement and test: authentication/abuse controls as appropriate; CSRF/origin controls where relevant; strict request/content validation; size/rate limits; secret/sensitive-data detection; logging redaction; encrypted transport/storage as applicable; tenant/access isolation; retention/deletion; incident/abuse handling; privacy notice/consent language; deterministic failure behavior; monitoring without recording sensitive payloads; and legal/privacy review.

## Release gate
This specification may be built and tested privately. No merge to main, production deployment, public intake, checkout activation, or public release without explicit human approval for that specific release.