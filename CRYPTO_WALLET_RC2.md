# JakeAI Wallet RC2 — Isolated Canary

Status: **PRIVATE PREVIEW / REAL-MONEY CANARY OFF**

This branch is synced to the current JakeAI main tree and preserves the merchant-only Base/native-USDC design.

## Scope
- JakeAI-owned merchant payments only.
- Customer uses their own non-custodial wallet.
- JakeAI receives native USDC on Base Mainnet.
- No exchange, swaps, customer balances, custody, creator payouts, yield, or token issuance.
- No private key or signing capability in the web/backend runtime.

## Isolated test console
- `/wallet-preview`
- Requires the existing `JAKEAI_COMMERCE_PREVIEW_KEY` for status/canary API calls.
- Real-chain canary amount: **$0.10 / 0.10 USDC**.
- Canary order is not in the public catalog and has no product fulfillment.
- `JAKEAI_CRYPTO_CANARY_ENABLED` is an additional preview-only kill switch and defaults OFF.

## Activation sequence
1. Verify preview service is on current main code.
2. Keep public production crypto disabled.
3. Confirm merchant address / Base RPC / official USDC contract / confirmation threshold.
4. Confirm legal/compliance procedure and admin review path.
5. Enable the canary flag in the isolated preview only.
6. Create one 0.10 USDC invoice.
7. Send exact native USDC on Base.
8. Verify transaction -> expect compliance hold.
9. Record approved compliance decision for exact order+tx.
10. Re-verify -> expect paid, with auto-fulfillment still OFF.
11. Re-test replay, wrong-network/token/amount and kill switch.
12. Only then prepare public Pay with USDC UI for explicit owner approval.
