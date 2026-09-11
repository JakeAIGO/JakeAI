#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "governance" / "commercial_rules_registry.json"
MASTER_PATH = ROOT / "governance" / "master_manifest.json"
REPORT_PATH = ROOT / "build" / "commercial_rules_report.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(registry: dict, master: dict) -> list[str]:
    errors = []
    if registry.get("schema_version") != "1.0":
        errors.append("registry schema_version must be 1.0")
    if registry.get("authority") != "canonical_commercial_configuration":
        errors.append("registry authority marker missing")

    defaults = registry.get("defaults", {})
    for field in (
        "commercial_authorized",
        "checkout_authorized",
        "publication_as_available_authorized",
        "fulfillment_verified",
        "refund_policy_verified",
        "legal_review_complete",
    ):
        if defaults.get(field) is not False:
            errors.append(f"default {field} must be false")

    terms = registry.get("platform_terms", {})
    for name in ("creator_revenue_split", "protocol_fee", "refunds"):
        term = terms.get(name)
        if not isinstance(term, dict):
            errors.append(f"platform term missing: {name}")
            continue
        if term.get("approved") is not False:
            errors.append(f"platform term {name} must remain unapproved")
        if term.get("public_claim_authorized") is not False:
            errors.append(f"platform term {name} public claim must remain unauthorized")

    master_products = master.get("products", {})
    products = registry.get("products", {})
    if set(products) != set(master_products):
        missing = sorted(set(master_products) - set(products))
        extra = sorted(set(products) - set(master_products))
        if missing:
            errors.append("commercial registry missing products: " + ", ".join(missing))
        if extra:
            errors.append("commercial registry has unknown products: " + ", ".join(extra))

    for product_id, master_product in master_products.items():
        product = products.get(product_id, {})
        if product.get("price_usd") != master_product.get("price_usd"):
            errors.append(f"{product_id}: price does not match master manifest")
        for field in ("commercial_authorized", "checkout_authorized", "fulfillment_verified", "legal_review_complete"):
            if product.get(field) is not False:
                errors.append(f"{product_id}: {field} must remain false before explicit approval")
        requires_metering = bool(master_product.get("requires_metering"))
        if requires_metering and product.get("metering_verified") is not False:
            errors.append(f"{product_id}: metering cannot be pre-verified while master baseline marks it unverified")
        if not requires_metering and not isinstance(product.get("metering_verified"), bool):
            errors.append(f"{product_id}: metering_verified must be boolean")

    split = terms.get("creator_revenue_split", {})
    creator = split.get("creator_share")
    jakeai = split.get("jakeai_share")
    if isinstance(creator, (int, float)) and isinstance(jakeai, (int, float)):
        if round(creator + jakeai, 10) != 1.0:
            errors.append("creator revenue split must sum to 1.0")
    else:
        errors.append("creator revenue split values must be numeric")

    fee = terms.get("protocol_fee", {}).get("rate")
    if not isinstance(fee, (int, float)) or not (0 <= fee <= 1):
        errors.append("protocol fee rate must be between 0 and 1")

    return errors


def main() -> int:
    report = {"status": "FAIL", "errors": []}
    try:
        registry = load(REGISTRY_PATH)
        master = load(MASTER_PATH)
        report["errors"] = validate(registry, master)
        report["product_count"] = len(registry.get("products", {}))
        report["commercial_authorized_count"] = sum(1 for p in registry.get("products", {}).values() if p.get("commercial_authorized") is True)
        report["status"] = "PASS" if not report["errors"] else "FAIL"
    except Exception as exc:
        report["errors"] = [str(exc)]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
