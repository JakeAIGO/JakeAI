"""Build a fail-closed Shopify/Meta agentic-commerce sync preview.

This module intentionally does not write to Shopify or Meta. It validates a
local staged configuration against JakeAI's public capability catalog and emits
only products that are explicitly enabled *and* eligible.

A future live writer must remain separately gated and require
SHOPIFY_AGENTIC_SYNC_ENABLED=true plus verified Shopify credentials.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_CONFIG = Path(__file__).with_name("shopify_meta_config.json")
DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / "catalog.json"


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _catalog_index(catalog: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        item["id"]: item
        for item in catalog.get("capabilities", [])
        if isinstance(item, dict) and item.get("id")
    }


def evaluate_product(
    product: Dict[str, Any],
    catalog_index: Dict[str, Dict[str, Any]],
    rules: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    if product.get("enabled") is not True:
        reasons.append("product_not_explicitly_enabled")

    price = product.get("price_usd")
    if rules.get("require_price_greater_than_zero", True):
        if not isinstance(price, (int, float)) or price <= 0:
            reasons.append("price_must_be_greater_than_zero")

    if rules.get("require_external_product_url", True) and not product.get("external_url"):
        reasons.append("missing_external_product_url")

    if rules.get("require_image_url", True) and not product.get("image_url"):
        reasons.append("missing_image_url")

    inventory = product.get("inventory_quantity")
    if rules.get("require_available_inventory", True):
        if not isinstance(inventory, int) or inventory <= 0:
            reasons.append("available_inventory_required")

    capability_id = product.get("catalog_capability_id")
    if rules.get("require_public_catalog_purchasable", True):
        if not capability_id:
            reasons.append("missing_catalog_capability_id")
        else:
            capability = catalog_index.get(capability_id)
            if not capability:
                reasons.append("catalog_capability_not_found")
            else:
                commerce = capability.get("commerce") or {}
                if commerce.get("purchasable") is not True:
                    reasons.append("public_catalog_not_purchasable")

    return (not reasons, reasons)


def meta_direct_checkout_eligible(product: Dict[str, Any], rules: Dict[str, Any]) -> bool:
    disallowed = set(rules.get("meta_direct_checkout_disallowed_types", []))
    return product.get("product_type") not in disallowed


def build_preview(config: Dict[str, Any], catalog: Dict[str, Any]) -> Dict[str, Any]:
    rules = config.get("eligibility_rules") or {}
    catalog_index = _catalog_index(catalog)

    eligible: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []

    for product in config.get("products", []):
        ok, reasons = evaluate_product(product, catalog_index, rules)
        record = {
            "product_id": product.get("product_id"),
            "catalog_capability_id": product.get("catalog_capability_id"),
            "title": product.get("title"),
            "price_usd": product.get("price_usd"),
            "external_url": product.get("external_url"),
            "image_url": product.get("image_url"),
            "inventory_quantity": product.get("inventory_quantity"),
            "product_type": product.get("product_type"),
            "meta_direct_checkout_eligible": meta_direct_checkout_eligible(product, rules),
        }
        if ok:
            eligible.append(record)
        else:
            blocked.append({**record, "blocked_reasons": reasons})

    return {
        "schema_version": "1.0",
        "adapter": "shopify_meta_agentic",
        "status": "preview_only",
        "live_write_enabled": bool((config.get("shopify") or {}).get("live_write_enabled")),
        "eligible_product_count": len(eligible),
        "blocked_product_count": len(blocked),
        "eligible_products": eligible,
        "blocked_products": blocked,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    preview = build_preview(_load_json(args.config), _load_json(args.catalog))
    rendered = json.dumps(preview, indent=2, sort_keys=True)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
