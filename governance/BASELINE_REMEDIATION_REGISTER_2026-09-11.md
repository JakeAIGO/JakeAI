# Jake AI Baseline Remediation Register — 2026-09-11

Status: ACTIVE CANDIDATE AUDIT — NOT PRODUCTION AUTHORIZATION

## Objective
Produce a recoverable, internally consistent Jake AI baseline that can be used as the canonical fallback before additional engines, products, or autonomous workflows are layered on top.

"Flawless" is treated as an engineering target, not an unprovable claim. Baseline approval requires evidence for every gate below and zero unresolved Critical blockers.

## Confirmed defects / inconsistencies

### CRITICAL-01 — Free gateway incorrectly depends on Stripe configuration
In `create_checkout_session`, `STRIPE_SECRET_KEY` is required before the free-product bypass executes. A free product can therefore fail because a paid processor is not configured.

Required correction: move free-product delivery before Stripe-secret validation while preserving product-existence, checkout-eligibility, and delivery-URL checks.

Verification: automated regression test must prove the free branch is reached before Stripe-secret lookup.

### HIGH-01 — Homepage overstates global checkout state
`index.html` displays a catalog-wide `Checkout Active` statement while multiple cards are explicitly disabled/pending and backend eligibility is per-product.

Required correction: replace global status with truthful per-product/readiness language generated or validated against canonical product state.

### HIGH-02 — Unsupported authority language
The solar guide is described on the homepage as an `Authoritative reference guide`. No repository evidence establishes an authority basis for that claim.

Required correction: use descriptive language unless authority can be substantiated and approved.

### HIGH-03 — README documented nonexistent/stale routes and autonomy
Previous README claimed `/v1/products/register`, `/v1/transactions/settle`, a private `/admin` application route, and commercial operation `without human intervention`. Current inspected backend does not establish those claims.

Status: corrected on the remediation branch. The README now distinguishes implemented code, runtime verification, and approval boundaries.

### HIGH-04 — Commercial and machine-readable drift risk
Prices, availability, route descriptions, creator economics, protocol fees, and capability claims are represented in multiple static and dynamic surfaces.

Required correction: converge on one canonical product/capability registry and derive or test all public surfaces against it.

### HIGH-05 — Static vs dynamic discovery drift
Static `llms.txt` / `agent_card.json` coexist with backend-generated `/llms.txt` and `/.well-known/agent.json`.

Required correction: public routing should prefer the dynamic source of truth; static compatibility files must either be generated from the same registry or explicitly deprecated.

### HIGH-06 — External-model Council runtime remains unverified
Provider code exists for Anthropic and Perplexity, but live provider configuration and successful runtime participation are not proven merely by source inspection.

Required correction: Council marketing and status must say implemented/configurable until runtime evidence proves successful execution.

### HIGH-07 — External API-key header policy needs security decision
The audit endpoint accepts optional `X-Anthropic-Key` and `X-Perplexity-Key` headers.

Required correction: decide whether BYOK is intentionally supported. If yes, define authentication, logging, retention, precedence, abuse controls, and proxy behavior. If no, remove public header-key support.

### MEDIUM-01 — Canonical public path convention needs enforcement
Website-facing paths should be `/api/v1/...`; direct backend paths are `/v1/...`. Documentation, examples, tests, and agent surfaces must preserve that distinction.

### MEDIUM-02 — "Real-Time" naming on demonstration energy product
The product registry title includes `PJM Real-Time Energy Tariff & 4CP Peak Forecast API` while its description and response correctly say values are demonstration data.

Required correction: rename or qualify the product title so the title itself cannot imply live pricing.

### MEDIUM-03 — Admin surface classification
A static `admin.html` exists. It must not be described as private or authenticated unless access controls are actually implemented and verified.

### MEDIUM-04 — Runtime/link verification incomplete
Repository routing configuration identifies public routes, but branch source inspection alone does not prove the deployed domain currently serves every expected link and status.

Required correction: before baseline promotion, execute a runtime link/route matrix against an isolated preview or approved non-production environment, then separately verify production after explicit deployment approval.

## Baseline verification matrix

### Application integrity
- [ ] Python syntax passes.
- [ ] Application imports without production credentials.
- [ ] FastAPI route table loads.
- [ ] Dependency installation resolves from a clean environment.
- [ ] No startup mutation unexpectedly activates checkout or publication.

### Commerce
- [ ] Free gateway works with no Stripe secret.
- [ ] Unknown product returns 404.
- [ ] Disabled/unfulfilled product fails closed.
- [ ] Metered product fails closed until entitlement exists.
- [ ] Paid checkout cannot expose delivery before verified paid status.
- [ ] Cancel/failure paths do not deliver content.
- [ ] Private delivery URLs are absent from public catalog/search/agent output.
- [ ] Prices presented to payment rail are server-controlled.
- [ ] Repeated purchase/session requests have an explicit idempotency policy.

### Website and links
- [ ] `/` loads expected candidate page.
- [ ] `/terms.html` resolves.
- [ ] `/privacy.html` resolves.
- [ ] `/refunds.html` resolves.
- [ ] `/docs` resolves to expected backend docs.
- [ ] `/openapi.json` resolves valid JSON.
- [ ] `/health` resolves healthy candidate state.
- [ ] `/health/checkout` resolves and accurately reports readiness.
- [ ] `/llms.txt` resolves authoritative generated content.
- [ ] `/.well-known/agent.json` resolves valid JSON.
- [ ] All homepage internal links resolve.
- [ ] All homepage external links are intentional and correct.
- [ ] No broken product checkout/access link exists.

### Claims and product truth
- [ ] No global checkout claim conflicts with per-product state.
- [ ] No demonstration data is labeled live/real-time without qualification.
- [ ] No external model/service is called live unless runtime evidence exists.
- [ ] No unsupported legal/safety/authority/verification claim remains.
- [ ] Creator split and protocol-fee language are internally consistent and approved.
- [ ] Product title, price, description, and availability match canonical registry.

### Security
- [ ] Secret scan clean.
- [ ] Private delivery URL scan clean for public outputs.
- [ ] SSRF protections tested against loopback/private/link-local/reserved targets.
- [ ] CORS configuration reviewed.
- [ ] BYOK/header-secret policy resolved.
- [ ] Error responses do not leak secrets or internal stack data.
- [ ] Request sizes/timeouts/rate-abuse exposure reviewed for network-fetching endpoints.

### Persistence and recovery
- [ ] Approved baseline commit SHA recorded.
- [ ] Product registry snapshot recorded.
- [ ] Deployment/runtime configuration inventory recorded without secret values.
- [ ] Rollback path documented.
- [ ] Baseline remains immutable after approval; subsequent work branches from it.

### Council gate
- [ ] Full candidate source and architecture summary prepared.
- [ ] Test evidence attached.
- [ ] Known limitations attached.
- [ ] Security findings attached.
- [ ] Legal/liability findings attached.
- [ ] Model disagreements recorded rather than averaged away.
- [ ] Council verdict recorded.
- [ ] Required human approval recorded before production promotion.

## Promotion rule
No production merge/deploy occurs from this remediation effort until the verification matrix is materially complete, all Critical blockers are closed, High blockers are either closed or explicitly accepted with rationale, and the Council packet has been reviewed.
