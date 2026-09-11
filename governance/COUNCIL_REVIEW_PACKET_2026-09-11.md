# JakeAI Master Baseline Engine — Council Review Packet

Status: CANDIDATE FOR COUNCIL REVIEW ONLY  
Production merge/deploy/publication authorization: NO  
Commercial activation authorization: NO

## Candidate identity

- Remediation branch: `fix/website-truthfulness-audit-2026-09-11`
- Last fully green code/test checkpoint before this packet: `1f0596b7db3210db404be5907ba7cac2454558a0`
- Master manifest: `governance/master_manifest.json`
- Manifest blob at review preparation: `7c22ee481072d02be8a9b41c62f9a5f3edb2adc7`
- Runtime dependency set is pinned in `requirements.txt`.
- Test dependency set is pinned in `requirements-test.txt`.

This packet is a review artifact. Adding or editing governance documentation changes the branch commit SHA but does not by itself alter runtime behavior. Any later runtime/code change requires a fresh full gate and a new candidate identity.

## What the candidate is intended to become

The JakeAI Master Baseline Engine is the canonical known-good fallback and comparison point for future JakeAI development. Experimental engines should branch from it, be diffed against it, pass the same gates, and never silently redefine commercial, security, safety, or publication truth.

Repository artifacts—not model memory—are the authoritative continuity mechanism. A future AI should be able to reconstruct the operating rules from the repository even if it has no access to the conversation that produced them.

## Baseline invariants

1. Fail closed when payment, fulfillment, metering, safety, provider configuration, or commercial approval is incomplete.
2. No paid delivery before verified payment bound to the exact product, amount, and currency.
3. Free products must not depend on payment-processor credentials.
4. Private delivery URLs must never appear in public catalog or machine-discovery output.
5. Claims must distinguish implemented, test-verified, production-runtime-verified, commercially approved, and unverified states.
6. Demonstration/static data must be labeled as such.
7. Safety-critical and consequential outputs remain advisory until independently validated for their intended use.
8. Provider secrets remain server-side and are not accepted through caller-supplied request headers.
9. External network-fetch tools fail closed by default pending hardened egress validation.
10. Commercial publication, spending, deployment, and release authority remain explicit human gates.
11. JakeAI owns its product/order/customer/license/pricing/refund/creator-ledger/revenue-share logic; payment processors are replaceable adapters.
12. Dynamic runtime machine-discovery surfaces are authoritative over stale repository copies.

## Repairs completed in the candidate

### Commerce and fulfillment

- Moved the free gateway before Stripe credential lookup.
- Paid Stripe sessions are now bound to product metadata.
- Verification checks paid status, exact product ID, expected amount, and USD currency before delivery.
- Metered/API-credit products fail closed until entitlement/metering exists.
- Products without configured fulfillment fail closed.
- Public catalog views remove `download_url`.
- Raw provider exception text is no longer returned to callers.

### Truth and claims

- Removed/reworded global checkout-active language and unsupported authoritative/live wording.
- PJM tariff data is explicitly demonstration data.
- Robotics output is classified as an unvalidated advisory physical-control model rather than optimized production control logic.
- Static `llms.txt` and `agent_card.json` are repository pointers, not commercial-state authorities.
- Current audit-product prices are locked against silent change pending explicit commercial approval.

### Security and privacy

- Restricted CORS origins and disabled credentialed wildcard behavior.
- Added SSRF checks for loopback, private, link-local, reserved, direct-IP, and mixed DNS resolutions.
- External network-fetch features are disabled by default pending hardened egress controls.
- Removed caller-supplied Anthropic/Perplexity secret-header overrides.
- Search-demand telemetry no longer stores requester IP or user-agent in that record.
- Privacy language now discloses third-party AI processing rather than promising no retention by external providers.

### Input and runtime integrity

- Added positive/range validation for energy, tax, settlement, and take-rate inputs.
- `/health` now reports process liveness only rather than claiming dependency/commerce health.
- Runtime and test dependencies are pinned.
- Master Baseline CI now executes the entire `tests/` directory rather than only the original static invariant file.

