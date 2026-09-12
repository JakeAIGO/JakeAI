# JakeAI

JakeAI is an autonomous AI-product marketplace and product-factory platform.

## Safety and deployment posture

Production commerce, deployment, publication, spending, and other consequential actions remain gated. Repository automation is designed to fail closed and preserve human approval for regulated or consequential changes.

## Crypto payment adapter (development only)

A merchant-only stablecoin payment adapter is under development on a feature branch. It is intentionally disabled and is not wired into live checkout. The current development scope is limited to accepting native USDC on Base as payment for JakeAI-owned products/services after independent payment verification and compliance clearance.

The adapter does **not** implement an exchange, customer custody, customer balances, P2P transfers, creator payouts, yield/investment features, or third-party money transmission. Private spending keys are not stored or used by the adapter.

Activation requires explicit review and approval of legal/compliance, sanctions screening, security, accounting/tax handling, wallet operations, RPC reliability, and end-to-end test results.
