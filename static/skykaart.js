'use strict';
const posterSurvey=document.getElementById('skykaart-survey');
if(posterSurvey){
 let retried=false;
 posterSurvey.addEventListener('error',()=>{
  if(!retried){retried=true;setTimeout(()=>posterSurvey.setAttribute('href',posterSurvey.getAttribute('href')+'?retry=1'),3000);}
  else posterSurvey.previousElementSibling.textContent='Surveybeeld niet beschikbaar';
 });
}
