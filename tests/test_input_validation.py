from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_ira_rejects_nonpositive_cost():
    response = client.post(
        "/v1/solar/ira-calculator",
        json={
            "system_cost": 0,
            "system_kw_dc": 400,
            "is_energy_community": False,
            "is_domestic_content": False,
        },
    )
    assert response.status_code == 422


def test_ira_rejects_nonpositive_system_size():
    response = client.post(
        "/v1/solar/ira-calculator",
        json={
            "system_cost": 500000,
            "system_kw_dc": 0,
            "is_energy_community": False,
            "is_domestic_content": False,
        },
    )
    assert response.status_code == 422


def test_tariff_rejects_zero_consumption_instead_of_dividing_by_zero():
    response = client.post(
        "/v1/energy/tariff-normalize",
        json={
            "utility": "Dominion_VA",
            "rate_class": "GS-3",
            "peak_demand_kw": 450,
            "monthly_consumption_kwh": 0,
        },
    )
    assert response.status_code == 422


def test_tariff_rejects_negative_peak_demand():
    response = client.post(
        "/v1/energy/tariff-normalize",
        json={
            "utility": "Dominion_VA",
            "rate_class": "GS-3",
            "peak_demand_kw": -1,
            "monthly_consumption_kwh": 180000,
        },
    )
    assert response.status_code == 422


def test_settlement_model_rejects_nonpositive_amount():
    try:
        main.SettlementRequest(product_id="p", buyer_did="did:test", amount=0)
    except Exception:
        pass
    else:
        raise AssertionError("SettlementRequest accepted a nonpositive amount")


def test_settlement_model_rejects_invalid_take_rate():
    try:
        main.SettlementRequest(product_id="p", buyer_did="did:test", amount=1, take_rate=1.1)
    except Exception:
        pass
    else:
        raise AssertionError("SettlementRequest accepted take_rate > 1.0")
