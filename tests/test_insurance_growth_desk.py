import insurance_growth_desk as desk


def test_insurance_guardrails_are_explicit(monkeypatch):
    monkeypatch.setenv("INSURANCE_BRAND_VERIFIED", "false")
    text = desk._insurance_instructions("iul_annuity_leads")
    assert "explicit human approval" in text
    assert "Do not provide individualized insurance" in text
    assert "Do not make annuity suitability or best-interest conclusions" in text
    assert "NOT verified" in text
    assert "sensitive traits" in text


def test_contact_approval_requires_verified_opt_in():
    assert desk._contact_approval_allowed("consent_pending", "") is False
    assert desk._contact_approval_allowed("do_not_contact", "form record") is False
    assert desk._contact_approval_allowed("opt_in_verified", "") is False


def test_verified_opt_in_can_reach_contact_approved():
    assert desk._contact_approval_allowed(
        "opt_in_verified",
        "Test form opt-in recorded 2026-09-21T14:00:00Z",
    ) is True


def test_marketing_mode_reuses_campaign_runtime():
    assert desk._underlying_workflow("first_term_marketing") == "campaign"
    assert desk._underlying_workflow("iul_annuity_leads") == "campaign"
    assert desk._underlying_workflow("lead_review") == "general"
