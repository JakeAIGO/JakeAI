"""JakeAI merchant-only stablecoin payment adapter (v0.1).

This module is intentionally fail-closed and is NOT wired into live checkout.
It validates normalized on-chain USDC payment observations for JakeAI-owned
products only. It does not exchange, custody customer funds, transmit funds for
third parties, or perform creator payouts.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Optional


BASE_MAINNET_CHAIN_ID = 8453
# Native USDC on Base. Contract address must be independently re-verified before activation.
BASE_NATIVE_USDC_CONTRACT = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
USDC_DECIMALS = 6


class PaymentState(str, Enum):
    CREATED = "created"
    AWAITING_PAYMENT = "awaiting_payment"
    DETECTED = "detected"
    VALIDATED = "validated"
    COMPLIANCE_HOLD = "compliance_hold"
    COMPLIANCE_CLEAR = "compliance_clear"
    PAID = "paid"
    FULFILLED = "fulfilled"
    EXPIRED = "expired"
    UNDERPAID = "underpaid"
    OVERPAID = "overpaid"
    WRONG_TOKEN_OR_NETWORK = "wrong_token_or_network"
    FAILED = "failed"


@dataclass(frozen=True)
class CryptoPaymentConfig:
    enabled: bool
    auto_fulfill_enabled: bool
    chain_id: int
    token_contract: str
    merchant_address: Optional[str]
    creator_payouts_enabled: bool = False
    customer_custody_enabled: bool = False
    exchange_functions_enabled: bool = False

    @classmethod
    def from_env(cls) -> "CryptoPaymentConfig":
        return cls(
            enabled=_env_bool("CRYPTO_PAYMENTS_ENABLED", False),
            auto_fulfill_enabled=_env_bool("CRYPTO_AUTO_FULFILL_ENABLED", False),
            chain_id=int(os.environ.get("CRYPTO_SUPPORTED_CHAIN_ID", str(BASE_MAINNET_CHAIN_ID))),
            token_contract=os.environ.get(
                "CRYPTO_SUPPORTED_TOKEN_CONTRACT", BASE_NATIVE_USDC_CONTRACT
            ).strip().lower(),
            merchant_address=_normalize_optional_address(
                os.environ.get("CRYPTO_MERCHANT_ADDRESS")
            ),
        )

    def activation_errors(self) -> list[str]:
        errors: list[str] = []
        if self.creator_payouts_enabled:
            errors.append("creator payouts are prohibited in merchant-only v0.1")
        if self.customer_custody_enabled:
            errors.append("customer custody is prohibited in merchant-only v0.1")
        if self.exchange_functions_enabled:
            errors.append("exchange functions are prohibited in merchant-only v0.1")
        if self.chain_id != BASE_MAINNET_CHAIN_ID:
            errors.append("unsupported chain")
        if self.token_contract != BASE_NATIVE_USDC_CONTRACT:
            errors.append("unsupported token contract")
        if self.enabled and not self.merchant_address:
            errors.append("merchant address is required before crypto payments can be enabled")
        return errors


@dataclass(frozen=True)
class PaymentInvoice:
    order_id: str
    amount_usd: Decimal
    amount_usdc: Decimal
    merchant_address: str
    state: PaymentState = PaymentState.AWAITING_PAYMENT

    @classmethod
    def create(cls, order_id: str, amount_usd: str | Decimal, merchant_address: str) -> "PaymentInvoice":
        usd = _money(amount_usd)
        if usd <= 0:
            raise ValueError("crypto invoice amount must be greater than zero")
        # For USDC merchant checkout v0.1, USD is the unit of account and the
        # requested stablecoin amount is 1:1. A future price/depeg policy can
        # replace this without changing order accounting.
        return cls(
            order_id=order_id,
            amount_usd=usd,
            amount_usdc=usd,
            merchant_address=_require_address(merchant_address),
        )


@dataclass(frozen=True)
class ObservedTransfer:
    chain_id: int
    token_contract: str
    tx_hash: str
    sender: str
    recipient: str
    amount_usdc: Decimal
    tx_success: bool
    confirmations: int

    def normalized(self) -> "ObservedTransfer":
        return ObservedTransfer(
            chain_id=int(self.chain_id),
            token_contract=_require_address(self.token_contract),
            tx_hash=_require_tx_hash(self.tx_hash),
            sender=_require_address(self.sender),
            recipient=_require_address(self.recipient),
            amount_usdc=_money(self.amount_usdc),
            tx_success=bool(self.tx_success),
            confirmations=max(0, int(self.confirmations)),
        )


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    state: PaymentState
    reason: str


class DuplicateTransactionRegistry:
    """Minimal in-memory replay guard for tests and single-process demos.

    Production must replace this with a unique database constraint on tx_hash.
    """

    def __init__(self) -> None:
        self._used: set[str] = set()

    def has(self, tx_hash: str) -> bool:
        return tx_hash.lower() in self._used

    def record(self, tx_hash: str) -> None:
        self._used.add(_require_tx_hash(tx_hash))


def validate_observed_payment(
    *,
    config: CryptoPaymentConfig,
    invoice: PaymentInvoice,
    transfer: ObservedTransfer,
    tx_registry: DuplicateTransactionRegistry,
    minimum_confirmations: int = 1,
    compliance_clear: bool = False,
) -> ValidationResult:
    """Validate a normalized transfer without spending or moving any funds.

    `compliance_clear` is deliberately supplied by a separate compliance layer.
    This adapter never assumes sanctions screening has passed.
    """

    errors = config.activation_errors()
    if errors:
        return ValidationResult(False, PaymentState.FAILED, "; ".join(errors))
    if not config.enabled:
        return ValidationResult(False, PaymentState.FAILED, "crypto payments are disabled")

    t = transfer.normalized()

    if t.chain_id != config.chain_id or t.token_contract != config.token_contract:
        return ValidationResult(
            False,
            PaymentState.WRONG_TOKEN_OR_NETWORK,
            "payment used an unsupported chain or token contract",
        )
    if t.recipient != invoice.merchant_address.lower():
        return ValidationResult(False, PaymentState.FAILED, "recipient does not match merchant wallet")
    if not t.tx_success:
        return ValidationResult(False, PaymentState.FAILED, "transaction receipt is not successful")
    if t.confirmations < minimum_confirmations:
        return ValidationResult(False, PaymentState.DETECTED, "payment detected but confirmation threshold not met")
    if tx_registry.has(t.tx_hash):
        return ValidationResult(False, PaymentState.FAILED, "transaction hash has already been consumed")

    if t.amount_usdc < invoice.amount_usdc:
        return ValidationResult(False, PaymentState.UNDERPAID, "received less USDC than invoiced")
    if t.amount_usdc > invoice.amount_usdc:
        return ValidationResult(False, PaymentState.OVERPAID, "received more USDC than invoiced; manual review required")

    if not compliance_clear:
        return ValidationResult(False, PaymentState.COMPLIANCE_HOLD, "payment awaits independent compliance clearance")

    tx_registry.record(t.tx_hash)
    return ValidationResult(True, PaymentState.COMPLIANCE_CLEAR, "payment validated and compliance-cleared")


def should_auto_fulfill(config: CryptoPaymentConfig, validation: ValidationResult) -> bool:
    """Fail-closed fulfillment gate.

    Even a valid payment cannot auto-fulfill unless the separate environment
    flag is deliberately enabled.
    """

    return bool(
        config.enabled
        and config.auto_fulfill_enabled
        and validation.accepted
        and validation.state == PaymentState.COMPLIANCE_CLEAR
        and not config.activation_errors()
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_optional_address(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None
    return _require_address(value)


def _require_address(value: str) -> str:
    value = str(value).strip().lower()
    if not re.fullmatch(r"0x[a-f0-9]{40}", value):
        raise ValueError("invalid EVM address")
    return value


def _require_tx_hash(value: str) -> str:
    value = str(value).strip().lower()
    if not re.fullmatch(r"0x[a-f0-9]{64}", value):
        raise ValueError("invalid transaction hash")
    return value


def _money(value: str | Decimal) -> Decimal:
    try:
        result = Decimal(str(value)).quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid monetary amount") from exc
    return result
