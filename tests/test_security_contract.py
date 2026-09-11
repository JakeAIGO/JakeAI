from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_ssrf_rejects_loopback_and_private_targets():
    assert main.is_safe_url("http://127.0.0.1/") is False
    assert main.is_safe_url("http://localhost/") is False
    assert main.is_safe_url("http://10.0.0.1/") is False
    assert main.is_safe_url("http://192.168.1.1/") is False
    assert main.is_safe_url("http://169.254.169.254/latest/meta-data/") is False
    assert main.is_safe_url("file:///etc/passwd") is False


def test_ssrf_rejects_hostname_if_any_resolution_is_private(monkeypatch):
    monkeypatch.setattr(
        main.socket,
        "getaddrinfo",
        lambda host, port: [
            (2, 1, 6, "", ("93.184.216.34", 0)),
            (2, 1, 6, "", ("127.0.0.1", 0)),
        ],
    )
    assert main.is_safe_url("https://example.test/path") is False


def test_ssrf_accepts_public_https_when_resolution_is_public(monkeypatch):
    monkeypatch.setattr(
        main.socket,
        "getaddrinfo",
        lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    assert main.is_safe_url("https://example.test/path") is True


def test_cors_allows_only_configured_origin():
    allowed = client.options(
        "/health",
        headers={
            "Origin": "https://www.jakeaiofficial.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers.get("access-control-allow-origin") == "https://www.jakeaiofficial.com"

    denied = client.options(
        "/health",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert denied.headers.get("access-control-allow-origin") is None


def test_error_contract_does_not_leak_internal_exception_details():
    response = client.get("/v1/checkout/buy/not-a-product", follow_redirects=False)
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["status_code"] == 404
    assert "traceback" not in str(payload).lower()
    assert "sk_" not in str(payload)


def test_public_catalog_strips_all_delivery_urls_even_for_free_products():
    response = client.get("/v1/products/list")
    assert response.status_code == 200
    serialized = response.text
    assert "download_url" not in serialized
    assert "docs.google.com/document/" not in serialized
    assert "drive.google.com/file/" not in serialized
