# JakeAI Shopify Order Bridge — Activation

The production endpoint is already deployed:

- Health: https://jakeaiofficial.com/api/v1/shopify/bridge/health
- Paid-order webhook: https://jakeaiofficial.com/api/v1/shopify/webhooks/orders-paid

The bridge is intentionally fail-closed until a JakeAI-owned Shopify app is connected.

## Required first-party app configuration

Use a JakeAI-owned Shopify custom/app integration for the store. The app must have the minimum scopes required for product synchronization and paid-order webhook delivery.

Store these server-side only:

- SHOPIFY_STORE_DOMAIN
- SHOPIFY_ADMIN_ACCESS_TOKEN
- SHOPIFY_WEBHOOK_SECRET

SHOPIFY_WEBHOOK_SECRET must be the signing secret/client secret for the same Shopify app that owns the webhook subscription. Do not invent an unrelated shared secret; Shopify signs HTTPS webhook deliveries with the app secret.

## Webhook subscription

Subscribe the JakeAI app to the Shopify ORDERS_PAID topic and send JSON deliveries to:

https://jakeaiofficial.com/api/v1/shopify/webhooks/orders-paid

Use the current stable Admin API/webhook version used by the JakeAI Shopify app. Shopify recommends app-specific webhook subscriptions in app configuration when practical; a shop-specific GraphQL webhookSubscriptionCreate subscription is also supported.

## Verification contract

The bridge:

1. reads the raw request body,
2. verifies X-Shopify-Hmac-Sha256 with the JakeAI-owned app secret,
3. rejects unexpected topics,
4. requires financial_status == paid,
5. maps only known JakeAI SKUs,
6. requires quantity 1 for current digital products,
7. verifies the line price against the expected JakeAI price,
8. records each Shopify order line idempotently,
9. never treats an unverified request as payment.

## Current fulfillment state

Automatic conversion into the JakeAI protected-order ledger is enabled for:

- JAI-SCOPE-001 — Scope Creep Guard
- JAI-INVOICE-001 — Invoice Nudge

Verified Shopify purchases for these products become JakeAI paid orders after HMAC, SKU, quantity, and price verification.

The following are deliberately held after payment until their product-specific entitlement adapters support Shopify as a source:

- JAI-GUITAR-001-MONTHLY
- JAI-GUITAR-001-ANNUAL
- JAI-GUITAR-001-SPRINT

Tattoo Designer (JAI-TATTOO-001) remains human-reviewed rather than auto-fulfilled.

## Do not publish Shopify drafts until

- the first-party app is installed,
- the three server-side variables above are present,
- /api/v1/shopify/bridge/health reports ready,
- a signed test ORDERS_PAID webhook has been accepted,
- duplicate-delivery idempotency has been confirmed,
- one controlled end-to-end purchase has been verified,
- the correct JakeAI entitlement/delivery result has been observed.

No live product should bypass this gate.
