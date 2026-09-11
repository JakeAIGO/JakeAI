#!/usr/bin/env python3
"""Fail-close public network fetch tools and remove request-supplied provider keys.

Repository-only remediation. No deployment, spending, checkout activation, or credential access.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"


def replace_once(text: str, old: str, new: str) -> tuple[str, bool]:
    if old not in text:
        return text, False
    return text.replace(old, new, 1), True


def main() -> int:
    text = MAIN.read_text(encoding="utf-8")
    changed = []

    edits = [
        (
            'ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "https://www.jakeaiofficial.com,https://jakeaiofficial.com").split(",") if o.strip()]\n',
            'ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "https://www.jakeaiofficial.com,https://jakeaiofficial.com").split(",") if o.strip()]\nNETWORK_FETCH_TOOLS_ENABLED = os.environ.get("NETWORK_FETCH_TOOLS_ENABLED", "false").strip().lower() == "true"\n',
        ),
        (
            'def extract_markdown(req: ExtractRequest):\n    """Clean web-to-markdown text extractor for LLMs"""\n    # SSRF protection',
            'def extract_markdown(req: ExtractRequest):\n    """Clean web-to-markdown text extractor for LLMs."""\n    if not NETWORK_FETCH_TOOLS_ENABLED:\n        raise HTTPException(status_code=503, detail="External network-fetch tools are disabled pending hardened egress controls.")\n    # SSRF protection',
        ),
        (
            'def audit_agent_card(req: AgentAuditRequest):\n    """Audits any domain for llms.txt & agent-card readability"""\n    clean_domain = req.domain.replace("https://", "").replace("http://", "").strip("/")',
            'def audit_agent_card(req: AgentAuditRequest):\n    """Audits a domain for llms.txt & agent-card readability when hardened egress is enabled."""\n    if not NETWORK_FETCH_TOOLS_ENABLED:\n        raise HTTPException(status_code=503, detail="External network-fetch tools are disabled pending hardened egress controls.")\n    clean_domain = req.domain.replace("https://", "").replace("http://", "").strip("/")',
        ),
        (
            '    anthropic_key = request.headers.get("X-Anthropic-Key") or os.environ.get("ANTHROPIC_API_KEY", "").strip()\n    perplexity_key = request.headers.get("X-Perplexity-Key") or os.environ.get("PERPLEXITY_API_KEY", "").strip()',
            '    # Provider credentials are server-side configuration only; never accept secrets in request headers.\n    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()\n    perplexity_key = os.environ.get("PERPLEXITY_API_KEY", "").strip()',
        ),
    ]

    for old, new in edits:
        text, did = replace_once(text, old, new)
        if did:
            changed.append(old.splitlines()[0][:72])

    MAIN.write_text(text, encoding="utf-8")
    if changed:
        print("Applied network hardening:")
        for item in changed:
            print(f"- {item}")
    else:
        print("No network hardening changes required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
