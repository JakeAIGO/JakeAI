from decimal import Decimal

import pytest

from crypto_payment_adapter import BASE_NATIVE_USDC_CONTRACT
from crypto_payment_integration import (
    ComplianceDecision,
    DenyByDefaultComplianceProvider,
    ERC20_TRANSFER_TOPIC,
    SqliteTransactionRegistry,
    parse_base_usdc_transfer,
)


MERCHANT = "0x" + "22" * 20
SENDER = "0x" + "11" * 20
TX_HASH = "0x" + "ab" * 32


def topic_address(address: str) -> str:
    return "0x" + ("0" * 24) + address[2:].lower()


def receipt(*, amount_raw: int = 5_000_000, status: int = 1, block: int = 100):
    return {
        "transactionHash": TX_HASH,
        "status": hex(status),
        "blockNumber": hex(block),
        "logs": [
            {
                "address": BASE_NATIVE_USDC_CONTRACT,
                "topics": [ERC20_TRANSFER_TOPIC, topic_address(SENDER), topic_address(MERCHANT)],
                "data": hex(amount_raw),
            }
        ],
    }


def test_parse_native_usdc_transfer():
    transfer = parse_base_usdc_transfer(
        receipt=receipt(), merchant_address=MERCHANT, latest_confirmed_block=101
    )
    assert transfer.sender == SENDER
    assert transfer.recipient == MERCHANT
    assert transfer.amount_usdc == Decimal("5")
    assert transfer.confirmations == 2
    assert transfer.tx_success is True


def test_parser_rejects_failed_receipt():
    with pytest.raises(ValueError, match="not successful"):
        parse_base_usdc_transfer(
            receipt=receipt(status=0), merchant_address=MERCHANT, latest_confirmed_block=101
        )


def test_parser_rejects_multiple_matching_transfers():
    r = receipt()
    r["logs"].append(dict(r["logs"][0]))
    with pytest.raises(ValueError, match="exactly one"):
        parse_base_usdc_transfer(
            receipt=r, merchant_address=MERCHANT, latest_confirmed_block=101
        )


def test_parser_ignores_wrong_token_and_then_fails_closed():
    r = receipt()
    r["logs"][0]["address"] = "0x" + "33" * 20
    with pytest.raises(ValueError, match="exactly one"):
        parse_base_usdc_transfer(
            receipt=r, merchant_address=MERCHANT, latest_confirmed_block=101
        )


def test_default_compliance_provider_never_clears():
    decision = DenyByDefaultComplianceProvider().screen(
        sender_address=SENDER, tx_hash=TX_HASH
    )
    assert decision.clear is False
    assert decision.provider == "unconfigured"


def test_persistent_registry_enforces_unique_tx_and_order(tmp_path):
    db = tmp_path / "payments.sqlite3"
    registry = SqliteTransactionRegistry(str(db))
    transfer = parse_base_usdc_transfer(
        receipt=receipt(), merchant_address=MERCHANT, latest_confirmed_block=101
    )
    clear = ComplianceDecision(clear=True, provider="test", reference="case-1")
    registry.record(
        TX_HASH,
        order_id="ord_1",
        transfer=transfer,
        block_number=100,
        compliance=clear,
        usd_fmv=Decimal("5.00"),
    )
    assert registry.has(TX_HASH)

    with pytest.raises(ValueError, match="already been consumed"):
        registry.record(
            TX_HASH,
            order_id="ord_2",
            transfer=transfer,
            block_number=100,
            compliance=clear,
        )

    other_tx = "0x" + "cd" * 32
    other_transfer = transfer.__class__(
        chain_id=transfer.chain_id,
        token_contract=transfer.token_contract,
        tx_hash=other_tx,
        sender=transfer.sender,
        recipient=transfer.recipient,
        amount_usdc=transfer.amount_usdc,
        tx_success=True,
        confirmations=transfer.confirmations,
    )
    with pytest.raises(ValueError, match="already been consumed"):
        registry.record(
            other_tx,
            order_id="ord_1",
            transfer=other_transfer,
            block_number=100,
            compliance=clear,
        )


def test_registry_rejects_uncleared_compliance(tmp_path):
    registry = SqliteTransactionRegistry(str(tmp_path / "payments.sqlite3"))
    transfer = parse_base_usdc_transfer(
        receipt=receipt(), merchant_address=MERCHANT, latest_confirmed_block=101
    )
    hold = ComplianceDecision(clear=False, provider="test", reason="hold")
    with pytest.raises(ValueError, match="without compliance clearance"):
        registry.record(
            TX_HASH,
            order_id="ord_1",
            transfer=transfer,
            block_number=100,
            compliance=hold,
        )
