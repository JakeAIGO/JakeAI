from agentic_commerce.shopify_meta_adapter import build_preview


def _catalog(purchasable=True):
    return {
        "capabilities": [
            {
                "id": "JAI-WF-9999",
                "commerce": {"purchasable": purchasable},
            }
        ]
    }


def _config(enabled=True, product_type="digital_product"):
    return {
        "shopify": {"live_write_enabled": False},
        "eligibility_rules": {
            "require_public_catalog_purchasable": True,
            "require_price_greater_than_zero": True,
            "require_external_product_url": True,
            "require_image_url": True,
            "require_available_inventory": True,
            "meta_direct_checkout_disallowed_types": [
                "subscription",
                "bundle",
                "customizable",
                "b2b_only",
            ],
        },
        "products": [
            {
                "product_id": "prod_test",
                "catalog_capability_id": "JAI-WF-9999",
                "title": "Test Product",
                "price_usd": 5.0,
                "product_type": product_type,
                "external_url": "https://jakeaiofficial.com/test",
                "image_url": "https://jakeaiofficial.com/assets/test.png",
                "inventory_quantity": 10,
                "enabled": enabled,
            }
        ],
    }


def test_eligible_product_is_emitted():
    preview = build_preview(_config(), _catalog())
    assert preview["eligible_product_count"] == 1
    assert preview["blocked_product_count"] == 0
    assert preview["eligible_products"][0]["meta_direct_checkout_eligible"] is True


def test_disabled_product_is_fail_closed():
    preview = build_preview(_config(enabled=False), _catalog())
    assert preview["eligible_product_count"] == 0
    assert "product_not_explicitly_enabled" in preview["blocked_products"][0]["blocked_reasons"]


def test_catalog_must_explicitly_allow_purchase():
    preview = build_preview(_config(), _catalog(purchasable=False))
    assert preview["eligible_product_count"] == 0
    assert "public_catalog_not_purchasable" in preview["blocked_products"][0]["blocked_reasons"]


def test_customizable_product_is_not_meta_direct_checkout_eligible():
    preview = build_preview(_config(product_type="customizable"), _catalog())
    assert preview["eligible_product_count"] == 1
    assert preview["eligible_products"][0]["meta_direct_checkout_eligible"] is False
