import { getStore } from "@netlify/blobs";

export default async (_request: Request) => {
  const store=getStore("jakeai-agent-observatory",{consistency:"strong"});
  const {blobs}=await store.list();
  const now=Date.now();
  const cut24=now-24*60*60*1000;
  const cut7=now-7*24*60*60*1000;
  const events:any[]=[];
  for(const item of blobs){
    try{
      const e=await store.get(item.key,{type:"json"});
      if(e && new Date(e.at).getTime()>=cut7) events.push(e);
    }catch(_){}
  }
  events.sort((a,b)=>String(b.at).localeCompare(String(a.at)));
  const fam=new Map<string,any>();
  const surfaces=new Map<string,number>();
  let requests24=0,machine24=0,verified24=0;
  for(const e of events){
    const ts=new Date(e.at).getTime();
    if(ts>=cut24){
      requests24++;
      if(e.machine_surface) machine24++;
      if(e.verification==="verified-ip") verified24++;
    }
    const fk=[e.provider,e.agent,e.purpose,e.verification].join("|");
    const prev=fam.get(fk)||{provider:e.provider,agent:e.agent,purpose:e.purpose,verification:e.verification,requests:0};
    prev.requests++; fam.set(fk,prev);
    if(e.machine_surface) surfaces.set(e.path,(surfaces.get(e.path)||0)+1);
  }
  const families=[...fam.values()].sort((a,b)=>b.requests-a.requests||String(a.agent).localeCompare(String(b.agent))).slice(0,20);
  const machine_surfaces=[...surfaces.entries()].map(([path,requests])=>({path,requests})).sort((a,b)=>b.requests-a.requests||a.path.localeCompare(b.path)).slice(0,20);
  return Response.json({
    service:"JakeAI AI Agent Observatory",
    measurement:"server-side edge observation; privacy-minimized",
    requests_24h:requests24,
    verified_requests_24h:verified24,
    machine_surface_reads_24h:machine24,
    families,
    machine_surfaces,
    latest:events.slice(0,20),
    verification_note:"claimed-ua means the crawler identified itself by user-agent but was not independently authenticated. Machine-surface means a direct read of a JakeAI machine-readable discovery surface. Raw IP addresses and raw user-agent strings are not stored."
  },{headers:{"cache-control":"no-store"}});
};

export const config={path:"/agent-observatory-summary.json"};
