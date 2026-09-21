import pilot_diagnostics as diag


def test_diagnostic_redaction_hides_secrets():
    text = diag._redact_diagnostic_text(
        "password=hunter2 access_code:ABC123 token=xyz Authorization: Bearer secret"
    )
    assert "hunter2" not in text
    assert "ABC123" not in text
    assert "xyz" not in text
    assert "Bearer secret" not in text
    assert "[REDACTED]" in text


def test_diagnostic_classifier_access():
    classification, action = diag._classify_diagnostic(
        "401 session invalid", "open private workspace"
    )
    assert classification == "ACCESS / SESSION"
    assert "JAI-J" in action


def test_diagnostic_classifier_consent():
    classification, action = diag._classify_diagnostic(
        "Contact approval requires verified opt-in evidence", "update lead"
    )
    assert classification == "CONSENT / LEAD STATE"
    assert "no outreach" in action.lower()


def test_diagnostic_code_has_jim_prefix():
    code = diag._diagnostic_code()
    assert code.startswith("JAI-J-")
    assert len(code) == len("JAI-J-") + 6
