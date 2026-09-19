import { getStore, getDeployStore } from "@netlify/blobs";
import { normalizeIntake, detectSecrets, qualifyCase, buildDraftProposal } from "../../lib/pilot-concierge-core.mjs";

function conciergeStore(){
  return Netlify.context?.deploy?.context === "production"
    ? getStore("jakeai-pilot-concierge", { consistency: "strong" })
    : getDeployStore("jakeai-pilot-concierge");
}
function response(body,status=200){
  return Response.json(body,{status,headers:{"Cache-Control":"no-store"}});
}
function adminAuthorized(req){
  const expected=Netlify.env.get("PILOT_CONCIERGE_ADMIN_TOKEN");
  if(!expected) return false;
  return (req.headers.get("authorization")||"") === "Bearer "+expected;
}
async function parseBody(req){
  const type=(req.headers.get("content-type")||"").toLowerCase();
  if(type.includes("application/json")) return await req.json();
  const params=new URLSearchParams(await req.text());
  return Object.fromEntries(params.entries());
}
async function ipHash(req){
  const raw=(req.headers.get("x-nf-client-connection-ip")||req.headers.get("x-forwarded-for")||"unknown").split(",")[0].trim();
  const bytes=new TextEncoder().encode(raw+"|pilot-concierge-v1");
  const hash=await crypto.subtle.digest("SHA-256",bytes);
  return Array.from(new Uint8Array(hash)).slice(0,12).map(b=>b.toString(16).padStart(2,"0")).join("");
}
async function rateAllowed(store,req){
  const h=await ipHash(req);
  const hour=new Date().toISOString().slice(0,13);
  const key="rate/"+hour+"/"+h;
  const current=await store.get(key,{type:"json"})||{count:0};
  const next={count:Number(current.count||0)+1,updated_at:new Date().toISOString()};
  await store.setJSON(key,next);
  return next.count<=5;
}
function validEmail(value){
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}
function caseId(){
  const stamp=new Date().toISOString().replace(/[-:.TZ]/g,"").slice(0,14);
  return "PC-"+stamp+"-"+crypto.randomUUID().slice(0,8).toUpperCase();
}
function publicReceipt(record){
  return {
    ok:true,
    id:record.id,
    received_at:record.created_at,
    fit:record.qualification.fit,
    next_step:"Human scope review required before any commercial commitment."
  };
}
async function listCases(store){
  const {blobs}=await store.list({prefix:"case/"});
  const rows=[];
  for(const b of blobs.slice(-150)){
    const item=await store.get(b.key,{type:"json"});
    if(item) rows.push(item);
  }
  rows.sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)));
  return rows.slice(0,100);
}

export default async (req)=>{
  const store=conciergeStore();

  if(req.method==="POST"){
    const raw=await parseBody(req);
    const isAdmin=adminAuthorized(req);
    const dryRun=Boolean(raw?.dry_run)&&isAdmin;
    const intake=normalizeIntake(raw);

    if(intake.bot_field) return response({ok:true});
    if(!dryRun && !(await rateAllowed(store,req))) return response({error:"Too many submissions from this connection. Please try again later."},429);
    if(!intake.name||!validEmail(intake.email)||intake.job.length<25||intake.desired_outcome.length<20){
      return response({error:"Please provide a name, valid email, recurring job, and desired outcome."},400);
    }
    if(detectSecrets(intake)){
      return response({error:"Possible credential or secret detected. Remove passwords, API keys, private keys, or access tokens and submit again."},422);
    }

    const qualification=qualifyCase(intake);
    const now=new Date().toISOString();
    const id=dryRun?"PC-DRY-RUN":caseId();
    const record={
      schema_version:"1.0",
      id,
      source:dryRun?"internal-dry-run":"founding-pilot-web-intake",
      input_trust:"untrusted_external",
      created_at:now,
      updated_at:now,
      queue_status:"new",
      intake,
      qualification,
      draft_proposal:buildDraftProposal(intake,qualification),
      authority:{
        customer_contact_authorized:false,
        spending_authorized:false,
        production_deployment_authorized:false,
        external_account_access_authorized:false,
        public_release_authorized:false
      },
      audit:[
        {at:now,event:"intake_received",actor:dryRun?"internal-test":"public-form"},
        {at:now,event:"auto_qualified",actor:"pilot-concierge-v1",score:qualification.score,risk:qualification.risk,fit:qualification.fit}
      ]
    };
    if(dryRun) return response({ok:true,dry_run:true,case:record});
    await store.setJSON("case/"+id,record);
    return response(publicReceipt(record),201);
  }

  if(req.method==="GET"){
    if(!adminAuthorized(req)) return response({error:"Unauthorized"},401);
    return response({ok:true,cases:await listCases(store)});
  }

  if(req.method==="PATCH"){
    if(!adminAuthorized(req)) return response({error:"Unauthorized"},401);
    const body=await parseBody(req);
    const id=String(body?.id||"").slice(0,80);
    const nextStatus=String(body?.status||"").slice(0,80);
    const note=String(body?.note||"").trim().slice(0,1500);
    const allowed=new Set(["new","approved_for_scoping","proposal_ready","hold","declined"]);
    if(!id||!allowed.has(nextStatus)) return response({error:"Invalid case update"},400);
    const key="case/"+id;
    const record=await store.get(key,{type:"json"});
    if(!record) return response({error:"Case not found"},404);
    const now=new Date().toISOString();
    record.queue_status=nextStatus;
    record.updated_at=now;
    record.audit=Array.isArray(record.audit)?record.audit:[];
    record.audit.push({at:now,event:"queue_status_changed",actor:"human-operator",status:nextStatus,note:note||undefined});
    await store.setJSON(key,record);
    return response({ok:true,case:record});
  }

  return response({error:"Method not allowed"},405);
};

export const config={path:"/pilot-concierge-api"};