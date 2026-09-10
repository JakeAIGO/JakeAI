"""Jake AI Multi-Model Advisory Council orchestrator.

Calls only providers that are actually configured and records provenance. Never
fabricates a provider response. Missing providers fail closed. Advisory output is
issue-spotting/research, not legal approval or professional advice.
"""
from __future__ import annotations
import json, os, time, urllib.request
from pathlib import Path

PROVIDERS = {
 "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1/responses", "gpt-5.6"),
 "anthropic": ("ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/messages", "claude-sonnet-4-5"),
 "gemini": ("GEMINI_API_KEY", None, "gemini-2.5-pro"),
 "perplexity": ("PERPLEXITY_API_KEY", "https://api.perplexity.ai/chat/completions", "sonar-pro"),
 "grok": ("XAI_API_KEY", "https://api.x.ai/v1/chat/completions", "grok-4"),
}

SYSTEM = """You are one independent member of the Jake AI Multi-Model Advisory Council. Analyze only the supplied package. Identify risks, missing evidence, required mitigations, and questions for qualified counsel. Do not claim legal approval. Return concise JSON with verdict (PASS_WITH_GATES|HOLD|REJECT), risks, mitigations, counsel_questions, confidence."""

def configured():
    return [name for name,(key,_,_) in PROVIDERS.items() if os.getenv(key)]

def run(package: str, out_path="product-discovery/run-output/council-latest.json"):
    # Provider adapters are intentionally explicit: a provider is never marked
    # participated unless a successful response is captured with timestamp/model.
    report={"schema":"jakeai.council.v1","created_at":int(time.time()),"advisory_only":True,
            "configured":configured(),"members":{},"status":"HOLD"}
    for name in PROVIDERS:
        if name not in report["configured"]:
            report["members"][name]={"status":"NOT_CONFIGURED","participated":False}
        else:
            report["members"][name]={"status":"ADAPTER_REQUIRED","participated":False,
              "note":"Credential detected; provider-specific transport must complete successfully before participation may be claimed."}
    report["status"]="READY_FOR_PROVIDER_ADAPTERS" if report["configured"] else "HOLD_NO_PROVIDERS_CONFIGURED"
    Path(out_path).parent.mkdir(parents=True,exist_ok=True)
    Path(out_path).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

if __name__ == "__main__":
    import sys
    package=Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv)>1 else ""
    print(json.dumps(run(package),indent=2))
