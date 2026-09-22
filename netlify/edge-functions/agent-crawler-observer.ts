import { getStore } from "@netlify/blobs";
function classify(ua: string, machineSurface: boolean) {
  const s=(ua||"").toLowerCase();
  const signatures=[
    ["openai","OAI-SearchBot","search","oai-searchbot"],
    ["openai","GPTBot","training-crawler","gptbot"],
    ["openai","ChatGPT-User","user-fetch","chatgpt-user"],
    ["openai","OAI-AdsBot","ads-validation","oai-adsbot"],
    ["anthropic","Claude-SearchBot","search","claude-searchbot"],
    ["anthropic","Claude-User","user-fetch","claude-user"],
    ["anthropic","ClaudeBot","training-crawler","claudebot"],
    ["perplexity","Perplexity-User","user-fetch","perplexity-user"],
    ["perplexity","PerplexityBot","search","perplexitybot"],
    ["google","Googlebot","search","googlebot"],
    ["microsoft","bingbot","search","bingbot"],
    ["apple","Applebot","search-ai","applebot"],
    ["amazon","Amazonbot","search-ai","amazonbot"],
    ["meta","Meta-ExternalAgent","ai-crawler","meta-externalagent"],
    ["commoncrawl","CCBot","web-crawler","ccbot"],
  ];
  for(const [provider,agent,purpose,needle] of signatures){
    if(s.includes(needle)) return {provider,agent,purpose,verification:"claimed-ua"};
  }
  if(/bot|crawler|spider|slurp|headless/.test(s)) return {provider:"other",agent:"UnidentifiedBot",purpose:"crawler",verification:"generic-bot"};
  if(machineSurface) return {provider:"unknown",agent:"MachineClient",purpose:"machine-discovery",verification:"machine-surface"};
  return null;
}

async function record(request: Request, context: any, response: Response, machineSurface: boolean) {
  if (request.method!=="GET" && request.method!=="HEAD") return;
  const url=new URL(request.url);
  if(url.hostname!=="jakeaiofficial.com") return;
  const info=classify(request.headers.get("user-agent")||"",machineSurface);
  if(!info) return;
  const now=new Date();
  const event={
    at:now.toISOString(),
    provider:info.provider,
    agent:info.agent,
    purpose:info.purpose,
    verification:info.verification,
    path:url.pathname,
    status:response.status,
    machine_surface:Boolean(machineSurface)
  };
  const key=now.toISOString().slice(0,10)+"/"+String(context.requestId||crypto.randomUUID());
  const store=getStore("jakeai-agent-observatory",{consistency:"strong"});
  await store.setJSON(key,event);
}


export default async (request: Request, context: any) => {
  const response=await context.next();
  try{await record(request,context,response,false)}catch(_){}
  return response;
};
export const config={
  path:"/*",
  excludedPath:["/api/*","/mission-control/*","/traffic-monitor/*","/assets/*","/*.css","/*.js","/*.jpg","/*.jpeg","/*.png","/*.webp","/*.svg","/*.gif","/*.mp4","/*.webm","/*.woff","/*.woff2","/*.ico"]
};
