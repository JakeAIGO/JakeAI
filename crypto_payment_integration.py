"""Persistent, fail-closed integration helpers for JakeAI crypto checkout v0.1.

This module does not initiate transactions, hold customer funds, exchange assets,
or enable live checkout. It turns Base transaction receipts into normalized USDC
observations, persists transaction replay protection, and requires an independent
compliance decision before fulfillment can be considered.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol

from crypto_payment_adapter import (
    BASE_MAINNET_CHAIN_ID,
    BASE_NATIVE_USDC_CONTRACT,
    ObservedTransfer,
    USDC_DECIMALS,
)

ERC20_TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)


@dataclass(frozen=True)
class ComplianceDecision:
    clear: bool
    provider: str
    reference: str | None = None
    reason: str = ""


class ComplianceProvider(Protocol):
    def screen(self, *, sender_address: str, tx_hash: str) -> ComplianceDecision:
        ...


class DenyByDefaultComplianceProvider:
    def screen(self, *, sender_address: str, tx_hash: str) -> ComplianceDecision:
        return ComplianceDecision(
            clear=False,
            provider="unconfigured",
            reason="no approved compliance screening provider/process configured",
        )


class SqliteTransactionRegistry:
    """Persistent replay guard with database-enforced unique tx/order IDs."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crypto_consumed_transactions (
                    tx_hash TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL UNIQUE,
                    chain_id INTEGER NOT NULL,
                    token_contract TEXT NOT NULL,
                    sender_address TEXT NOT NULL,
                    recipient_address TEXT NOT NULL,
                    amount_usdc TEXT NOT NULL,
                    block_number INTEGER,
                    compliance_provider TEXT NOT NULL,
                    compliance_reference TEXT,
                    usd_fmv TEXT,
                    consumed_at TEXT NOT NULL
                )
                """
            )

    def get(self, tx_hash: str) -> dict | None:
        tx_hash = tx_hash.strip().lower()
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM crypto_consumed_transactions WHERE tx_hash = ?",
                (tx_hash,),
            ).fetchone()
        return dict(row) if row else None

    def has(self, tx_hash: str) -> bool:
        return self.get(tx_hash) is not None

    def record(
        self,
        tx_hash: str,
        *,
        order_id: str,
        transfer: ObservedTransfer,
        block_number: int | None,
        compliance: ComplianceDecision,
        usd_fmv: Decimal | None = None,
    ) -> None:
        if not compliance.clear:
            raise ValueError("cannot consume transaction without compliance clearance")
        t = transfer.normalized()
        supplied_tx = tx_hash.strip().lower()
        if supplied_tx != t.tx_hash:
            raise ValueError("transaction hash does not match normalized transfer")
        if not order_id.strip():
            raise ValueError("order_id is required")
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO crypto_consumed_transactions (
                        tx_hash, order_id, chain_id, token_contract,
                        sender_address, recipient_address, amount_usdc,
                        block_number, compliance_provider, compliance_reference,
                        usd_fmv, consumed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        t.tx_hash,
                        order_id.strip(),
                        t.chain_id,
                        t.token_contract,
                        t.sender,
                        t.recipient,
                        str(t.amount_usdc),
                        block_number,
                        compliance.provider,
                        compliance.reference,
                        str(usd_fmv) if usd_fmv is not None else None,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("transaction hash or order has already been consumed") from exc


def parse_base_usdc_transfer(
    *,
    receipt: dict,
    merchant_address: str,
    latest_confirmed_block: int,
) -> ObservedTransfer:
    tx_hash = _hex(receipt.get("transactionHash"), 64, "transaction hash")
    status = receipt.get("status")
    if _quantity(status, "status") != 1:
        raise ValueError("transaction receipt is not successful")

    block_number = _quantity(receipt.get("blockNumber"), "block number")
    if latest_confirmed_block < block_number:
        raise ValueError("latest confirmed block precedes transaction block")

    merchant = _address(merchant_address)
    matches: list[ObservedTransfer] = []
    for log in receipt.get("logs") or []:
        try:
            contract = _address(log.get("address"))
        except ValueError:
            continue
        if contract != BASE_NATIVE_USDC_CONTRACT:
            continue

        topics = log.get("topics") or []
        if len(topics) < 3 or str(topics[0]).lower() != ERC20_TRANSFER_TOPIC:
            continue
        sender = _topic_address(topics[1])
        recipient = _topic_address(topics[2])
        if recipient != merchant:
            continue

        raw_amount = _quantity(log.get("data"), "USDC transfer amount")
        amount = Decimal(raw_amount) / (Decimal(10) ** USDC_DECIMALS)
        matches.append(
            ObservedTransfer(
                chain_id=BASE_MAINNET_CHAIN_ID,
                token_contract=contract,
                tx_hash=tx_hash,
                sender=sender,
                recipient=recipient,
                amount_usdc=amount,
                tx_success=True,
                confirmations=(latest_confirmed_block - block_number) + 1,
            )
        )

    if len(matches) != 1:
        raise ValueError("expected exactly one native-USDC transfer to merchant")
    return matches[0]


def _quantity(value: object, label: str) -> int:
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"invalid {label}")
        return value
    if isinstance(value, str) and value.startswith("0x"):
        try:
            result = int(value, 16)
        except ValueError as exc:
            raise ValueError(f"invalid {label}") from exc
        if result < 0:
            raise ValueError(f"invalid {label}")
        return result
    raise ValueError(f"invalid {label}")


def _hex(value: object, hex_chars: int, label: str) -> str:
    text = str(value or "").strip().lower()
    if not text.startswith("0x") or len(text) != 2 + hex_chars:
        raise ValueError(f"invalid {label}")
    try:
        int(text[2:], 16)
    except ValueError as exc:
        raise ValueError(f"invalid {label}") from exc
    return text


def _address(value: object) -> str:
    return _hex(value, 40, "EVM address")


def _topic_address(value: object) -> str:
    topic = _hex(value, 64, "address topic")
    return "0x" + topic[-40:]
