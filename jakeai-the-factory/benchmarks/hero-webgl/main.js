import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

const canvas = document.querySelector('#scene');
const perf = document.querySelector('#perf');
const beat = document.querySelector('#beat');
const enter = document.querySelector('#enter');
const originCard = document.querySelector('#originCard');
const incidentCard = document.querySelector('#incidentCard');
const retry = document.querySelector('#retry');
const repair = document.querySelector('#repair');
const incidentStatus = document.querySelector('#incidentStatus');
const repairChip = document.querySelector('#repairChip');
const app = document.querySelector('#app');

const renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:false, powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.7));
renderer.setSize(innerWidth, innerHeight, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.12;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x020711);
scene.fog = new THREE.FogExp2(0x03101b, 0.026);

const camera = new THREE.PerspectiveCamera(54, innerWidth/innerHeight, 0.1, 220);
camera.position.set(0, 8.5, 26);

scene.add(new THREE.HemisphereLight(0x7adfff, 0x120018, 1.25));
const key = new THREE.DirectionalLight(0xbfeeff, 3.3); key.position.set(12,22,8); scene.add(key);
const magenta = new THREE.PointLight(0xff2fd1, 42, 42, 2); magenta.position.set(-11,5,-5); scene.add(magenta);
const cyan = new THREE.PointLight(0x00d9ff, 48, 48, 2); cyan.position.set(12,7,-10); scene.add(cyan);
const gold = new THREE.PointLight(0xff9c35, 28, 30, 2); gold.position.set(0,3,7); scene.add(gold);
const alarm = new THREE.PointLight(0xff143d, 0, 30, 2); alarm.position.set(0,5,-33); scene.add(alarm);

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene,camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth,innerHeight), 1.0, 0.65, 0.16);
composer.addPass(bloom);

const matDark = new THREE.MeshStandardMaterial({color:0x08131f,metalness:.82,roughness:.26});
const matFloor = new THREE.MeshStandardMaterial({color:0x07111c,metalness:.72,roughness:.34});
const matCyan = new THREE.MeshStandardMaterial({color:0x062a38,emissive:0x00cfff,emissiveIntensity:3.0,metalness:.58,roughness:.22});
const matMag = new THREE.MeshStandardMaterial({color:0x2a0525,emissive:0xff1fd0,emissiveIntensity:2.6,metalness:.5,roughness:.26});
const matGold = new THREE.MeshStandardMaterial({color:0x38240e,emissive:0xffa13f,emissiveIntensity:2.1,metalness:.45,roughness:.25});
const matRed = new THREE.MeshStandardMaterial({color:0x35040c,emissive:0xff123e,emissiveIntensity:4.2,metalness:.45,roughness:.2});
const matGlass = new THREE.MeshPhysicalMaterial({color:0x0b3040,transparent:true,opacity:.16,transmission:.55,roughness:.08,metalness:.08,side:THREE.DoubleSide});

const hall = new THREE.Group(); scene.add(hall);
const floor = new THREE.Mesh(new THREE.PlaneGeometry(54,86),matFloor); floor.rotation.x=-Math.PI/2; floor.position.z=-15; hall.add(floor);
for(let i=-6;i<=6;i++){
  const rail = new THREE.Mesh(new THREE.BoxGeometry(.05,.03,80), i%2===0?matCyan:matMag);
  rail.position.set(i*2.1,.025,-14); hall.add(rail);
}
for(let z=-48; z<16; z+=8){
  const cross = new THREE.Mesh(new THREE.BoxGeometry(28,.025,.045), z%16===0?matCyan:matMag);
  cross.position.set(0,.03,z); hall.add(cross);
}

function addTower(x,z,h=12,accent=matCyan){
  const g=new THREE.Group();
  const body=new THREE.Mesh(new THREE.CylinderGeometry(2.5,3.2,h,8),matDark); body.position.y=h/2; g.add(body);
  for(let y=2;y<h;y+=2.4){const ring=new THREE.Mesh(new THREE.TorusGeometry(3.05,.09,10,48),accent); ring.rotation.x=Math.PI/2; ring.position.y=y; g.add(ring)}
  const cap=new THREE.Mesh(new THREE.CylinderGeometry(1.4,2.8,.6,10),accent); cap.position.y=h+.25; g.add(cap);
  g.position.set(x,0,z); hall.add(g); return g;
}
const towers=[addTower(-9,-10,14,matCyan),addTower(9,-18,17,matMag),addTower(-10,-31,19,matGold),addTower(10,-41,15,matCyan)];

