'use strict';
// Keep all view coordinates in the same 900×540 tangent plane as the survey WCS.
let equipmentState = null, viewingTarget = null, viewerZoom = 'fov', viewRequest = 0;
let viewAbort = null, imageAbort = null, imageObjectURL = null;
let lastViewerScope = saved('astro-viewer-scope');
function rememberViewerScope(id){lastViewerScope=id;persist('astro-viewer-scope',id);}
const angular = minutes => minutes < 1 ? n(minutes*60,1)+'″' : n(minutes,minutes<10?1:0)+'′';
const sizeText = t => t?.major ? (Math.abs(t.major-t.minor)>.01 ? angular(t.major)+' × '+angular(t.minor) : angular(t.major)) : 'maat onbekend';
const percent = (t,s) => t.major ? t.major/60/Math.max(s.width,s.height)*100 : null;
const pct = value => value == null ? '—' : value < .1 ? '<'+n(.1,1)+'%' : n(value,value<10?1:0)+'%';
function getEquipment(){return state?.equipment || equipmentState;}

let targetData=null,targetLoading=false,targetRequestedRevision='',targetListError='';
let targetWhen=saved('astro-target-when') || 'night',targetKind=saved('astro-target-kind') || 'all',targetQuery='';
let targetSort=saved('astro-target-sort') || 'recommended';
const targetSorts=[['recommended','Aanbevolen'],['altitude','Hoogte nu ↓'],['best','Hoogte nacht ↓'],['large','Grootste eerst'],['small','Kleinste eerst'],['bright','Helderste eerst']];
if(!targetSorts.some(x=>x[0]===targetSort))targetSort='recommended';
if(!['night','now','day'].includes(targetWhen))targetWhen='night';
if(!['all','nebula','galaxy','cluster','planet'].includes(targetKind))targetKind='all';
function selectedScope(){const e=getEquipment();return e?.scopes.find(s=>s.id===(lastViewerScope || e.selected)) || e?.scopes.find(s=>s.id===e.selected) || e?.scopes[0];}
async function refreshTargetList(revision){
 const scope=selectedScope();if(!scope)return;
 const key=revision+'|'+scope.id+'|'+targetWhen;
 if(targetLoading || targetRequestedRevision===key)return;
 targetRequestedRevision=key;targetLoading=true;targetListError='';
 try{const r=await fetch('/api/targets?'+new URLSearchParams({scope:scope.id,window:targetWhen}),{signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error();targetData=await r.json();}
 catch{targetListError='Doelenlijst kon niet worden geladen.';setTimeout(()=>{targetRequestedRevision='';if(tab==='targets')render(true);},10000);}
 finally{targetLoading=false;if(tab==='targets')render(true);}
}
function inTargetWindow(t){
 if(t.category==='moon')return false;
 if(t.category==='planet')return t.sun_distance>=20 && (targetWhen==='now'?t.altitude>15 && state.astronomy.sun_altitude<-.833:targetWhen==='day'?t.day_max_altitude>15:t.best_altitude>15);
 return targetWhen==='now'?t.altitude>0:targetWhen==='day'?t.day_max_altitude>0:t.best_altitude>0;
}
function targetOrder(a,b){
 const val=t=>targetSort==='recommended'?t.recommendation?.score:targetSort==='altitude'?t.altitude:targetSort==='best'?t.best_altitude:targetSort==='bright'?t.magnitude:t.major;
 const av=val(a),bv=val(b);if(av==null&&bv!=null)return 1;if(bv==null&&av!=null)return -1;
 return (av!=null&&bv!=null?(targetSort==='small'||targetSort==='bright'?av-bv:bv-av):0) || b.altitude-a.altitude || a.name.localeCompare(b.name);
}
targetsView=function(){
 const a=state?.astronomy;if(!a)return empty('Waarneemdoelen worden berekend…');
 refreshTargetList(a.updated_at);refreshCaptureSummary();
 const chosen=selectedScope();
 const rows=targetData?.location_key===`${Number(state.config.latitude).toFixed(5)},${Number(state.config.longitude).toFixed(5)}` && targetData.scope_id===chosen?.id && targetData.window===targetWhen?targetData.targets:[];
 const query=targetQuery.toLocaleLowerCase('nl').replace(/\s/g,'');
 if((favoritesOnly||uncapturedOnly)&&(!captureSummary||captureSummaryError))return empty(captureSummaryError?'Opnametellers niet bereikbaar':'Loading capture history…');
 const all=rows.filter(t=>historyFilter(t,chosen?.id) && inTargetWindow(t) && (targetKind==='all'||t.category===targetKind) && (!query||`${t.id} ${t.name} ${t.aliases||''}`.toLocaleLowerCase('nl').replace(/\s/g,'').includes(query))).sort(targetOrder);
 const pages=Math.max(1,Math.ceil(all.length/3));targetPage=Math.min(targetPage,pages-1);
 const scopes=(getEquipment()?.scopes||[]).filter(s=>s.builtin||s.id===chosen?.id);
 const period={night:'Komende nacht',now:'Nu boven horizon',day:'Komende 24 uur'}[targetWhen];
 return `<section class="catalog-view"><div class="catalog-heading"><div><h1>Waarneemdoelen</h1><p class="fine">${n(all.length)} doelen · ${period}${targetKind==='nebula'?' · nevels':''}</p></div><button class="moon-shortcut" data-target="moon" aria-label="Bekijk Maan">☾ Maan <strong>${n(a.moon.altitude)}°</strong><small>${n(a.moon.illumination)}% verlicht</small></button><div class="pager"><button id="target-prev" aria-label="Vorige doelen" ${targetPage===0?'disabled':''}>‹</button><span>${targetPage+1}/${pages}</span><button id="target-next" aria-label="Volgende doelen" ${targetPage>=pages-1?'disabled':''}>›</button></div></div>`+
 `<div class="target-toolbar"><select id="target-scope" aria-label="Telescoop voor aanbevelingen">${getEquipment().scopes.map(s=>`<option data-no-i18n value="${esc(s.id)}" ${s.id===chosen?.id?'selected':''}>${esc(s.name)}</option>`).join('')}</select><select id="target-sort" aria-label="Doelen sorteren">${targetSorts.map(([id,label])=>`<option value="${id}" ${targetSort===id?'selected':''}>${label}</option>`).join('')}</select><button id="open-target-filters">Filters / zoeken${targetQuery?' ●':''}</button></div>`+
 (all.length?`<div class="targets-list">${all.slice(targetPage*3,targetPage*3+3).map(t=>`<article class="target-row panel capture-target-row" style="--scope-cols:${scopes.length}"><button class="target-main" data-target="${esc(t.id)}" aria-label="Bekijk ${esc(t.name)}"><strong>${esc(t.name)} ↗</strong><span class="fine">${sizeText(t)} · ${esc(t.kind)}${t.magnitude!=null?' · mag '+n(t.magnitude,1):''}</span><span class="fine recommendation-reason">${targetSort==='recommended'?esc(t.recommendation?.reasons.join(' · ')):'Beste nacht '+n(t.best_altitude)+'° · '+tm(t.best_time)}</span></button><div class="target-height"><strong>${n(t.altitude,1)}°</strong><span class="fine">nu · ${esc(t.direction)}</span></div>${scopes.map(s=>`<button class="scope-count" data-capture-target="${esc(t.id)}" data-capture-scope="${esc(s.id)}" aria-label="Opnames ${esc(t.name)} met ${esc(s.name)}"><strong>${pct(percent(t,s))}</strong><span data-no-i18n>${esc(s.name)}</span><small>${captureCount(t.id,s.id)} opnames</small></button>`).join('')}</article>`).join('')}</div>`:`<div class="catalog-empty">${targetLoading?'De catalogus wordt geladen…':targetListError||'Geen doelen voor deze filters.'}</div>`)+
 `<p class="fine catalog-foot"><span data-no-i18n>${nightDates(a)}</span> · ${targetSort==='recommended'?'Advies ≈ · geen garantie · ':'% = lange beeldrand · '}boven horizon ≠ goed fotografeerbaar · <span id="counts-status">${captureSummaryError?'Opnametellers niet bereikbaar':'OpenNGC'}</span></p></section>`;
};
content.addEventListener('click',event=>{
 const row=event.target.closest('[data-target]');if(row)openTarget(row.dataset.target);
 const photos=event.target.closest('[data-capture-target]');if(photos)openTarget(photos.dataset.captureTarget,photos.dataset.captureScope,true);
 if(event.target.closest('#open-target-filters')){for(const [id,value]of [['target-when',targetWhen],['target-kind',targetKind],['target-query',targetQuery]])$('#'+id).value=value;$('#target-filters-dialog').showModal();}
});
content.addEventListener('change',event=>{if(event.target.id==='target-scope'){rememberViewerScope(event.target.value);}else if(event.target.id==='target-sort'){targetSort=event.target.value;persist('astro-target-sort',targetSort);}else return;targetPage=0;render(true);});
$('#close-target-filters').onclick=()=>$('#target-filters-dialog').close();
$('#target-filter').onsubmit=event=>{event.preventDefault();targetWhen=$('#target-when').value;targetKind=$('#target-kind').value;targetQuery=$('#target-query').value;persist('astro-target-when',targetWhen);persist('astro-target-kind',targetKind);targetPage=0;$('#target-filters-dialog').close();render(true);};

function renderEquipment(){
 const e=getEquipment();if(!e)return;
 $('#scope-list').innerHTML=e.scopes.map(s=>`<div class="scope-row"><button class="scope-select ${s.id===e.selected?'chosen':''}" data-scope="${esc(s.id)}" aria-pressed="${s.id===e.selected}"><span><strong data-no-i18n>${esc(s.name)}</strong><small>${n(s.width,2)}° × ${n(s.height,2)}° ${s.id===e.selected?'· standaard':''}</small></span><span>${s.id===e.selected?'✓':'○'}</span></button>${!s.builtin?`<button class="scope-remove" data-remove="${esc(s.id)}" aria-label="Verwijder ${esc(s.name)}">✕</button>`:''}</div>`).join('');
 $('#add-scope').disabled=e.scopes.length>=14;
 if(!settingsReady)settingsLoading(true);
}
async function writeEquipment(e){
 if(!settingsReady)throw Error(I18N.t('Instellingen konden niet worden geladen.'));
 const previousDefault=getEquipment()?.selected;
 const r=await fetch('/api/equipment',{method:'POST',headers:{'Content-Type':'application/json','X-Astro-Token':token},body:JSON.stringify({selected:e.selected,custom:e.scopes.filter(s=>!s.builtin)}),signal:AbortSignal.timeout(10000)});
 const result=await r.json();if(!r.ok)throw Error(result.error||'Opslaan is niet gelukt.');
 if(result.equipment.selected!==previousDefault)rememberViewerScope(result.equipment.selected);
 equipmentState=result.equipment;if(state)state.equipment=equipmentState;renderEquipment();render(true);
 $('#settings-message').textContent='Telescoopinstellingen opgeslagen.';
}
function settingsSection(scopes){
 $('#display-settings').hidden=true;$('#settings-display').classList.remove('selected');$('#settings-display').setAttribute('aria-pressed','false');
 $('#system-settings').hidden=true;$('#settings-system').classList.remove('selected');$('#settings-system').setAttribute('aria-pressed','false');
 $('#place-settings').hidden=scopes;$('#scope-settings').hidden=!scopes;
 for(const [id,selected] of [['settings-place',!scopes],['settings-scopes',scopes]]){$('#'+id).classList.toggle('selected',selected);$('#'+id).setAttribute('aria-pressed',selected);}
 $('#settings-message').textContent='';
}
$('#settings-place').onclick=()=>settingsSection(false);
$('#settings-scopes').onclick=()=>{settingsSection(true);renderEquipment();};
const originalSettings=$('#settings').onclick;
$('#settings').onclick=async()=>{
 settingsSection(false);$('#scope-form').hidden=true;$('#add-scope').hidden=false;
 await originalSettings();
};
let savingEquipment=false;
$('#scope-list').onclick=async event=>{
 const choose=event.target.closest('[data-scope]'),remove=event.target.closest('[data-remove]');if(!settingsReady || savingEquipment || (!choose&&!remove))return;
 const e=structuredClone(getEquipment());
 if(choose)e.selected=choose.dataset.scope;
 if(remove){e.scopes=e.scopes.filter(s=>s.id!==remove.dataset.remove);if(e.selected===remove.dataset.remove)e.selected=e.scopes[0].id;}
 savingEquipment=true;$('#scope-list').classList.add('saving');
 try{await writeEquipment(e);}catch(error){$('#settings-message').textContent=error.message;}finally{savingEquipment=false;$('#scope-list').classList.remove('saving');}
};
$('#add-scope').onclick=()=>{$('#scope-form').reset();$('#scope-form').hidden=false;$('#add-scope').hidden=true;$('#scope-form').scrollIntoView({block:'nearest'});};
$('#cancel-scope').onclick=()=>{$('#scope-form').hidden=true;$('#add-scope').hidden=false;};
$('#scope-form').onsubmit=async event=>{
 event.preventDefault();if(savingEquipment)return;savingEquipment=true;
 const button=$('#scope-form button[type=submit]');button.disabled=true;
 const e=structuredClone(getEquipment());const id='custom-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,7);
 e.scopes.push({id,name:$('#scope-name').value.trim(),width:Number($('#scope-width').value),height:Number($('#scope-height').value),builtin:false});e.selected=id;
 try{await writeEquipment(e);$('#scope-form').hidden=true;$('#add-scope').hidden=false;}catch(error){$('#settings-message').textContent=error.message;}finally{button.disabled=false;savingEquipment=false;}
};

function openTarget(ident,scopeId=null,own=false){
 viewingTarget=ident;viewerZoom='fov';if(scopeId)rememberViewerScope(scopeId);
 const e=getEquipment();if(!e)return;
 $('#viewer-scope').innerHTML=e.scopes.map(s=>`<option data-no-i18n value="${esc(s.id)}">${esc(s.name)}</option>`).join('');
 $('#viewer-scope').value=e.scopes.some(s=>s.id===lastViewerScope)?lastViewerScope:e.selected;
 $('#target-title').textContent=targetData?.targets.find(t=>t.id===ident)?.name || ident.toUpperCase();$('#target-dialog').showModal();setTargetMode(own);if(!own)loadTarget();
}
$('#close-target').onclick=()=>$('#target-dialog').close();
$('#target-dialog').addEventListener('close',()=>{if($('#target-dialog').open)return;ownVersion++;if(tab==='targets')render(true);viewRequest++;viewAbort?.abort();imageAbort?.abort();if(imageObjectURL)URL.revokeObjectURL(imageObjectURL);imageObjectURL=null;viewingTarget=null;});
$('#viewer-scope').onchange=()=>{rememberViewerScope($('#viewer-scope').value);if(ownMode)loadOwnCaptures();else loadTarget();if(tab==='targets')render(true);};
$('#zoom-target').onclick=()=>{viewerZoom='target';loadTarget();};
$('#zoom-fov').onclick=()=>{viewerZoom='fov';loadTarget();};
$('#retry-target').onclick=()=>loadTarget();

const planetPhotos={
 venus:{width:800,height:390,cx:196,cy:195,diameter:334,crop:true,credit:'NASA/JPL-Caltech · Mariner 10 (1974)',url:'https://science.nasa.gov/photojournal/venus-from-mariner-10/'},
 mars:{width:800,height:800,cx:400,cy:391,diameter:550,credit:'NASA/ESA · Hubble Heritage, Bell & Wolff (2016)',url:'https://science.nasa.gov/image-detail/hs-2016-15-a-full_tif/'},
 jupiter:{width:800,height:800,cx:394,cy:412,diameter:590,credit:'NASA/ESA · Simon & Wong (2019)',url:'https://science.nasa.gov/asset/hubble/jupiter-2019/'},
 saturn:{width:800,height:571,cx:408,cy:281,diameter:179,credit:'NASA/ESA · Simon, Wong & OPAL (2019)',url:'https://science.nasa.gov/asset/hubble/saturn-2019/'}
};
function moonPhaseImage(degrees){
 const canvas=document.createElement('canvas');canvas.width=canvas.height=220;
 const ctx=canvas.getContext('2d'),pixels=ctx.createImageData(220,220),phase=degrees*Math.PI/180;
 for(let y=0;y<220;y++)for(let x=0;x<220;x++){
  const xx=(x-109.5)/109,yy=(y-109.5)/109,rr=xx*xx+yy*yy;if(rr>1)continue;
  const lit=xx*Math.sin(phase)-Math.sqrt(1-rr)*Math.cos(phase)>0,shade=lit?220:30,i=(y*220+x)*4;
  pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=shade;pixels.data[i+3]=255;
 }
 ctx.putImageData(pixels,0,0);return canvas.toDataURL();
}
function drawTarget(v,url){
 const g=v.geometry,t=v.target;let picture='';
 if(url && v.survey)picture=`<image href="${esc(url)}" width="900" height="540"/>`;
 if(url && t.id==='moon')picture=`<image href="${esc(url)}" x="${450-g.target_pixels/2}" y="${270-g.target_pixels/2}" width="${g.target_pixels}" height="${g.target_pixels}"/>`;
 if(url && !v.survey && t.id!=='moon'){
  const p=planetPhotos[t.id],scale=g.target_pixels/p.diameter;
  // NASA reference photos retain their original pixels; nested SVG clips the two-panel Venus plate.
  picture=`<svg x="${450-p.cx*scale}" y="${270-p.cy*scale}" width="${(p.crop?390:p.width)*scale}" height="${p.height*scale}" viewBox="0 0 ${p.crop?390:p.width} ${p.height}" overflow="hidden"><image href="${esc(url)}" width="${p.width}" height="${p.height}"/></svg>`;
 }
 const tiny=g.target_pixels!=null && g.target_pixels<4;
 const fallback=!url && g.target_pixels!=null?`<circle cx="450" cy="270" r="${Math.max(.3,g.target_pixels/2)}" fill="none" stroke="currentColor" stroke-dasharray="5 5"/>`:'';
 const marker=tiny?'<path d="M438 270h-8m40 0h-8m-12-12v-8m0 40v-8" stroke="currentColor" stroke-width="2"/><text x="465" y="295" class="sky-label">doel</text>':'';
 $('#target-sky').innerHTML=`<rect width="900" height="540" fill="#020402"/>${picture}${fallback}<polygon points="${g.roi.map(p=>p.join(',')).join(' ')}" fill="none" stroke="currentColor" stroke-width="3"/>${marker}${v.survey?'<text x="18" y="30" class="sky-label">N ↑ · O ←</text>':''}<text x="18" y="521" class="sky-label">${g.roi_outside?'Kader valt (deels) buiten beeld':'Kader = één opname'}</text>`;
}
async function loadTarget(){
 const version=++viewRequest;viewAbort?.abort();imageAbort?.abort();viewAbort=new AbortController();
 if(imageObjectURL)URL.revokeObjectURL(imageObjectURL);imageObjectURL=null;
 $('#target-title').textContent=targetData?.targets.find(t=>t.id===viewingTarget)?.name || 'Doel bekijken';
 $('#target-subtitle').textContent='Beeldveld berekenen…';$('#target-sky').replaceChildren();$('#image-status').textContent='Beeld laden…';$('#retry-target').hidden=true;
 $('#viewer-fov').textContent='';$('#viewer-ratio').textContent='';$('#viewer-recommendation').textContent='';
 $('#target-credit').textContent='';$('#target-scale').textContent='';
 for(const mode of ['target','fov']){$('#zoom-'+mode).classList.toggle('selected',viewerZoom===mode);$('#zoom-'+mode).setAttribute('aria-pressed',viewerZoom===mode);}
 try{
  const args=new URLSearchParams({scope:$('#viewer-scope').value,zoom:viewerZoom,window:targetWhen});
  const r=await fetch('/api/targets/'+encodeURIComponent(viewingTarget)+'/view?'+args,{signal:AbortSignal.any([viewAbort.signal,AbortSignal.timeout(10000)])});
  if(!r.ok)throw Error('Doelgegevens konden niet worden geladen.');const v=await r.json();if(version!==viewRequest)return;
  const t=v.target,s=v.scope;
  $('#target-title').textContent=t.name;
  $('#viewer-recommendation').textContent=t.category==='nebula'||t.category==='galaxy'||t.category==='cluster'?'Advies ('+v.recommendation.basis+'): '+v.recommendation.reasons.join(' · ')+'. Schatting.':'';
  $('#target-subtitle').textContent=sizeText(t)+' · '+t.size_note;
  $('#viewer-fov').textContent=n(s.width,2)+'° × '+n(s.height,2)+'°';
  $('#viewer-ratio').textContent=(t.major?pct(percent(t,s))+' van de lange beeldrand. ':'Afmeting onbekend. ')+(t.id==='moon'?n(t.illumination)+'% verlicht. ':'Beste hoogte '+n(t.best_altitude)+'° om '+tm(t.best_time)+'. ')+(t.altitude<=0?'Nu onder de horizon. ':'Nu '+n(t.altitude)+'° '+t.direction+'. ');
  $('#target-scale').textContent=(v.geometry.size_unknown && viewerZoom==='target'?'Context · ':'')+'beeldbreedte '+n(v.geometry.field_width,v.geometry.field_width<.1?3:2)+'°';
  const p=planetPhotos[t.id];
  if(t.id==='moon'){
   $('#target-credit').textContent='Schematische actuele maanfase · noord boven · Skyfield/JPL';
   drawTarget(v,moonPhaseImage(t.phase_angle));$('#image-status').textContent='';return;
  }
  $('#target-credit').innerHTML=v.survey?`<a href="https://aladin.cds.unistra.fr/hips/" target="_blank" rel="noreferrer">${esc(v.survey_name)} / CDS hips2fits</a> · archiefbeeld`:`<a href="${p.url}" target="_blank" rel="noreferrer">${p.credit}</a><br>Referentiefoto op schaal ≈ · fase en ringstand niet actueel`;
  drawTarget(v,null);
  imageAbort=new AbortController();
  try{
   const im=await fetch(v.image,{signal:AbortSignal.any([imageAbort.signal,AbortSignal.timeout(30000)])});if(!im.ok)throw Error();
   const blob=await im.blob();if(version!==viewRequest)return;
   imageObjectURL=URL.createObjectURL(blob);const preview=new Image();preview.src=imageObjectURL;await preview.decode();if(version!==viewRequest)return;
   drawTarget(v,imageObjectURL);$('#image-status').textContent='';
  }catch(error){if(version!==viewRequest)return;$('#image-status').textContent='Beeld niet beschikbaar · kader op schaal';$('#retry-target').hidden=false;}
 }catch(error){if(version!==viewRequest)return;$('#image-status').textContent=error.message||'Laden is niet gelukt.';$('#retry-target').hidden=false;}
}
