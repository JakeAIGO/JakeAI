// JakeAI: The Factory — deterministic, bounded Agent Arena simulation.
// Human UI and future machine clients can submit the same permitted strategy actions.
export const STRATEGIES={
  SPEED:{label:'SPEED',speed:1.55,reliability:.72,efficiency:.78,repair:.45},
  EFFICIENCY:{label:'EFFICIENCY',speed:.9,reliability:.9,efficiency:1.5,repair:.8},
  RELIABILITY:{label:'RELIABILITY',speed:.78,reliability:1.55,efficiency:.95,repair:1.25},
  ROOT_CAUSE:{label:'ROOT CAUSE',speed:.7,reliability:1.42,efficiency:1.15,repair:1.75}
};
export const CHALLENGES=[
 {id:'dependency_fault',label:'DEPENDENCY FAULT',weights:{speed:.12,reliability:.28,efficiency:.18,repair:.42}},
 {id:'launch_window',label:'LAUNCH WINDOW',weights:{speed:.38,reliability:.25,efficiency:.25,repair:.12}},
 {id:'budget_crunch',label:'BUDGET CRUNCH',weights:{speed:.12,reliability:.25,efficiency:.48,repair:.15}},
 {id:'regression_storm',label:'REGRESSION STORM',weights:{speed:.08,reliability:.42,efficiency:.14,repair:.36}}
];
function hash(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)}return h>>>0}
function noise(seed){let x=seed||1;return()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return(x>>>0)/4294967295}}
export function chooseStrategy(agent,challenge,history=[]){const keys=Object.keys(STRATEGIES),bias=agent==='CYAN'?{EFFICIENCY:.12,ROOT_CAUSE:.08}:{SPEED:.11,RELIABILITY:.09};let best=keys[0],bestScore=-1;for(const k of keys){const s=STRATEGIES[k],w=challenge.weights;let score=s.speed*w.speed+s.reliability*w.reliability+s.efficiency*w.efficiency+s.repair*w.repair+(bias[k]||0);if(history.at(-1)?.strategy===k)score-=.05;if(score>bestScore){bestScore=score;best=k}}return best}
export function runMatch(runNumber=1,history=[]){const challenge=CHALLENGES[(runNumber-1)%CHALLENGES.length],rng=noise(hash(`${challenge.id}:${runNumber}`));const agents=['CYAN','GOLD'].map(name=>{const strategy=chooseStrategy(name,challenge,history.filter(h=>h.agent===name)),s=STRATEGIES[strategy],w=challenge.weights;const base=(s.speed*w.speed+s.reliability*w.reliability+s.efficiency*w.efficiency+s.repair*w.repair)*70;const variance=(rng()-.5)*7;const score=Math.round(base+variance);return{name,strategy,score,reason:`${strategy} prioritized for ${challenge.label}`}});return{runNumber,challenge,agents,winner:[...agents].sort((a,b)=>b.score-a.score)[0]}}
export function validateAgentAction(action){const allowed=['select_strategy','repair_failure','route_product'];if(!action||!allowed.includes(action.action))return{accepted:false,error:'ACTION_NOT_PERMITTED'};if(action.action==='select_strategy'&&!STRATEGIES[action.choice])return{accepted:false,error:'UNKNOWN_STRATEGY'};return{accepted:true}}
