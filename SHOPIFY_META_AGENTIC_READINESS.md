# Shopify + Meta Agentic Commerce — JakeAI Readiness

Status: **staged / no external writes / no checkout change**

## Decision

JakeAI will use Shopify's Agentic plan as a replaceable commerce-distribution
adapter while keeping `jakeaiofficial.com` as the canonical storefront and
JakeAI's existing commerce, entitlement, audit, and release controls as the
source of truth.

Meta is the first direct-checkout target.

## Current safe state

- No Shopify or Meta product sync is active from this repository.
- No Meta direct checkout is activated by this change.
- No pricing, Stripe, wallet, entitlement, or production-deployment behavior is changed.
- The adapter is preview-only and fail-closed.
- Products must be explicitly enabled and must also be marked purchasable in the
  JakeAI public catalog before they can appear in a sync preview.

## Shopify / Meta eligibility gates encoded here

A staged product is blocked unless it has:

1. an explicit JakeAI enable flag;
2. a public catalog capability with `commerce.purchasable=true`;
3. a price greater than zero;
4. an external JakeAI product URL;
5. a product image URL;
6. available inventory.

For Meta direct checkout, the adapter additionally treats the following as
ineligible: subscriptions, bundles, customizable products, and B2B-only products.

## Current JakeAI product reality

There is not yet a clean Meta-direct-checkout launch product in the present
public commerce set:

- **Make the Damn Thing for Free™** is $0, while Shopify Catalog requires a
  price greater than zero.
- **Genesis Commission #001** is a customizable commission, which is not a fit
  for Meta direct checkout.
- **Game QA Autopilot**, **Where the Hell Are My Glasses?**, and **Pool Coach**
  are still gated or unavailable in JakeAI's own commerce controls.

Therefore the correct first release is the adapter and account setup, not a
forced product activation.

## Account-side setup required before live sync

1. Create/connect the Shopify Agentic-plan store.
2. Complete Shopify business details, identity verification, and requested
   business-registration documentation.
3. Add Terms of service, Privacy policy, and Return/refund policy in Shopify.
4. Add and verify `jakeaiofficial.com` as the existing external store domain.
5. Install **Facebook and Instagram by Meta** in Shopify and enable product-feed
   syncing.
6. Keep Meta direct checkout off until one fixed-price D2C JakeAI product has
   passed fulfillment, entitlement, image, pricing, and refund-path QA.
7. Activate that one product first, verify a complete test order lifecycle, then
   expand the catalog deliberately.

## Recommended first launch product profile

A first Meta product should be:

- fixed-price;
- direct-to-consumer;
- non-subscription;
- non-customizable;
- immediately fulfillable;
- represented by one stable JakeAI product URL and one dedicated image;
- covered by a tested refund/delivery path.

Do not use a safety-critical, professional-advice, or otherwise regulated
workflow as the first agentic-commerce product.

## Rollback

Rollback is simply to leave all staged products disabled, keep
`catalog_sync_enabled=false`, and keep Meta direct checkout disabled.
No existing JakeAI checkout path depends on this adapter.
