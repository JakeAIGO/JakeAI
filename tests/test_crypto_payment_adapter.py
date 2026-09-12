from decimal import Decimal

from crypto_payment_adapter import (
    BASE_MAINNET_CHAIN_ID,
    BASE_NATIVE_USDC_CONTRACT,
    CryptoPaymentConfig,
    DuplicateTransactionRegistry,
    ObservedTransfer,
    PaymentInvoice,
    PaymentState,
    should_auto_fulfill,
    validate_observed_payment,
)


MERCHANT = "0x1111111111111111111111111111111111111111"
SENDER = "0x2222222222222222222222222222222222222222"
TX = "0x" + "a" * 64


def config(*, enabled=True, auto=False):
    return CryptoPaymentConfig(
        enabled=enabled,
        auto_fulfill_enabled=auto,
        chain_id=BASE_MAINNET_CHAIN_ID,
        token_contract=BASE_NATIVE_USDC_CONTRACT,
        merchant_address=MERCHANT,
    )


def transfer(*, amount="5.00", chain_id=BASE_MAINNET_CHAIN_ID, token=BASE_NATIVE_USDC_CONTRACT, recipient=MERCHANT, success=True, confirmations=1, tx_hash=TX):
    return ObservedTransfer(
        chain_id=chain_id,
        token_contract=token,
        tx_hash=tx_hash,
        sender=SENDER,
        recipient=recipient,
        amount_usdc=Decimal(amount),
        tx_success=success,
        confirmations=confirmations,
    )


def invoice():
    return PaymentInvoice.create("ord_test", "5.00", MERCHANT)


def test_disabled_by_default_behavior_is_fail_closed():
    result = validate_observed_payment(
        config=config(enabled=False),
        invoice=invoice(),
        transfer=transfer(),
        tx_registry=DuplicateTransactionRegistry(),
        compliance_clear=True,
    )
    assert result.accepted is False
    assert result.state == PaymentState.FAILED


def test_valid_payment_stops_at_compliance_hold_without_clearance():
    result = validate_observed_payment(
        config=config(),
        invoice=invoice(),
        transfer=transfer(),
        tx_registry=DuplicateTransactionRegistry(),
        compliance_clear=False,
    )
    assert result.accepted is False
    assert result.state == PaymentState.COMPLIANCE_HOLD


def test_valid_cleared_payment_is_accepted_once():
    registry = DuplicateTransactionRegistry()
    first = validate_observed_payment(
        config=config(),
        invoice=invoice(),
        transfer=transfer(),
        tx_registry=registry,
        compliance_clear=True,
    )
    second = validate_observed_payment(
        config=config(),
        invoice=invoice(),
        transfer=transfer(),
        tx_registry=registry,
        compliance_clear=True,
    )
    assert first.accepted is True
    assert first.state == PaymentState.COMPLIANCE_CLEAR
    assert second.accepted is False
    assert second.state == PaymentState.FAILED


def test_wrong_chain_is_rejected():
    result = validate_observed_payment(
        config=config(),
        invoice=invoice(),
        transfer=transfer(chain_id=1),
        tx_registry=DuplicateTransactionRegistry(),
        compliance_clear=True,
    )
    assert result.state == PaymentState.WRONG_TOKEN_OR_NETWORK


def test_wrong_token_is_rejected():
    result = validate_observed_payment(
        config=config(),
        invoice=invoice(),
        transfer=transfer(token="0x3333333333333333333333333333333333333333"),
        tx_registry=DuplicateTransactionRegistry(),
        compliance_clear=True,
    )
    assert result.state == PaymentState.WRONG_TOKEN_OR_NETWORK


def test_wrong_recipient_is_rejected():
    result = validate_observed_payment(
        config=config(),
        invoice=invoice(),
        transfer=transfer(recipient="0x4444444444444444444444444444444444444444"),
        tx_registry=DuplicateTransactionRegistry(),
        compliance_clear=True,
    )
    assert result.state == PaymentState.FAILED


def test_underpayment_and_overpayment_require_no_fulfillment():
    under = validate_observed_payment(
        config=config(),
        invoice=invoice(),
        transfer=transfer(amount="4.99"),
        tx_registry=DuplicateTransactionRegistry(),
        compliance_clear=True,
    )
    over = validate_observed_payment(
        config=config(),
        invoice=invoice(),
        transfer=transfer(amount="5.01", tx_hash="0x" + "b" * 64),
        tx_registry=DuplicateTransactionRegistry(),
        compliance_clear=True,
    )
    assert under.state == PaymentState.UNDERPAID
    assert over.state == PaymentState.OVERPAID


def test_insufficient_confirmations_stays_detected():
    result = validate_observed_payment(
        config=config(),
        invoice=invoice(),
        transfer=transfer(confirmations=0),
        tx_registry=DuplicateTransactionRegistry(),
        compliance_clear=True,
    )
    assert result.state == PaymentState.DETECTED


def test_auto_fulfill_requires_separate_flag():
    result = validate_observed_payment(
        config=config(),
        invoice=invoice(),
        transfer=transfer(),
        tx_registry=DuplicateTransactionRegistry(),
        compliance_clear=True,
    )
    assert should_auto_fulfill(config(auto=False), result) is False
    assert should_auto_fulfill(config(auto=True), result) is True
