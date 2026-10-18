/* Local integration boundary. The imported canvas never contacts its original server. */
(() => {
 'use strict';
 const project=new URLSearchParams(location.search).get('project');
 const prefix='/api/yaoguang/'+encodeURIComponent(project);
 const nativeFetch=window.fetch.bind(window);
 const bridge=window.StudioCanvasBridge={project,pendingSave:null,saveError:null};
 function rewrite(value){return typeof value==='string'&&value.startsWith('/api/')&&!value.startsWith('/api/yaoguang/')?prefix+value.slice(4):value;}
 bridge.rewrite=rewrite;
 window.fetch=function(input,options={}){
  const original=typeof input==='string'?input:input.url;
  const url=typeof input==='string'?rewrite(input):new Request(rewrite(input.url.replace(location.origin,'')),input);
  let body=options.body;
  if(typeof body==='string'&&/\/canvas-(llm|video|video-tasks|image-tasks)$/.test(original)){
   try{const data={...bridge.context?.(),...JSON.parse(body)};body=JSON.stringify(data);}catch{}
  }
  const request=nativeFetch(url,{...options,body});
  if(options.method==='PUT'&&/\/canvases\/[^/]+$/.test(original)){
   bridge.saving=true;bridge.saveConflict=false;
   bridge.pendingSave=request.then(async response=>{bridge.saveConflict=response.status===409;if(!response.ok&&response.status!==409){const data=await response.clone().json().catch(()=>({}));throw Error(typeof data.detail==='string'?data.detail:'画布保存失败');}bridge.saveError=null;return response;}).catch(error=>{bridge.saveError=error;return null;}).finally(()=>{bridge.saving=false;});
  }
  return request;
 };
 // Apply trusted presentation attributes through DOM CSS APIs, without relaxing CSP.
 function markup(value){return String(value).replace(/\sstyle\s*=\s*(["'])(.*?)\1/gs,' data-yg-runtime-style="$2"').replace(/\son\w+\s*=\s*(["']).*?\1/gs,'');}
 const html=Object.getOwnPropertyDescriptor(Element.prototype,'innerHTML');
 Object.defineProperty(Element.prototype,'innerHTML',{...html,set(value){html.set.call(this,markup(value));apply(this);}});
 const insert=Element.prototype.insertAdjacentHTML;
 Element.prototype.insertAdjacentHTML=function(position,value){insert.call(this,position,markup(value));apply(this.parentElement||this);};
 function apply(root){
  for(const el of root.querySelectorAll('[data-yg-runtime-style],[data-yg-static-style]')){
   const text=el.getAttribute('data-yg-runtime-style')??el.getAttribute('data-yg-static-style');el.style.cssText=text;
   el.removeAttribute('data-yg-runtime-style');el.removeAttribute('data-yg-static-style');
  }
  for(const el of root.querySelectorAll('[src^="/api/media-preview"]'))el.setAttribute('src',rewrite(el.getAttribute('src')));
 }
 document.addEventListener('DOMContentLoaded',()=>apply(document));
 const observer=new MutationObserver(records=>{for(const record of records)for(const node of record.addedNodes)if(node.nodeType===1)apply(node.parentElement||node);});
 observer.observe(document.documentElement,{childList:true,subtree:true});
})();
