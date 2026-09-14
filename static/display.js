'use strict';
I18N.ready.then(()=>{updateClock();if(state)render(true);});
let displayProfile=null, savingDisplay=false;
function loadDisplaySettings(d){
 displayProfile=d.profile;
 for(const [id,key] of [['brightness','active'],['idle-brightness','idle'],['idle-timeout','timeout']])$('#'+id).value=d.profile[key];
 $('#auto-dim').checked=d.profile.auto_dim;
 $('#brightness-value').textContent=d.profile.active+'%';$('#idle-brightness-value').textContent=d.profile.idle+'%';
 $('#idle-brightness').max=d.profile.active;
 document.querySelectorAll('#display-settings input').forEach(e=>e.disabled=!d.available);
 $('#brightness-info').textContent=d.available?'De eerste aanraking laat het scherm alleen oplichten.':'Helderheidsregeling is alleen beschikbaar op het Pi-scherm.';
}
$('#settings-display').onclick=()=>{settingsSection(false);$('#place-settings').hidden=true;$('#display-settings').hidden=false;$('#settings-place').classList.remove('selected');$('#settings-place').setAttribute('aria-pressed','false');$('#settings-display').classList.add('selected');$('#settings-display').setAttribute('aria-pressed','true');};
for(const id of ['brightness','idle-brightness'])$('#'+id).oninput=()=>{
 const active=Number($('#brightness').value);$('#idle-brightness').max=active;
 $('#brightness-value').textContent=active+'%';$('#idle-brightness-value').textContent=$('#idle-brightness').value+'%';
};
async function saveDisplay(){
 if(!settingsReady||savingDisplay)return;
 if(!$('#idle-timeout').reportValidity())return;
 const profile={active:Number($('#brightness').value),idle:Number($('#idle-brightness').value),timeout:Number($('#idle-timeout').value),auto_dim:$('#auto-dim').checked};
 savingDisplay=true;document.querySelectorAll('#display-settings input').forEach(e=>e.disabled=true);
 try{await saveSettings({display:profile});displayProfile=profile;$('#settings-message').textContent='Scherminstellingen opgeslagen.';}
 catch(error){$('#settings-message').textContent=error.message;}
 finally{savingDisplay=false;loadDisplaySettings({profile:displayProfile,available:true});}
}
for(const id of ['brightness','idle-brightness','idle-timeout','auto-dim'])$('#'+id).onchange=saveDisplay;

// Only a browser running on the Pi loopback address can drive the backlight.
// Capture listeners precede target handlers, including native modal dialogs.
if(document.documentElement.classList.contains('kiosk')){
 let enabled=false,dimmed=false,deadline=Infinity,activityToken='',pending=false,blocked=false,blockUntil=0,gesture=0,lastSent=0;
 const pointers=new Set();
 function receive(d){enabled=!!d.available;dimmed=!!d.dimmed;deadline=d.profile.auto_dim?performance.now()+d.seconds_until_idle*1000:Infinity;}
 async function activity(){
  if(pending)return;pending=true;lastSent=performance.now();
  try{const r=await fetch('/api/display/activity',{method:'POST',headers:{'Content-Type':'application/json','X-Astro-Token':activityToken},body:'{}',signal:AbortSignal.timeout(2000)});if(!r.ok)throw Error();receive(await r.json());}
  catch{enabled=false;}finally{pending=false;}
 }
 async function check(){
  try{const r=await fetch('/api/display',{signal:AbortSignal.timeout(2000)});if(!r.ok)throw Error();const s=await r.json();if(!s.local_display)return;activityToken=s.token;if(!pending)receive(s.display);}
  catch{enabled=false;}
  setTimeout(check,500);
 }
 const stop=e=>{e.preventDefault();e.stopImmediatePropagation();};
 window.addEventListener('pointerdown',e=>{
  const asleep=enabled&&(dimmed||performance.now()>=deadline);
  if(blocked&&!pointers.size&&!pending&&!asleep){blocked=false;blockUntil=0;}
  if(asleep||blocked){blocked=true;gesture++;pointers.add(e.pointerId);stop(e);if(enabled)activity();return;}
  if(enabled)activity();
 },true);
 for(const name of ['pointerup','pointercancel'])window.addEventListener(name,e=>{
  if(!blocked)return;stop(e);pointers.delete(e.pointerId);blockUntil=performance.now()+700;
  const version=gesture;setTimeout(()=>{if(!pointers.size&&version===gesture)blocked=false;},700);
 },true);
 for(const name of ['click','dblclick','contextmenu','mousedown','mouseup','touchstart','touchmove','touchend'])window.addEventListener(name,e=>{
  if(blocked||performance.now()<blockUntil)stop(e);
 },{capture:true,passive:false});
 window.addEventListener('pointermove',e=>{if(blocked){stop(e);return;}if(enabled&&e.buttons&&performance.now()-lastSent>1000)activity();},true);
 window.addEventListener('keydown',e=>{if(enabled&&(dimmed||performance.now()>=deadline)){stop(e);activity();}else if(enabled&&performance.now()-lastSent>500)activity();},true);
 check();
}
