'use strict';
document.documentElement.classList.add('js');
const menu=document.querySelector('.menu-toggle'),nav=document.querySelector('.site-nav');
menu?.addEventListener('click',()=>{const open=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(open));nav.classList.toggle('open',open);});
document.querySelectorAll('.copy-code').forEach(button=>button.addEventListener('click',async()=>{
 try{await navigator.clipboard.writeText(button.closest('.code-block').querySelector('code').textContent);button.textContent='Copied';}
 catch{button.textContent='Select text to copy';}
 setTimeout(()=>{button.textContent='Copy';},2200);
}));
const reveal=document.querySelector('#compare-reveal'),comparison=document.querySelector('.compare');
reveal?.addEventListener('input',()=>comparison.style.setProperty('--reveal',reveal.value+'%'));
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{
 const category=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
 document.querySelectorAll('.screen-card').forEach(card=>{card.hidden=category!=='all'&&card.dataset.category!==category;});
 document.querySelector('#gallery-status').textContent=document.querySelectorAll('.screen-card:not([hidden])').length+' screenshots shown';
}));
const dialog=document.querySelector('#shot-dialog');
document.querySelectorAll('[data-shot]').forEach(button=>button.addEventListener('click',()=>{
 const card=button.closest('.screen-card'),picture=card.querySelector('img');
 dialog.querySelector('img').src=picture.src;dialog.querySelector('img').alt=picture.alt;
 dialog.querySelector('h2').textContent=card.querySelector('h2').textContent;
 dialog.querySelector('p').textContent=card.querySelector('.credit').textContent;
 dialog.querySelector('.original-shot').href=picture.src;dialog.showModal();
}));
dialog?.querySelector('.close-button').addEventListener('click',()=>dialog.close());
dialog?.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
