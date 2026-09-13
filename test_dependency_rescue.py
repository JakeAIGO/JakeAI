from datetime import date
from dependency_rescue import scan_text, scan_files

TODAY = date(2026, 9, 12)

def test_cloudflare_header_detected():
    r = scan_text('headers = {"X-Auth-User-Service-Key": "REDACTED"}', today=TODAY)
    finding = r["findings"][0]
    assert finding["id"] == "cloudflare-service-key"
    assert finding["days_to_deadline"] == 18
    assert finding["confidence"] == "confirmed-signature"
    assert finding["human_verification_required"] is True

def test_google_v22_detected():
    r = scan_text('client = google.ads.googleads.v22.services.GoogleAdsServiceClient()', today=TODAY)
    finding = next(x for x in r["findings"] if x["id"] == "google-ads-v22")
    assert finding["deadline"] == "2026-10-07"
    assert finding["source_checked"] == "2026-09-12"

def test_coralogix_exact_endpoint_is_confirmed():
    r = scan_text('https://api.eu1.coralogix.com/logs/rest/bulk', today=TODAY)
    finding = next(x for x in r["findings"] if x["id"] == "coralogix-legacy-ingest")
    assert finding["confidence"] == "confirmed-signature"

def test_databricks_supervisor_rule_is_present():
    r = scan_text('Databricks Supervisor API', today=TODAY)
    finding = next(x for x in r["findings"] if x["id"] == "databricks-supervisor-api")
    assert finding["deadline"] == "2026-09-30"

def test_qlik_general_reference_is_candidate_not_confirmed():
    r = scan_text('Qlik webhook CloudEvent migration notes', today=TODAY)
    finding = next(x for x in r["findings"] if x["id"] == "qlik-cloudevent-legacy")
    assert finding["confidence"] == "review-candidate"

def test_ews_online_endpoint_is_confirmed_and_timing_is_qualified():
    r = scan_text('https://outlook.office365.com/EWS/Exchange.asmx', today=TODAY)
    finding = next(x for x in r["findings"] if x["id"] == "ews-exchange-online")
    assert finding["confidence"] == "confirmed-signature"
    assert finding["deadline"] == "2026-10-01"
    assert "phased" in finding["timing_note"].lower()
    assert "2027-04-01" in finding["timing_note"]
    assert finding["source_checked"] == "2026-09-13"

def test_generic_ews_path_is_candidate():
    r = scan_text('server=https://mail.example.com/EWS/Exchange.asmx', today=TODAY)
    finding = next(x for x in r["findings"] if x["id"] == "ews-exchange-online")
    assert finding["confidence"] == "review-candidate"

def test_unknown_is_not_claimed_safe():
    r = scan_text('ordinary_configuration=true', today=TODAY)
    assert r["status"] == "NO_KNOWN_MATCHES"
    assert "does not prove" in r["limitations"]

def test_secret_fails_closed():
    r = scan_text('api_key="abcdefghijklmnopqrstuvwxyz123456"', today=TODAY)
    assert r["status"] == "BLOCKED_SECRET_DETECTED"
    assert r["findings"] == []

def test_private_key_fails_closed():
    r = scan_text('-----BEGIN PRIVATE KEY-----\nREDACTME', today=TODAY)
    assert r["status"] == "BLOCKED_SECRET_DETECTED"

def test_batch_blocks_if_any_file_has_secret():
    r = scan_files([('clean.txt','google.ads.googleads.v22'), ('secret.txt','password=abcdefghijklmnop1234')], today=TODAY)
    assert r["status"] == "BLOCKED_SECRET_DETECTED"

def test_evidence_line_number():
    r = scan_text('one\ntwo\nhttps://outlook.office365.com/EWS/Exchange.asmx\nfour', today=TODAY)
    assert r["findings"][0]["matches"][0]["line"] == 3
