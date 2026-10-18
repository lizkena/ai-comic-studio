/* Adaptation code, kept separate from the attributed original frontend. */
(() => {
 const bridge=window.StudioCanvasBridge;
 let currentConfig=null;
 const send=data=>parent.postMessage({source:'studio-original-canvas',project:bridge.project,...data},location.origin);
 bridge.context=()=>({studio_node_id:selectedId||'text',studio_node_title:selectedNode()?.title||'画布镜头'});
 backToCanvasList=()=>send({type:'return'});
 // The donor uses double-click; also offer the requested right-click entry.
 document.addEventListener('contextmenu',event=>{
  if(event.target.closest('.image-node,.composer,.asset-panel,.smart-back,.create-menu,.canvas-agent-panel,input,textarea,[contenteditable]'))return;
  event.preventDefault();event.stopImmediatePropagation();openCreateMenu(event);
 },true);
 const originalSave=saveCanvas;
 let serializedSave=Promise.resolve();
 saveCanvas=function(){serializedSave=serializedSave.catch(()=>{}).then(()=>originalSave());return serializedSave;};
 bridge.flush=async()=>{for(let attempt=0;attempt<3;attempt++){clearTimeout(saveTimer);await saveCanvas();await bridge.pendingSave;if(bridge.saveError)throw bridge.saveError;if(!bridge.saveConflict)return;}throw Error('画布正在被其他窗口更新，请稍后再返回');};
 const previousLoad=window.onload;
 window.onload=async()=>{
  await previousLoad();
  applyTheme(params.get('theme')||'dark');
  const cfg=await fetch('/api/config').then(r=>r.json());
  currentConfig=cfg;
  settings.engine='api';
  if(!canvas.nodes?.length&&cfg.project_bindings){settings.provider_id=cfg.project_bindings.image||settings.provider_id;settings.model=cfg.project_models.image||settings.model;}
  engineSelect.replaceChildren(new Option('工作台模型','api'));engineSelect.value='api';
  const label=document.querySelector('#canvasAgentToggle span');if(label)label.textContent='创作助手';
  document.querySelector('#canvasAgentToggle').setAttribute('aria-expanded','false');
  document.querySelector('#canvasAgentToggle').onclick=()=>toggleAgent();
  setupAgent(cfg);
  const status=document.createElement('div');status.className='studio-canvas-status';document.body.append(status);
  const updateSaveStatus=()=>{status.textContent=bridge.saveError?'保存失败：'+bridge.saveError.message:bridge.saving?'正在保存画布…':'原版无限画布 · 本地自动保存';status.setAttribute('role','status');};
  updateSaveStatus();setInterval(updateSaveStatus,500);
  updateProviderModels();render();send({type:'ready'});
 };
 const originalTimelineBody=smartMinimaxBodyHtml;
 smartMinimaxBodyHtml=function(node){return originalTimelineBody(node).replace(/<select class="minimax-engine-select"[\s\S]*?<\/select>/,'<select class="minimax-engine-select" data-minimax-engine><option value="comfyui">工作台视频模型</option></select>');};
 runMinimaxNode=async function(nodeId){
  const node=nodes.find(n=>n.id===nodeId&&n.type==='smart-minimax');if(!node||node.running)return;
  savePromptDraftForCurrent();const segment=smartMinimaxSelectedSegment(node);node.running=true;node.runStartedAt=nowMs();render();
  try{
   const cfg=currentConfig||await fetch('/api/config').then(r=>r.json());
   const provider=cfg.project_bindings.video||cfg.api_providers.find(p=>p.video_models.length)?.id;
   const channel=cfg.api_providers.find(p=>p.id===provider);const model=cfg.project_models.video||channel?.video_models[0];
   if(!provider||!model)throw Error('请先在工作台设置中配置视频模型');
   const response=await fetch('/api/canvas-video',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:smartMinimaxPrompt(node),provider_id:provider,model,duration:segment?.duration||8,aspect_ratio:(segment?.aspectRatio||node.aspectRatio||'16:9').split(' ')[0],images:smartMinimaxRefsForKind(node,'image'),audios:smartMinimaxRefsForKind(node,'audio'),videos:smartMinimaxRefsForKind(node,'video'),studio_node_id:node.id,studio_node_title:node.title})});
   const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'视频生成未完成');
   const items=resultMediaUrls(result);if(!items.length)throw Error('视频任务没有返回可播放文件');
   items.forEach(item=>smartMinimaxSetSegmentResult(node,segment,item));node.studioJobId=result.job_id;toast('当前片段已生成');
  }catch(error){toast(error.message);}finally{node.running=false;node.runFinishedAt=nowMs();node.runElapsedMs=node.runFinishedAt-node.runStartedAt;render();await bridge.flush();}
 };
 function toggleAgent(){const panel=document.querySelector('#canvasAgentPanel');panel.classList.toggle('studio-open');document.querySelector('#canvasAgentToggle').setAttribute('aria-expanded',String(panel.classList.contains('studio-open')));}
 function bubble(role,text){const el=document.createElement('div');el.className='canvas-agent-bubble '+role;el.textContent=text;document.querySelector('#canvasAgentMessages').append(el);el.scrollIntoView({block:'nearest'});}
 async function setupAgent(cfg){
  const platform=document.querySelector('#canvasAgentProvider'),model=document.querySelector('#canvasAgentModel');
  const channels=cfg.api_providers.filter(p=>p.chat_models.length);
  platform.replaceChildren(...channels.map(p=>new Option(p.name,p.id)));
  if(cfg.project_bindings.text)platform.value=cfg.project_bindings.text;
  const models=()=>{model.replaceChildren(...(channels.find(p=>p.id===platform.value)?.chat_models||[]).map(m=>new Option(m,m)));if(cfg.project_models.text)model.value=cfg.project_models.text;};models();platform.onchange=models;
  document.querySelector('#canvasAgentClose').onclick=toggleAgent;
  for(const id of ['canvasAgentAdd','canvasAgentMention','canvasAgentSkill'])document.getElementById(id).hidden=true;
  const input=document.querySelector('#canvasAgentInput'),button=document.querySelector('#canvasAgentSend');input.placeholder='描述你要处理的文本，选中节点会自动带入上下文…';
  try{const data=await fetch('/api/assistant-history').then(r=>r.json());for(const item of data.messages){bubble('user',item.request);bubble('assistant',item.reply);}}catch{}
  async function submit(){
   const request=input.value.trim();if(!request||button.disabled)return;
   const node=selectedNode(),base=node?.type==='smart-prompt'?promptNodeLLMInputText(node):inputPromptTextFor(node)||'';
   bubble('user',request);input.value='';button.disabled=true;
   const split=/拆.*(分镜|镜头)|(分镜|镜头).*拆/.test(request);
   try{
    const response=await fetch('/api/canvas-llm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:'当前节点文本：\n'+base+'\n\n用户要求：'+request,system_prompt:split?'将文本拆成独立镜头描述，每个镜头完整保留人物、画面、动作和对白。镜头之间只用单独一行的 <<<SHOT>>> 分隔，不添加开场总结。':'根据用户要求处理当前画布文本，返回可以直接使用的完整结果。',provider:platform.value,model:model.value,studio_node_id:node?.id||'assistant',studio_node_title:node?.title||'创作助手'})});
    const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'生成未完成');
    const parts=split?result.text.split(/\s*<<<SHOT>>>\s*/).filter(p=>p.trim()):[result.text];
    pushUndo();const origin=node?{x:node.x+(node.w||316)+110,y:node.y}:viewportCenter();
    parts.forEach((text,index)=>{const out=createPromptNode(origin.x,origin.y+index*300,{skipUndo:true});out.text=text;out.title=split?'镜头 '+String(index+1).padStart(2,'0'):'助手结果';out.studioJobId=result.job_id;if(node)canvas.connections.push({from:node.id,to:out.id,kind:'input'});});
    render();await bridge.flush();bubble('assistant',`已生成 ${parts.length} 个文本节点并放入画布。\n\n`+result.text);
   }catch(error){bubble('assistant',error.message);}finally{button.disabled=false;}
  }
  button.onclick=submit;input.addEventListener('keydown',event=>{if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();submit();}});
 }
 function scope(){const node=selectedNode();return {workspace:'storyboard',stage:'storyboard',canvas_node_id:node?.id||null,canvas_node_title:node?.title||'无限画布',screen:{page:'canvas',selected_kind:node?.type||null,selected_text:(node?.text||'').slice(0,8000),connections:(canvas?.connections||[]).filter(c=>c.from===node?.id||c.to===node?.id).map(c=>({from:nodes.find(n=>n.id===c.from)?.title,to:nodes.find(n=>n.id===c.to)?.title}))}};}
 let lastScope='';
 setInterval(()=>{const next=scope(),text=JSON.stringify(next);if(text!==lastScope){lastScope=text;send({type:'scope',scope:next});}},500);
 window.addEventListener('message',async event=>{
  if(event.source!==parent||event.origin!==location.origin||event.data?.source!=='studio-canvas-parent')return;
  const data=event.data;
  if(data.type==='theme')applyTheme(canvas?.settings?.studioTheme||data.theme);
  if(data.type==='flush'){try{await bridge.flush();send({type:'flushed',request:data.request});}catch(error){send({type:'flushed',request:data.request,error:error.message});}}
  if(data.type==='refresh'){await loadCanvas();render();}
 });
})();
