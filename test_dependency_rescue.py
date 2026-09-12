from datetime import date
from dependency_rescue import scan_text, scan_files

TODAY = date(2026, 9, 12)

def test_cloudflare_header_detected():
    r = scan_text('headers = {"X-Auth-User-Service-Key": "REDACTED"}', today=TODAY)
    assert r["findings"][0]["id"] == "cloudflare-service-key"
    assert r["findings"][0]["days_to_deadline"] == 18

def test_google_v22_detected():
    r = scan_text('client = google.ads.googleads.v22.services.GoogleAdsServiceClient()', today=TODAY)
    assert any(x["id"] == "google-ads-v22" for x in r["findings"])

def test_ews_detected():
    r = scan_text('https://outlook.office365.com/EWS/Exchange.asmx', today=TODAY)
    assert any(x["id"] == "ews-exchange-online" for x in r["findings"])

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
    r = scan_files([('clean.txt','/v22/'), ('secret.txt','password=abcdefghijklmnop1234')], today=TODAY)
    assert r["status"] == "BLOCKED_SECRET_DETECTED"

def test_evidence_line_number():
    r = scan_text('one\ntwo\n/EWS/Exchange.asmx\nfour', today=TODAY)
    assert r["findings"][0]["matches"][0]["line"] == 3
