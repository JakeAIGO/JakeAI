# JakeAI Master Baseline Engine

Status: CANDIDATE GOVERNANCE SPECIFICATION — NOT PRODUCTION AUTHORIZATION
Date: 2026-09-11

## Purpose
The Master Baseline Engine is JakeAI's canonical known-good fallback and comparison point. Experimental engines, products, workflows, marketing claims, commerce changes, and deployment changes must be evaluated against it before promotion.

## Permanent pipeline
MASTER BASELINE -> WORKING BRANCH -> AUTOMATED TESTS -> TRUTH/CLAIMS AUDIT -> SECURITY/LIABILITY AUDIT -> COUNCIL REVIEW -> HUMAN APPROVAL WHERE REQUIRED -> PRODUCTION

No stage may silently bypass a failed or unknown earlier stage.

## Baseline invariants
1. Fail closed: unavailable, unmetered, unfulfilled, unverified, or safety-sensitive products are not chargeable.
2. Paid delivery is withheld until payment is independently verified and bound to the exact product, amount, and currency.
3. Free products do not depend on a paid processor or processor credentials.
4. Public catalog responses never expose private delivery URLs.
5. Public claims describe only implemented, deployed, tested, and authorized behavior.
6. Demonstration/static/cached data is labeled as such and never represented as live.
7. Consequential commercial, legal, safety, publication, spending, and production actions retain their required approval gates.
8. No secret/token/API key is committed to source or exposed to clients.
9. Canonical website API path is /api/v1/...; backend/direct deployment paths are documented separately.
10. Machine-readable discovery surfaces derive from the same canonical product/capability registry wherever practicable.
11. Brand continuity uses approved canonical JakeAI assets and naming; generated variants must not redefine the master identity.
12. External payment processors are adapters. JakeAI owns product, order, customer, license, pricing, refund, creator-ledger, and revenue-share logic.
13. External network-fetch tools remain disabled by default until hardened egress is independently validated.
14. Safety-critical or consequential outputs remain advisory until independently validated for their intended use.
15. Repository artifacts, manifests, tests, and freeze records—not chat memory—are the continuity authority for reconstructing the baseline.

## Canonical source-of-truth target
A single registry should own product identity, title, description, price, commercial state, fulfillment state, metering requirement, safety/legal state, and public capability status. Website cards, llms.txt, agent-card output, checkout eligibility, and public API metadata should be generated or validated against that registry.

## Promotion gates
A candidate may be proposed for production only when:
- syntax/import/static checks pass;
- checkout eligibility tests pass;
- free-access tests prove no Stripe dependency;
- paid-delivery tests prove payment verification precedes delivery and is bound to the exact product, amount, and currency;
- catalog tests prove delivery URLs are absent from public output;
- claim-consistency tests pass across website, registry, llms.txt, agent card, and docs;
- routing tests pass for canonical public paths;
- runtime-only claims have runtime evidence;
- security review has no unresolved critical issue;
- legal/liability review has no unresolved blocking issue;
- Council packet records disagreements, limitations, and evidence;
- required human approval is recorded.

## Recovery rule
If a later build becomes inconsistent or unsafe, compare it to the most recently approved Master Baseline. Do not reconstruct production truth from chat memory, marketing copy, or an experimental branch.

## Versioning rule
An approved baseline is immutable. Improvements create a new candidate version. Only after all promotion gates pass does the candidate become the next approved baseline.

## Current candidate scope
The 2026-09-11 remediation candidate must resolve at minimum:
- free gateway checkout ordering bug;
- global checkout-status overclaim;
- unsupported authority/live/autonomy claims;
- pricing drift between machine-readable surfaces and registry;
- static/dynamic discovery drift;
- canonical API path documentation;
- claim-consistency regression tests;
- Council review packet;
- retirement of temporary write-capable remediation automation;
- candidate freeze and reproducible dependency/test configuration.

Nothing in this document authorizes merge, deployment, spending, public posting, checkout activation, or production modification.