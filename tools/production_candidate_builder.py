#!/usr/bin/env python3
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "governance" / "production_candidate_policy.json"
OUT = ROOT / "build" / "production_candidate"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_sha(ref="HEAD"):
    p = subprocess.run(["git", "rev-parse", ref], cwd=ROOT, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or "git rev-parse failed")
    return p.stdout.strip()


def approved_modules(policy):
    modules = []
    root = ROOT / policy["module_root"]
    if not root.exists():
        return modules
    for manifest in sorted(root.glob("*/module.json")):
        data = load(manifest)
        if data.get("module_id") == "_template":
            continue
        if data.get("production_authorized") is True and data.get("publication_authorized") is True:
            modules.append({
                "module_id": data["module_id"],
                "kind": data.get("kind"),
                "commercial_authorized": data.get("commercial_authorized") is True,
                "manifest_sha256": sha256(manifest),
            })
    return modules


def approved_products(registry):
    out = []
    for product_id, data in sorted(registry.get("products", {}).items()):
        if data.get("commercial_authorized") is True and data.get("checkout_authorized") is True:
            required = ["fulfillment_verified", "legal_review_complete"]
            if any(data.get(k) is not True for k in required):
                raise ValueError(f"{product_id}: authorized product missing verification")
            out.append({"product_id": product_id, "price_usd": data["price_usd"]})
    return out


def approved_platform_terms(registry):
    terms = {}
    for key, data in sorted(registry.get("platform_terms", {}).items()):
        if isinstance(data, dict) and data.get("approved") is True and data.get("public_claim_authorized") is True:
            terms[key] = data
    return terms


def build():
    policy = load(POLICY_PATH)
    registry_path = ROOT / policy["commercial_registry"]
    registry = load(registry_path)
    candidate = {
        "schema_version": "1.0",
        "engine": policy["engine"],
        "source_baseline": policy["baseline_ref"],
        "builder_head": git_sha(),
        "production_authorized": False,
        "publication_authorized": False,
        "commercial_authorized": False,
        "modules": approved_modules(policy),
        "products": approved_products(registry),
        "platform_terms": approved_platform_terms(registry),
        "release_state": "candidate_only_not_authorized_for_production",
    }
    fingerprint = {
        "schema_version": "1.0",
        "builder_head": candidate["builder_head"],
        "policy_sha256": sha256(POLICY_PATH),
        "commercial_registry_sha256": sha256(registry_path),
        "candidate_manifest_sha256": hashlib.sha256((json.dumps(candidate, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest(),
    }
    review = [
        "# JakeAI Production Candidate Review",
        "",
        f"Source baseline: `{candidate['source_baseline']}`",
        f"Builder head: `{candidate['builder_head']}`",
        "",
        f"Approved modules included: **{len(candidate['modules'])}**",
        f"Approved commercial products included: **{len(candidate['products'])}**",
        f"Approved public platform terms included: **{len(candidate['platform_terms'])}**",
        "",
        "This artifact is a candidate assembly only. It does not authorize merge, deployment, publication, checkout activation, spending, or commercial release.",
        "",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "candidate_manifest.json").write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "candidate_fingerprint.json").write_text(json.dumps(fingerprint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "candidate_review.md").write_text("\n".join(review), encoding="utf-8")
    print(json.dumps({"status": "PASS", "modules": len(candidate["modules"]), "products": len(candidate["products"]), "terms": len(candidate["platform_terms"]), "builder_head": candidate["builder_head"]}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(build())
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        sys.exit(1)
