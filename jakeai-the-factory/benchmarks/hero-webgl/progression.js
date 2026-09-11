// Persistent, evolving Factory progression. Local-first: no account or paid backend required.
const KEY='jakeai_factory_save_v1';
export const DISTRICTS=[
 {id:'origin',name:'Origin Bay',xp:0},
 {id:'repair',name:'Self-Repair Bay',xp:40},
 {id:'arena',name:'Agent Arena',xp:90},
 {id:'observatory',name:'Opportunity Observatory',xp:160},
 {id:'social',name:'Social City',xp:260},
 {id:'council',name:'Council Chamber',xp:400},
 {id:'beyond',name:'The Beyond',xp:650}
];
export function newSave(){return{version:1,createdAt:Date.now(),lastVisit:Date.now(),visits:1,xp:0,level:1,products:0,learning:0,arenaRuns:0,streak:1,lastDay:new Date().toISOString().slice(0,10),unlocks:['origin'],discoveries:[],legacy:[]}}
export function loadSave(){try{const x=JSON.parse(localStorage.getItem(KEY));if(!x)return newSave();const today=new Date().toISOString().slice(0,10);if(x.lastDay!==today){const d=Math.round((new Date(today)-new Date(x.lastDay))/86400000);x.streak=d===1?(x.streak||1)+1:1;x.lastDay=today;x.visits=(x.visits||1)+1}x.lastVisit=Date.now();return normalize(x)}catch{return newSave()}}
function normalize(s){s.xp=s.xp||0;s.level=Math.max(1,Math.floor(s.xp/100)+1);s.unlocks=DISTRICTS.filter(d=>s.xp>=d.xp).map(d=>d.id);return s}
export function award(s,{xp=0,products=0,learning=0,arenaRuns=0,discovery=null}={}){s.xp+=xp;s.products+=products;s.learning+=learning;s.arenaRuns+=arenaRuns;if(discovery&&!s.discoveries.includes(discovery))s.discoveries.push(discovery);normalize(s);save(s);return s}
export function save(s){s.lastVisit=Date.now();localStorage.setItem(KEY,JSON.stringify(s))}
export function returnHook(s){const next=DISTRICTS.find(d=>!s.unlocks.includes(d.id));const hooks=[];if(next)hooks.push(`${next.name} unlocks at ${next.xp} XP`);hooks.push(`Factory visit streak: ${s.streak} day${s.streak===1?'':'s'}`);const daily=['Dependency Kraken','Viral Storm','Budget Blackout','Compliance Dragon','Infinite Retry Loop'];const day=Math.floor(Date.now()/86400000);hooks.push(`Today's anomaly: ${daily[day%daily.length]}`);return hooks}
export function snapshot(s){return{level:s.level,xp:s.xp,visits:s.visits,streak:s.streak,products:s.products,learning:s.learning,arenaRuns:s.arenaRuns,unlocks:[...s.unlocks],discoveries:[...s.discoveries]}}
