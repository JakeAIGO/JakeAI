import * as THREE from 'three';
import{worldProfile,dominantTrait}from'./progression.js';
export function evolveWorld({scene,hall,save,materials}){const {mc,mm,mg,dark}=materials,p=worldProfile(save),trait=dominantTrait(save),g=new THREE.Group();g.name='PLAYER_HISTORY_ARCHITECTURE';hall.add(g);
// Every unlocked district adds a visible skyline beacon.
(save.unlocks||[]).forEach((id,i)=>{const a=i/Math.max(1,save.unlocks.length)*Math.PI*2,r=15+i*.55,h=2.5+i*1.1+save.level*.18,m=trait==='velocity'?mg:(trait==='discovery'?mm:mc),tower=new THREE.Mesh(new THREE.CylinderGeometry(.45,.8,h,6),i%3===0?m:dark);tower.position.set(Math.cos(a)*r,h/2,-22+Math.sin(a)*r);g.add(tower);const cap=new THREE.Mesh(new THREE.TorusGeometry(.72,.07,8,32),m);cap.rotation.x=Math.PI/2;cap.position.set(tower.position.x,h+.1,tower.position.z);g.add(cap)});
// Learning becomes a literal memory constellation above the production core.
const memories=Math.min(32,(save.learning||0)+(save.discoveries?.length||0));for(let i=0;i<memories;i++){const a=i*.91,r=4+(i%5)*.7,y=10+(i%4)*.7,n=new THREE.Mesh(new THREE.OctahedronGeometry(.13+(i%3)*.035),i%2?mc:mm);n.position.set(Math.cos(a)*r,y,-24+Math.sin(a)*r);n.userData={memory:true,phase:i*.47,baseY:y};g.add(n)}
// Factory specialization creates unique physical infrastructure.
if(trait==='reliability'){for(const x of[-12,12])for(let z=-8;z>-55;z-=10){const shield=new THREE.Mesh(new THREE.TorusGeometry(2.2,.14,10,48),mc);shield.rotation.y=Math.PI/2;shield.position.set(x,4,z);g.add(shield)}}
if(trait==='discovery'){for(let i=0;i<7;i++){const dish=new THREE.Mesh(new THREE.RingGeometry(1,1.6,24),mm);dish.position.set(-12+i*4,10+(i%2)*2,-18-i*4);dish.rotation.x=-.7;g.add(dish)}}
if(trait==='velocity'){for(const x of[-8,-4,4,8]){const rail=new THREE.Mesh(new THREE.BoxGeometry(.12,.08,78),mg);rail.position.set(x,.18,-20);g.add(rail)}}
if(trait==='efficiency'){for(let i=0;i<10;i++){const cell=new THREE.Mesh(new THREE.BoxGeometry(1.4,.12,1.4),mc);cell.position.set(-12+(i%5)*6,.12,-12-Math.floor(i/5)*28);cell.rotation.y=Math.PI/4;g.add(cell)}}
g.scale.setScalar(p.scale);return{group:g,profile:p,update(t){g.children.forEach((o,i)=>{if(o.userData.memory){o.position.y=o.userData.baseY+Math.sin(t*1.5+o.userData.phase)*.35;o.rotation.y=t+i}})}}}
