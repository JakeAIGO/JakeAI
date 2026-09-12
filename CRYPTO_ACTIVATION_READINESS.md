# JakeAI Merchant Crypto Checkout — Activation Readiness

Status: **CANDIDATE / OFF**

This implementation is for JakeAI-owned products only. It is not the creator marketplace and does not perform creator payouts, customer custody, exchange, swaps, stored balances, lending, yield, or third-party money transmission.

## Locked payment rail

- Unit of account: USD
- Settlement asset: native USDC on Base Mainnet
- Base chain ID: `8453`
- Native USDC contract: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
- Merchant receiving address: supplied by deployment environment (`CRYPTO_MERCHANT_ADDRESS`), never hardcoded as a spending credential
- Website/backend contains no seed phrase, private key, signing key, or transaction-broadcast capability

## Runtime gates

Activation requires all of the following:

- `CRYPTO_PAYMENTS_ENABLED=true`
- `CRYPTO_LEGAL_APPROVED=true`
- valid `CRYPTO_MERCHANT_ADDRESS`
- Base Mainnet RPC configured through `BASE_RPC_URL`
- RPC host on `BASE_RPC_ALLOWED_HOSTS`
- independent compliance decision for the exact transaction hash
- required confirmation count (`CRYPTO_MIN_CONFIRMATIONS`, currently planned at 2)
- exact invoice amount in native Base USDC
- successful receipt, correct network, token and recipient
- unused transaction hash and unused order

Automatic digital delivery additionally requires:

- `CRYPTO_AUTO_FULFILL_ENABLED=true`

If any gate fails, payment fulfillment fails closed.

## Checkout flow

1. Buyer selects a JakeAI-owned paid product.
2. Backend creates a tracked crypto order and returns exact USDC amount, Base network, official token contract and merchant public address.
3. Buyer sends native USDC on Base from the buyer's wallet.
4. Buyer submits the transaction hash.
5. Backend independently reads Base Mainnet through HTTPS JSON-RPC and verifies chain ID, successful receipt, official native-USDC Transfer event, merchant recipient, exact amount, confirmation count and replay status.
6. First valid verification remains on `compliance_hold` unless an approved compliance review exists for that exact order/transaction.
7. Authorized reviewer records the external sanctions/risk review result. The application does not claim to perform that legal/compliance analysis itself.
8. Buyer/operator re-submits the transaction hash.
9. If all checks clear, the transaction is recorded once and the commerce order becomes paid.
10. Delivery occurs only when the separate auto-fulfillment flag is enabled.

## Manual compliance administration

The administration endpoint is inaccessible unless `CRYPTO_ADMIN_TOKEN` is securely provisioned in the deployment environment. No token is stored in source control. Approval is bound to the exact order ID and transaction hash and is immutable through the current endpoint; a duplicate decision is rejected.

The reviewer must follow an approved sanctions/risk procedure outside the payment code. A manual database record is evidence that the procedure was performed; it is not itself sanctions screening.

## Accounting record

A cleared transaction persists:

- transaction hash
- order ID
- chain ID
- token contract
- sender and recipient public addresses
- USDC amount
- block number
- compliance provider/reference
- USD fair-market-value field
- consumption timestamp

Each transaction hash and order can be consumed only once.

## RPC security

The verifier is read-only. It only permits `eth_chainId`, `eth_getTransactionReceipt`, and `eth_blockNumber`; requires HTTPS; rejects embedded URL credentials; restricts the host to a deployment allowlist; limits response size; uses a timeout; verifies chain ID 8453 before trusting a receipt; and has no method for `eth_sendRawTransaction`.

## Production configuration already staged OFF

Production currently has the public merchant address, Base RPC configuration, Base chain/token configuration and confirmation threshold available as environment configuration. `CRYPTO_PAYMENTS_ENABLED`, `CRYPTO_AUTO_FULFILL_ENABLED`, and `CRYPTO_LEGAL_APPROVED` remain false. Configuration changes were staged without triggering a deployment.

## Pre-activation Council gate

Before changing any OFF flag:

1. GitHub CI must pass on the final candidate commit.
2. Security review must confirm no private signing material is present in source, logs, environment variables used by the public service, or web responses.
3. Legal/regulatory review must confirm the merchant-only scope and current federal/Virginia treatment remain acceptable.
4. Sanctions/compliance procedure must be approved and `CRYPTO_ADMIN_TOKEN` or an approved automated screening provider must be provisioned securely.
5. Tax/accounting treatment and USD FMV record procedure must be approved.
6. Refund/incorrect-network/incorrect-token customer terms must be approved.
7. One deliberately minimal-value controlled transaction must pass the end-to-end flow before public promotion.
8. Human owner must explicitly authorize merge/deployment and separately authorize enabling crypto checkout.

## Kill switch

Set `CRYPTO_PAYMENTS_ENABLED=false` to stop new crypto checkout immediately. `CRYPTO_AUTO_FULFILL_ENABLED=false` independently prevents automatic delivery even for a cleared payment.
