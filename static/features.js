'use strict';
const tr=(value)=>I18N.t(value);
let favoritesOnly=saved('astro-favorites-only')==='1',uncapturedOnly=saved('astro-uncaptured-only')==='1';
const isFavorite=(object,scope)=>captureSummary?.favorites?.[scope]?.includes(object)||false;
function historyFilter(target,scope){return (!favoritesOnly||isFavorite(target.id,scope))&&(!uncapturedOnly||captureSummary&&!captureSummaryError&&captureCount(target.id,scope)===0);}
function favoriteButton(){const id=viewingTarget,scope=$('#viewer-scope').value,selected=isFavorite(id,scope);$('#target-favorite').textContent=selected?'★ Favorite':'☆ Favorite';$('#target-favorite').classList.toggle('selected',selected);$('#target-favorite').setAttribute('aria-pressed',String(selected));}
$('#target-favorite').onclick=async()=>{
 const button=$('#target-favorite');button.disabled=true;
 try{await freshToken();const r=await fetch('/api/favorites',{method:'POST',headers:{'Content-Type':'application/json','X-Astro-Token':token},body:JSON.stringify({object:viewingTarget,scope:$('#viewer-scope').value,enabled:!isFavorite(viewingTarget,$('#viewer-scope').value)}),signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error('Could not save.');await refreshCaptureSummary(true);favoriteButton();}
 catch(error){$('#viewer-recommendation').textContent=error.message;}finally{button.disabled=false;}
};
const priorOpenTarget=openTarget;
openTarget=function(...args){priorOpenTarget(...args);refreshCaptureSummary().then(favoriteButton);favoriteButton();};
$('#viewer-scope').addEventListener('change',favoriteButton);
const previousFilterSubmit=$('#target-filter').onsubmit;
$('#target-filter').onsubmit=event=>{favoritesOnly=$('#target-favorites').checked;uncapturedOnly=$('#target-uncaptured').checked;persist('astro-favorites-only',favoritesOnly?'1':'0');persist('astro-uncaptured-only',uncapturedOnly?'1':'0');previousFilterSubmit(event);};
content.addEventListener('click',event=>{if(event.target.closest('#open-target-filters')){$('#target-favorites').checked=favoritesOnly;$('#target-uncaptured').checked=uncapturedOnly;}});

$('#language').value=I18N.language;
$('#language').onchange=async event=>{const language=event.target.value;try{await saveSettings({language});I18N.set(language);$('#settings-message').textContent='Language saved.';}catch(error){event.target.value=I18N.language;$('#settings-message').textContent=error.message;}};
window.addEventListener('astro-language',()=>{updateClock();render(true);if($('#scope-settings').hidden===false)renderEquipment();if(photoContext&&$('#capture-dialog').open)renderPhoto();if(planData)renderPlan();if(compareData)renderComparison(compareData);});

let backupTimer=null;
async function readBackup(){
 try{const r=await fetch('/api/backup',{signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error('Could not load backup status.');showBackup(await r.json());}
 catch(error){$('#backup-status').textContent=error.message;$('#create-backup').disabled=!settingsReady;}
}
function showBackup(data){
 clearTimeout(backupTimer);$('#create-backup').disabled=!settingsReady||data.status==='running';$('#download-backup').hidden=data.status!=='ready';
 $('#backup-status').textContent=data.status==='running'?'Creating a consistent backup…':data.status==='ready'?'Backup ready · '+day(data.created_at)+' '+tm(data.created_at):data.error||'';
 if(data.status==='ready')$('#download-backup').href=data.url;
 if(data.status==='running')backupTimer=setTimeout(readBackup,2000);
}
$('#settings-system').onclick=()=>{settingsSection(false);$('#place-settings').hidden=true;$('#system-settings').hidden=false;$('#settings-place').classList.remove('selected');$('#settings-place').setAttribute('aria-pressed','false');$('#settings-system').classList.add('selected');$('#settings-system').setAttribute('aria-pressed','true');readBackup();};
$('#create-backup').onclick=async()=>{
 $('#create-backup').disabled=true;
 try{await freshToken();const r=await fetch('/api/backup',{method:'POST',headers:{'Content-Type':'application/json','X-Astro-Token':token},body:'{}',signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error('Backup could not be started.');showBackup(await r.json());}
 catch(error){$('#backup-status').textContent=error.message;$('#create-backup').disabled=!settingsReady;}
};

let planData=null,planVersion=0;
$('#target-plan').onclick=async()=>{
 const ident=viewingTarget,version=++planVersion;planData=null;$('#plan-object').textContent=$('#target-title').textContent;$('#plan-body').textContent='Loading altitude chart…';$('#plan-dialog').showModal();
 try{const r=await fetch('/api/targets/'+encodeURIComponent(ident)+'/plan',{signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error('Could not load altitude chart.');const data=await r.json();if(version!==planVersion)return;planData=data;renderPlan();}
 catch(error){if(version===planVersion)$('#plan-body').textContent=error.message;}
};
$('#close-plan').onclick=()=>$('#plan-dialog').close();$('#plan-dialog').addEventListener('close',()=>{planVersion++;});
function renderPlan(){
 if(!planData)return;const rows=planData.samples,night=rows.filter(r=>r.night),start=night[0]?.time||rows[0].time,end=night.at(-1)?.time||rows.at(-1).time;
 const selected=rows.filter(r=>r.time>=start&&r.time<=end),span=Math.max(3600,end-start),x=t=>48+(t-start)/span*690,y=a=>157-(Math.max(-90,Math.min(90,a))+90)/180*140;
 const path=key=>selected.map((r,i)=>(i?'L':'M')+x(r.time).toFixed(1)+' '+y(r[key]).toFixed(1)).join(' ');
 const lines=[-90,-60,-30,0,30,60,90].map(a=>`<path d="M48 ${y(a)}H738" stroke="${a===30?'var(--accent)':'var(--line)'}" stroke-dasharray="${a===30?'5 4':'1 0'}"/><text x="39" y="${y(a)+4}" text-anchor="end" fill="var(--muted)">${a}°</text>`).join('');
 const ticks=Array.from({length:5},(_,i)=>start+span*i/4).map(t=>`<text x="${x(t)}" y="180" text-anchor="middle" fill="var(--muted)">${esc(tm(t))}</text>`).join('');
 const darkness=selected.slice(0,-1).filter(r=>r.sun<-12).map(r=>`<rect x="${x(r.time)}" y="16" width="${690*600/span+.5}" height="141" fill="var(--bg)"/>`).join('');
 const clouds=selected.filter(r=>r.cloud!=null).map(r=>`<rect x="${x(r.time)}" y="2" width="${Math.max(2,690*600/span)}" height="${r.cloud/100*10}" fill="var(--cloud)"/>`).join('');
 const best=planData.best,window=best?`<rect x="${x(best.start)}" y="16" width="${x(best.end)-x(best.start)}" height="141" fill="var(--accent)" opacity=".09"/>`:'';
 const advice=best?`<div class="plan-window"><strong>${tm(best.start)} – ${tm(best.end)}</strong><p>${n(best.minutes)} min · ${tr('Best imaging window')}<br>${best.weather_available?tr('Cloud forecast')+' '+n(best.cloud)+'%':tr('Geometric estimate; weather unavailable.')}</p></div><p class="fine">${tr(best.weather_available&&best.cloud>60?'Cloud forecast suggests poor conditions.':'Estimated window; check local clouds and obstructions.')}</p>`:`<p class="fine">${tr('No continuous window of at least 30 minutes above 30° with the Sun below −12°.')}</p>`;
 $('#plan-body').innerHTML=`<p class="fine">${nightDates(planData)}</p><svg id="altitude-chart" viewBox="0 0 780 192" role="img" aria-label="Altitude through the night" preserveAspectRatio="none"><g font-size="12" font-family="sans-serif">${darkness}${window}${clouds}${lines}${ticks}<path d="${path('altitude')}" fill="none" stroke="var(--accent)" stroke-width="2.5"/><path d="${path('moon')}" fill="none" stroke="var(--warn)" stroke-width="1.5"/></g></svg><div class="chart-legend"><span class="chart-target">— Target altitude</span><span class="chart-moon">— Moon altitude</span></div>${advice}<p class="fine">Dark shading: Sun below −12°. Dashed line: 30° altitude. Top bars: cloud cover.</p>`;
}

let compareId=null,compareData=null,compareTimer=null,blinkTimer=null,compareVersion=0;
function stopBlink(){clearInterval(blinkTimer);blinkTimer=null;$('#comparison-blink').textContent='Blink';applySwipe();}
function applySwipe(){const value=Number($('#comparison-swipe').value);$('#comparison-reference').style.clipPath=`inset(0 0 0 ${100-value}%)`;}
function fitComparison(){const stage=$('#comparison-stage'),image=$('#comparison-images');if(!compareData?.width||stage.hidden)return;const width=Math.min(stage.clientWidth,stage.clientHeight*compareData.width/compareData.height);image.style.setProperty('--compare-width',width+'px');image.style.setProperty('--compare-ratio',compareData.width+'/'+compareData.height);}
window.addEventListener('resize',fitComparison);
$('#capture-compare').onclick=()=>{compareId=photoContext.data.items[photoIndex].id;compareData=null;$('#comparison-caption').textContent=$('#capture-title').textContent;$('#comparison-stage').hidden=$('#comparison-controls').hidden=true;$('#comparison-details').textContent='';$('#comparison-status').textContent='Loading…';$('#start-comparison').hidden=true;$('#comparison-dialog').showModal();pollComparison();};
async function pollComparison(){
 const id=compareId,version=++compareVersion;clearTimeout(compareTimer);
 try{const r=await fetch('/api/captures/'+id+'/comparison',{signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error('Comparison status unavailable.');const data=await r.json();if(id!==compareId||version!==compareVersion||!$('#comparison-dialog').open)return;compareData=data;renderComparison(data);if(['queued','solving','reference'].includes(data.status))compareTimer=setTimeout(pollComparison,2000);}
 catch(error){if(version===compareVersion){$('#comparison-status').textContent=error.message;$('#start-comparison').hidden=false;$('#start-comparison').disabled=false;}}
}
function renderComparison(data){
 const ready=data.status==='ready',busy=['queued','solving','reference'].includes(data.status);
 $('#comparison-status').textContent=data.error||({queued:'Queued',solving:'Matching stars locally…',reference:'Loading and aligning reference…',ready:'Comparison ready'})[data.status]||(!data.supported?'Comparison needs a deep-sky photograph with recognizable stars.':!data.available?'Install the local ASTAP solver and D50 star database first.':'');
 $('#comparison-stage').hidden=$('#comparison-controls').hidden=!ready;$('#start-comparison').hidden=ready||busy;$('#start-comparison').disabled=!data.available||!data.supported;
 $('#comparison-info').textContent=ready?'Reference colors and resolution differ from your telescope. Alignment is based on the solved star field.':'Local star matching keeps your photograph on this Pi. Only sky coordinates are sent to the reference image service.';
 if(ready){$('#comparison-own').src=data.own;$('#comparison-reference').src=data.reference;const c=data.calibration;$('#comparison-details').textContent=data.survey+' / CDS · '+n(c.width_degrees,2)+'° × '+n(c.height_degrees,2)+'° · '+n(c.rotation,1)+'° · '+n(c.pixel_scale,2)+'″/px';fitComparison();applySwipe();}
}
$('#start-comparison').onclick=async()=>{
 $('#start-comparison').disabled=true;
 try{await freshToken();const r=await fetch('/api/captures/'+compareId+'/comparison',{method:'POST',headers:{'Content-Type':'application/json','X-Astro-Token':token},body:'{}',signal:AbortSignal.timeout(10000)});const data=await r.json();if(!r.ok)throw Error(data.error);pollComparison();}
 catch(error){$('#comparison-status').textContent=error.message;$('#start-comparison').disabled=false;}
};
$('#comparison-swipe').oninput=()=>{stopBlink();applySwipe();};
$('#comparison-blink').onclick=()=>{if(blinkTimer){stopBlink();return;}let reference=true;$('#comparison-blink').textContent='Stop blinking';blinkTimer=setInterval(()=>{reference=!reference;$('#comparison-reference').style.clipPath=reference?'inset(0)':'inset(0 0 0 100%)';},700);};
$('#comparison-own').onload=$('#comparison-reference').onload=fitComparison;
$('#comparison-own').onerror=$('#comparison-reference').onerror=()=>{$('#comparison-status').textContent='Image could not be loaded.';};
$('#close-comparison').onclick=()=>$('#comparison-dialog').close();$('#comparison-dialog').addEventListener('close',()=>{compareVersion++;clearTimeout(compareTimer);stopBlink();});