## Verification evidence

The candidate has passed the static repository audit and, at checkpoint `1f0596b7db3210db404be5907ba7cac2454558a0`, the expanded Master Baseline CI completed successfully after running the full regression suite. A live read-only smoke run for that checkpoint also completed successfully against selected public GET surfaces.

The live smoke is deliberately limited. It verifies reachability and minimal sanity for public read-only surfaces; it does not prove that the remediation branch is deployed, that paid checkout works in production, that Game QA fulfillment is live, that external model API keys are configured, or that all products are commercially approved.

## Verified / unverified matrix

### Verified in repository or CI

- Static repository audit.
- Full test-suite execution.
- Free checkout behavior without Stripe credentials.
- Metered-product fail-closed behavior.
- Game QA fail-closed behavior without delivery configuration.
- Public catalog delivery-URL privacy.
- Stripe product/amount/currency/payment-state binding through mocked runtime tests.
- Input validation contracts.
- CORS/SSRF baseline contracts.
- Privacy and claim consistency contracts.
- Manifest/catalog price-category alignment.

### Verified only as current production read-only reachability

- Site root.
- `/health`.
- `/llms.txt`.
- `/.well-known/agent.json`.
- `/docs`.
- `/openapi.json`.
- Terms, privacy, and refund pages.

### Still unverified or deliberately blocked

- Remediation candidate deployed to production.
- Live paid Stripe purchase and fulfillment.
- Game QA paid delivery.
- Entitlement/metering for API-credit products.
- External Anthropic and Perplexity runtime configuration/success.
- Hardened outbound-network egress suitable for enabling extraction/agent-card audit tools.
- Robotics physical-control validity.
- Tax/financial product legal and subject-matter validation for production reliance.
- Final commercial approval for prices, protocol fee, creator revenue split, and transaction language.
- Final legal review of terms/refunds/privacy for the intended operating model.

## Council questions requiring explicit verdicts

1. Architecture: Is the Master Baseline source-of-truth model sufficient to prevent future drift and AI-memory fragmentation?
2. Security: Are the checkout binding, secret handling, SSRF fail-closed posture, privacy minimization, and provider-error handling adequate for baseline promotion?
3. Commerce: Should any product be commercially approved now, or should all remain false until fulfillment/metering and pricing decisions are individually signed off?
4. Legal/liability: Are the solar/tax, robotics, autonomous-commerce, settlement, refund, and privacy claims appropriately constrained? What must be changed before launch?
5. Product truth: Are any remaining labels or descriptions stronger than the evidence supports?
6. Operations: Should the write-capable remediation workflow be removed/disabled before baseline promotion so the final baseline becomes immutable except through controlled review?
7. Reproducibility: Are direct dependency pins sufficient, or should the baseline add a full transitive lock/constraints file and artifact hashes before promotion?
8. Release: GO, CONDITIONAL GO, or NO-GO for promotion to a canonical baseline. This is separate from production deployment authorization.

## Recommended Council disposition

Current recommendation: **CONDITIONAL GO FOR MASTER-BASELINE DESIGN, NO-GO FOR PRODUCTION/COMMERCIAL ACTIVATION.**

Rationale: the candidate now has substantially stronger fail-closed behavior, truthful capability labeling, CI coverage, and a canonical manifest. However, production promotion should wait until the Council resolves the commercial/legal decisions, the final candidate is fingerprinted, the write-capable repair mechanism is retired or constrained, and the exact reviewed SHA receives a clean final gate.

## Required finalization sequence after Council review

1. Resolve Council NO-GO and conditional findings.
2. Apply only approved changes on the remediation branch.
3. Run static audit + full regression suite + security/privacy/claim checks.
4. Run read-only production smoke for comparison only.
5. Freeze exact candidate SHA and manifest/dependency hashes.
6. Disable/remove the temporary write-capable remediation workflow.
7. Record Council verdicts and human approvals.
8. Only after explicit authorization: create controlled PR/merge/deploy process.

No step in this packet authorizes merge, deployment, publication, checkout activation, spending, or external release.
