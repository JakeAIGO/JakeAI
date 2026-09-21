(()=>{"use strict";
if(navigator.globalPrivacyControl===true||navigator.doNotTrack==="1"||window.doNotTrack==="1")return;
if(location.pathname.startsWith("/mission-control")||location.pathname.startsWith("/traffic-monitor"))return;
const uuid=()=>crypto.randomUUID?crypto.randomUUID():(Date.now().toString(36)+"-"+Math.random().toString(36).slice(2)+"-"+Math.random().toString(36).slice(2));
const getId=(store,key)=>{try{let v=store.getItem(key);if(!v){v=uuid();store.setItem(key,v)}return v}catch(e){return uuid()}};
const visitor=getId(localStorage,"jakeai_anon_visitor");
const session=getId(sessionStorage,"jakeai_anon_session");
const internal=(()=>{try{return localStorage.getItem("jakeai_internal_operator")==="1"||navigator.webdriver===true}catch(e){return navigator.webdriver===true}})();
const params=new URLSearchParams(location.search);
let source="",medium="",campaign="";
try{
  source=sessionStorage.getItem("jakeai_acq_source")||"";
  medium=sessionStorage.getItem("jakeai_acq_medium")||"";
  campaign=sessionStorage.getItem("jakeai_acq_campaign")||"";
}catch(e){}
let refHost="";
try{refHost=document.referrer?new URL(document.referrer).hostname:""}catch(e){}
if(!source){
  source=(params.get("utm_source")||((refHost&&refHost!==location.hostname)?refHost:"direct")).slice(0,160);
  medium=(params.get("utm_medium")||"").slice(0,120);
  campaign=(params.get("utm_campaign")||"").slice(0,180);
  try{
    sessionStorage.setItem("jakeai_acq_source",source);
    sessionStorage.setItem("jakeai_acq_medium",medium);
    sessionStorage.setItem("jakeai_acq_campaign",campaign);
  }catch(e){}
}
const device=()=>{
  const w=Math.min(screen.width||innerWidth,screen.height||innerHeight);
  return w<600?"mobile":w<1024?"tablet":"desktop";
};
const cleanPath=()=>location.pathname+(["#commission","#foundry","#arcade","#catalog","#direct"].includes(location.hash)?location.hash:"");
const send=(event_type,extra={})=>{
  const body={
    event_id:uuid(),
    visitor_id:visitor,
    session_id:session,
    event_type,
    path:String(extra.path||cleanPath()).slice(0,500),
    referrer_host:String(refHost||"").slice(0,240),
    source:String(source||"direct").slice(0,160),
    medium:String(medium||"").slice(0,120),
    campaign:String(campaign||"").slice(0,180),
    device:device(),
    internal
  };
  try{
    fetch("/api/v1/traffic/event",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(body),
      keepalive:true,
      credentials:"omit"
    }).catch(()=>{});
  }catch(e){}
};
window.JakeAITraffic={track:(type,extra)=>send(type,extra||{})};
send("page_view");
const section=()=>{if(location.hash==="#commission")send("commission_view",{path:"/#commission"})};
section();
addEventListener("hashchange",section,{passive:true});
document.addEventListener("click",e=>{
  const a=e.target&&e.target.closest?e.target.closest("a[href]"):null;
  if(!a)return;
  let u;try{u=new URL(a.href,location.href)}catch(err){return}
  if(u.origin!==location.origin)return;
  if(/^\/(product-factory|arcade|catalog|direct)\/?/.test(u.pathname)||u.hash==="#commission"){
    send("cta",{path:u.pathname+(u.hash||"")});
  }
},{passive:true});
})();