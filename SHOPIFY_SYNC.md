# JakeAI → Shopify Distribution Flow

JakeAI is the source of truth. Shopify is a downstream sales/discovery adapter.

## Automatic path

A catalog capability is eligible for Shopify only when all of these are true:

1. `lifecycle_status == "production"`
2. `publication_status == "listed_live"`
3. `commerce.purchasable == true`
4. `distribution.shopify.enabled == true`
5. `distribution.shopify.security_review == "passed"`
6. `human_url` is HTTPS
7. Required product art is an HTTPS URL

When eligible, `shopify_catalog_sync.py` creates or updates a Shopify mirror using the canonical JakeAI ID. It writes the stable `jakeai-catalog-sync` tag and JakeAI metadata so duplicate mirrors are refused rather than guessed.

## Release states

- `draft` — automatically mirrored to Shopify as DRAFT. Never customer-visible.
- `approved_live` — ACTIVE and published to the Shopify Online Store.

The default is `draft`. Public Shopify release therefore remains a separate human-controlled gate.

## Variants

- `base_only` — one Shopify variant using `commerce.price`.
- `plans` — Shopify variants are generated from `commerce.plans`.

Digital mirrors are marked as not requiring shipping.

## Automation

`.github/workflows/shopify-catalog-sync.yml` runs when the JakeAI catalog, sync adapter, or product artwork changes. It always compiles the adapter and performs a dry-run validation first.

Remote Shopify synchronization requires two GitHub repository secrets:

- `SHOPIFY_STORE_DOMAIN`
- `SHOPIFY_ADMIN_ACCESS_TOKEN`

If either is absent, the job stops before any Shopify mutation. No secret value is printed.

Required Shopify Admin API scope: `write_products` (plus the read scopes granted to the app for product/publication lookup).

## Failure policy

The sync is fail-closed. Missing security review, missing product art, unsafe/missing URL, duplicate Shopify mirrors, API errors, or invalid product data prevent that sync from completing rather than silently publishing bad data.
