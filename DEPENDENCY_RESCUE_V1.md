# JakeAI Dependency Rescue v1 — Build Candidate

Status: **NOT PUBLIC / NOT FOR SALE / HUMAN APPROVAL REQUIRED**

## Promise
Analyze customer-supplied, redacted text configuration/code artifacts for supported vendor-deprecation signatures and return evidence-linked remediation and verification guidance.

## Supported v1 rule packs
- Cloudflare legacy Service Key authentication
- Coralogix legacy ingestion patterns
- Google Ads API v22
- Qlik webhook/CloudEvent migration candidates
- Microsoft Exchange Web Services candidates

## Safety boundaries
- Offline text analysis only.
- No credentials or production access required.
- Potential secrets fail closed before dependency analysis.
- No automatic edits, deployment, revocation, migration, ad changes, or infrastructure actions.
- A no-match result is never represented as proof that an artifact is safe.
- Findings require human verification against current authoritative vendor documentation before customer action.
- EWS findings require classification because on-premises and Exchange Online applicability differs and Graph parity must not be assumed.

## Release gates still required
1. Execute automated tests in an isolated environment.
2. Adversarial corpus: false positives, stale examples, comments/docs, generated files, mixed versions, unsupported platforms, encoded/obfuscated secrets, large files and binary rejection.
3. Security review: upload limits, archive traversal, decompression bombs, MIME/content validation, retention/deletion, logging redaction, tenant isolation.
4. Refresh every vendor rule against current primary-source documentation and record evidence/version/date in a rule manifest.
5. Legal/liability/claims review.
6. Define fulfillment artifact and verify delivery before checkout can be enabled.
7. Human publication approval.

## Commercial hypothesis
First-sale test: one redacted artifact/repository scan with a human-readable Dependency Rescue report. Proposed test price: $9.99. Pricing and checkout remain unactivated pending explicit approval and fulfillment verification.

## Rollback
Feature branch only. No production behavior changed. Delete/close the branch or PR to abandon the candidate.
