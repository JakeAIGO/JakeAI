const clamp=(n,min,max)=>Math.max(min,Math.min(max,n));

export function text(value,max=2500){
  return String(value??"").replace(/\u0000/g,"").trim().slice(0,max);
}

export function normalizeIntake(raw={}){
  return {
    name:text(raw.name,160),
    email:text(raw.email,240).toLowerCase(),
    company:text(raw.company,240),
    role:text(raw.role,180),
    job:text(raw.job,2500),
    desired_outcome:text(raw.desired_outcome,1800),
    tools:text(raw.tools,1500),
    approval_boundaries:text(raw.approval_boundaries,1800),
    frequency:text(raw.frequency,120),
    data_sensitivity:text(raw.data_sensitivity,120),
    constraints_context:text(raw.constraints_context,2200),
    bot_field:text(raw["bot-field"]||raw.bot_field,200)
  };
}

export function detectSecrets(intake){
  const hay=[intake.job,intake.desired_outcome,intake.tools,intake.approval_boundaries,intake.constraints_context].join("\n");
  const patterns=[
    /-----BEGIN [A-Z ]*PRIVATE KEY-----/i,
    /\bsk-[A-Za-z0-9_-]{16,}\b/,
    /\bgh[pousr]_[A-Za-z0-9]{20,}\b/i,
    /\bAKIA[A-Z0-9]{16}\b/,
    /\b(?:password|passwd|api[_ -]?key|secret|access[_ -]?token)\s*[:=]\s*[^\s,;]{8,}/i
  ];
  return patterns.some(r=>r.test(hay));
}

function words(s){return text(s,5000).toLowerCase();}
function toolCount(s){
  const parts=text(s,1500).split(/[\n,;]+/).map(x=>x.trim()).filter(Boolean);
  return Math.min(new Set(parts.map(x=>x.toLowerCase())).size,12);
}
function hasAny(s,arr){return arr.some(x=>s.includes(x));}

export function qualifyCase(intake){
  const job=words(intake.job), outcome=words(intake.desired_outcome), tools=words(intake.tools), boundaries=words(intake.approval_boundaries);
  let score=20;
  const freq=intake.frequency.toLowerCase();
  if(freq.includes("several")) score+=20;
  else if(freq.includes("daily")) score+=18;
  else if(freq.includes("event")||freq.includes("message")) score+=18;
  else if(freq.includes("weekly")) score+=14;
  else if(freq.includes("needed")) score+=8;
  else score+=6;

  if(intake.job.length>=120) score+=10; else if(intake.job.length>=50) score+=6;
  if(intake.desired_outcome.length>=90) score+=12; else if(intake.desired_outcome.length>=40) score+=7;
  if(hasAny(outcome,["time","hour","minute","cost","revenue","accuracy","response","lead","error","miss","faster","reduce","increase","percent","%"])) score+=5;
  const tc=toolCount(intake.tools);
  if(tc>0) score+=8;
  if(hasAny(tools,["gmail","email","google drive","drive","slack","crm","spreadsheet","sheets","github","website","browser","netlify"])) score+=4;
  if(intake.approval_boundaries.length>=30) score+=9;
  if(hasAny(boundaries,["send","spend","purchase","submit","delete","publish","contract","payment","external"])) score+=4;
  if(intake.constraints_context.length>=30) score+=4;

  let riskPoints=0;
  const sensitivity=intake.data_sensitivity.toLowerCase();
  if(sensitivity.includes("regulated")) riskPoints+=5;
  else if(sensitivity.includes("personal")) riskPoints+=3;
  else if(sensitivity.includes("confidential")) riskPoints+=2;
  else if(sensitivity.includes("not sure")) riskPoints+=2;

  const actionText=job+" "+outcome+" "+tools;
  if(hasAny(actionText,["purchase","payment","spend money","wire transfer","bank account"])) riskPoints+=4;
  if(hasAny(actionText,["delete","destroy","terminate","cancel account"])) riskPoints+=3;
  if(hasAny(actionText,["submit bid","submit proposal","sign contract","execute contract"])) riskPoints+=4;
  if(hasAny(actionText,["publish publicly","post publicly","send automatically","email automatically"])) riskPoints+=2;
  if(hasAny(actionText,["medical","patient","health record","legal advice","credit decision","employment decision"])) riskPoints+=4;

  const risk=riskPoints>=7?"high":riskPoints>=3?"medium":"low";
  if(risk==="high") score-=18; else if(risk==="medium") score-=7;
  score=clamp(score,0,100);

  const open=[];
  if(tc===0) open.push("Which systems or tools contain the inputs and where should the output land?");
  if(intake.approval_boundaries.length<30) open.push("Which actions must always stop for explicit human approval?");
  if(intake.desired_outcome.length<70) open.push("What measurable result would prove the pilot is useful?");
  if(freq.includes("needed")||freq==="other") open.push("What exact event or condition should trigger the workflow?");
  if(tc>=5) open.push("Which tools are mandatory for phase one, and which can wait?");
  if(sensitivity.includes("regulated")||sensitivity.includes("not sure")) open.push("What compliance, retention, access-control or audit requirements apply?");
  if(!intake.role) open.push("Who owns final operational approval for this workflow?");

  const fit=(score>=75&&risk!=="high")?"strong-fit":score>=55?"review":"needs-clarification";
  const complexity=tc>=5?"high":tc>=3?"medium":"low";

  let setup=500, monthly=199;
  if(freq.includes("several")||freq.includes("event")){setup+=200;monthly+=100;}
  if(tc>=4){setup+=250;monthly+=100;}
  if(sensitivity.includes("confidential")){setup+=150;monthly+=50;}
  if(sensitivity.includes("personal")){setup+=300;monthly+=150;}
  if(sensitivity.includes("regulated")){setup+=750;monthly+=400;}
  if(risk==="high"){setup+=250;monthly+=100;}
  setup=Math.ceil(setup/50)*50;
  monthly=Math.ceil(monthly/50)*50-1;

  const gates=[];
  if(boundaries) gates.push(intake.approval_boundaries);
  else gates.push("External communications, spending, publication, destructive actions and contractual commitments require human approval.");
  if(risk!=="low") gates.push("Production authority remains disabled until the risk/compliance review is complete.");

  return {
    score,fit,risk,complexity,tool_count:tc,
    preliminary_price:{setup_from:setup,managed_monthly_from:monthly,currency:"USD",internal_estimate_only:true},
    open_questions:open.slice(0,6),
    approval_gates:gates,
    recommended_path:risk==="high"?"scope → risk review → bounded prototype → evidence → human release":"scope → bounded prototype → evidence → human release"
  };
}

export function buildDraftProposal(intake,q){
  const tools=intake.tools||"Tools to be confirmed during scoping";
  const questions=q.open_questions.length?q.open_questions.map(x=>"• "+x).join("\n"):"• No blocking clarification identified by first-pass triage.";
  return [
    "JakeAI Founding Pilot — Draft Scope",
    "",
    "Recurring job",
    intake.job,
    "",
    "Desired outcome",
    intake.desired_outcome,
    "",
    "Phase-one systems",
    tools,
    "",
    "Proposed path",
    q.recommended_path,
    "",
    "Human approval gates",
    ...q.approval_gates.map(x=>"• "+x),
    "",
    "Open questions",
    questions,
    "",
    "Internal preliminary commercial band",
    "Pilot setup: from $"+q.preliminary_price.setup_from,
    "Managed operation after successful pilot: from $"+q.preliminary_price.managed_monthly_from+"/month",
    "",
    "This is an internal draft, not a customer quote or authorization. Final scope and price require human approval."
  ].join("\n");
}