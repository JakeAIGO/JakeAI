# JakeAI Commercial Rules Registry — Internal Council Review

Date: 2026-09-11

Scope: internal repository governance review of the Commercial Rules Registry candidate. This is not external legal advice and does not represent a live review by Anthropic, Perplexity, Grok, Gemini, or any other external model provider.

## Result

**GO for canonical baseline inclusion; NO-GO for commercial activation.**

The registry materially improves control because commercial facts that were previously scattered across code, copy, and product metadata now have a single fail-closed authority. Prices are checked against the Master Manifest; creator split, protocol fee, and refund terms are explicitly marked proposed/unapproved; product checkout and commercial authorization default false; and metering, fulfillment, legal review, refund verification, Council review, and explicit human commercial approval remain required promotion conditions.

## Council lanes

- Architecture: GO. The registry is separated from runtime execution and can be validated deterministically.
- Commerce: GO for baseline inclusion. NO-GO for sale activation until product-specific fulfillment/metering/refund/legal conditions are verified.
- Security: GO. The registry adds no credentials and fails closed on authorization state.
- Legal/liability: CONDITIONAL GO for baseline inclusion. The registry correctly marks commercial terms as unapproved and does not substitute for final legal review.
- Product truth: GO. Public fee/split claims are not authorized merely because proposed values exist in the registry.
- Release: GO for a new baseline anchor after an exact-head full gate passes; NO-GO for merge to main, deployment, publication, checkout activation, or commercial release.

## Findings closed during build

1. Commercial rule files were explicitly added to change-control commerce/legal classification.
2. The registry is treated as a protected self-modification surface.
3. Product prices are locked to the Master Manifest by deterministic tests.
4. Commercial, checkout, fulfillment, and legal states fail closed.
5. The proposed 50/50 creator split and 1% protocol fee remain unapproved and cannot be treated as authorized public terms.

## Required before any commercial activation

Product-specific fulfillment verification, metering verification where required, refund-policy verification, final legal/liability review, Council approval, and explicit human commercial approval must all be recorded. Paid checkout and fulfillment must also be verified in the intended deployment environment before a product is represented as commercially available.
