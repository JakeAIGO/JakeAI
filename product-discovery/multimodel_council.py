"""Jake AI Multi-Model Advisory Council.

Real provider calls are opt-in, provenance-recorded, and fail closed. A provider is
never marked as participating unless a successful response is captured. Advisory
output is issue-spotting/research only; it is not legal approval or professional advice.
"""
from __future__ import annotations
import hashlib, json, os, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

SYSTEM = """You are one independent member of the Jake AI Multi-Model Advisory Council. Analyze only the supplied review package. Identify material risks, missing evidence, required mitigations, and questions for qualified counsel. Do not claim legal approval. Return JSON only with: verdict (PASS_WITH_GATES|HOLD|REJECT), risks (array), mitigations (array), counsel_questions (array), confidence (0-1), rationale (string)."""

PROVIDERS = {
    "openai": {"key":"OPENAI_API_KEY", "model_env":"OPENAI_COUNCIL_MODEL", "model":"gpt-5.6-sol"},
    "anthropic": {"key":"ANTHROPIC_API_KEY", "model_env":"ANTHROPIC_COUNCIL_MODEL", "model":"claude-sonnet-5"},
    "gemini": {"key":"GEMINI_API_KEY", "model_env":"GEMINI_COUNCIL_MODEL", "model":"gemini-2.5-pro"},
    "perplexity": {"key":"PERPLEXITY_API_KEY", "model_env":"PERPLEXITY_COUNCIL_MODEL", "model":"sonar-pro"},
    "grok": {"key":"XAI_API_KEY", "model_env":"XAI_COUNCIL_MODEL", "model":"grok-4.6"},
}

def _post(url, body, headers):
    req=urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type":"application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())

def _prompt(package): return f"{SYSTEM}\n\nREVIEW PACKAGE:\n{package}"

def _openai(package, key, model):
    d=_post("https://api.openai.com/v1/responses", {"model":model,"input":_prompt(package),"store":False}, {"Authorization":f"Bearer {key}"})
    texts=[]
    for item in d.get("output",[]):
        for c in item.get("content",[]):
            if c.get("type") in ("output_text","text") and c.get("text"): texts.append(c["text"])
    return "\n".join(texts), d.get("id")

def _anthropic(package, key, model):
    d=_post("https://api.anthropic.com/v1/messages", {"model":model,"max_tokens":2500,"system":SYSTEM,"messages":[{"role":"user","content":package}]}, {"x-api-key":key,"anthropic-version":"2023-06-01"})
    return "\n".join(x.get("text","") for x in d.get("content",[]) if x.get("type")=="text"), d.get("id")

def _gemini(package, key, model):
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model, safe='')}:generateContent?key={urllib.parse.quote(key, safe='')}"
    d=_post(url, {"systemInstruction":{"parts":[{"text":SYSTEM}]},"contents":[{"role":"user","parts":[{"text":package}]}],"generationConfig":{"responseMimeType":"application/json"}}, {})
    texts=[]
    for cand in d.get("candidates",[]):
        texts += [p.get("text","") for p in cand.get("content",{}).get("parts",[]) if p.get("text")]
    return "\n".join(texts), d.get("responseId")

def _chat_compatible(url, package, key, model):
    d=_post(url, {"model":model,"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":package}]}, {"Authorization":f"Bearer {key}"})
    return d["choices"][0]["message"]["content"], d.get("id")

def _perplexity(package,key,model): return _chat_compatible("https://api.perplexity.ai/chat/completions",package,key,model)
def _grok(package,key,model): return _chat_compatible("https://api.x.ai/v1/chat/completions",package,key,model)
ADAPTERS={"openai":_openai,"anthropic":_anthropic,"gemini":_gemini,"perplexity":_perplexity,"grok":_grok}

def _parse(text):
    s=text.strip()
    if s.startswith("```"):
        s=s.split("\n",1)[1].rsplit("```",1)[0].strip()
        if s.startswith("json"): s=s[4:].lstrip()
    obj=json.loads(s)
    if obj.get("verdict") not in {"PASS_WITH_GATES","HOLD","REJECT"}: raise ValueError("invalid verdict")
    return obj

def run(package, out_path="product-discovery/run-output/council-latest.json", live=None):
    live=(os.getenv("COUNCIL_LIVE_CALLS")=="1") if live is None else live
    digest=hashlib.sha256(package.encode()).hexdigest()
    report={"schema":"jakeai.council.v2","created_at":int(time.time()),"advisory_only":True,"package_sha256":digest,"live_calls_authorized":bool(live),"members":{}}
    for name,cfg in PROVIDERS.items():
        key=os.getenv(cfg["key"]); model=os.getenv(cfg["model_env"],cfg["model"])
        base={"provider":name,"model_requested":model,"participated":False}
        if not key:
            report["members"][name]={**base,"status":"NOT_CONFIGURED"}; continue
        if not live:
            report["members"][name]={**base,"status":"LIVE_CALL_NOT_AUTHORIZED"}; continue
        try:
            text, request_id=ADAPTERS[name](package,key,model)
            analysis=_parse(text)
            report["members"][name]={**base,"status":"SUCCESS","participated":True,"request_id":request_id,"received_at":int(time.time()),"analysis":analysis}
        except Exception as e:
            report["members"][name]={**base,"status":"ERROR","error_type":type(e).__name__,"error":str(e)[:500]}
    successful=[v for v in report["members"].values() if v.get("participated")]
    verdicts=[v["analysis"]["verdict"] for v in successful]
    report["participating_count"]=len(successful)
    report["status"]="COUNCIL_COMPLETE" if len(successful)==len(PROVIDERS) else ("COUNCIL_PARTIAL" if successful else "HOLD_NO_VERIFIED_RESPONSES")
    report["consensus"]={"unanimous":bool(verdicts) and len(set(verdicts))==1,"verdict":verdicts[0] if verdicts and len(set(verdicts))==1 else None,"verdicts":verdicts}
    Path(out_path).parent.mkdir(parents=True,exist_ok=True)
    Path(out_path).write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    import sys
    if len(sys.argv)<2: raise SystemExit("usage: multimodel_council.py <review-package>")
    package=Path(sys.argv[1]).read_text(encoding="utf-8")
    print(json.dumps(run(package),indent=2))
