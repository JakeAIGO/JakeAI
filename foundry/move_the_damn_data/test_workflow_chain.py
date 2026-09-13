from workflow_chain import MoveTheDamnDataChain


def full_case():
    return {
        "lead": {
            "name": "Test Customer",
            "email": "customer@example.com",
            "request": "Need a verified service quote",
            "opt_in": True,
        },
        "quote": {
            "customer_name": "Test Customer",
            "scope": "Verified scope only",
            "verified_price": "1250.00",
            "price_verified": True,
        },
        "job": {
            "job_id": "JOB-001",
            "approved_scope": "Verified scope only",
            "status": "scheduled",
            "quote_approved": True,
        },
        "invoice": {
            "invoice_id": "INV-001",
            "quoted_total": "1250.00",
            "invoice_total": "1250.00",
        },
        "follow_up": {
            "recipient": "customer@example.com",
            "purpose": "completion follow-up",
            "message": "Your verified job record is complete.",
            "communication_allowed": True,
        },
    }


def test_full_chain_stops_at_external_approval_gate():
    chain = MoveTheDamnDataChain()
    results = chain.run_case("case-001", full_case())
    assert [r.stage for r in results] == ["lead", "quote", "job", "invoice", "follow_up"]
    assert [r.status for r in results] == ["completed", "prepared", "completed", "completed", "awaiting_approval"]
    assert results[-1].output["delivery_state"] == "prepared_not_sent"
    assert results[-1].output["human_approval_required"] is True


def test_no_opt_in_blocks_lead():
    case = full_case()
    case["lead"]["opt_in"] = False
    results = MoveTheDamnDataChain().run_case("case-no-optin", case)
    assert len(results) == 1
    assert results[0].status == "blocked"


def test_bad_email_routes_to_review():
    case = full_case()
    case["lead"]["email"] = "not-an-email"
    results = MoveTheDamnDataChain().run_case("case-bad-email", case)
    assert results[0].status == "human_review"


def test_quote_requires_verified_price():
    chain = MoveTheDamnDataChain()
    result = chain.process_quote(
        "case-unverified-price",
        {
            "customer_name": "Test Customer",
            "scope": "Some scope",
            "verified_price": "100.00",
            "price_verified": False,
        },
    )
    assert result.status == "blocked"
    assert "verified" in result.reason


def test_quote_rejects_missing_price():
    chain = MoveTheDamnDataChain()
    result = chain.process_quote(
        "case-missing-price",
        {"customer_name": "Test Customer", "scope": "Some scope", "price_verified": True},
    )
    assert result.status == "human_review"
    assert "verified_price" in result.reason


def test_job_cannot_advance_without_quote_approval():
    chain = MoveTheDamnDataChain()
    result = chain.process_job(
        "case-job-gate",
        {
            "job_id": "JOB-2",
            "approved_scope": "Scope",
            "status": "scheduled",
            "quote_approved": False,
        },
    )
    assert result.status == "blocked"


def test_unrecognized_job_status_routes_to_review():
    chain = MoveTheDamnDataChain()
    result = chain.process_job(
        "case-job-status",
        {
            "job_id": "JOB-3",
            "approved_scope": "Scope",
            "status": "teleported",
            "quote_approved": True,
        },
    )
    assert result.status == "human_review"


def test_invoice_difference_requires_verification():
    chain = MoveTheDamnDataChain()
    result = chain.process_invoice(
        "case-invoice-delta",
        {"invoice_id": "INV-2", "quoted_total": "100.00", "invoice_total": "125.00"},
    )
    assert result.status == "human_review"
    assert result.output["difference"] == "25.00"


def test_verified_invoice_difference_can_reconcile():
    chain = MoveTheDamnDataChain()
    result = chain.process_invoice(
        "case-invoice-verified",
        {
            "invoice_id": "INV-3",
            "quoted_total": "100.00",
            "invoice_total": "125.00",
            "difference_verified": True,
        },
    )
    assert result.status == "completed"
    assert result.output["reconciliation"] == "verified_difference"


def test_follow_up_never_sends_by_itself():
    chain = MoveTheDamnDataChain()
    result = chain.process_follow_up(
        "case-followup",
        {
            "recipient": "customer@example.com",
            "purpose": "test",
            "message": "Hello",
            "communication_allowed": True,
        },
    )
    assert result.status == "awaiting_approval"
    assert result.output["delivery_state"] == "prepared_not_sent"


def test_unauthorized_follow_up_is_blocked():
    chain = MoveTheDamnDataChain()
    result = chain.process_follow_up(
        "case-followup-blocked",
        {
            "recipient": "customer@example.com",
            "purpose": "test",
            "message": "Hello",
            "communication_allowed": False,
        },
    )
    assert result.status == "blocked"


def test_duplicate_stage_does_not_perform_second_action():
    chain = MoveTheDamnDataChain()
    payload = {
        "name": "Test Customer",
        "email": "customer@example.com",
        "request": "Need help",
        "opt_in": True,
    }
    first = chain.process_lead("case-duplicate", payload)
    second = chain.process_lead("case-duplicate", payload)
    assert first.status == "completed"
    assert second.status == "duplicate"
    assert second.audit_id == first.audit_id
    assert len(chain.audit_log) == 1
