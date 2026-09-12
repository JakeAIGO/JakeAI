"""Read-only Base RPC verification for JakeAI merchant USDC payments.

No signing or broadcasting capability exists here. RPC configuration is deploy-
controlled, HTTPS-only, host-allowlisted, response-size-limited, and verified to
be Base Mainnet before payment data is trusted.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable
from urllib import request
from urllib.parse import urlparse

from crypto_payment_adapter import (
    BASE_MAINNET_CHAIN_ID,
    CryptoPaymentConfig,
    DuplicateTransactionRegistry,
    PaymentInvoice,
    PaymentState,
    ValidationResult,
    validate_observed_payment,
)
from crypto_payment_integration import (
    ComplianceDecision,
    ComplianceProvider,
    SqliteTransactionRegistry,
    parse_base_usdc_transfer,
)

JsonRpcCaller = Callable[[str, list], object]
DEFAULT_ALLOWED_RPC_HOSTS = {"mainnet.base.org"}
MAX_RPC_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True)
class RpcVerificationResult:
    validation: ValidationResult
    compliance: ComplianceDecision
    tx_hash: str
    block_number: int | None
    recorded: bool


class BaseRpcClient:
    def __init__(self, rpc_url: str, timeout_seconds: int = 10) -> None:
        self.rpc_url = str(rpc_url).strip()
        self.timeout_seconds = int(timeout_seconds)
        parsed = urlparse(self.rpc_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("Base RPC URL must use HTTPS")
        configured = {
            h.strip().lower()
            for h in os.environ.get("BASE_RPC_ALLOWED_HOSTS", "mainnet.base.org").split(",")
            if h.strip()
        }
        allowed_hosts = configured or DEFAULT_ALLOWED_RPC_HOSTS
        if parsed.hostname.lower() not in allowed_hosts:
            raise ValueError("Base RPC host is not allowlisted")
        if parsed.username or parsed.password:
            raise ValueError("Base RPC URL must not embed credentials")

    def call(self, method: str, params: list) -> object:
        if method not in {"eth_getTransactionReceipt", "eth_blockNumber", "eth_chainId"}:
            raise ValueError("RPC method is not allowed")
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
        req = request.Request(self.rpc_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            raw = response.read(MAX_RPC_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RPC_RESPONSE_BYTES:
            raise RuntimeError("Base RPC response exceeded size limit")
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Base RPC returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise RuntimeError("Base RPC returned unexpected response")
        if body.get("error"):
            raise RuntimeError(f"Base RPC error: {body['error']}")
        if "result" not in body:
            raise RuntimeError("Base RPC response missing result")
        return body["result"]

    def chain_id(self) -> int:
        result = self.call("eth_chainId", [])
        if not isinstance(result, str) or not result.startswith("0x"):
            raise RuntimeError("unexpected chain ID response")
        return int(result, 16)

    def transaction_receipt(self, tx_hash: str) -> dict | None:
        result = self.call("eth_getTransactionReceipt", [tx_hash])
        if result is None:
            return None
        if not isinstance(result, dict):
            raise RuntimeError("unexpected receipt response")
        return result

    def latest_block_number(self) -> int:
        result = self.call("eth_blockNumber", [])
        if not isinstance(result, str) or not result.startswith("0x"):
            raise RuntimeError("unexpected block number response")
        return int(result, 16)


def _same_order_record(existing: dict | None, invoice: PaymentInvoice, transfer) -> bool:
    if not existing:
        return False
    return bool(
        existing.get("order_id") == invoice.order_id
        and int(existing.get("chain_id")) == int(transfer.chain_id)
        and str(existing.get("token_contract", "")).lower() == transfer.token_contract.lower()
        and str(existing.get("recipient_address", "")).lower() == transfer.recipient.lower()
        and Decimal(str(existing.get("amount_usdc"))) == transfer.amount_usdc
    )


def _existing_success(existing: dict, transfer, receipt: dict) -> RpcVerificationResult:
    compliance = ComplianceDecision(
        clear=True,
        provider=existing.get("compliance_provider") or "recorded",
        reference=existing.get("compliance_reference"),
        reason="payment was previously compliance-cleared and recorded for this order",
    )
    return RpcVerificationResult(
        validation=ValidationResult(True, PaymentState.COMPLIANCE_CLEAR, "payment was already recorded for this order"),
        compliance=compliance,
        tx_hash=transfer.tx_hash,
        block_number=int(receipt["blockNumber"], 16),
        recorded=True,
    )


def verify_submitted_payment(
    *,
    rpc: BaseRpcClient,
    config: CryptoPaymentConfig,
    invoice: PaymentInvoice,
    tx_hash: str,
    compliance_provider: ComplianceProvider,
    registry: SqliteTransactionRegistry,
    minimum_confirmations: int = 2,
    usd_fmv: Decimal | None = None,
) -> RpcVerificationResult:
    if not config.enabled:
        return RpcVerificationResult(
            validation=ValidationResult(False, PaymentState.FAILED, "crypto payments are disabled"),
            compliance=ComplianceDecision(False, provider="not-run", reason="payments disabled"),
            tx_hash=tx_hash, block_number=None, recorded=False,
        )
    if rpc.chain_id() != BASE_MAINNET_CHAIN_ID:
        return RpcVerificationResult(
            validation=ValidationResult(False, PaymentState.WRONG_TOKEN_OR_NETWORK, "RPC endpoint is not Base Mainnet"),
            compliance=ComplianceDecision(False, provider="not-run", reason="wrong RPC chain"),
            tx_hash=tx_hash, block_number=None, recorded=False,
        )

    receipt = rpc.transaction_receipt(tx_hash)
    if receipt is None:
        return RpcVerificationResult(
            validation=ValidationResult(False, PaymentState.AWAITING_PAYMENT, "transaction not found or not yet mined"),
            compliance=ComplianceDecision(False, provider="not-run", reason="receipt unavailable"),
            tx_hash=tx_hash, block_number=None, recorded=False,
        )

    latest_block = rpc.latest_block_number()
    transfer = parse_base_usdc_transfer(receipt=receipt, merchant_address=invoice.merchant_address, latest_confirmed_block=latest_block)
    normalized_submitted = str(tx_hash).strip().lower()
    if transfer.tx_hash != normalized_submitted:
        return RpcVerificationResult(
            validation=ValidationResult(False, PaymentState.FAILED, "receipt hash does not match submitted transaction"),
            compliance=ComplianceDecision(False, provider="not-run", reason="hash mismatch"),
            tx_hash=normalized_submitted, block_number=None, recorded=False,
        )

    existing = registry.get(transfer.tx_hash)
    if existing:
        if _same_order_record(existing, invoice, transfer):
            return _existing_success(existing, transfer, receipt)
        return RpcVerificationResult(
            validation=ValidationResult(False, PaymentState.FAILED, "transaction hash has already been consumed by another order"),
            compliance=ComplianceDecision(False, provider="not-run", reason="duplicate transaction"),
            tx_hash=transfer.tx_hash, block_number=int(receipt["blockNumber"], 16), recorded=False,
        )

    transient_registry = DuplicateTransactionRegistry()
    compliance = compliance_provider.screen(sender_address=transfer.sender, tx_hash=transfer.tx_hash)
    validation = validate_observed_payment(
        config=config,
        invoice=invoice,
        transfer=transfer,
        tx_registry=transient_registry,
        minimum_confirmations=minimum_confirmations,
        compliance_clear=compliance.clear,
    )
    block_number = int(receipt["blockNumber"], 16)
    if not validation.accepted:
        return RpcVerificationResult(
            validation=validation,
            compliance=compliance,
            tx_hash=transfer.tx_hash,
            block_number=block_number,
            recorded=False,
        )

    try:
        registry.record(
            transfer.tx_hash,
            order_id=invoice.order_id,
            transfer=transfer,
            block_number=block_number,
            compliance=compliance,
            usd_fmv=usd_fmv,
        )
    except ValueError:
        existing = registry.get(transfer.tx_hash)
        if _same_order_record(existing, invoice, transfer):
            return _existing_success(existing, transfer, receipt)
        raise

    return RpcVerificationResult(
        validation=validation,
        compliance=compliance,
        tx_hash=transfer.tx_hash,
        block_number=block_number,
        recorded=True,
    )