const core=new THREE.Group(); hall.add(core); core.position.set(0,4,-24);
const orbMat=new THREE.MeshPhysicalMaterial({color:0x0a1930,emissive:0x00d8ff,emissiveIntensity:2.8,metalness:.1,roughness:.05,transmission:.15,transparent:true,opacity:.92});
const orb=new THREE.Mesh(new THREE.IcosahedronGeometry(3.2,3),orbMat); core.add(orb);
for(let i=0;i<4;i++){const r=new THREE.Mesh(new THREE.TorusGeometry(5+i*.75,.08,12,96),i%2?matMag:matCyan);r.rotation.set(Math.random()*2,Math.random()*2,Math.random()*2);core.add(r)}

const repairBay = new THREE.Group(); hall.add(repairBay); repairBay.position.set(0,0,-36);
const repairBase = new THREE.Mesh(new THREE.CylinderGeometry(5.2,6.4,1.1,8),matDark); repairBase.position.y=.55; repairBay.add(repairBase);
for(let i=0;i<3;i++){const r=new THREE.Mesh(new THREE.TorusGeometry(4.5+i*.45,.11,12,72),i===1?matMag:matCyan);r.rotation.x=Math.PI/2;r.position.y=1.15+i*.35;repairBay.add(r)}
const repairCore = new THREE.Mesh(new THREE.OctahedronGeometry(2.1,1),matGold); repairCore.position.y=4.2; repairBay.add(repairCore);

const archGeo=new THREE.BoxGeometry(.45,8,.45);
for(let z=-4;z>-52;z-=8){
  for(const x of [-13,13]){const p=new THREE.Mesh(archGeo,matDark);p.position.set(x,4,z);hall.add(p)}
  const beam=new THREE.Mesh(new THREE.BoxGeometry(26.5,.45,.45),matDark);beam.position.set(0,8,z);hall.add(beam);
  const strip=new THREE.Mesh(new THREE.BoxGeometry(24,.08,.08),z%16===0?matCyan:matMag);strip.position.set(0,7.78,z+.26);hall.add(strip)
}

// ---- Spectacle layer: conveyors, drones, holograms, energy spine ----
const spectacle = new THREE.Group(); hall.add(spectacle);
const conveyorBelts=[];
for(const laneX of [-6.2,6.2]){
  const belt = new THREE.Group();
  const railL=new THREE.Mesh(new THREE.BoxGeometry(.16,.22,54),matDark);railL.position.set(laneX-.8,.55,-21);belt.add(railL);
  const railR=railL.clone();railR.position.x=laneX+.8;belt.add(railR);
  for(let i=0;i<14;i++){
    const pod=new THREE.Mesh(new THREE.BoxGeometry(1.1,.5,1.7),i%3===0?matGold:(i%2?matCyan:matMag));
    pod.position.set(laneX,.85,8-i*4.1);
    pod.userData.speed=.018+(i%4)*.004;
    belt.add(pod); conveyorBelts.push(pod);
  }
  spectacle.add(belt);
}

const drones=[];
for(let i=0;i<10;i++){
  const d=new THREE.Group();
  const body=new THREE.Mesh(new THREE.SphereGeometry(.32,12,10),i%2?matCyan:matMag);d.add(body);
  const wing=new THREE.Mesh(new THREE.TorusGeometry(.62,.045,6,28),matGold);wing.rotation.x=Math.PI/2;d.add(wing);
  d.position.set((i%2?-1:1)*(7+Math.random()*5),3+Math.random()*7,-4-Math.random()*44);
  d.userData.base=d.position.clone(); d.userData.phase=Math.random()*Math.PI*2;
  drones.push(d); spectacle.add(d);
}

const holoPanels=[];
for(let i=0;i<8;i++){
  const panel=new THREE.Mesh(new THREE.PlaneGeometry(3.6,1.8),new THREE.MeshBasicMaterial({color:i%2?0xff33cc:0x22ddff,transparent:true,opacity:.16,wireframe:true,side:THREE.DoubleSide}));
  panel.position.set(i%2?-11.7:11.7,4.2+(i%3)*1.15,-6-i*5.8);panel.rotation.y=i%2?Math.PI/2:-Math.PI/2;
  holoPanels.push(panel); spectacle.add(panel);
}

const energySpine=[];
for(let z=6;z>-52;z-=3.4){
  const node=new THREE.Mesh(new THREE.IcosahedronGeometry(.24,1),z%6.8===0?matGold:matCyan);
  node.position.set(0,6.7,z);energySpine.push(node);spectacle.add(node);
}
const energyBeam=new THREE.Mesh(new THREE.CylinderGeometry(.05,.05,58,8),new THREE.MeshBasicMaterial({color:0x29e7ff,transparent:true,opacity:.36}));
energyBeam.rotation.x=Math.PI/2;energyBeam.position.set(0,6.7,-23);spectacle.add(energyBeam);

