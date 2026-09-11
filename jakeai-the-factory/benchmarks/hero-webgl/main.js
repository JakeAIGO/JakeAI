import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

const canvas = document.querySelector('#scene');
const perf = document.querySelector('#perf');
const beat = document.querySelector('#beat');
const enter = document.querySelector('#enter');

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

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene,camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth,innerHeight), 1.0, 0.65, 0.16);
composer.addPass(bloom);

const matDark = new THREE.MeshStandardMaterial({color:0x08131f,metalness:.82,roughness:.26});
const matFloor = new THREE.MeshStandardMaterial({color:0x07111c,metalness:.72,roughness:.34});
const matCyan = new THREE.MeshStandardMaterial({color:0x062a38,emissive:0x00cfff,emissiveIntensity:3.0,metalness:.58,roughness:.22});
const matMag = new THREE.MeshStandardMaterial({color:0x2a0525,emissive:0xff1fd0,emissiveIntensity:2.6,metalness:.5,roughness:.26});
const matGold = new THREE.MeshStandardMaterial({color:0x38240e,emissive:0xffa13f,emissiveIntensity:2.1,metalness:.45,roughness:.25});

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

const archGeo=new THREE.BoxGeometry(.45,8,.45);
for(let z=-4;z>-52;z-=8){
  for(const x of [-13,13]){const p=new THREE.Mesh(archGeo,matDark);p.position.set(x,4,z);hall.add(p)}
  const beam=new THREE.Mesh(new THREE.BoxGeometry(26.5,.45,.45),matDark);beam.position.set(0,8,z);hall.add(beam);
  const strip=new THREE.Mesh(new THREE.BoxGeometry(24,.08,.08),z%16===0?matCyan:matMag);strip.position.set(0,7.78,z+.26);hall.add(strip)
}

const particles=900;
const pos=new Float32Array(particles*3);
for(let i=0;i<particles;i++){pos[i*3]=(Math.random()-.5)*36;pos[i*3+1]=Math.random()*18;pos[i*3+2]=-52+Math.random()*74}
const pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.BufferAttribute(pos,3));
const pm=new THREE.PointsMaterial({color:0x6fe9ff,size:.055,transparent:true,opacity:.62,depthWrite:false});scene.add(new THREE.Points(pg,pm));

const holo=new THREE.Mesh(new THREE.CylinderGeometry(4.6,4.6,.09,64),new THREE.MeshBasicMaterial({color:0x00cfff,transparent:true,opacity:.23,wireframe:true}));holo.position.set(0,.18,4.4);scene.add(holo);
const marker=new THREE.Mesh(new THREE.TorusGeometry(3.4,.09,12,64),matGold);marker.position.set(0,.25,4.4);marker.rotation.x=Math.PI/2;scene.add(marker);

const clock=new THREE.Clock();
let entered=false, targetZ=0, pointerX=0, pointerY=0;
addEventListener('pointermove',e=>{pointerX=(e.clientX/innerWidth-.5);pointerY=(e.clientY/innerHeight-.5)});
enter.addEventListener('click',()=>{entered=true;targetZ=-28;beat.textContent='Autonomous systems engaged. Follow the light.';enter.textContent='FACTORY ONLINE'});

let frames=0,lastFps=performance.now();
function animate(){requestAnimationFrame(animate);const t=clock.getElapsedTime();
  core.rotation.y=t*.32; orb.rotation.x=t*.21;orb.rotation.y=t*.36;
  towers.forEach((tw,i)=>{tw.rotation.y=Math.sin(t*.28+i)*.05});
  magenta.intensity=38+Math.sin(t*1.7)*7; cyan.intensity=44+Math.sin(t*1.3+1)*8;
  if(entered){camera.position.z=THREE.MathUtils.lerp(camera.position.z,targetZ,.012);camera.position.y=7.2+Math.sin(t*.35)*.45;}
  else{camera.position.z=26+Math.sin(t*.18)*1.1;camera.position.y=8.5+Math.sin(t*.32)*.25;}
  camera.position.x=THREE.MathUtils.lerp(camera.position.x,pointerX*1.3,.025);camera.rotation.x=THREE.MathUtils.lerp(camera.rotation.x,-.05+pointerY*.03,.03);camera.lookAt(0,4,entered?-28:-20);
  composer.render();
  frames++; const now=performance.now(); if(now-lastFps>700){perf.textContent=`FPS ${Math.round(frames*1000/(now-lastFps))}`;frames=0;lastFps=now;}
}
animate();

function resize(){renderer.setSize(innerWidth,innerHeight,false);renderer.setPixelRatio(Math.min(devicePixelRatio,innerWidth<700?1.35:1.7));camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();composer.setSize(innerWidth,innerHeight)}
addEventListener('resize',resize,{passive:true});
