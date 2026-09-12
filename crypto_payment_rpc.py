"""Read-only Base RPC verification for JakeAI merchant USDC payments.

This module never signs or broadcasts transactions. It only reads public
blockchain data, parses a Base native-USDC receipt, validates it against a JakeAI
invoice, requires an external compliance clearance, and then records the
transaction once. Live checkout remains separately feature-gated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable
from urllib import request

from crypto_payment_adapter import (
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


@dataclass(frozen=True)
class RpcVerificationResult:
    validation: ValidationResult
    compliance: ComplianceDecision
    tx_hash: str
    block_number: int | None
    recorded: bool


class BaseRpcClient:
    """Minimal read-only JSON-RPC client.

    The endpoint is supplied at runtime. No wallet key or signing capability is
    accepted by this class.
    """

    def __init__(self, rpc_url: str, timeout_seconds: int = 10) -> None:
        self.rpc_url = str(rpc_url).strip()
        self.timeout_seconds = int(timeout_seconds)
        if not self.rpc_url.startswith("https://"):
            raise ValueError("Base RPC URL must use HTTPS")

    def call(self, method: str, params: list) -> object:
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        ).encode("utf-8")
        req = request.Request(
            self.rpc_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        if body.get("error"):
            raise RuntimeError(f"Base RPC error: {body['error']}")
        if "result" not in body:
            raise RuntimeError("Base RPC response missing result")
        return body["result"]

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
    """Verify one customer-supplied transaction hash, fail-closed.

    Payment is never recorded unless receipt validation and the independent
    compliance decision both pass.
    """

    if not config.enabled:
        return RpcVerificationResult(
            validation=ValidationResult(False, PaymentState.FAILED, "crypto payments are disabled"),
            compliance=ComplianceDecision(False, provider="not-run", reason="payments disabled"),
            tx_hash=tx_hash,
            block_number=None,
            recorded=False,
        )

    receipt = rpc.transaction_receipt(tx_hash)
    if receipt is None:
        return RpcVerificationResult(
            validation=ValidationResult(False, PaymentState.AWAITING_PAYMENT, "transaction not found or not yet mined"),
            compliance=ComplianceDecision(False, provider="not-run", reason="receipt unavailable"),
            tx_hash=tx_hash,
            block_number=None,
            recorded=False,
        )

    latest_block = rpc.latest_block_number()
    transfer = parse_base_usdc_transfer(
        receipt=receipt,
        merchant_address=invoice.merchant_address,
        latest_confirmed_block=latest_block,
    )

    # Require the receipt itself to be for the submitted hash.
    normalized_submitted = str(tx_hash).strip().lower()
    if transfer.tx_hash != normalized_submitted:
        return RpcVerificationResult(
            validation=ValidationResult(False, PaymentState.FAILED, "receipt hash does not match submitted transaction"),
            compliance=ComplianceDecision(False, provider="not-run", reason="hash mismatch"),
            tx_hash=normalized_submitted,
            block_number=None,
            recorded=False,
        )

    if registry.has(transfer.tx_hash):
        return RpcVerificationResult(
            validation=ValidationResult(False, PaymentState.FAILED, "transaction hash has already been consumed"),
            compliance=ComplianceDecision(False, provider="not-run", reason="duplicate transaction"),
            tx_hash=transfer.tx_hash,
            block_number=int(receipt["blockNumber"], 16),
            recorded=False,
        )

    # Use an in-memory guard inside validation, then rely on SQLite uniqueness as
    # the authoritative persistent replay protection when recording.
    transient_registry = DuplicateTransactionRegistry()
    compliance = compliance_provider.screen(
        sender_address=transfer.sender,
        tx_hash=transfer.tx_hash,
    )
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

    registry.record(
        transfer.tx_hash,
        order_id=invoice.order_id,
        transfer=transfer,
        block_number=block_number,
        compliance=compliance,
        usd_fmv=usd_fmv,
    )
    return RpcVerificationResult(
        validation=validation,
        compliance=compliance,
        tx_hash=transfer.tx_hash,
        block_number=block_number,
        recorded=True,
    )
