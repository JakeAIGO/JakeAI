"""JakeAI public-claim consistency checks.

These tests are deliberately fail-closed: they verify code/document relationships
without changing pricing, checkout, deployment, or publication state.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_canonical_machine_routes_are_proxied():
    redirects = read("_redirects")
    assert "/llms.txt  https://agent-commerce-network-production-56e8.up.railway.app/llms.txt  200!" in redirects
    assert "/.well-known/agent.json  https://agent-commerce-network-production-56e8.up.railway.app/.well-known/agent.json  200!" in redirects
    assert "/api/*  https://agent-commerce-network-production-56e8.up.railway.app/:splat  200" in redirects


def test_backend_owns_dynamic_machine_surfaces():
    main = read("main.py")
    assert '@app.get("/llms.txt"' in main
    assert '@app.get("/.well-known/agent.json"' in main


def test_commercial_actions_remain_fail_closed():
    validation = read(".github/workflows/product-validation.yml")
    for marker in (
        '"publication_authorized": False',
        '"spending_authorized": False',
        '"build_authorized": False',
        '"human_approval_required": True',
    ):
        assert marker in validation


def test_audit_prices_are_not_silently_changed():
    """Lock currently implemented catalog prices pending explicit commercial approval."""
    main = read("main.py")
    single = re.search(r'"id":\s*"prod_multi_model_audit_08"[\s\S]{0,1200}?"price_cents":\s*(\d+)', main)
    pack = re.search(r'"id":\s*"prod_audit_pack_10"[\s\S]{0,1200}?"price_cents":\s*(\d+)', main)
    assert single and int(single.group(1)) == 200
    assert pack and int(pack.group(1)) == 1800


def test_named_audit_providers_are_implemented_but_not_claimed_live_here():
    main = read("main.py")
    audit = read("TRUTH_AND_CLAIMS_AUDIT.md")
    assert "api.anthropic.com/v1/messages" in main
    assert "api.perplexity.ai/chat/completions" in main
    assert "Successful live runtime participation is still UNVERIFIED" in audit
