'use strict';
// One catalog for static HTML, dynamic status text and accessible names.
// Source strings are retained per node so switching language is reversible.
const I18N = (()=>{
 let language;
 try{language=localStorage.getItem('astro-language');}catch{}
 language=['en-US','nl-NL'].includes(language)?language:(document.documentElement.lang==='nl-NL'?'nl-NL':'en-US');
 let pairs=[],exact=new Map(),patterns=[];
 const originals=new WeakMap();
 let observer;
 const escape=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 function prepare(entries){
  pairs=entries;exact=new Map();patterns=[];
  for(const [en,nl] of pairs){
   for(const source of new Set([en,nl])){
    exact.set(source,[en,nl]);
    if(/\{\d+\}/.test(source)){
     const keys=[];let cursor=0,regex='^';
     for(const match of source.matchAll(/\{(\d+)\}/g)){regex+=escape(source.slice(cursor,match.index))+'(.+?)';keys.push(match[1]);cursor=match.index+match[0].length;}
     patterns.push({regex:new RegExp(regex+escape(source.slice(cursor))+'$'),keys,en,nl});
    }
   }
  }
 }
 function translate(value,depth=0){
  const text=String(value??''),trim=text.trim(),pair=exact.get(trim);
  let result;
  if(pair)result=pair[language==='nl-NL'?1:0];
  else for(const p of patterns){const m=trim.match(p.regex);if(m){const args={};p.keys.forEach((key,i)=>args[key]=m[i+1]);result=(language==='nl-NL'?p.nl:p.en).replace(/\{(\d+)\}/g,(_,key)=>translate(args[key],depth+1));break;}}
  if(result===undefined&&depth<6){
   if(/[.!?:]$/.test(trim))result=translate(trim.slice(0,-1),depth+1)+trim.slice(-1);
   const chunks=trim.split(/(\s*[·↗]\s*|\n|\. (?=[A-Z]))/);
   if(chunks.length>1)result=chunks.map((s,i)=>i%2?s:translate(s,depth+1)).join('');
  }
  return result===undefined?text:text.slice(0,text.indexOf(trim))+result+text.slice(text.indexOf(trim)+trim.length);
 }
 function textNode(node){
  if(node.parentElement?.closest('[data-no-i18n],script,style,textarea,code'))return;
  const current=node.nodeValue,record=originals.get(node);
  const source=record&&current===record.rendered?record.source:current;
  const rendered=translate(source);originals.set(node,{source,rendered});
  if(rendered!==current)node.nodeValue=rendered;
 }
 function localize(root=document.body){
  if(!root)return;
  observer?.disconnect();
  if(root.nodeType===Node.TEXT_NODE)textNode(root);
  else{
   const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;
   while(node=walker.nextNode())textNode(node);
   const elements=root instanceof Element?[root,...root.querySelectorAll('[aria-label],[placeholder],[title],[alt]')]:[];
   for(const element of elements){
    if(element.closest('[data-no-i18n]'))continue;
    let record=originals.get(element)||{};
    for(const key of ['aria-label','placeholder','title','alt']){
     if(!element.hasAttribute(key))continue;
     const current=element.getAttribute(key),old=record[key],source=old&&current===old.rendered?old.source:current;
     const rendered=translate(source);record[key]={source,rendered};if(rendered!==current)element.setAttribute(key,rendered);
    }
    originals.set(element,record);
   }
  }
  observer?.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['aria-label','placeholder','title','alt']});
 }
 function set(value){
  if(!['en-US','nl-NL'].includes(value))throw Error('Unsupported language');
  language=value;document.documentElement.lang=value;
  try{localStorage.setItem('astro-language',value);}catch{}
  localize();window.dispatchEvent(new Event('astro-language'));
 }
 const ready=fetch('/static/locales.json').then(r=>{if(!r.ok)throw Error();return r.json();}).then(entries=>{
  prepare(entries);document.documentElement.lang=language;
  observer=new MutationObserver(records=>{
   const roots=new Set();for(const record of records){if(record.type==='childList')record.addedNodes.forEach(n=>roots.add(n));else roots.add(record.target);}
   for(const root of roots)if(root.isConnected)localize(root);
  });localize();
 }).catch(()=>{document.documentElement.lang=language;});
 return {get language(){return language;},t:translate,set,localize,ready};
})();
