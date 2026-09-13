'use strict';
let captureSummary=null,captureSummaryAt=0,captureSummaryLoading=false,captureSummaryError=false;
let capturePage=0,captureScope='',captureQuery='',captureTrash=false,captureList=null,captureListKey='',captureLoading=false,captureError='';
let ownMode=false,ownVersion=0,ownPage=0,ownRows=null;
let uploadTarget=null,uploading=false,objectSearchVersion=0;
let photoContext=null,photoIndex=0,photoZoom=false;
const captureCount=(object,scope)=>captureSummary?.counts?.[object]?.[scope] ?? (captureSummaryError?'?':captureSummary?0:'…');
const capDate=c=>c.observed_on?new Date(c.observed_on+'T12:00:00').toLocaleDateString(I18N.language)+' · opname':day(c.uploaded_at)+' · upload';
const capScopes=()=>{const all=new Map((captureSummary?.scopes||[]).map(s=>[s.id,s]));for(const s of getEquipment()?.scopes||[])all.set(s.id,s);return [...all.values()];};

async function refreshCaptureSummary(force=false){
 if(captureSummaryLoading||(!force&&Date.now()-captureSummaryAt<30000))return;
 captureSummaryLoading=true;captureSummaryAt=Date.now();
 try{const r=await fetch('/api/captures/summary',{signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error();captureSummary=await r.json();captureSummaryError=false;}
 catch{captureSummaryError=true;}
 finally{captureSummaryLoading=false;if(tab==='targets'||tab==='captures')render(true);}
}
const galleryArgs=()=>({scope:captureScope,q:captureQuery,trash:captureTrash?'1':'0'});
function captureCards(data,where){return `<div class="capture-grid">${data.items.map((c,i)=>`<button class="capture-card" data-photo-index="${i}" data-photo-context="${where}" aria-label="Bekijk opname ${esc(c.object_name)} met ${esc(c.scope_name)}"><img src="/capture-file/${c.id}/thumb" alt="${esc(c.object_name)}" loading="lazy"><div><strong>${esc(c.object_name)}</strong><span>${esc(c.scope_name)} · ${capDate(c)}</span></div></button>`).join('')}</div>`;}
async function refreshCaptures(){
 const key=JSON.stringify([galleryArgs(),capturePage,captureSummaryAt]);if(captureLoading||key===captureListKey)return;
 captureLoading=true;captureListKey=key;captureError='';
 try{const args=new URLSearchParams({...galleryArgs(),page:capturePage});const r=await fetch('/api/captures?'+args,{signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error();const result=await r.json();
  if(JSON.stringify([galleryArgs(),capturePage,captureSummaryAt])===key){captureList=result;capturePage=result.page;captureListKey=JSON.stringify([galleryArgs(),capturePage,captureSummaryAt]);}
 }catch{captureError='Opnames konden niet worden geladen.';}
 finally{captureLoading=false;if(tab==='captures')render(true);}
}
capturesView=function(){
 refreshCaptureSummary();refreshCaptures();
 const data=captureList,changed=captureListKey!==JSON.stringify([galleryArgs(),capturePage,captureSummaryAt]);
 return `<section class="captures-view"><div class="captures-heading"><div><h1>${captureTrash?'Prullenbak':'Captures'}</h1><p class="fine">${data?.total||0} opnames · nieuwste uploads eerst</p></div><button id="add-gallery-capture">＋ Upload</button><button id="toggle-trash">${captureTrash?'Terug':'Prullenbak'}</button><div class="pager"><button id="captures-prev" aria-label="Vorige opnames" ${!capturePage?'disabled':''}>‹</button><span>${capturePage+1}/${Math.max(1,Math.ceil((data?.total||0)/6))}</span><button id="captures-next" aria-label="Volgende opnames" ${!data||(capturePage+1)*6>=data.total?'disabled':''}>›</button></div></div>
 <form id="capture-filter" class="capture-filter"><select id="capture-scope-filter" aria-label="Opnames filteren op telescoop"><option value="">Alle telescopen</option>${capScopes().map(s=>`<option data-no-i18n value="${esc(s.id)}" ${captureScope===s.id?'selected':''}>${esc(s.name)}</option>`).join('')}</select><input id="capture-query" type="search" aria-label="Opnames zoeken" placeholder="Object / notitie" value="${esc(captureQuery)}"><button type="button" data-keyboard="capture-query">⌨</button><button type="submit">Zoek</button></form>
 ${captureError?`<div class="catalog-empty">${esc(captureError)} <button id="retry-captures">Opnieuw</button></div>`:changed||!data?'<div class="catalog-empty">Opnames laden…</div>':data.items.length?captureCards(data,'all'):`<div class="catalog-empty">${captureTrash?'De prullenbak is leeg.':'Nog geen opnames voor deze selectie. Upload JPG of PNG via deze pagina op je telefoon of computer, of bij een object.'}</div>`}
 <p class="fine catalog-foot">${captureSummary?'Originelen '+n(captureSummary.original_bytes/1024**2,1)+' MB · '+n(captureSummary.free_bytes/1024**3,1)+' GB vrij op Pi':'Opslag op Pi'} · ${captureTrash?'Bestanden blijven bewaard; herstellen via de foto.':'Eigen opnames · geen FOV-overlay'}</p></section>`;
};

function setTargetMode(own){
 if(!own&&!getEquipment().scopes.some(s=>s.id===$('#viewer-scope').value))$('#viewer-scope').value=selectedScope().id;
 ownMode=own;ownVersion++;
 $('#reference-detail').hidden=own;$('#reference-caption').hidden=own;$('#own-captures').hidden=!own;
 $('#show-reference').classList.toggle('selected',!own);$('#show-own').classList.toggle('selected',own);
 $('#show-reference').setAttribute('aria-pressed',!own);$('#show-own').setAttribute('aria-pressed',own);
 if(own){viewRequest++;viewAbort?.abort();imageAbort?.abort();$('#target-subtitle').textContent='Eigen opnames · gekozen telescoop';ownPage=0;loadOwnCaptures();}
}
async function loadOwnCaptures(){
 const version=++ownVersion,ident=viewingTarget,scope=$('#viewer-scope').value;
 $('#own-captures').innerHTML='<div class="catalog-empty">Eigen opnames laden…</div>';
 try{const r=await fetch('/api/captures?'+new URLSearchParams({object:ident,scope,page:ownPage}),{signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error();const data=await r.json();if(version!==ownVersion)return;
  ownRows=data;ownPage=data.page;
  const scopes=capScopes();
  $('#own-captures').innerHTML=`<div class="own-toolbar"><select id="own-scope" aria-label="Telescoop voor eigen opnames">${scopes.map(s=>`<option data-no-i18n value="${esc(s.id)}" ${s.id===scope?'selected':''}>${esc(s.name)}</option>`).join('')}</select><span class="fine">${data.total} opnames</span><button id="own-prev" aria-label="Vorige eigen opnames" ${!ownPage?'disabled':''}>‹</button><button id="own-next" aria-label="Volgende eigen opnames" ${(ownPage+1)*6>=data.total?'disabled':''}>›</button></div>`+(data.items.length?captureCards(data,'own'):'<div class="catalog-empty">Nog geen opnames met deze telescoop. Voeg een JPG of PNG toe.</div>');
 }catch{if(version===ownVersion)$('#own-captures').innerHTML='<div class="catalog-empty">Laden mislukt. <button id="retry-own">Opnieuw</button></div>';}
}
$('#show-reference').onclick=()=>{setTargetMode(false);loadTarget();};
$('#show-own').onclick=()=>setTargetMode(true);
$('#add-target-capture').onclick=()=>openUpload(viewingTarget);
$('#own-captures').addEventListener('change',e=>{if(e.target.id!=='own-scope')return;const id=e.target.value;if(getEquipment().scopes.some(s=>s.id===id)){rememberViewerScope(id);$('#viewer-scope').value=id;}else{const o=document.createElement('option');o.value=id;o.textContent=e.target.selectedOptions[0].text;$('#viewer-scope').append(o);$('#viewer-scope').value=id;}ownPage=0;loadOwnCaptures();});
$('#own-captures').addEventListener('click',e=>{if(e.target.closest('#own-prev')){ownPage--;loadOwnCaptures();}if(e.target.closest('#own-next')){ownPage++;loadOwnCaptures();}if(e.target.closest('#retry-own'))loadOwnCaptures();});

function openUpload(ident=null){
 uploadTarget=ident;$('#upload-form').reset();$('#upload-message').textContent='';$('#upload-object-results').replaceChildren();$('#upload-object-picker').hidden=!!ident;
 $('#upload-object-name').textContent=ident?(targetData?.targets.find(t=>t.id===ident)?.name || $('#target-title').textContent):'Kies een object';
 $('#upload-scope').innerHTML=(getEquipment()?.scopes||[]).map(s=>`<option data-no-i18n value="${esc(s.id)}">${esc(s.name)}</option>`).join('');
 $('#upload-scope').value=selectedScope()?.id||'';
 if(ident&&getEquipment()?.scopes.some(s=>s.id===$('#viewer-scope').value))$('#upload-scope').value=$('#viewer-scope').value;
 $('#upload-dialog').showModal();
}
$('#close-upload').onclick=()=>{if(!uploading)$('#upload-dialog').close();};
$('#upload-dialog').addEventListener('cancel',e=>{if(uploading)e.preventDefault();});
let lookupTimer;
$('#upload-object-query').oninput=()=>{clearTimeout(lookupTimer);const version=++objectSearchVersion;uploadTarget=null;$('#upload-object-name').textContent='Kies een object';lookupTimer=setTimeout(async()=>{
 try{const r=await fetch('/api/objects?'+new URLSearchParams({q:$('#upload-object-query').value}),{signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error();const data=await r.json();if(version!==objectSearchVersion)return;$('#upload-object-results').innerHTML=data.items.length?data.items.map(t=>`<button type="button" data-upload-object="${esc(t.id)}">${esc(t.name)}</button>`).join(''):'<p class="fine">Geen object gevonden.</p>';}
 catch{if(version===objectSearchVersion)$('#upload-object-results').textContent='Zoeken mislukt. Probeer opnieuw.';}
 },250);};
$('#upload-object-results').onclick=e=>{const b=e.target.closest('[data-upload-object]');if(b){uploadTarget=b.dataset.uploadObject;$('#upload-object-name').textContent=b.textContent;$('#upload-object-results').replaceChildren();objectSearchVersion++;}};
async function freshToken(){const r=await fetch('/api/settings',{signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error('Geen verbinding met de Pi.');token=(await r.json()).token;}
async function capturesChanged(){captureListKey='';await refreshCaptureSummary(true);if(ownMode&&viewingTarget)loadOwnCaptures();if(tab==='captures')render(true);}
$('#upload-form').onsubmit=async e=>{
 e.preventDefault();if(uploading)return;
 const files=[...$('#upload-files').files],ident=uploadTarget,scope=$('#upload-scope').value,date=$('#upload-date').value,note=$('#upload-note').value;
 if(!ident||!files.length){$('#upload-message').textContent='Kies een object en één of meer foto’s.';return;}
 uploading=true;$('#upload-submit').disabled=$('#close-upload').disabled=true;const messages=[];let success=0;
 try{
  await freshToken();
  for(let i=0;i<files.length;i++){
   const file=files[i];$('#upload-message').textContent=`Upload ${i+1}/${files.length}: ${file.name}`;
   if(!/\.(jpe?g|png)$/i.test(file.name)||file.size>25*1024**2){messages.push(file.name+': alleen JPG/PNG tot 25 MB.');continue;}
   const form=new FormData();form.append('file',file);form.append('object',ident);form.append('scope',scope);form.append('observed_on',date);form.append('note',note);
   try{const r=await fetch('/api/captures',{method:'POST',headers:{'X-Astro-Token':token},body:form,signal:AbortSignal.timeout(180000)});const data=await r.json();if(!r.ok)throw Error(data.error||'Upload mislukt.');success++;}
   catch(error){messages.push(file.name+': '+I18N.t(error.message));}
  }
  if(success){rememberViewerScope(scope);if(viewingTarget)$('#viewer-scope').value=scope;await capturesChanged();}
  $('#upload-message').textContent=`${success} van ${files.length} opnames opgeslagen.`+(messages.length?'\n'+messages.join('\n'):' Je kunt dit venster sluiten.');
  if(success===files.length)$('#upload-files').value='';
 }catch(error){$('#upload-message').textContent=error.message;}
 finally{uploading=false;$('#upload-submit').disabled=$('#close-upload').disabled=false;}
};

function showPhoto(context,index){photoContext=context;photoIndex=index;photoZoom=false;renderPhoto();if(!$('#capture-dialog').open)$('#capture-dialog').showModal();}
function renderPhoto(){
 const c=photoContext.data.items[photoIndex];$('#capture-title').textContent=c.object_name;$('#capture-subtitle').textContent=c.scope_name+' · '+capDate(c)+' · '+c.width+'×'+c.height;
 $('#capture-photo').src='/capture-file/'+c.id+'/preview';$('#capture-photo').alt='Eigen opname van '+c.object_name+' met '+c.scope_name;
 $('#capture-photo-wrap').classList.toggle('zoomed',photoZoom);$('#capture-zoom').textContent=photoZoom?'Passend':'Vergroten';
 $('#capture-note').textContent=c.note;$('#capture-view-message').textContent='';$('#capture-original').href='/capture-file/'+c.id+'/original';$('#capture-original').setAttribute('download',c.filename);
 $('#capture-previous').disabled=photoContext.data.page===0&&photoIndex===0;
 $('#capture-next').disabled=photoContext.data.page*6+photoIndex+1>=photoContext.data.total;
 $('#capture-trash').textContent=c.trashed?'Herstellen':'Prullenbak';
}
$('#capture-photo').onerror=()=>{$('#capture-view-message').textContent='Afbeelding kon niet worden geladen. Het origineel blijft via de downloadknop bereikbaar.';};
async function stepPhoto(step){
 const next=photoIndex+step,data=photoContext.data;if(next>=0&&next<data.items.length){photoIndex=next;photoZoom=false;renderPhoto();return;}
 try{const r=await fetch('/api/captures?'+new URLSearchParams({...photoContext.args,page:data.page+step}),{signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error();photoContext.data=await r.json();photoIndex=step>0?0:photoContext.data.items.length-1;photoZoom=false;if(photoIndex>=0)renderPhoto();}
 catch{$('#capture-view-message').textContent='Volgende opname kon niet worden geladen.';}
}
$('#capture-previous').onclick=()=>stepPhoto(-1);$('#capture-next').onclick=()=>stepPhoto(1);
$('#capture-zoom').onclick=()=>{photoZoom=!photoZoom;$('#capture-photo-wrap').classList.toggle('zoomed',photoZoom);$('#capture-zoom').textContent=photoZoom?'Passend':'Vergroten';};
$('#close-capture').onclick=()=>$('#capture-dialog').close();
$('#capture-object').onclick=()=>{const c=photoContext.data.items[photoIndex];$('#capture-dialog').close();if($('#target-dialog').open)$('#target-dialog').close();const scope=getEquipment().scopes.some(s=>s.id===c.scope_id)?c.scope_id:null;openTarget(c.object_id,scope);};
$('#capture-trash').onclick=async()=>{
 const c=photoContext.data.items[photoIndex];$('#capture-trash').disabled=true;
 try{await freshToken();const r=await fetch('/api/captures/'+c.id+'/trash',{method:'POST',headers:{'Content-Type':'application/json','X-Astro-Token':token},body:JSON.stringify({trashed:!c.trashed}),signal:AbortSignal.timeout(10000)});const result=await r.json();if(!r.ok)throw Error(result.error);$('#capture-dialog').close();await capturesChanged();}
 catch(error){$('#capture-view-message').textContent=error.message||'Wijziging mislukt.';}finally{$('#capture-trash').disabled=false;}
};
content.addEventListener('input',e=>{if(e.target.id==='capture-query')captureQuery=e.target.value;});
content.addEventListener('change',e=>{if(e.target.id==='capture-scope-filter'){captureScope=e.target.value;capturePage=0;captureList=null;render(true);}});
content.addEventListener('submit',e=>{if(e.target.id==='capture-filter'){e.preventDefault();capturePage=0;captureList=null;captureListKey='';render(true);}});
content.addEventListener('click',e=>{
 if(e.target.closest('#add-gallery-capture'))openUpload();
 if(e.target.closest('#toggle-trash')){captureTrash=!captureTrash;capturePage=0;captureList=null;render(true);}
 if(e.target.closest('#captures-prev')){capturePage--;captureList=null;render(true);}
 if(e.target.closest('#captures-next')){capturePage++;captureList=null;render(true);}
 if(e.target.closest('#retry-captures')){captureListKey='';render(true);}
});
document.addEventListener('click',e=>{const card=e.target.closest('[data-photo-index]');if(card){const own=card.dataset.photoContext==='own';showPhoto({data:structuredClone(own?ownRows:captureList),args:own?{object:viewingTarget,scope:$('#viewer-scope').value}:galleryArgs()},Number(card.dataset.photoIndex));}});

// The Pi has no physical keyboard; phone and desktop users can still type normally.
let keyboardTarget='';
$('#keyboard-keys').innerHTML=[...'1234567890QWERTYUIOPASDFGHJKLZXCVBNM'].map(k=>`<button type="button" data-key="${k}">${k}</button>`).join('')+'<button type="button" data-key="-">-</button><button type="button" data-key=" ">Spatie</button><button type="button" data-key="back">⌫</button><button type="button" data-key="clear">Wis</button>';
document.addEventListener('click',e=>{const b=e.target.closest('[data-keyboard]');if(b){keyboardTarget=b.dataset.keyboard;$('#keyboard-value').value=$('#'+keyboardTarget).value;$('#keyboard-dialog').showModal();}});
$('#keyboard-keys').onclick=e=>{const b=e.target.closest('[data-key]');if(!b)return;const input=$('#keyboard-value'),key=b.dataset.key;input.value=key==='clear'?'':key==='back'?input.value.slice(0,-1):input.value+key;};
$('#keyboard-done').onclick=()=>{const input=$('#'+keyboardTarget);if(input){input.value=$('#keyboard-value').value;input.dispatchEvent(new Event('input',{bubbles:true}));}$('#keyboard-dialog').close();};
