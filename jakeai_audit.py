#!/usr/bin/env python3
"""
JakeAI Autonomous Pre-Deployment Audit CLI & CI/CD Runner
Domain: https://www.jakeaiofficial.com
Queries the live Multi-Model Advisory Council endpoint (Claude 3.5 Sonnet + Perplexity Sonar-Pro).
Exits with 0 on GO, exits with 1 on NO-GO to protect production deployments.
"""

import sys
import os
import argparse
import json
import urllib.request
import urllib.error

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

DEFAULT_ENDPOINT = "https://www.jakeaiofficial.com/api/v1/tools/multi-model-audit"

def run_audit(content: str, domain: str = "jakeaiofficial.com", endpoint: str = DEFAULT_ENDPOINT):
    payload = {
        "content": content,
        "domain": domain
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "JakeAI-CI-CD-Runner/1.0"}
    )
    
    print(f"\n{BOLD}{CYAN}=== JAKEAI MULTI-MODEL PRE-DEPLOYMENT AUDIT ==={RESET}")
    print(f" Target Domain : {domain}")
    print(f" Audit Gateway : {endpoint}")
    print(f" Payload Size  : {len(content)} characters")
    print(f" Models        : Claude 3.5 Sonnet (Architecture/Risk) + Perplexity Sonar-Pro (Market)\n")

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"{RED}[FAIL] HTTP Error {e.code}: {err_body}{RESET}")
        return False
    except Exception as e:
        print(f"{RED}[FAIL] Network Connection Error: {str(e)}{RESET}")
        return False

    verdict = res_data.get("consensus_verdict", "UNKNOWN").upper()
    audits = res_data.get("audits", {})

    print(f"{BOLD}--- 1. CLAUDE (ARCHITECTURAL & LEGAL AUDIT) ---{RESET}")
    print(audits.get("technical_and_legal_risk", "No response").strip())
    print("\n" + "-" * 50 + "\n")

    print(f"{BOLD}--- 2. PERPLEXITY (MARKET & STANDARDS SCOUT) ---{RESET}")
    print(audits.get("market_intelligence_and_standards", "No response").strip())
    print("\n" + "=" * 50)

    if "GO" in verdict and "NO-GO" not in verdict:
        print(f"\n{GREEN}{BOLD}✓ FINAL VERDICT: GO (PRE-DEPLOYMENT PASSED){RESET}\n")
        return True
    else:
        print(f"\n{RED}{BOLD}✗ FINAL VERDICT: NO-GO (DEPLOYMENT BLOCKED — RESOLVE ISSUES ABOVE){RESET}\n")
        return False

def main():
    parser = argparse.ArgumentParser(description="JakeAI Multi-Model CI/CD Audit CLI")
    parser.add_argument("--file", "-f", help="Path to file or git diff to audit")
    parser.add_argument("--content", "-c", help="Inline text or proposal to audit")
    parser.add_argument("--domain", "-d", default="jakeaiofficial.com", help="Target domain")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Custom endpoint URL")
    args = parser.parse_args()

    content = ""
    if args.file and os.path.exists(args.file):
        with open(args.file, "r") as f:
            content = f.read()
    elif args.content:
        content = args.content
    else:
        # Default fallback to git diff
        try:
            import subprocess
            content = subprocess.check_output(["git", "diff", "HEAD~1"]).decode("utf-8")
        except Exception:
            print("Error: Specify --file, --content, or run inside a git repository.")
            sys.exit(1)

    passed = run_audit(content, domain=args.domain, endpoint=args.endpoint)
    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