const gateRing=new THREE.Group(); gateRing.position.set(0,4.2,-49); spectacle.add(gateRing);
for(let i=0;i<3;i++){
  const r=new THREE.Mesh(new THREE.TorusGeometry(5.4+i*.55,.1,12,80),i===1?matGold:(i%2?matMag:matCyan));
  r.rotation.set(i*.4,.2+i*.6,.1); gateRing.add(r);
}
const gateGlass=new THREE.Mesh(new THREE.CircleGeometry(4.75,64),matGlass); gateGlass.rotation.y=Math.PI; gateRing.add(gateGlass);

const particles=1100;
const pos=new Float32Array(particles*3);
for(let i=0;i<particles;i++){pos[i*3]=(Math.random()-.5)*36;pos[i*3+1]=Math.random()*18;pos[i*3+2]=-52+Math.random()*74}
const pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.BufferAttribute(pos,3));
const pm=new THREE.PointsMaterial({color:0x6fe9ff,size:.055,transparent:true,opacity:.62,depthWrite:false});scene.add(new THREE.Points(pg,pm));

const sparkCount=240;
const sparkPos=new Float32Array(sparkCount*3);
const sparkVel=[];
for(let i=0;i<sparkCount;i++){sparkPos[i*3]=0;sparkPos[i*3+1]=4;sparkPos[i*3+2]=-36;sparkVel.push(new THREE.Vector3())}
const sparkGeo=new THREE.BufferGeometry();sparkGeo.setAttribute('position',new THREE.BufferAttribute(sparkPos,3));
const sparkMat=new THREE.PointsMaterial({color:0xff3658,size:.13,transparent:true,opacity:0,depthWrite:false});
const sparks=new THREE.Points(sparkGeo,sparkMat);scene.add(sparks);

const holo=new THREE.Mesh(new THREE.CylinderGeometry(4.6,4.6,.09,64),new THREE.MeshBasicMaterial({color:0x00cfff,transparent:true,opacity:.23,wireframe:true}));holo.position.set(0,.18,4.4);scene.add(holo);
const marker=new THREE.Mesh(new THREE.TorusGeometry(3.4,.09,12,64),matGold);marker.position.set(0,.25,4.4);marker.rotation.x=Math.PI/2;scene.add(marker);

const clock=new THREE.Clock();
let entered=false, incident=false, repaired=false, targetZ=0, pointerX=0, pointerY=0, shake=0;
let revealPhase=0, revealStart=performance.now();
addEventListener('pointermove',e=>{pointerX=(e.clientX/innerWidth-.5);pointerY=(e.clientY/innerHeight-.5)});

function triggerIncident(){
  if(incident||repaired)return;
  incident=true; targetZ=-32; shake=1.0; alarm.intensity=70; sparkMat.opacity=1; app.classList.add('alert-flash');
  repairCore.material=matRed;
  for(let i=0;i<sparkCount;i++) sparkVel[i].set((Math.random()-.5)*.16,Math.random()*.17+.03,(Math.random()-.5)*.16);
  originCard.classList.add('hidden'); incidentCard.classList.remove('hidden'); repairChip.textContent='SELF-REPAIR: INCIDENT';
}

enter.addEventListener('click',()=>{
  if(!entered){
    entered=true;targetZ=-28;beat.textContent='Autonomous systems engaged. Follow the light.';enter.textContent='FACTORY ONLINE';
    setTimeout(triggerIncident,2500);
  }
});

retry.addEventListener('click',()=>{
  shake=1.35; alarm.intensity=95; incidentStatus.textContent='Retry changed nothing. Resources burned. Root cause still waving at us.';
  repairChip.textContent='WASTED RETRY // -EFFICIENCY';
});

repair.addEventListener('click',()=>{
  repaired=true;incident=false;shake=.35; alarm.intensity=0; sparkMat.opacity=0; app.classList.remove('alert-flash');
  repairCore.material=matCyan; incidentStatus.textContent='Responsible layer repaired. Regression check passed. Institutional learning saved.';
  repairChip.textContent='SELF-REPAIR: LEARNED +1';
  repair.textContent='ROOT CAUSE FIXED'; retry.disabled=true; repair.disabled=true;
  targetZ=-46;
  setTimeout(()=>incidentCard.classList.add('hidden'),1800);
});

