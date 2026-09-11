# JakeAIOfficial.com Website Repair Audit — 2026-09-11

Status: remediation branch only; production/main not changed by this file.

## Priority 0 — Truthfulness / checkout state

1. The catalog header currently says `Checkout Active` even though multiple products are explicitly `Checkout Disabled` and Game QA Autopilot is `COMING SOON / Checkout Pending`. Replace the global claim with per-product status language such as `Checkout status shown per product`.
2. Game QA Autopilot remains correctly fail-closed until `GAME_QA_DELIVERY_URL` is configured and the end-to-end paid checkout -> Stripe verification -> private delivery flow is tested. Do not switch to `AVAILABLE / BUY NOW` until that evidence exists.
3. The free Gateway product route checks for `STRIPE_SECRET_KEY` before executing the free-product bypass. This creates an unnecessary dependency: a $0 product can fail with `STRIPE_SECRET_KEY missing` even though Stripe is not needed. Move the free-delivery branch before the Stripe-key check.

## Priority 1 — Overclaim / legal-risk copy

4. Change `Authoritative reference guide` for the solar/BESS product to neutral wording such as `Technical reference guide` unless an external authority basis is documented.
5. The Machine Protocol section currently says bots `query and transact directly` and the developer section says creators can `monetize machine traffic`. These should be framed as design/availability claims only to the extent the production endpoints and settlement path are actually verified.
6. Keep demonstration-data labeling on PJM/tariff outputs. Do not imply live market data.
7. Keep API-credit products fail-closed until entitlement/metering exists.

## Priority 2 — Commerce integrity

8. Preserve payment verification before private delivery. Paid products must never redirect to delivery content before `payment_status == paid`.
9. Preserve public catalog sanitization so private `download_url` values never appear in catalog responses.
10. Verify every visible `Buy` button against the production backend before advertising availability.

## Priority 3 — Deployment verification

11. Compare production Netlify output against GitHub `main`; staged fixes are not proof of production state.
12. Verify Netlify proxy rules for `/api/v1/*`, `/llms.txt`, `/docs`, `/health`, and `/health/checkout` against the Railway backend.
13. Record the exact deployed commit/version fingerprint after repair.

## Current known-safe behavior to preserve

- CORS is origin-restricted rather than wildcard credentialed CORS.
- Public product views exclude private delivery URLs.
- SSRF protection exists on public URL extraction.
- Products without delivery configuration fail closed.
- API-credit categories fail closed until metering/entitlement exists.
- Stripe paid-delivery flow verifies payment before redirecting to private delivery.

## Release gate

Do not merge this remediation branch to production until the following are evidenced:

- free Gateway access works without Stripe dependency;
- every enabled paid checkout can reach Stripe;
- successful payment is verified server-side;
- private delivery occurs only after successful verification;
- disabled/pending products cannot take payment;
- homepage status language matches actual per-product availability;
- legal/privacy/refund links resolve;
- `/llms.txt` and agent-facing discovery endpoints resolve;
- deployed production version matches the reviewed commit.
