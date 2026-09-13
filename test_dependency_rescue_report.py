from dependency_rescue_report import render_markdown


def test_blocked_secret_report_discloses_no_findings():
    text = render_markdown({"status": "BLOCKED_SECRET_DETECTED", "results": []}, "T-1")
    assert "BLOCKED" in text
    assert "No dependency conclusions" in text


def test_no_match_report_does_not_claim_safe():
    text = render_markdown({"status": "COMPLETE", "results": [{"filename": "x.txt", "findings": []}]}, "T-2")
    assert "No supported signatures found" in text
    assert "not** proof" in text


def test_findings_report_contains_source_and_no_execution_claim():
    finding = {
        "vendor": "Cloudflare",
        "title": "Legacy Service Key authentication",
        "deadline": "2026-09-30",
        "days_to_deadline": 18,
        "confidence": "confirmed-signature",
        "source_checked": "2026-09-12",
        "source_url": "https://developers.cloudflare.com/example",
        "matches": [{"line": 4, "evidence": "X-Auth-User-Service-Key"}],
        "remediation": "Migrate to a scoped API Token.",
        "verification": "Test before revocation.",
    }
    text = render_markdown({"status": "COMPLETE", "results": [{"filename": "config.yml", "findings": [finding]}]}, "T-3")
    assert "confirmed signatures" in text
    assert "line 4" in text
    assert "https://developers.cloudflare.com/example" in text
    assert "No production changes were made" in text
    assert "not a guarantee" in text


def test_report_renders_phased_timing_context():
    finding = {
        "vendor": "Microsoft Exchange Online",
        "title": "Exchange Web Services phased disablement",
        "deadline": "2026-10-01",
        "days_to_deadline": 19,
        "timing_note": "Phased disablement begins 2026-10-01; permanent retirement is 2027-04-01.",
        "confidence": "confirmed-signature",
        "source_checked": "2026-09-13",
        "source_url": "https://learn.microsoft.com/example",
        "matches": [{"line": 2, "evidence": "EWS"}],
        "remediation": "Classify the caller before migration.",
        "verification": "Verify required behavior against the replacement.",
    }
    text = render_markdown({"status": "COMPLETE", "results": [{"filename": "ews.py", "findings": [finding]}]}, "T-4")
    assert "Vendor date" in text
    assert "Timing context" in text
    assert "2027-04-01" in text
