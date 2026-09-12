from decimal import Decimal

from crypto_payment_adapter import CryptoPaymentConfig, PaymentInvoice
from crypto_payment_integration import ComplianceDecision, DenyByDefaultComplianceProvider, SqliteTransactionRegistry
from crypto_payment_rpc import verify_submitted_payment


MERCHANT = "0x" + "22" * 20
SENDER = "0x" + "11" * 20
TX_HASH = "0x" + "ab" * 32
USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def topic_address(address: str) -> str:
    return "0x" + "0" * 24 + address[2:]


def receipt(amount_raw=5_000_000):
    return {
        "transactionHash": TX_HASH,
        "status": "0x1",
        "blockNumber": "0x64",
        "logs": [{
            "address": USDC,
            "topics": [TRANSFER_TOPIC, topic_address(SENDER), topic_address(MERCHANT)],
            "data": hex(amount_raw),
        }],
    }


class FakeRpc:
    def __init__(self, receipt_value, chain_id=8453):
        self.receipt_value = receipt_value
        self._chain_id = chain_id

    def chain_id(self):
        return self._chain_id

    def transaction_receipt(self, tx_hash):
        return self.receipt_value

    def latest_block_number(self):
        return 101


class ClearCompliance:
    def screen(self, *, sender_address, tx_hash):
        return ComplianceDecision(True, provider="test", reference="clear-1")


def config(enabled=True):
    return CryptoPaymentConfig(
        enabled=enabled,
        auto_fulfill_enabled=False,
        chain_id=8453,
        token_contract=USDC,
        merchant_address=MERCHANT,
    )


def invoice():
    return PaymentInvoice.create("ord_1", "5.00", MERCHANT)


def test_disabled_mode_does_not_query_or_record(tmp_path):
    registry = SqliteTransactionRegistry(str(tmp_path / "db.sqlite3"))
    result = verify_submitted_payment(
        rpc=FakeRpc(receipt()), config=config(False), invoice=invoice(), tx_hash=TX_HASH,
        compliance_provider=ClearCompliance(), registry=registry,
    )
    assert result.recorded is False
    assert result.validation.accepted is False


def test_wrong_rpc_chain_fails_closed(tmp_path):
    registry = SqliteTransactionRegistry(str(tmp_path / "db.sqlite3"))
    result = verify_submitted_payment(
        rpc=FakeRpc(receipt(), chain_id=1), config=config(), invoice=invoice(), tx_hash=TX_HASH,
        compliance_provider=ClearCompliance(), registry=registry,
    )
    assert result.recorded is False
    assert result.validation.state.value == "wrong_token_or_network"


def test_missing_receipt_stays_awaiting_payment(tmp_path):
    registry = SqliteTransactionRegistry(str(tmp_path / "db.sqlite3"))
    result = verify_submitted_payment(
        rpc=FakeRpc(None), config=config(), invoice=invoice(), tx_hash=TX_HASH,
        compliance_provider=ClearCompliance(), registry=registry,
    )
    assert result.recorded is False
    assert result.validation.state.value == "awaiting_payment"


def test_compliance_hold_never_records(tmp_path):
    registry = SqliteTransactionRegistry(str(tmp_path / "db.sqlite3"))
    result = verify_submitted_payment(
        rpc=FakeRpc(receipt()), config=config(), invoice=invoice(), tx_hash=TX_HASH,
        compliance_provider=DenyByDefaultComplianceProvider(), registry=registry,
        minimum_confirmations=2,
    )
    assert result.recorded is False
    assert result.validation.state.value == "compliance_hold"
    assert not registry.has(TX_HASH)


def test_clear_payment_records_once(tmp_path):
    registry = SqliteTransactionRegistry(str(tmp_path / "db.sqlite3"))
    result = verify_submitted_payment(
        rpc=FakeRpc(receipt()), config=config(), invoice=invoice(), tx_hash=TX_HASH,
        compliance_provider=ClearCompliance(), registry=registry,
        minimum_confirmations=2, usd_fmv=Decimal("5.00"),
    )
    assert result.recorded is True
    assert result.validation.accepted is True
    assert registry.has(TX_HASH)

    again = verify_submitted_payment(
        rpc=FakeRpc(receipt()), config=config(), invoice=invoice(), tx_hash=TX_HASH,
        compliance_provider=ClearCompliance(), registry=registry,
        minimum_confirmations=2,
    )
    assert again.recorded is False
    assert "already been consumed" in again.validation.reason


def test_wrong_amount_is_not_recorded(tmp_path):
    registry = SqliteTransactionRegistry(str(tmp_path / "db.sqlite3"))
    result = verify_submitted_payment(
        rpc=FakeRpc(receipt(amount_raw=4_000_000)), config=config(), invoice=invoice(), tx_hash=TX_HASH,
        compliance_provider=ClearCompliance(), registry=registry, minimum_confirmations=2,
    )
    assert result.recorded is False
    assert result.validation.state.value == "underpaid"
