/* Layout-only action alongside the existing selected-node arrangement. */
(()=>{
 const button=document.createElement('button');button.id='studioOrganizeAll';button.type='button';
 button.className='studio-organize-button';button.textContent='整理归类';button.disabled=true;
 button.title='将全部卡片按类型归类排列，只调整位置；Ctrl+Z 可撤销';button.setAttribute('aria-label','一键整理全部卡片并归类');
 document.querySelector('#smartArrangeBtn').insertAdjacentElement('beforebegin',button);
 const headings=document.createElement('div');headings.className='studio-organize-headings';headings.setAttribute('aria-hidden','true');world.append(headings);
 function owners(){const result=new Map();for(const n of nodes.filter(isSmartGroupNode))for(const id of n.items||[])if(!result.has(id))result.set(id,n.id);return result;}
 function refreshHeadings(){
  headings.replaceChildren();
  if(!canvas?.settings?.studioOrganizedLayout)return;
  const grouped=owners();
  for(const [key,label]of StudioCanvasOrganizer.categories){
   const group=nodes.filter(n=>n.id!==SMART_LOG_PREVIEW_NODE_ID&&!grouped.has(n.id)&&StudioCanvasOrganizer.category(n,StudioNodeModel)===key);if(!group.length)continue;
   const title=document.createElement('div');title.className='studio-organize-heading';title.textContent=label+' · '+group.length;
   title.style.left=Math.min(...group.map(n=>n.x))+'px';title.style.top=(Math.min(...group.map(n=>n.y))-65)+'px';title.style.fontSize=Math.min(48,13/viewport.scale)+'px';headings.append(title);
  }
 }
 async function organize(){
  if(!nodes.filter(n=>n.id!==SMART_LOG_PREVIEW_NODE_ID).length){toast('画布上还没有卡片');return;}
  if(button.disabled)return;button.disabled=true;
  try{
   // Flush draft fields before rendering; no generation or model calls.
   await StudioCanvasBridge.flush();
   const grouped=owners(),targets=nodes.filter(n=>n.id!==SMART_LOG_PREVIEW_NODE_ID&&!grouped.has(n.id));
   const bounds=new Map(targets.map(n=>{const items=[n,...nodes.filter(m=>grouped.get(m.id)===n.id)],rs=items.map(nodeRect);return [n.id,{x:Math.min(...rs.map(r=>r.x)),y:Math.min(...rs.map(r=>r.y)),right:Math.max(...rs.map(r=>r.x+r.width)),bottom:Math.max(...rs.map(r=>r.y+r.height))}];}));
   const plan=StudioCanvasOrganizer.plan(targets,canvas.connections,StudioNodeModel,n=>{
    const shown=imageLayout(n.images||[],nodeScale(n),n);
    const bound=bounds.get(n.id);return {width:Math.max(shown.width,bound.right-bound.x),height:Math.max(shown.height,(Number(n.h)||0)*nodeScale(n),bound.bottom-bound.y)};
   });
   pushUndo();undoStack.at(-1).studioLayoutOnly={positions:nodes.map(n=>({id:n.id,x:n.x,y:n.y})),viewport:{...viewport},classified:!!canvas.settings?.studioOrganizedLayout};
   const byId=new Map(nodes.map(n=>[n.id,n]));
   for(const move of plan.moves){const n=byId.get(move.id),bound=bounds.get(n.id),dx=move.x-bound.x,dy=move.y-bound.y;n.x+=dx;n.y+=dy;for(const m of nodes.filter(m=>grouped.get(m.id)===n.id)){m.x+=dx;m.y+=dy;}}
   canvas.settings||={};canvas.settings.studioOrganizedLayout=true;canvasDefaultSmartSettings.studioOrganizedLayout=true;
   render();
   const rs=targets.map(nodeRect),left=Math.min(...rs.map(r=>r.x)),top=Math.min(...rs.map(r=>r.y))-70,right=Math.max(...rs.map(r=>r.x+r.width)),bottom=Math.max(...rs.map(r=>r.y+r.height));
   const side=document.querySelector('.studio-canvas-sidebar')?.getBoundingClientRect(),availableLeft=side?side.right-shell.getBoundingClientRect().left+24:40;
   const panel=document.querySelector('.canvas-agent-panel.studio-open'),availableRight=panel?panel.getBoundingClientRect().left-shell.getBoundingClientRect().left-24:shell.clientWidth-24;
   const width=Math.max(200,availableRight-availableLeft),height=Math.max(200,shell.clientHeight-240);
   viewport.scale=Math.max(.06,Math.min(.82,width/(right-left+160),height/(bottom-top+160)));
   viewport.x=availableLeft+width/2-(left+right)/2*viewport.scale;viewport.y=80+height/2-(top+bottom)/2*viewport.scale;
   applyViewport();refreshHeadings();await StudioCanvasBridge.flush();
   toast('已归类整理 '+targets.length+' 张卡片，可按 Ctrl+Z 撤销');
  }catch(error){toast('整理未完成：'+error.message);}finally{button.disabled=false;}
 }
 button.addEventListener('pointerdown',e=>e.stopPropagation());button.addEventListener('mousedown',e=>e.stopPropagation());
 button.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();organize();});
 const previousLoad=window.onload;window.onload=async function(...args){if(previousLoad)await previousLoad.apply(this,args);button.disabled=false;};
 const previousRender=render;render=function(){previousRender();if(!headings.isConnected)world.append(headings);refreshHeadings();};
 const previousViewport=applyViewport;applyViewport=function(){previousViewport();for(const title of headings.children)title.style.fontSize=Math.min(48,13/viewport.scale)+'px';};
 const previousUndo=performUndo;performUndo=function(){
  const layout=undoStack.at(-1)?.studioLayoutOnly;if(!layout)return previousUndo();undoStack.pop();
  const byId=new Map(nodes.map(n=>[n.id,n]));for(const saved of layout.positions){const n=byId.get(saved.id);if(n){n.x=saved.x;n.y=saved.y;}}
  canvas.settings||={};if(layout.classified){canvas.settings.studioOrganizedLayout=true;canvasDefaultSmartSettings.studioOrganizedLayout=true;}else{delete canvas.settings.studioOrganizedLayout;delete canvasDefaultSmartSettings.studioOrganizedLayout;}
  Object.assign(viewport,layout.viewport);render();applyViewport();scheduleSave();toast('已撤销归类整理');
 };
})();
