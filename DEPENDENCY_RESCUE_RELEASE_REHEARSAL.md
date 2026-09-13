# JakeAI Dependency Rescue v1 — Release Rehearsal

Status: **PRE-RELEASE / NOT PUBLIC / HUMAN APPROVAL REQUIRED**

Rehearsal date: 2026-09-13

## End-to-end synthetic fulfillment rehearsal

A synthetic redacted text artifact was constructed containing one supported signature for each active v1 rule pack, with no live credentials or customer data:

- Cloudflare `X-Auth-User-Service-Key`
- Coralogix legacy `/logs/rest/bulk` endpoint
- Databricks `supervisor_api` reference
- Google Ads `google.ads.googleads.v22`
- Qlik webhook/CloudEvent reference
- Exchange Online `https://outlook.office365.com/EWS/Exchange.asmx`

The current rule behavior produced six findings: five `confirmed-signature` findings and one Qlik `review-candidate`, matching the intended confidence model. Using a 2026-09-13 scan date, the timing calculations were 17 days to the September 30 rules, 18 days to the Exchange Online phased-disablement start, 23 days to the Qlik change, and 24 days to the Google Ads v22 sunset.

The report path was reviewed for the required customer-facing elements: artifact name, vendor date, confidence classification, primary-source URL, evidence location, remediation guidance, verification guidance, safe-cutover sequence, timing context for EWS, and limitations. The report does not claim that no-match means safe and does not claim that JakeAI executes migrations or production changes.

## Current-source verification

The active rule claims were rechecked against current primary/vendor sources on 2026-09-13:

- Cloudflare: Service Key authentication stops working September 30, 2026; API Tokens are the replacement.
- Coralogix: listed legacy ingestion endpoints are permanently disabled September 30, 2026; regional endpoints and Bearer authentication are the replacement path.
- Databricks: Supervisor API (Beta) reaches end of life September 30, 2026; Databricks recommends migration to custom agents on Databricks Apps.
- Google Ads: API v22 sunsets October 7, 2026; v22 requests begin failing from that date.
- Qlik: legacy webhook attributes are removed October 6, 2026; webhook-triggered automations relying on removed fields can break.
- Exchange Online EWS: phased disablement begins October 1, 2026 and permanent retirement is April 1, 2027. Applicability can vary by workload/tenant, and on-premises Exchange EWS is outside this retirement.

## Claims/legal-liability screen

PASS for a limited pilot, subject to the remaining human publication gate, because the product language is framed as an artifact-level diagnostic rather than a guarantee or managed migration service.

Required claims boundaries for any storefront/intake copy:

1. Say **supported signatures** or **supported rule packs**; never claim comprehensive dependency detection.
2. Say findings require human verification against current vendor documentation before action.
3. Say no-match is not proof of safety or absence of unsupported/runtime-only dependencies.
4. Do not promise zero downtime, complete migration equivalence, security certification, legal compliance, or guaranteed prevention of outages/data loss.
5. Do not request credentials or production access.
6. Do not claim JakeAI changes production systems, rotates credentials, or performs migrations.
7. For Exchange Online EWS, describe October 1, 2026 as the phased-disablement start, not universal permanent retirement.
8. Preserve vendor/source attribution and do not imply affiliation with the vendors whose deprecations are analyzed.

## Pilot fulfillment controls

For customer #1, use controlled manual fulfillment only. Public web upload remains disabled.

- Accept only specifically approved, redacted UTF-8 text/config/code artifacts.
- Reject archives, binaries, symlinks, unsupported types, oversize files, and secret-positive artifacts.
- Run the scanner offline.
- Human-review each finding and current vendor source before delivery.
- Deliver the generated Markdown Rescue Report.
- Make no production changes.
- Delete submitted artifacts after fulfillment under the approved pilot retention procedure.

## Release decision

Engineering/fulfillment rehearsal: **PASS**.
Current-source claims verification: **PASS** for the six active v1 rule packs.
Claims/liability wording: **PASS WITH BOUNDARIES** listed above.
Public web upload: **BLOCKED** pending hardened retention/deletion, logging redaction, MIME/content validation, tenant isolation, abuse controls, and failure handling.
Checkout/publication: **BLOCKED UNTIL EXPLICIT HUMAN APPROVAL**.
