import os
from types import SimpleNamespace

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_health_endpoint_is_liveness_only():
    response = client.get('/health')
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'alive'
    assert body.get('scope') == 'process_liveness_only'
    assert 'JakeAI Core' in body['service']


def test_unknown_product_checkout_returns_404():
    response = client.get('/v1/checkout/buy/does-not-exist', follow_redirects=False)
    assert response.status_code == 404
    assert response.json()['error']['status_code'] == 404


def test_free_gateway_works_without_stripe_secret(monkeypatch):
    monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
    response = client.get('/v1/checkout/buy/prod_make_free_00', follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'].startswith('https://docs.google.com/')


def test_metered_product_checkout_fails_closed():
    response = client.get('/v1/checkout/buy/prod_scrape_01', follow_redirects=False)
    assert response.status_code == 503
    assert 'not available' in response.json()['error']['message'].lower()


def test_game_qa_checkout_fails_closed_without_delivery_url():
    assert not main.is_product_checkout_enabled('prod_game_qa_autopilot_01')
    response = client.get('/v1/checkout/buy/prod_game_qa_autopilot_01', follow_redirects=False)
    assert response.status_code == 503


def test_public_catalog_never_exposes_delivery_urls():
    response = client.get('/v1/products/list')
    assert response.status_code == 200
    products = response.json()
    assert products
    assert all('download_url' not in product for product in products)


def test_llms_txt_reports_checkout_state_without_private_links():
    response = client.get('/llms.txt')
    assert response.status_code == 200
    text = response.text
    assert 'prod_make_free_00' in text
    assert 'Status: available' in text
    assert 'prod_scrape_01' in text
    assert 'Status: checkout_disabled' in text
    assert 'docs.google.com/document/' not in text
    assert 'drive.google.com/file/' not in text


def test_agent_card_never_exposes_delivery_urls():
    response = client.get('/.well-known/agent.json')
    assert response.status_code == 200
    payload = response.json()
    assert payload['active_catalog']
    assert all('download_url' not in p for p in payload['active_catalog'])


def test_unpaid_stripe_session_withholds_delivery(monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_placeholder')
    monkeypatch.setattr(
        main.stripe.checkout.Session,
        'retrieve',
        lambda session_id: SimpleNamespace(
            payment_status='unpaid',
            metadata={'product_id': 'prod_solar_guide_04'},
            amount_total=300,
            currency='usd',
        ),
    )
    response = client.get(
        '/v1/checkout/verify',
        params={'product_id': 'prod_solar_guide_04', 'session_id': 'cs_test_unpaid'},
        follow_redirects=False,
    )
    assert response.status_code == 402
    assert 'withheld' in response.json()['error']['message'].lower()


def test_paid_session_delivers_only_after_verification(monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_placeholder')
    monkeypatch.setattr(
        main.stripe.checkout.Session,
        'retrieve',
        lambda session_id: SimpleNamespace(
            payment_status='paid',
            metadata={'product_id': 'prod_solar_guide_04'},
            amount_total=300,
            currency='usd',
        ),
    )
    response = client.get(
        '/v1/checkout/verify',
        params={'product_id': 'prod_solar_guide_04', 'session_id': 'cs_test_paid'},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers['location'].startswith('https://drive.google.com/file/')


def test_paid_session_cannot_be_replayed_for_different_product(monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_placeholder')
    monkeypatch.setattr(
        main.stripe.checkout.Session,
        'retrieve',
        lambda session_id: SimpleNamespace(
            payment_status='paid',
            metadata={'product_id': 'prod_make_free_00'},
            amount_total=0,
            currency='usd',
        ),
    )
    response = client.get(
        '/v1/checkout/verify',
        params={'product_id': 'prod_solar_guide_04', 'session_id': 'cs_test_wrong_product'},
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert 'product mismatch' in response.json()['error']['message'].lower()


def test_paid_session_amount_must_match_catalog_price(monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_placeholder')
    monkeypatch.setattr(
        main.stripe.checkout.Session,
        'retrieve',
        lambda session_id: SimpleNamespace(
            payment_status='paid',
            metadata={'product_id': 'prod_solar_guide_04'},
            amount_total=1,
            currency='usd',
        ),
    )
    response = client.get(
        '/v1/checkout/verify',
        params={'product_id': 'prod_solar_guide_04', 'session_id': 'cs_test_wrong_amount'},
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert 'amount mismatch' in response.json()['error']['message'].lower()
