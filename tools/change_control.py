#!/usr/bin/env python3
import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "governance" / "change_control_policy.json"
REPORT_PATH = ROOT / "build" / "change_control_report.json"


def run_git(*args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "git command failed")
    return proc.stdout.strip()


def load_policy(path: Path = POLICY_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatch(path, pattern)


def classify_paths(paths: list[str], policy: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for category, patterns in policy["scope_rules"].items():
        hits = sorted({p for p in paths if any(matches(p, pat) for pat in patterns)})
        if hits:
            out[category] = hits
    return out


def required_reviews(categories: set[str], policy: dict) -> set[str]:
    required: set[str] = set()
    for category in categories:
        required.update(policy.get("review_requirements", {}).get(category, []))
    return required


def validate_change_request(data: dict, categories: set[str], changed_paths: set[str], policy: dict) -> list[str]:
    errors: list[str] = []
    required_fields = [
        "schema_version", "id", "title", "baseline_ref", "purpose", "risk_class",
        "scope_categories", "reviews", "production_authorized", "publication_authorized",
        "commercial_authorized", "human_approval_record", "unresolved_conditions"
    ]
    for field in required_fields:
        if field not in data:
            errors.append(f"missing field: {field}")

    if errors:
        return errors

    if data["schema_version"] != "1.0":
        errors.append("schema_version must be 1.0")
    if data["baseline_ref"] not in {"baseline/master-2026-09-11", "origin/baseline/master-2026-09-11"}:
        errors.append("baseline_ref must identify baseline/master-2026-09-11")
    if data["risk_class"] not in policy["risk_levels"]:
        errors.append("risk_class is invalid")
    if not isinstance(data["scope_categories"], list):
        errors.append("scope_categories must be a list")
    else:
        declared = set(data["scope_categories"])
        missing_scopes = categories - declared
        if missing_scopes:
            errors.append("scope_categories missing: " + ", ".join(sorted(missing_scopes)))

    reviews = data["reviews"]
    if not isinstance(reviews, dict):
        errors.append("reviews must be an object")
        reviews = {}
    required = required_reviews(categories, policy)
    missing_reviews = sorted(r for r in required if r not in reviews)
    if missing_reviews:
        errors.append("required review lanes missing: " + ", ".join(missing_reviews))

    valid_review_states = {"pending", "approved", "not_required", "blocked"}
    for lane, state in reviews.items():
        if state not in valid_review_states:
            errors.append(f"invalid review state for {lane}: {state}")

    authorization_fields = ["production_authorized", "publication_authorized", "commercial_authorized"]
    for field in authorization_fields:
        if not isinstance(data[field], bool):
            errors.append(f"{field} must be boolean")
        if data[field] is True:
            if data.get("status") != "approved":
                errors.append(f"{field}=true requires status=approved")
            if not str(data.get("human_approval_record") or "").strip():
                errors.append(f"{field}=true requires a human_approval_record")

    self_mod = set(policy.get("self_modification_paths", [])) & changed_paths
    if self_mod:
        if data["risk_class"] not in {"high", "critical"}:
            errors.append("change-control self-modification requires high or critical risk_class")
        for lane in ("council", "human"):
            if lane not in reviews:
                errors.append(f"change-control self-modification requires {lane} review lane")

    return errors


def verify_manifest_fail_closed(policy: dict) -> list[str]:
    errors: list[str] = []
    manifest_path = ROOT / policy["protected_manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in ("production_authorized", "publication_authorized"):
        if manifest.get(key) is not False:
            errors.append(f"{policy['protected_manifest']} must keep {key}=false in this change-control phase")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="JakeAI Master Baseline change-control gate")
    parser.add_argument("--base", default=None, help="Baseline git ref")
    parser.add_argument("--policy", default=str(POLICY_PATH), help="Policy JSON path")
    args = parser.parse_args()

    policy = load_policy(Path(args.policy))
    base = args.base or policy["baseline_ref"]
    report = {
        "status": "FAIL",
        "base": base,
        "head": None,
        "changed_paths": [],
        "categories": {},
        "change_requests": [],
        "errors": [],
    }

    try:
        head = run_git("rev-parse", "HEAD")
        report["head"] = head
        ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", base, "HEAD"], cwd=ROOT)
        if ancestor.returncode != 0:
            report["errors"].append(f"HEAD is not descended from canonical baseline {base}")
        diff_text = run_git("diff", "--name-only", f"{base}...HEAD")
        changed = sorted({p for p in diff_text.splitlines() if p.strip()})
        report["changed_paths"] = changed
        categories_map = classify_paths(changed, policy)
        report["categories"] = categories_map
        categories = set(categories_map)
        changed_set = set(changed)

        request_paths = [p for p in changed if matches(p, policy["change_request_glob"])]
        if changed and not request_paths:
            report["errors"].append("non-empty baseline diff requires a changed governance/change_requests/*.json declaration")

        for request_path in request_paths:
            try:
                data = json.loads((ROOT / request_path).read_text(encoding="utf-8"))
                errors = validate_change_request(data, categories, changed_set, policy)
                report["change_requests"].append({"path": request_path, "id": data.get("id"), "errors": errors})
                report["errors"].extend(f"{request_path}: {e}" for e in errors)
            except Exception as exc:
                report["errors"].append(f"{request_path}: invalid change request: {exc}")

        report["errors"].extend(verify_manifest_fail_closed(policy))
    except Exception as exc:
        report["errors"].append(str(exc))

    report["status"] = "PASS" if not report["errors"] else "FAIL"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
