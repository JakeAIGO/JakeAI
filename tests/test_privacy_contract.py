from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_search_demand_telemetry_does_not_persist_ip_or_user_agent():
    source = read("main.py")
    assert 'background_tasks.add_task(log_unmet_query, q, "not_collected", "not_collected", len(matches))' in source
    assert 'client_ip = request.client.host' not in source
    assert 'ua = request.headers.get("user-agent"' not in source


def test_privacy_policy_discloses_search_demand_retention():
    privacy = read("privacy.html")
    assert "search term and match count" in privacy
    assert "does not persist the requester IP address or user-agent" in privacy


def test_privacy_policy_does_not_overclaim_tls_version():
    privacy = read("privacy.html")
    assert "TLS 1.3" not in privacy
    assert "HTTPS encryption in transit" in privacy


def test_privacy_policy_is_payment_provider_neutral():
    privacy = read("privacy.html")
    assert "payment details (processed securely via Stripe" not in privacy
    assert "configured payment provider" in privacy


def test_privacy_policy_discloses_external_ai_processing():
    privacy = read("privacy.html")
    assert "third-party AI providers" in privacy
    assert "their own applicable terms and privacy practices" in privacy
    assert "does not claim that third-party providers never retain submitted content" in privacy
    assert "is not retained or used to train public machine learning models" not in privacy
