# JakeAI Wallet RC2 — Upload-Ready Release Candidate

Status: **PRIVATE PREVIEW / PUBLIC ACTIVATION OFF**

The wallet release is synchronized to the current JakeAI codebase and designed as a merchant-only Base/native-USDC payment rail.

## What is complete
- Base Mainnet / native USDC verification.
- Exact-amount invoice creation.
- Independent read-only RPC verification.
- Confirmation threshold and replay protection.
- Compliance hold before paid state.
- Isolated manual compliance bridge for the canary; the admin token never enters the browser.
- Separate payment, legal, product-allowlist, canary and auto-fulfillment gates.
- Customer-facing `crypto-checkout.html` prepared but deliberately unlinked and `noindex` until owner approval.
- Crypto-specific Terms, Refund and Privacy language prepared as release-candidate copy.
- Production guard prepared to mount the crypto runtime while all crypto activation variables remain fail-closed.

## Locked scope
- JakeAI-owned merchant payments only.
- Customer uses a wallet they control.
- JakeAI receives native USDC on Base Mainnet.
- No exchange, swaps, customer balances, custody, creator payouts, yield or token issuance.
- No seed phrase, private key, signing or transaction broadcasting in the web/backend runtime.

## Isolated canary
- Private console: `/wallet-preview`
- Canary: **0.10 USDC**
- No product delivery is attached.
- `JAKEAI_WALLET_PREVIEW_ONLY=true` locks general crypto routes behind the preview password on the isolated service.
- `JAKEAI_CRYPTO_CANARY_ENABLED=false` remains OFF until the controlled transaction is explicitly authorized.

## Public activation gates
Public USDC checkout requires all of these simultaneously:
1. `CRYPTO_PAYMENTS_ENABLED=true`
2. `CRYPTO_LEGAL_APPROVED=true`
3. valid `CRYPTO_MERCHANT_ADDRESS`
4. Base RPC configured and allowlisted
5. `CRYPTO_PRODUCT_ALLOWLIST` containing the exact product ID
6. required confirmations
7. transaction-specific compliance clearance
8. separate `CRYPTO_AUTO_FULFILL_ENABLED=true` before automatic delivery

No single switch can silently enable the full flow.

## Remaining human gates
- Complete/approve the external sanctions-risk procedure.
- Review the release-candidate legal copy.
- Run one authorized 0.10 USDC canary.
- Review the canary evidence.
- Explicitly approve merge/upload.
- Separately approve public crypto activation and the first crypto-enabled product.
