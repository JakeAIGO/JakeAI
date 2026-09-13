# JakeAI Dependency Rescue v1 — Build Candidate

Status: **NOT PUBLIC / NOT FOR SALE / HUMAN APPROVAL REQUIRED**

## Promise
Analyze customer-supplied, redacted text configuration/code artifacts for supported vendor-deprecation signatures and return evidence-linked remediation and verification guidance.

## Supported v1 rule packs
- Cloudflare legacy Service Key authentication
- Coralogix legacy ingestion patterns
- Databricks Supervisor API (Beta) end of life
- Google Ads API v22
- Qlik webhook/CloudEvent migration candidates
- Microsoft Exchange Online EWS phased-disablement candidates

## Safety boundaries
- Offline text analysis only.
- No credentials or production access required.
- Potential secrets fail closed before dependency analysis.
- No automatic edits, deployment, revocation, migration, ad changes, or infrastructure actions.
- A no-match result is never represented as proof that an artifact is safe.
- Findings require human verification against current authoritative vendor documentation before customer action.
- EWS findings require classification because on-premises and Exchange Online applicability differs and Graph parity must not be assumed.
- For Exchange Online EWS, October 1, 2026 is treated as the start of phased disablement, not the universal permanent-retirement date. Permanent retirement is April 1, 2027.

## Pilot fulfillment decision
The first-customer candidate uses **controlled manual fulfillment**, not a public web-upload endpoint. This avoids pretending that upload retention, deletion, logging redaction, and tenant isolation are solved before they are implemented and tested.

Pilot sequence:
1. Customer is instructed to submit only redacted UTF-8 text/config/code artifacts through the specifically approved intake path used for the pilot.
2. Operator rejects archives, binaries, symlinks, unsupported types, oversize files, and any artifact that triggers secret detection.
3. Scanner runs offline.
4. Human reviewer verifies every surfaced vendor source and customer-impact claim before delivery.
5. Customer receives the Markdown Rescue Report; no production changes are performed.
6. Submitted artifacts are deleted after fulfillment according to the pilot retention policy established before checkout is enabled.

A public upload flow remains blocked until retention/deletion, logging redaction, MIME/content handling, tenant isolation, abuse limits, and failure handling are implemented and verified.

## Release gates still required
1. Automated tests and PR guardrails pass on the final release-candidate head.
2. Adversarial corpus remains green for false positives, stale examples, comments/docs, mixed versions, unsupported platforms, secrets, large files and binary rejection.
3. Define and verify the exact pilot intake channel and retention/deletion procedure; do not enable public upload yet.
4. Refresh every active vendor rule against current primary-source documentation before publication.
5. Legal/liability/claims review of storefront copy and report language.
6. Verify one complete fulfillment rehearsal from redacted artifact through delivered Rescue Report before checkout can be enabled.
7. Human publication approval.

## Commercial hypothesis
First-sale test: one redacted artifact/repository scan with a human-readable Dependency Rescue report. Proposed test price: $9.99. Pricing and checkout remain unactivated pending explicit approval and fulfillment verification.

## Rollback
Feature branch only. No production behavior changed. Delete/close the branch or PR to abandon the candidate.
