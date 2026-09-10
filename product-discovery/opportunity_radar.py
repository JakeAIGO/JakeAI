"""
JakeAI Opportunity Radar
Stage 0 of the Autonomous Product Discovery Pipeline
Version 0.2.1
"""
from __future__ import annotations
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RADAR_VERSION="0.2.1"

OPERATIONAL_TERMS={"shortage","bottleneck","capacity","delay","downtime","scrap","rework","yield","maintenance","compliance","integration","supplier","supply chain","inventory","quality","inspection","scheduling","planning","forecasting","monitoring","optimization","cost","labor","workforce","risk","incident","failure","production","manufacturing","deployment","logistics","energy","infrastructure","construction","robotics","recall","defect","constraint","backlog"}
VALUE_TERMS={"save","reduce","increase","improve","accelerate","prevent","avoid","optimize","automate","streamline","efficiency","productivity","revenue","cost","downtime","scrap","rework","yield","capacity","margin","profit","savings","growth","billion","million","investment"}
AI_EXECUTABLE_TERMS={"data","analysis","monitor","detect","classify","compare","score","rank","forecast","schedule","report","alert","document","research","review","optimize","recommend","triage","coordinate","workflow","software","api","digital","model","tracking","planning","inspection","prediction"}
BUSINESS_CHANGE_TERMS={"acquisition","acquire","acquires","acquiring","merger","buy","buys","buying","purchase","expansion","expand","factory opening","new factory","new plant","plant opening","facility opening","investment","contract","partnership","supplier","production increase","production ramp","capacity expansion","layoff","layoffs","restructuring","recall","regulation","regulatory","shortage","bottleneck","backlog","failure","shutdown","downtime"}
HIGH_IMPACT_TERMS={"billion","million","major","largest","record","critical","mission-critical","global","national","industry-wide","shortage","bottleneck","capacity"}
UNRESOLVED_VALUES={"","unknown","unresolved","none","null","n/a"}

def normalize(v): return "" if v is None else re.sub(r"\s+"," ",str(v)).strip().lower()
def matches(t,terms): return sorted(x for x in terms if x in t)
def unresolved(v): return normalize(v) in UNRESOLVED_VALUES

def evaluate_signal(s):
    text=normalize(" ".join(str(s.get(k) or "") for k in ("title","summary","description","content","problem","industry","why_it_matters","economic_value","work_created")))
    op,val,exe,bus,imp=(matches(text,x) for x in (OPERATIONAL_TERMS,VALUE_TERMS,AI_EXECUTABLE_TERMS,BUSINESS_CHANGE_TERMS,HIGH_IMPACT_TERMS))
    source=s.get("source") or s.get("source_name"); url=s.get("source_url") or s.get("url"); pub=s.get("published_at")
    try: independent=int(s.get("independent_sources",1))
    except (TypeError,ValueError): independent=1
    ps,vs,xs,bs,is_ = min(25,len(op)*4),min(20,len(val)*4),min(20,len(exe)*3),min(20,len(bus)*5),min(10,len(imp)*3)
    es=min(15,(5 if source else 0)+(5 if url else 0)+(3 if pub else 0)+(min(7,independent-1) if independent>1 else 0))
    total=min(100,ps+vs+xs+bs+is_+es)
    research={"buyer_unresolved":unresolved(s.get("buyer")),"work_created_unresolved":unresolved(s.get("work_created")),"economic_value_unresolved":unresolved(s.get("economic_value")),"repeatability_unresolved":unresolved(s.get("repeatable"))}
    n=sum(research.values()); meaningful=bool(op or bus or imp)
    disposition="PROMOTE_TO_DISCOVERY" if total>=70 and n<=1 else ("NEEDS_MORE_EVIDENCE" if meaningful and (total>=25 or n>=2) else "REJECT_NOISE")
    if disposition=="PROMOTE_TO_DISCOVERY" and (not source or not url): disposition="NEEDS_MORE_EVIDENCE"
    action={"PROMOTE_TO_DISCOVERY":"SEND_TO_PRODUCT_DISCOVERY","NEEDS_MORE_EVIDENCE":"RESEARCH_COMMERCIAL_EVIDENCE","REJECT_NOISE":"ARCHIVE_SIGNAL"}[disposition]
    research["unresolved_fields"]=n
    return {"radar_version":RADAR_VERSION,"evaluated_at":datetime.now(timezone.utc).isoformat(),"signal_id":s.get("signal_id") or s.get("id"),"title":s.get("title","Untitled signal"),"industry":s.get("industry","Unknown"),"source":source,"source_url":url,"published_at":pub,"radar_score":total,"disposition":disposition,"next_action":action,"score_breakdown":{"real_operational_problem":ps,"economic_value_signal":vs,"ai_executability":xs,"business_change_signal":bs,"impact_signal":is_,"evidence_quality":es},"research_status":research,"evidence":{"operational_signals":op,"value_signals":val,"ai_executable_signals":exe,"business_change_signals":bus,"high_impact_signals":imp,"independent_sources":independent},"original_signal":s}

def save_result(r):
    d=Path("product-discovery/radar-output"); d.mkdir(parents=True,exist_ok=True)
    sid=r.get("signal_id") or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    p=d/f"{re.sub(r'[^A-Za-z0-9._-]','-',str(sid))}-radar.json"
    p.write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding="utf-8"); return p

def main():
    if len(sys.argv)!=2: print("Usage: python product-discovery/opportunity_radar.py <signal.json>"); return 2
    p=Path(sys.argv[1])
    if not p.exists(): print(f"ERROR: Signal file not found: {p}"); return 2
    r=evaluate_signal(json.loads(p.read_text(encoding="utf-8"))); out=save_result(r)
    print("="*70,"\nJAKEAI OPPORTUNITY RADAR — STAGE 0 v0.2.1\n","="*70,sep="")
    print(f"Signal: {r['title']}\nIndustry: {r['industry']}\nRadar score: {r['radar_score']} / 100\nDisposition: {r['disposition']}\nNext action: {r['next_action']}\n\nOutput: {out}\n"+"="*70)
    return 0

if __name__=="__main__": raise SystemExit(main())