let frames=0,lastFps=performance.now();
function animate(){requestAnimationFrame(animate);const dt=Math.min(clock.getDelta(),.05);const t=clock.elapsedTime;
  core.rotation.y=t*.32; orb.rotation.x=t*.21;orb.rotation.y=t*.36;
  repairCore.rotation.x=t*.7;repairCore.rotation.y=t*1.05;
  repairBay.children.forEach((c,i)=>{if(c.geometry?.type==='TorusGeometry')c.rotation.z=t*(i%2?.32:-.26)});
  towers.forEach((tw,i)=>{tw.rotation.y=Math.sin(t*.28+i)*.05});
  magenta.intensity=38+Math.sin(t*1.7)*7; cyan.intensity=44+Math.sin(t*1.3+1)*8;
  if(incident) alarm.intensity=58+Math.sin(t*8)*26;

  // Spectacle animation
  conveyorBelts.forEach((pod,i)=>{
    pod.position.z-=pod.userData.speed*60*dt;
    if(pod.position.z<-49) pod.position.z=10+(i%4)*1.2;
    pod.position.y=.85+Math.sin(t*2+i)*.08;
  });
  drones.forEach((d,i)=>{
    const b=d.userData.base,p=d.userData.phase;
    d.position.x=b.x+Math.sin(t*.55+p)*1.6;
    d.position.y=b.y+Math.sin(t*1.2+p)*.45;
    d.position.z=b.z+Math.cos(t*.37+p)*1.3;
    d.rotation.y=t*.8+p;
  });
  holoPanels.forEach((p,i)=>{p.material.opacity=.11+(Math.sin(t*2.4+i)*.5+.5)*.13;p.scale.y=.92+Math.sin(t*1.6+i)*.05});
  energySpine.forEach((n,i)=>{const s=1+Math.sin(t*4-i*.55)*.45;n.scale.setScalar(s)});
  energyBeam.material.opacity=.24+(Math.sin(t*3.4)*.5+.5)*.26;
  gateRing.rotation.z=t*.08; gateRing.children.forEach((c,i)=>{if(c.geometry?.type==='TorusGeometry')c.rotation.y+=dt*(i%2?-.36:.28)});

  const sp=sparkGeo.attributes.position.array;
  if(sparkMat.opacity>0){for(let i=0;i<sparkCount;i++){sp[i*3]+=sparkVel[i].x;sp[i*3+1]+=sparkVel[i].y;sp[i*3+2]+=sparkVel[i].z;sparkVel[i].y-=.0025;if(sp[i*3+1]<.4){sp[i*3]=0;sp[i*3+1]=4;sp[i*3+2]=-36}}sparkGeo.attributes.position.needsUpdate=true}

  // Autonomous opening reveal before user input
  if(!entered){
    const rt=(performance.now()-revealStart)/1000;
    if(rt<3.2){camera.position.z=26-rt*1.35;camera.position.y=9.2-rt*.35;camera.position.x=Math.sin(rt*.6)*.45;beat.textContent=rt<1.3?'Factory systems waking up…':rt<2.3?'Opportunity engines online…':'Self-repair standing by.';}
    else{camera.position.z=21.7+Math.sin(t*.18)*1.1;camera.position.y=8.1+Math.sin(t*.32)*.25;}
  } else {
    camera.position.z=THREE.MathUtils.lerp(camera.position.z,targetZ,.018);camera.position.y=7.2+Math.sin(t*.35)*.45;
  }

  const sx=(Math.random()-.5)*shake*.5, sy=(Math.random()-.5)*shake*.32; shake=Math.max(0,shake-dt*.9);
  camera.position.x=THREE.MathUtils.lerp(camera.position.x,pointerX*1.3,.025)+sx; camera.position.y+=sy;
  camera.rotation.x=THREE.MathUtils.lerp(camera.rotation.x,-.05+pointerY*.03,.03);camera.lookAt(0,4,incident?-36:(repaired?-49:(entered?-28:-20)));
  bloom.strength=incident?1.45:(repaired?1.22:1.05+Math.sin(t*.6)*.08);
  renderer.toneMappingExposure=1.08+(Math.sin(t*.4)*.5+.5)*.08;
  composer.render();
  frames++; const now=performance.now(); if(now-lastFps>700){perf.textContent=`FPS ${Math.round(frames*1000/(now-lastFps))}`;frames=0;lastFps=now;}
}
animate();

function resize(){renderer.setSize(innerWidth,innerHeight,false);renderer.setPixelRatio(Math.min(devicePixelRatio,innerWidth<700?1.35:1.7));camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();composer.setSize(innerWidth,innerHeight)}
addEventListener('resize',resize,{passive:true});
