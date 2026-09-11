#!/usr/bin/env python3
import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "governance" / "module_sandbox_policy.json"
REPORT_PATH = ROOT / "build" / "module_sandbox_report.json"
SECRET_PATTERNS = [
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"sk_test_[A-Za-z0-9]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or "git failed")
    return p.stdout.strip()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def matches(path, pattern):
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatch(path, pattern)


def module_for(path, root):
    parts = Path(path).parts
    return parts[1] if len(parts) >= 2 and parts[0] == root else None


def validate_manifest(module_dir, policy):
    errors = []
    path = module_dir / policy["manifest_name"]
    if not path.exists():
        return [f"{module_dir}: missing {policy['manifest_name']}"]
    try:
        data = load_json(path)
    except Exception as exc:
        return [f"{path}: invalid JSON: {exc}"]
    for field in policy["required_manifest_fields"]:
        if field not in data:
            errors.append(f"{path}: missing field {field}")
    if errors:
        return errors
    if data["schema_version"] != "1.0":
        errors.append(f"{path}: schema_version must be 1.0")
    if data["module_id"] != module_dir.name:
        errors.append(f"{path}: module_id must equal directory name")
    if data["kind"] not in policy["allowed_module_kinds"]:
        errors.append(f"{path}: invalid kind")
    for field in ("entrypoints", "capabilities", "dependencies", "data_access", "secrets_required"):
        if not isinstance(data[field], list):
            errors.append(f"{path}: {field} must be a list")
    if data["network_access"] not in ("none", "restricted", "required"):
        errors.append(f"{path}: network_access must be none, restricted, or required")
    for field in ("production_authorized", "publication_authorized", "commercial_authorized"):
        if data[field] is not False:
            errors.append(f"{path}: {field} must remain false in sandbox")
    return errors


def scan_secrets(paths):
    errors = []
    for rel in paths:
        p = ROOT / rel
        if not p.is_file() or p.stat().st_size > 1_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"{rel}: possible embedded secret")
    return errors


def protected_core_override_errors(protected_hits, changed, policy):
    if not protected_hits:
        return []
    contract = policy["protected_core_override"]
    request_paths = [p for p in changed if matches(p, policy["change_request_glob"])]
    eligible = []
    for rel in request_paths:
        try:
            data = load_json(ROOT / rel)
        except Exception:
            continue
        if data.get(contract["flag"]) is not True:
            continue
        if data.get("risk_class") not in contract["required_risk"]:
            continue
        reviews = data.get("reviews") if isinstance(data.get("reviews"), dict) else {}
        if any(reviews.get(lane) != "approved" for lane in contract["required_reviews"]):
            continue
        if contract.get("require_human_record") and not str(data.get("human_approval_record") or "").strip():
            continue
        if contract.get("require_all_release_authorizations_false"):
            if any(data.get(field) is not False for field in ("production_authorized", "publication_authorized", "commercial_authorized")):
                continue
        approved_paths = data.get(contract["paths_field"])
        if not isinstance(approved_paths, list):
            continue
        if set(protected_hits).issubset(set(approved_paths)):
            eligible.append(data.get("id", rel))
    if eligible:
        return []
    return [
        "sandbox candidate modifies protected core without an approved governed override: "
        + ", ".join(protected_hits)
    ]


def main():
    ap = argparse.ArgumentParser(description="JakeAI module boundary/sandbox gate")
    ap.add_argument("--base", default="origin/baseline/master-v2-2026-09-11")
    args = ap.parse_args()
    policy = load_json(POLICY_PATH)
    report = {"status": "FAIL", "base": args.base, "head": None, "changed_paths": [], "modules": [], "errors": []}
    try:
        report["head"] = git("rev-parse", "HEAD")
        changed = sorted(x for x in git("diff", "--name-only", f"{args.base}...HEAD").splitlines() if x)
        report["changed_paths"] = changed
        root = policy["module_root"]
        modules = sorted({m for p in changed if (m := module_for(p, root))})
        report["modules"] = modules
        protected = set(policy["protected_core_paths"])
        protected_hits = sorted(protected.intersection(changed))
        report["errors"].extend(protected_core_override_errors(protected_hits, changed, policy))
        non_module_code = [p for p in changed if not p.startswith(root + "/") and p.startswith(("src/", "app/", "lib/", "services/"))]
        if non_module_code:
            report["errors"].append("new product/runtime code must live under modules/: " + ", ".join(non_module_code))
        for module in modules:
            report["errors"].extend(validate_manifest(ROOT / root / module, policy))
        report["errors"].extend(scan_secrets([p for p in changed if p.startswith(root + "/")]))
    except Exception as exc:
        report["errors"].append(str(exc))
    report["status"] = "PASS" if not report["errors"] else "FAIL"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
