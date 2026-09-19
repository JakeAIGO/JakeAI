import { getStore, getDeployStore } from "@netlify/blobs";

const ALLOWED = new Set(["page_view","shared_visit","take","copy","share_click","explore_jakeai"]);

function store(){
  return Netlify.context?.deploy?.context === "production"
    ? getStore("emergency-companion-events")
    : getDeployStore("emergency-companion-events");
}
function clean(value,max=64){
  return String(value||"").replace(/[^a-zA-Z0-9._-]/g,"").slice(0,max)||"direct";
}
export default async (req) => {
  const s=store();

  if(req.method==="POST"){
    let body={};
    try{body=await req.json()}catch{}
    const event=String(body?.event||"");
    if(!ALLOWED.has(event)) return Response.json({error:"Invalid event"},{status:400});
    const now=new Date();
    const record={
      event,
      ref:clean(body?.ref),
      at:now.toISOString()
    };
    const key="event/"+now.toISOString().slice(0,10)+"/"+now.getTime()+"-"+crypto.randomUUID();
    await s.setJSON(key,record);
    return new Response(null,{status:204,headers:{"Cache-Control":"no-store"}});
  }

  if(req.method==="GET"){
    const {blobs}=await s.list({prefix:"event/"});
    const totals={page_view:0,shared_visit:0,take:0,copy:0,share_click:0,explore_jakeai:0};
    const refs={};
    for(const b of blobs){
      const row=await s.get(b.key,{type:"json"});
      if(!row||!ALLOWED.has(row.event)) continue;
      totals[row.event]=(totals[row.event]||0)+1;
      refs[row.ref]=(refs[row.ref]||0)+1;
    }
    const companionActions=totals.take+totals.copy;
    return Response.json({
      totals,
      companion_actions:companionActions,
      refs,
      note:"Aggregate event counts only; no IP address, user agent, email, account ID, or recipient identity is stored."
    },{headers:{"Cache-Control":"no-store"}});
  }

  return new Response("Method not allowed",{status:405});
};

export const config={path:"/emergency-companion-events"};