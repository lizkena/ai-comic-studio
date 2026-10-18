/* Only controls visibility and rendered size; no prompt, model, edge or generation changes. */
(()=>{
 const manualClosed=new Set();
 const mediaRatios=new Map();
 const labels={text:'文本卡',split:'拆分镜头',character:'角色卡',location:'场景卡',prop:'道具卡',shot:'镜头卡',txt2img:'文生图',image:'图片卡',video:'视频',audio:'音频',compose:'剪辑合成'};
 const managed=n=>!!n?.studioKind;
 const collapsed=n=>managed(n)&&(!isNodeSelected(n.id)||manualClosed.has(n.id));
 const originalLayout=imageLayout;
 const visual=n=>['video','image','character','location','prop','shot','txt2img'].includes(StudioNodeModel.kind(n));
 function displayRatio(n,media=(n.images||[])[0]){
  const saved=mediaRatios.get(media?.url);if(saved)return saved;
  if(Number(media?.width)>0&&Number(media?.height)>0)return media.width/media.height;
  const pair=String(n.studioRatio||'16:9').split(':').map(Number);
  return pair.length===2&&pair.every(x=>Number.isFinite(x)&&x>0)?pair[0]/pair[1]:16/9;
 }
 imageLayout=function(images,scale,n){const layout=originalLayout(images,scale,n);if(!collapsed(n))return layout;const media=(n.images||[]).filter(m=>['image','video'].includes(m.kind||'image'));const height=visual(n)?(media.length?media.reduce((sum,m)=>sum+(layout.width-22)/displayRatio(n,m),0)+Math.max(0,media.length-1)*6:(layout.width-22)/displayRatio(n))+87:260;return {...layout,height:Math.ceil(height)};};
 function rememberRatio(element,n){
  const w=element.tagName==='VIDEO'?element.videoWidth:element.naturalWidth,h=element.tagName==='VIDEO'?element.videoHeight:element.naturalHeight;
  const media=element.getAttribute?(n.images||[]).find(m=>m.url===element.getAttribute('src')):(n.images||[])[0];
  if(!w||!h||!media)return false;
  const ratio=w/h,changed=mediaRatios.get(media.url)!==ratio;mediaRatios.set(media.url,ratio);return changed;
 }
 function syncFold(){
  for(const n of nodes){
   if(!managed(n))continue;
   if(!isNodeSelected(n.id))manualClosed.delete(n.id);
   const el=world.querySelector(`.image-node[data-id="${CSS.escape(n.id)}"]`),card=el?.querySelector('.studio-node-card');
   if(!el||!card)continue;
   const title=el.querySelector('.node-title'),type=n.studioIdentityParentId?'身份卡':labels[StudioNodeModel.nodeRole(n)]||'卡片';
   const name=n.studioIdentityParentId?(n.title||n.studioIdentityName||'未命名身份'):(n.title&&n.title!==labels[StudioNodeModel.nodeRole(n)]?n.title:n.studioCharacter||'未命名');
   if(title){
    const signature=type+' · '+name;
    if(title.dataset.foldLabel!==signature||!title.querySelector('.studio-fold-type')){
     const badge=document.createElement('span');badge.className='studio-fold-type';badge.textContent=type;
     const caption=document.createElement('span');caption.className='studio-fold-name';caption.textContent=name;
     title.replaceChildren(badge,caption);title.dataset.foldLabel=signature;
    }
    title.title=signature;
   }
   const folded=collapsed(n),wasFolded=el.classList.contains('studio-folded');
   el.classList.toggle('studio-folded',folded);
   el.classList.toggle('studio-fold-video',StudioNodeModel.kind(n)==='video');
   if(visual(n)){
    card.querySelectorAll('.studio-preview img,.studio-preview video').forEach(media=>rememberRatio(media,n));
    el.style.setProperty('--studio-fold-ratio',String(displayRatio(n)));
   }
   // The existing identity observer must not save a temporary folded height into the card.
   if(folded)el.studioIdentityResizeObserver?.disconnect();
   else if(wasFolded)el.studioIdentityResizeObserver?.observe(card);
   el.style.height=imageLayout(n.images||[],nodeScale(n),n).height+'px';
   let toggle=el.querySelector('.studio-fold-toggle');
   if(!toggle){toggle=document.createElement('button');toggle.type='button';toggle.className='studio-fold-toggle';toggle.dataset.foldOwner=n.id;el.querySelector('.node-head').append(toggle);}
   toggle.textContent=folded?'展开':'收起';toggle.setAttribute('aria-expanded',String(!folded));toggle.setAttribute('aria-label',(folded?'展开':'收起')+(n.title||'卡片')+'编辑内容');
   card.querySelectorAll(':scope>.studio-fold-visible').forEach(x=>x.classList.remove('studio-fold-visible'));
   const previews=[...card.querySelectorAll(':scope>.studio-preview')];
   const preview=n.studioIdentityParentId?previews.at(-1):previews[0]||card.querySelector(':scope>.studio-output-video');
   if(preview)preview.classList.add('studio-fold-visible');
   card.querySelector(':scope>.studio-error')?.classList.add('studio-fold-visible');
   let summary=card.querySelector(':scope>.studio-fold-summary');
   if(!summary){summary=document.createElement('div');summary.className='studio-fold-summary';card.append(summary);}
   summary.textContent=preview?'':String(n.text||n.studioPrompt||'选中卡片以查看和编辑').slice(0,280);
  }
  if(typeof renderConnections==='function')renderConnections();
  if(typeof renderMinimap==='function')renderMinimap();
 }
 function mediaLoaded(event){const media=event.target;if(!['IMG','VIDEO'].includes(media.tagName))return;const el=media.closest('.studio-managed-node'),n=nodes.find(x=>x.id===el?.dataset.id);if(n&&visual(n)&&media.closest('.studio-preview')&&rememberRatio(media,n))syncFold();}
 document.addEventListener('loadedmetadata',mediaLoaded,true);
 document.addEventListener('load',mediaLoaded,true);
 for(const type of ['pointerdown','mousedown','dblclick'])document.addEventListener(type,event=>{if(event.target.closest('.studio-fold-toggle')){event.stopImmediatePropagation();}},true);
 document.addEventListener('click',event=>{
  const button=event.target.closest('.studio-fold-toggle');if(!button)return;
  event.preventDefault();event.stopImmediatePropagation();
  const id=button.dataset.foldOwner,n=nodes.find(x=>x.id===id);if(!n)return;
  if(collapsed(n)){manualClosed.delete(id);selectedId=id;selectedIds=[id];}
  else manualClosed.add(id);
  syncSelectionUi();
 },true);
 const originalRender=render;render=function(){originalRender();syncFold();};
 const originalSelection=syncSelectionUi;syncSelectionUi=function(){originalSelection();syncFold();};
})();
