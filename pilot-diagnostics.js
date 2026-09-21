(function(){
  'use strict';
  const cfg=window.JAKEAI_PILOT_DIAGNOSTICS||{};
  const submitUrl=cfg.submitUrl||'/api/v1/insurance/diagnostics';
  const listUrl=cfg.listUrl||'/api/v1/insurance/diagnostics';
  let lastError={action:'Manual problem report',errorText:''};
  let flag=false;
  let shot='';
  let shotName='';
  let lastResult=null;
  let reports=[];
  const $=id=>document.getElementById(id);
  const esc=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const message=e=>e&&e.message?String(e.message):String(e||'Unknown error');
  const ignoreUrl=url=>String(url||'').includes('/insurance/diagnostics')||String(url||'').includes('/insurance/me');
  function remember(action,error){
    lastError={action:action||'Application error',errorText:message(error)};
    flag=true;
    renderFlag();
  }
  window.JakeAIDiagnostics={remember:remember,open:open};
  const nativeFetch=window.fetch.bind(window);
  window.fetch=async function(input,init){
    const url=typeof input==='string'?input:(input&&input.url)||'';
    try{
      const res=await nativeFetch(input,init);
      if(!res.ok&&!ignoreUrl(url)){
        let detail='';
        try{
          const clone=res.clone();
          const data=await clone.json();
          detail=typeof data.detail==='string'?data.detail:(data.detail?JSON.stringify(data.detail):(data.error||data.message||''));
        }catch(_){}
        remember((init&&init.method?init.method:'GET')+' '+url,new Error((detail||'Request failed')+' (HTTP '+res.status+')'));
      }
      return res;
    }catch(e){
      if(!ignoreUrl(url))remember((init&&init.method?init.method:'GET')+' '+url,e);
      throw e;
    }
  };
  window.addEventListener('error',e=>remember('Browser error',e.error||e.message));
  window.addEventListener('unhandledrejection',e=>remember('Unhandled request failure',e.reason));

  const css='.jaiDiagFab{position:fixed;right:18px;bottom:18px;z-index:9998;display:flex;align-items:center;gap:8px;border:1px solid #68dffc55;background:#071b27f2;color:#eaffff;border-radius:999px;padding:11px 14px;font-weight:900;cursor:pointer;box-shadow:0 15px 45px #0008}.jaiDiagFab.hot{border-color:#ffd36f99}.jaiDiagDot{display:none;width:8px;height:8px;border-radius:50%;background:#ffd36f;box-shadow:0 0 10px #ffd36f}.jaiDiagFab.hot .jaiDiagDot{display:block}.jaiDiagBack{position:fixed;inset:0;z-index:9999;background:#000c;backdrop-filter:blur(9px);overflow:auto;padding:24px 12px}.jaiDiagModal{max-width:900px;margin:auto;border:1px solid #2a536a;border-radius:22px;background:#06121bee;color:#effcff;padding:22px;box-shadow:0 25px 90px #000b}.jaiDiagHead{display:flex;justify-content:space-between;gap:18px}.jaiDiagHead h2{margin:5px 0}.jaiDiagHead p{margin:5px 0;color:#91aebb;line-height:1.45}.jaiDiagClose{width:38px;height:38px;border:1px solid #31586b;border-radius:50%;background:#0a2230;color:#fff}.jaiDiagGrid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:16px}.jaiDiagGrid label{display:grid;gap:5px;color:#91aebb;font-size:12px}.jaiDiagGrid input,.jaiDiagGrid textarea{width:100%;border:1px solid #285066;background:#040c12;color:#eefaff;border-radius:11px;padding:11px;font:inherit}.jaiDiagGrid textarea{min-height:92px;resize:vertical}.jaiDiagWide{grid-column:1/-1}.jaiDiagShot{margin-top:12px;border:1px dashed #5edfff55;border-radius:13px;padding:13px;display:flex;gap:12px;align-items:center;justify-content:space-between}.jaiDiagShot span{display:block;color:#819cab;font-size:11px;margin-top:4px}.jaiDiagShot input{max-width:260px}.jaiDiagPreview{margin-top:10px;display:flex;gap:12px;align-items:flex-start}.jaiDiagPreview img{max-width:240px;max-height:170px;border-radius:10px;border:1px solid #285066}.jaiDiagBtns{display:flex;gap:8px;justify-content:flex-end;margin-top:14px}.jaiDiagBtns button,.jaiDiagPreview button{border:1px solid #416b80;background:#0d2a39;color:#eaffff;border-radius:999px;padding:10px 13px;font-weight:800}.jaiDiagBtns .primary{background:#baf6ff;color:#061318}.jaiDiagResult{margin-top:13px;padding:13px;border-left:3px solid #6ee8ff;background:#092433;border-radius:0 10px 10px 0}.jaiDiagResult strong,.jaiDiagResult span{display:block}.jaiDiagResult strong{color:#78e8ff}.jaiDiagResult span{font-size:11px;color:#a7c4d0;margin-top:3px}.jaiDiagResult p{margin:7px 0 0;line-height:1.4}.jaiDiagStatus{color:#9bc1d0;font-size:12px}.jaiDiagHistory{border-top:1px solid #29495a;margin-top:16px;padding-top:14px}.jaiDiagItem{padding:10px;margin-top:8px;border:1px solid #244354;border-radius:11px;background:#071722}.jaiDiagItem div{display:flex;justify-content:space-between;gap:8px}.jaiDiagItem small{color:#7896a6}.jaiDiagItem p{margin:6px 0;font-size:12px}.jaiDiagItem a{font-size:11px;color:#7fe9ff}.jaiDiagFine{font-size:10px;color:#668697;margin-top:13px}@media(max-width:620px){.jaiDiagFab span{display:none}.jaiDiagFab{width:44px;height:44px;padding:0;justify-content:center}.jaiDiagGrid{grid-template-columns:1fr}.jaiDiagWide{grid-column:auto}.jaiDiagShot,.jaiDiagPreview,.jaiDiagBtns{flex-direction:column;align-items:stretch}.jaiDiagPreview img{max-width:100%}}';
  const style=document.createElement('style');style.textContent=css;document.head.appendChild(style);
  const btn=document.createElement('button');btn.id='jaiDiagFab';btn.className='jaiDiagFab';btn.innerHTML='<b>⚠</b><span>Report Problem</span><i class="jaiDiagDot"></i>';btn.onclick=open;document.body.appendChild(btn);
  function renderFlag(){btn.classList.toggle('hot',flag)}
  function area(){const m=document.getElementById('mode');return m&&m.value?m.value:(cfg.label||document.title)}
  function modalHtml(){
    return '<div class="jaiDiagBack" id="jaiDiagBack"><section class="jaiDiagModal"><div class="jaiDiagHead"><div><div class="eyebrow">JAKEAI PILOT DIAGNOSTICS</div><h2>Report a problem / diagnose</h2><p>Private support only. This does not email, post, call, text, buy ads, contact a lead, or publish anything.</p></div><button class="jaiDiagClose" id="jaiDiagClose">×</button></div><div class="jaiDiagGrid"><label>What were you doing?<input id="jaiDiagAction" value="'+esc(lastError.action)+'"></label><label>Area<input id="jaiDiagArea" value="'+esc(area())+'" readonly></label><label class="jaiDiagWide">Error text<textarea id="jaiDiagError" placeholder="Paste the error here. Recent app errors are filled automatically.">'+esc(lastError.errorText)+'</textarea></label><label class="jaiDiagWide">Anything else we should know?<textarea id="jaiDiagNotes" placeholder="What did you click or enter immediately before the problem?"></textarea></label></div><div class="jaiDiagShot" id="jaiDiagShot"><div><strong>Optional screenshot</strong><span>Paste a screenshot here, or choose PNG/JPG/WEBP under 1.5 MB. Review it first so no secret or private information is visible.</span></div><input id="jaiDiagFile" type="file" accept="image/png,image/jpeg,image/webp"></div><div id="jaiDiagPreview"></div><div id="jaiDiagResult"></div><div class="jaiDiagBtns"><button id="jaiDiagCopy">Copy Report</button><button class="primary" id="jaiDiagSend">Send to JakeAI Diagnostics</button></div><p class="jaiDiagStatus" id="jaiDiagStatus"></p><div class="jaiDiagHistory"><strong>Recent diagnostic reports</strong><div id="jaiDiagList"></div></div><div class="jaiDiagFine">Reference the JAI-J code when asking JakeAI for help. Reports stay inside this private pilot diagnostic ledger.</div></section></div>';
  }
  async function open(){
    flag=false;renderFlag();
    let host=document.getElementById('jaiDiagHost');
    if(!host){host=document.createElement('div');host.id='jaiDiagHost';document.body.appendChild(host)}
    host.innerHTML=modalHtml();
    $('jaiDiagClose').onclick=()=>{host.innerHTML=''};
    $('jaiDiagCopy').onclick=copy;
    $('jaiDiagSend').onclick=submit;
    $('jaiDiagFile').onchange=e=>addFile(e.target.files&&e.target.files[0]);
    $('jaiDiagShot').onpaste=e=>{
      const item=[...e.clipboardData.items].find(x=>x.type.startsWith('image/'));
      if(item){e.preventDefault();addFile(item.getAsFile())}
    };
    renderPreview();
    await loadReports();
  }
  function addFile(file){
    if(!file)return;
    if(!['image/png','image/jpeg','image/webp'].includes(file.type)){status('Use a PNG, JPG, or WEBP screenshot.');return}
    if(file.size>1500000){status('Screenshot is too large. Keep it under 1.5 MB.');return}
    const r=new FileReader();
    r.onload=()=>{shot=String(r.result||'');shotName=file.name||'pasted-screenshot';renderPreview()};
    r.onerror=()=>status('Could not read that screenshot.');
    r.readAsDataURL(file);
  }
  function renderPreview(){
    const p=$('jaiDiagPreview');if(!p)return;
    p.innerHTML=shot?'<div class="jaiDiagPreview"><img src="'+shot+'" alt="Screenshot preview"><div><strong>'+esc(shotName)+'</strong><button id="jaiDiagRemove">Remove screenshot</button></div></div>':'';
    if($('jaiDiagRemove'))$('jaiDiagRemove').onclick=()=>{shot='';shotName='';renderPreview()};
  }
  function status(t){if($('jaiDiagStatus'))$('jaiDiagStatus').textContent=t}
  async function submit(){
    const errorText=$('jaiDiagError').value.trim(),notes=$('jaiDiagNotes').value.trim();
    if(!errorText&&!notes){status('Add the error text or a note first.');return}
    const b=$('jaiDiagSend');b.disabled=true;b.textContent='Saving…';status('Saving private diagnostic…');
    try{
      const r=await nativeFetch(submitUrl,{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({area:$('jaiDiagArea').value,action:$('jaiDiagAction').value,error_text:errorText,notes:notes,page_url:location.href,user_agent:navigator.userAgent,client_time:new Date().toISOString(),screenshot_data:shot})});
      const d=await r.json().catch(()=>({}));
      if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'Diagnostic request failed');
      lastResult=d;shot='';shotName='';renderPreview();
      $('jaiDiagResult').innerHTML='<div class="jaiDiagResult"><strong>'+esc(d.report_code)+'</strong><span>'+esc(d.classification)+'</span><p>'+esc(d.next_action)+'</p></div>';
      status('Stored privately as '+d.report_code+'.');
      await loadReports();
    }catch(e){status('Diagnostic submission failed: '+message(e)+'. Use Copy Report so nothing is lost.')}
    finally{b.disabled=false;b.textContent='Send to JakeAI Diagnostics'}
  }
  async function copy(){
    const text=[lastResult?'Report: '+lastResult.report_code:'JakeAI pilot diagnostic draft','Area: '+($('jaiDiagArea')?$('jaiDiagArea').value:area()),'Action: '+($('jaiDiagAction')?$('jaiDiagAction').value:lastError.action),'Error: '+($('jaiDiagError')?$('jaiDiagError').value:lastError.errorText),'Notes: '+($('jaiDiagNotes')?$('jaiDiagNotes').value:'not entered'),'Page: '+location.href,'Browser: '+navigator.userAgent,lastResult?'Classification: '+lastResult.classification:'',lastResult?'Next action: '+lastResult.next_action:''].filter(Boolean).join('\n');
    try{await navigator.clipboard.writeText(text);status('Diagnostic report copied.')}catch(_){status('Browser copy was blocked. Select and copy the error text manually.')}
  }
  async function loadReports(){
    try{
      const r=await nativeFetch(listUrl,{credentials:'include'});if(!r.ok)return;
      const d=await r.json();reports=d.items||[];renderReports();
    }catch(_){}
  }
  function renderReports(){
    const h=$('jaiDiagList');if(!h)return;
    h.innerHTML=reports.length?reports.map(r=>'<div class="jaiDiagItem"><div><strong>'+esc(r.report_code)+'</strong><small>'+esc(new Date(r.created_at).toLocaleString())+'</small></div><p>'+esc(r.classification)+' · '+esc(r.action)+'</p><small>'+esc(r.next_action)+'</small>'+(r.has_screenshot?'<br><a target="_blank" rel="noreferrer" href="/api/v1/insurance/diagnostics/'+encodeURIComponent(r.report_code)+'/screenshot">Open screenshot</a>':'')+'</div>').join(''):'<p class="muted">No diagnostic reports yet.</p>';
  }
})();