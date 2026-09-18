import sqlite3
import pytest
from fastapi import HTTPException
import commerce_app

def setup_db(monkeypatch,tmp_path):
    db=str(tmp_path/"commerce.db")
    monkeypatch.setattr(commerce_app,"COMMERCE_DB_PATH",db)
    commerce_app._init_commerce_tables()
    return db

def test_paid_order_issues_idempotent_entitlement_and_receipt(monkeypatch,tmp_path):
    setup_db(monkeypatch,tmp_path)
    oid=commerce_app._create_order("prod_test",500,"pending_payment","test")
    commerce_app._mark_order_paid(oid,"cs_test")
    first=commerce_app._issue_entitlement_and_receipt(oid,"card","cs_test")
    second=commerce_app._issue_entitlement_and_receipt(oid,"card","cs_test")
    assert first==second
    receipt=commerce_app._get_receipt(oid)
    assert receipt["amount_cents"]==500
    assert receipt["payment_rail"]=="card"
    assert receipt["entitlement_status"]=="active"
    assert receipt["buyer_type"]=="human"

def test_unpaid_order_cannot_receive_entitlement(monkeypatch,tmp_path):
    setup_db(monkeypatch,tmp_path)
    oid=commerce_app._create_order("prod_test",500,"pending_payment","test")
    with pytest.raises(HTTPException) as exc:
        commerce_app._issue_entitlement_and_receipt(oid,"card","cs_test")
    assert exc.value.status_code==409

def test_machine_receipt_preserves_agent_authority(monkeypatch,tmp_path):
    setup_db(monkeypatch,tmp_path)
    oid=commerce_app._create_order("prod_test",500,"pending_payment","agent-test")
    commerce_app._mark_order_paid(oid,"agent-payment")
    commerce_app._issue_entitlement_and_receipt(oid,"card","agent-payment",buyer_type="agent",principal="did:a2a:buyer-agent",authorized_by="did:a2a:principal")
    receipt=commerce_app._get_receipt(oid)
    assert receipt["buyer_type"]=="agent"
    assert receipt["principal"]=="did:a2a:buyer-agent"
    assert receipt["authorized_by"]=="did:a2a:principal"
