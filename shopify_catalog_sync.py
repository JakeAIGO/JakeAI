#!/usr/bin/env python3
"""Mirror approved JakeAI catalog products into Shopify.

JakeAI remains the source of truth. This sync is intentionally fail-closed:
a catalog item is not mirrored unless it is production, listed_live,
purchasable, has passed the Shopify security gate, and has an HTTPS human page.

Public Shopify release is a separate gate. Items default to DRAFT and are only
made ACTIVE/published when distribution.shopify.release_state == "approved_live".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2026-07")
SYNC_TAG = "jakeai-catalog-sync"

FIND_PRODUCT = """
query FindJakeAIMirror($query: String!) {
  products(first: 10, query: $query) {
    nodes {
      id
      title
      handle
      status
      tags
      variants(first: 100) {
        nodes { id title sku price }
      }
    }
  }
}
"""

SET_PRODUCT = """
mutation SyncJakeAIProduct($input: ProductSetInput!) {
  productSet(synchronous: true, input: $input) {
    product { id title handle status }
    userErrors { field message }
  }
}
"""

UPDATE_METADATA = """
mutation UpdateJakeAIMetadata($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
    product { id status }
    userErrors { field message }
  }
}
"""

PUBLICATIONS = """
query JakeAIPublications {
  publications(first: 50) {
    nodes { id name }
  }
}
"""

PUBLISH_PRODUCT = """
mutation PublishJakeAIProduct($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) {
    userErrors { field message }
  }
}
"""


class SyncError(RuntimeError):
    pass


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "product"


def _money(value: Any) -> str:
    return f"{float(value):.2f}"


def _shopify_cfg(item: dict[str, Any]) -> dict[str, Any]:
    distribution = item.get("distribution") or {}
    return distribution.get("shopify") or {}


def _eligible(item: dict[str, Any]) -> tuple[bool, str]:
    cfg = _shopify_cfg(item)
    commerce = item.get("commerce") or {}
    is_sellable_release = (
        item.get("lifecycle_status") == "production"
        and item.get("publication_status") == "listed_live"
        and bool(commerce.get("purchasable"))
    )

    # Mandatory routing decision: every production/listed/purchasable JakeAI
    # product must either enter Shopify or carry an explicit skip reason.
    if is_sellable_release and not cfg:
        raise SyncError(
            f"{item.get('id')}: sellable release has no distribution.shopify decision"
        )
    if is_sellable_release and cfg.get("enabled") is False:
        if not str(cfg.get("skip_reason") or "").strip():
            raise SyncError(
                f"{item.get('id')}: Shopify disabled without distribution.shopify.skip_reason"
            )
        return False, "explicit-shopify-skip"

    if not cfg.get("enabled"):
        return False, "shopify-disabled"
    if item.get("lifecycle_status") != "production":
        return False, "not-production"
    if item.get("publication_status") != "listed_live":
        return False, "not-uploaded/listed-live"
    if not commerce.get("purchasable"):
        return False, "not-purchasable"
    if cfg.get("security_review") != "passed":
        return False, "security-review-not-passed"
    human_url = str(item.get("human_url") or "")
    if not human_url.startswith("https://"):
        return False, "missing-safe-human-url"
    image_url = str(cfg.get("image_url") or "")
    if cfg.get("require_image", True) and not image_url.startswith("https://"):
        return False, "missing-product-art"
    if cfg.get("release_state", "draft") not in {"draft", "approved_live"}:
        return False, "invalid-release-state"
    return True, "ready"


def _variants(item: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = _shopify_cfg(item)
    commerce = item.get("commerce") or {}
    canonical_id = item["id"]
    mode = cfg.get("variant_mode", "base_only")

    if mode == "plans":
        plans = commerce.get("plans") or []
        if not plans:
            raise SyncError(f"{canonical_id}: variant_mode=plans but commerce.plans is empty")
        option_values = [{"name": str(p["name"])} for p in plans]
        variants = []
        sku_map = cfg.get("variant_skus") or {}
        for p in plans:
            sku = str(
                p.get("shopify_sku")
                or sku_map.get(str(p.get("id") or ""))
                or p.get("id")
                or f"{canonical_id}-{_slug(str(p['name']))}"
            )
            variants.append(
                {
                    "optionValues": [{"optionName": "Plan", "name": str(p["name"])}],
                    "price": _money(p["price"]),
                    "sku": sku,
                    "inventoryItem": {"sku": sku, "requiresShipping": False},
                }
            )
        return [{"name": "Plan", "values": option_values}], variants

    price = commerce.get("price")
    if price is None:
        raise SyncError(f"{canonical_id}: no simple commerce.price for base_only mirror")
    sku = str(cfg.get("sku") or canonical_id)
    return (
        [{"name": "Title", "values": [{"name": "Default"}]}],
        [
            {
                "optionValues": [{"optionName": "Title", "name": "Default"}],
                "price": _money(price),
                "sku": sku,
                "inventoryItem": {"sku": sku, "requiresShipping": False},
            }
        ],
    )


def _image_file(canonical_id: str, title: str, image_url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(image_url)
    ext = Path(parsed.path).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}:
        ext = ".jpg"
    return {
        "filename": f"{_slug(canonical_id)}{ext}",
        "contentType": "IMAGE",
        "alt": title,
        "duplicateResolutionMode": "REPLACE",
        "originalSource": image_url,
    }


def _product_input(item: dict[str, Any], existing_id: str | None) -> dict[str, Any]:
    cfg = _shopify_cfg(item)
    canonical_id = item["id"]
    title = item["name"]
    summary = item.get("summary") or ""
    categories = item.get("category") or []
    if isinstance(categories, str):
        categories = [categories]

    product_options, variants = _variants(item)
    tags = [
        "JakeAI",
        SYNC_TAG,
        canonical_id,
        "digital-product",
        *[str(x) for x in categories],
    ]
    tags = list(dict.fromkeys(tags))

    release_state = cfg.get("release_state", "draft")
    payload: dict[str, Any] = {
        "handle": str(cfg.get("handle") or _slug(title)),
        "title": title,
        "descriptionHtml": (
            f"<p>{summary}</p>"
            f"<p><strong>Canonical JakeAI ID:</strong> {canonical_id}</p>"
            f"<p>Canonical product page: {item['human_url']}</p>"
        ),
        "vendor": "JakeAI",
        "productType": str(cfg.get("product_type") or item.get("type") or "Digital Workflow"),
        "status": "ACTIVE" if release_state == "approved_live" else "DRAFT",
        "tags": tags,
        "seo": {
            "title": title,
            "description": str(summary)[:320],
        },
        "productOptions": product_options,
        "variants": variants,
    }
    if existing_id:
        payload["id"] = existing_id

    image_url = str(cfg.get("image_url") or "")
    if image_url:
        payload["files"] = [_image_file(canonical_id, title, image_url)]
    return payload


def _metadata_input(item: dict[str, Any], product_id: str) -> dict[str, Any]:
    cfg = _shopify_cfg(item)
    return {
        "id": product_id,
        "metafields": [
            {
                "namespace": "jakeai",
                "key": "canonical_id",
                "type": "single_line_text_field",
                "value": item["id"],
            },
            {
                "namespace": "jakeai",
                "key": "canonical_url",
                "type": "url",
                "value": item["human_url"],
            },
            {
                "namespace": "jakeai",
                "key": "source_catalog",
                "type": "url",
                "value": "https://jakeaiofficial.com/catalog.json",
            },
            {
                "namespace": "jakeai",
                "key": "fulfillment_owner",
                "type": "single_line_text_field",
                "value": "JakeAI",
            },
            {
                "namespace": "jakeai",
                "key": "sync_policy",
                "type": "single_line_text_field",
                "value": "JakeAI catalog is source of truth",
            },
            {
                "namespace": "jakeai",
                "key": "release_policy",
                "type": "single_line_text_field",
                "value": str(cfg.get("release_state", "draft")),
            },
        ],
    }


class ShopifyClient:
    def __init__(self, domain: str, token: str, api_version: str) -> None:
        domain = domain.strip().removeprefix("https://").rstrip("/")
        if not domain.endswith(".myshopify.com"):
            raise SyncError("SHOPIFY_STORE_DOMAIN must be the store's *.myshopify.com domain")
        if not token.strip():
            raise SyncError("SHOPIFY_ADMIN_ACCESS_TOKEN is missing")
        self.endpoint = f"https://{domain}/admin/api/{api_version}/graphql.json"
        self.token = token.strip()

    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": self.token,
                "User-Agent": "JakeAI-Shopify-Catalog-Sync/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise SyncError(f"Shopify HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise SyncError(f"Shopify request failed: {exc}") from exc

        if payload.get("errors"):
            raise SyncError(f"Shopify GraphQL error: {payload['errors']}")
        return payload.get("data") or {}

    def find_mirror(self, canonical_id: str) -> dict[str, Any] | None:
        query = f"tag:{SYNC_TAG} AND tag:{canonical_id}"
        data = self.graphql(FIND_PRODUCT, {"query": query})
        nodes = ((data.get("products") or {}).get("nodes") or [])
        if not nodes:
            return None
        if len(nodes) > 1:
            raise SyncError(f"{canonical_id}: multiple Shopify mirrors found; refusing to guess")
        return nodes[0]

    def set_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.graphql(SET_PRODUCT, {"input": payload})
        result = data.get("productSet") or {}
        errors = result.get("userErrors") or []
        if errors:
            raise SyncError(f"productSet failed: {errors}")
        product = result.get("product")
        if not product:
            raise SyncError("productSet returned no product")
        return product

    def update_metadata(self, payload: dict[str, Any]) -> None:
        data = self.graphql(UPDATE_METADATA, {"product": payload})
        result = data.get("productUpdate") or {}
        errors = result.get("userErrors") or []
        if errors:
            raise SyncError(f"productUpdate metadata failed: {errors}")

    def online_store_publication_id(self) -> str:
        data = self.graphql(PUBLICATIONS)
        nodes = ((data.get("publications") or {}).get("nodes") or [])
        for node in nodes:
            if str(node.get("name") or "").strip().lower() == "online store":
                return node["id"]
        raise SyncError("Online Store publication was not found")

    def publish_online_store(self, product_id: str, publication_id: str) -> None:
        data = self.graphql(
            PUBLISH_PRODUCT,
            {"id": product_id, "input": [{"publicationId": publication_id}]},
        )
        result = data.get("publishablePublish") or {}
        errors = result.get("userErrors") or []
        if errors:
            raise SyncError(f"publishablePublish failed: {errors}")


def load_catalog(path: str) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    capabilities = raw.get("capabilities")
    if not isinstance(capabilities, list):
        raise SyncError("catalog.json must contain a capabilities array")
    return capabilities


def plan_item(item: dict[str, Any]) -> dict[str, Any]:
    ok, reason = _eligible(item)
    cfg = _shopify_cfg(item)
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "eligible": ok,
        "reason": reason,
        "target_status": "ACTIVE" if cfg.get("release_state") == "approved_live" else "DRAFT",
        "image_url": cfg.get("image_url"),
        "variant_mode": cfg.get("variant_mode", "base_only"),
    }


def sync(catalog_path: str, dry_run: bool = False) -> int:
    items = load_catalog(catalog_path)
    plans = [plan_item(item) for item in items]
    eligible_items = [item for item in items if _eligible(item)[0]]

    if dry_run:
        print(json.dumps({"eligible_count": len(eligible_items), "products": plans}, indent=2))
        for item in eligible_items:
            _product_input(item, None)
        return 0

    domain = os.environ.get("SHOPIFY_STORE_DOMAIN", "")
    token = os.environ.get("SHOPIFY_ADMIN_ACCESS_TOKEN", "")
    client = ShopifyClient(domain, token, DEFAULT_API_VERSION)
    publication_id: str | None = None

    for item in eligible_items:
        canonical_id = item["id"]
        existing = client.find_mirror(canonical_id)
        payload = _product_input(item, existing["id"] if existing else None)
        product = client.set_product(payload)
        client.update_metadata(_metadata_input(item, product["id"]))

        cfg = _shopify_cfg(item)
        if cfg.get("release_state") == "approved_live":
            if publication_id is None:
                publication_id = client.online_store_publication_id()
            client.publish_online_store(product["id"], publication_id)

        action = "updated" if existing else "created"
        print(f"{canonical_id}: {action} Shopify mirror -> {product['status']}")

    print(f"Shopify sync complete: {len(eligible_items)} eligible product(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync approved JakeAI products to Shopify")
    parser.add_argument("--catalog", default="catalog.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        return sync(args.catalog, args.dry_run)
    except (SyncError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"SHOPIFY SYNC FAILED CLOSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
