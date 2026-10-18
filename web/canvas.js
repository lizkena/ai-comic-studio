import {labels,newNode,newId,connect as connectGraph,removeNodes,worldPoint,zoomAt,dimensions,wirePath,curvePath,createHistory} from './canvas-model.js?v=20261010-canvas';
import {submitAgentAction} from './agent-actions.js?v=20261010-agent-buttons';

export function createCanvas({state,api,esc,icon,render,toast,dialog,closeDialog,save,providerSelect,openProject,markSaved,loadAssistant,assistantView}){
 let graph=null,pid=null,selected=new Set(),linkFrom=null,seq=0,saved=0,saving=null,timer=null,busy=false,drag=null,space=false,error='',draft=null;
 const history=createHistory(),pending=new Set(),assistantInputs=new Map();let inspectedJob='',suppressPortClickUntil=0;
 const setProject=p=>{state().project=p;state().dirty=false;markSaved(p);};
 const active=()=>state().page==='canvas'&&graph&&pid===state().project?.id;
 const node=()=>graph?.nodes.find(n=>selected.has(n.id));
 const media=f=>'/media/'+encodeURIComponent(f);
 const button=(action,label,disabled=false)=>`<button type="button" class="small" data-canvas="${action}" ${disabled?'disabled':''}>${label}</button>`;
 const key=()=>`comic-canvas-draft-${pid}`;
 const guarded=fn=>async ev=>{try{await fn(ev)}catch(e){toast(e.message,true)}};
 function stash(){try{localStorage.setItem(key(),JSON.stringify(graph))}catch{}}
 function status(){const el=document.querySelector('#canvas-save-state');if(el)el.textContent=error?'保存未完成':saving?'正在保存':seq>saved?'等待保存':'本地已保存';}
 function changed(){seq++;error='';stash();status();clearTimeout(timer);timer=setTimeout(()=>flush().catch(e=>toast(e.message,true)),700);}
 async function flush(){
  clearTimeout(timer);if(!graph||seq===saved)return;if(saving)return saving;
  const id=pid;saving=(async()=>{while(id===pid&&seq>saved){const at=seq,snapshot=structuredClone(graph);try{const result=await api(`/projects/${id}/canvas`,'PUT',snapshot);graph.revision=result.revision;saved=at;error='';if(seq===saved){try{localStorage.removeItem(key())}catch{}}else stash();}catch(e){error=e.message;stash();throw e;}}})();status();
  try{await saving}finally{saving=null;status();}
 }
 async function open(id){
  await flush();await save();const [project,result]=await Promise.all([api(`/projects/${id}/workflow`),api(`/projects/${id}/canvas`)]);
  pid=id;graph=result;setProject(project);state().dirty=false;state().page='canvas';selected=new Set();linkFrom=null;history.clear();seq=saved=0;error='';draft=null;
  try{const old=JSON.parse(localStorage.getItem(key())||'null');if(old?.nodes)draft=old;}catch{}
  await loadAssistant();render();
 }
 async function refresh(){
  await save();if(seq!==saved)stash();const local=seq!==saved?structuredClone(graph):null;
  const [p,result]=await Promise.all([api(`/projects/${pid}/workflow`),api(`/projects/${pid}/canvas`)]);
  setProject(p);graph=result;seq=saved=0;error='';selected=new Set();history.clear();draft=local;render();toast('已读取最新画布，本地草稿保留');
 }
 function create(){dialog('自由创作 · 无限画布',`<p class="help">已有剧本、分镜或素材可以直接开始，缺少的内容再让助手补充。</p><div class="field"><label for="canvas-name">作品名称</label><input id="canvas-name" value="自由创作短片" maxlength="120"></div><div class="field"><label for="canvas-style">视觉风格</label><select id="canvas-style"><option>写实电影</option><option>三维国漫</option><option>二维动画</option></select></div><div class="field"><label for="canvas-source">已有剧本（可稍后填写）</label><textarea id="canvas-source" placeholder="粘贴剧本，也可以在画布中上传文本文件"></textarea></div>`,`<button class="primary" data-action="canvas-create">${icon('plus')}创建画布</button>`);}
 async function createProject(){const name=document.querySelector('#canvas-name').value.trim(),source=document.querySelector('#canvas-source').value,style=document.querySelector('#canvas-style').value;const project=await api('/canvas-projects','POST',{name,source,settings:{style}});closeDialog();await open(project.id);if(source.trim()){history.record(graph);const n=newNode('script');n.title='已有剧本';n.data.text=source;graph.nodes.push(n);selected=new Set([n.id]);changed();paint();}Object.assign(state(),await api('/projects'));}
 function view(){return `<main class="canvas-page"><div class="canvas-top"><div><div class="eyebrow">FREE CREATION / 无限画布</div><h2>${esc(state().project?.name)}</h2></div><div class="row wrap"><span id="canvas-save-state" class="help"></span>${button('import-project',icon('folder')+'导入当前作品')}${button('export',icon('download')+'导出画布')}<button class="small" data-wb="assistant-toggle">${icon('spark')}创作助手</button><button class="small" data-action="canvas-return">${icon('back')}常规工作台</button></div></div>${draft?`<div class="notice warning canvas-recovery">发现未完成保存的本地草稿。${button('restore','恢复草稿')}${button('discard-draft','忽略草稿')}</div>`:''}<div class="canvas-layout"><aside class="canvas-palette"><strong>添加节点</strong>${Object.entries(labels).map(([kind,name])=>button('add-'+kind,icon(({text:'edit',script:'book',shot:'film',image:'image',video:'play',audio:'mic',asset:'folder',group:'folder'})[kind])+name)).join('')}<label class="canvas-file-button">${icon('folder')}导入剧本<input type="file" data-canvas-file="text" accept=".txt,.md,.json"></label><label class="canvas-file-button">${icon('image')}上传素材<input type="file" data-canvas-file="media" accept="image/png,image/jpeg,image/webp,video/*,audio/*" multiple></label><label class="canvas-file-button">${icon('link')}导入画布<input type="file" data-canvas-file="graph" accept=".json"></label>${button('library',icon('folder')+'选用资产库')}<div class="canvas-help">拖动标题移动节点<br>拖动输出圆点到输入圆点连线<br>滚轮缩放 · 空格拖动平移<br>方向键移动 · Delete 删除<br>Ctrl+Z 撤销 / Ctrl+Y 重做</div></aside><section id="canvas-viewport" class="canvas-viewport" tabindex="0" aria-label="无限画布，方向键移动所选节点"><div id="canvas-world"><svg id="canvas-wires" aria-label="节点连线"></svg><div id="canvas-nodes"></div></div><div id="canvas-empty"></div><div class="canvas-view-tools">${button('undo',icon('back')+'撤销')}${button('redo',icon('refresh')+'重做')}${button('zoom-out','−')}<span id="canvas-zoom">100%</span>${button('zoom-in','＋')}${button('fit',icon('eye')+'适应画布')}</div><div id="canvas-link-tip" role="status"></div></section><aside id="canvas-inspector" class="canvas-inspector"></aside></div><div class="canvas-assistant-overlay">${assistantView()}</div></main>`;}
 function preview(n){const file=n.data.file;if(file&&n.kind==='audio')return `<audio controls preload="none" src="${esc(media(file))}"></audio>`;if(file&&n.kind==='video')return `<video controls preload="metadata" src="${esc(media(file))}"></video>`;if(file)return `<img src="${esc(media(file))}" alt="${esc(n.title)}" loading="lazy">`;return `<p>${esc((n.data.text||'点击节点，在右侧填写内容').slice(0,150))}</p>`;}
 function link(source,target){
  const made=connectGraph(graph,source,target),n=graph.nodes.find(n=>n.id===target);if(n.kind==='video'){
   const seen=new Set(),shots=[];function visit(id){if(seen.has(id))return;seen.add(id);const item=graph.nodes.find(n=>n.id===id);if(item.kind==='shot')shots.push(item);else if(item.kind!=='video')for(const edge of graph.edges.filter(e=>e.target===id))visit(edge.source);}visit(source);
   if(shots.length===1){if(!n.data.duration_override)n.data.duration=shots[0].data.duration||8;if(!n.data.dialogue_override)n.data.dialogue=shots[0].data.dialogue||'';}
  }return made;
 }
 function finishLink(source,target){
  if(!connectGraph({...graph,edges:[...graph.edges]},source,target))return false;
  history.record(graph);link(source,target);changed();return true;
 }
 function clickPort(id,port){
  if(port==='output')linkFrom=id;
  else if(linkFrom){const source=linkFrom;linkFrom=null;try{finishLink(source,id)}finally{paint();}return;}
  paint();
 }
 function jobState(n){const job=state().jobs.find(j=>j.id===n.data.job_id);return job?({queued:'排队中',running:'制作中',waiting_dependency:'等待依赖',succeeded:'已完成',failed:'失败',cancelled:'已取消'}[job.status]||job.status):'';}
 function wires(){const svg=document.querySelector('#canvas-wires');if(!svg)return;const byId=new Map(graph.nodes.map(n=>[n.id,n]));svg.innerHTML=graph.edges.map(e=>`<path d="${wirePath(byId.get(e.source),byId.get(e.target))}"/>`).join('');}
 function transform(){const world=document.querySelector('#canvas-world');if(world)world.style.transform=`translate(${graph.viewport.x}px,${graph.viewport.y}px) scale(${graph.viewport.zoom})`;const el=document.querySelector('#canvas-zoom');if(el)el.textContent=Math.round(graph.viewport.zoom*100)+'%';}
 function paint(inspect=true){
  if(!active())return;const layer=document.querySelector('#canvas-nodes');if(!layer)return;
  updateScope();const contextLabel=document.querySelector('.canvas-assistant-overlay .wb-agent-context span');if(contextLabel)contextLabel.textContent='当前范围：画布 · '+(node()?.title||'无限画布');
  layer.innerHTML=[...graph.nodes].sort((a,b)=>(a.kind==='group'?0:1)-(b.kind==='group'?0:1)).map(n=>{const d=dimensions(n);return `<article class="canvas-node kind-${n.kind} ${n.kind==='group'?'canvas-group':''} ${selected.has(n.id)?'selected':''}" data-node="${n.id}" tabindex="0" aria-label="${esc(labels[n.kind]+': '+n.title)}"><header class="canvas-node-header"><span>${esc(labels[n.kind])}</span><small>${esc(jobState(n))}</small></header><strong class="canvas-node-title">${esc(n.title)}</strong>${n.kind!=='group'?`<div class="canvas-node-preview">${preview(n)}</div><button class="canvas-port input" data-port="input" aria-label="连接到${esc(n.title)}的输入"></button><button class="canvas-port output" data-port="output" aria-label="从${esc(n.title)}连接输出"></button>`:''}</article>`}).join('');
  for(const card of layer.children){const n=graph.nodes.find(n=>n.id===card.dataset.node),d=dimensions(n);Object.assign(card.style,{left:n.x+'px',top:n.y+'px',width:d.w+'px',height:d.h+'px'});}wires();transform();const empty=document.querySelector('#canvas-empty');empty.innerHTML=graph.nodes.length?'':`<div class="canvas-welcome">${icon('film')}<h3>直接开始你的短片</h3><p>添加剧本或分镜，连上图片与视频节点。<br>也可以导入现有作品，继续制作。</p>${button('add-script',icon('plus')+'添加剧本')}</div>`;
  document.querySelector('#canvas-link-tip').textContent=linkFrom?'正在连线：点击目标节点左侧圆点；Esc 取消':'';
  if(inspect)inspector();status();
 }
 function updateScope(){const n=node();state().canvasScope={workspace:'storyboard',stage:n?.kind==='script'?'script':['asset','audio'].includes(n?.kind)?'assets':n?.kind==='video'?'video':'storyboard',target_id:n?.data.segment_id||n?.data.asset_id||null,episode_id:n?.data.episode_id||null,canvas_node_id:n?.id||null,canvas_node_title:n?.title||'无限画布',screen:{page:'canvas',selected_kind:n?.kind||null,selected_text:(n?.data.text||'').slice(0,4000),connections:graph.edges.filter(e=>e.source===n?.id||e.target===n?.id).map(e=>({from:graph.nodes.find(x=>x.id===e.source)?.title,to:graph.nodes.find(x=>x.id===e.target)?.title}))}};}
 async function beforeAssistant(){
  if(!active())return;await flush();await save();const n=node();
  if(n&&['script','shot'].includes(n.kind)&&(n.data.text||graph.edges.some(e=>e.target===n.id))){
   busy=true;try{const p=await api(`/projects/${pid}/workflow`),result=await api(`/projects/${pid}/canvas/prepare/${n.id}`,'POST',{revision:graph.revision,project_revision:p.revision});setProject(result.project);graph=result.canvas;seq=saved=0;history.clear();}finally{busy=false;}
  }
  updateScope();if(node())assistantInputs.set(node().id,node().data.text||'');
 }
 async function assistantResult(message){
  if(!active())return;const n=graph.nodes.find(n=>n.id===message.scope?.canvas_node_id);if(!n)return;
  if(message.job_id){n.data.job_id=message.job_id;n.data.submitted_text=n.data.text||'';changed();await flush();}
  if(message.status==='applied'&&(n.data.text||'')===assistantInputs.get(n.id)){
   const p=state().project;markSaved(p);const seg=p.segments.find(s=>s.id===n.data.segment_id),asset=p.assets.find(a=>a.id===n.data.asset_id),ep=p.outputs.script?.episodes?.find(e=>e.id===n.data.episode_id);
   if(seg){n.data.text=n.kind==='image'?seg.image_prompt:seg.prompt;if(['shot','video'].includes(n.kind)){n.data.dialogue=seg.dialogue_text||seg.shots.map(s=>s.dialogue).filter(Boolean).join('\n');n.data.duration=seg.duration;}}
   else if(asset)n.data.text=asset.image_prompt||asset.description;
   else if(ep)n.data.text=ep.scenes.map(s=>s.action).join('\n\n');changed();await flush();
  }
 }
 function inspector(){
  const panel=document.querySelector('#canvas-inspector');if(!panel)return;const n=node();
  const resetScroll=inspectedJob.split(':')[0]!== (n?.id||'');inspectedJob=(n?.id||'')+':'+(n?jobState(n):'');
  if(!n){panel.innerHTML=`<h3>节点属性</h3><p class="help">选择节点编辑内容。参考图与音色可直接上传，也可从资产库选用。</p><div class="panel"><strong>最短制作路径</strong><p class="help">已有分镜 → 镜头图片 → 视频<br>已有剧本 → 拆分分镜 → 制作短片</p></div><p class="help">只有点击生成才调用服务。项目类型、记忆与技能沿用当前作品。</p>${button('assistant','查看助手记录')}`;return;}
  const outgoing=graph.edges.filter(e=>e.source===n.id||e.target===n.id);
  const producing=pending.has(n.id)||['queued','running','waiting_dependency'].includes(state().jobs.find(j=>j.id===n.data.job_id)?.status);
  const generated=!!(n.data.file||n.data.job_id||n.kind==='shot'&&n.data.segment_id&&n.data.text);
  const genName=n.kind==='script'?'拆分剧本为分镜':n.kind==='shot'?'生成镜头描述':n.kind==='image'?'生成镜头图片':'生成视频';
  panel.innerHTML=`<div class="row between"><h3>${esc(labels[n.kind])}</h3><small>${selected.size} 个已选</small></div><div class="field"><label for="canvas-title">名称</label><input id="canvas-title" data-canvas-field="title" value="${esc(n.title)}"></div>${n.kind!=='group'?`<div class="field"><label for="canvas-text">${n.kind==='script'?'剧本原文':n.kind==='shot'?'镜头描述 / 提示词':'内容 / 制作要求'}</label><textarea id="canvas-text" data-canvas-field="text" placeholder="可直接填写已有内容">${esc(n.data.text||'')}</textarea></div>`:''}${['shot','video'].includes(n.kind)?`<div class="field"><label for="canvas-duration">镜头时长 / 秒</label><input id="canvas-duration" data-canvas-field="duration" type="number" min="1" max="120" value="${n.data.duration||8}"></div><div class="field"><label for="canvas-dialogue">台词（音色绑定可选）</label><textarea id="canvas-dialogue" data-canvas-field="dialogue" placeholder="角色：台词，或 00:00–00:02 角色：台词">${esc(n.data.dialogue||'')}</textarea></div>`:''}${n.kind==='asset'?`<div class="field"><label>参考类型</label><select data-canvas-field="asset_kind">${[['character','角色'],['location','场景'],['prop','道具']].map(([k,v])=>`<option value="${k}" ${n.data.asset_kind===k?'selected':''}>${v}</option>`).join('')}</select></div>`:''}${['image','video','audio','asset'].includes(n.kind)?`<label class="canvas-file-button">${icon('folder')}上传${n.kind==='audio'?'音色':'素材'}<input type="file" data-canvas-file="node" accept="${n.kind==='audio'?'audio/*':n.kind==='video'?'video/*':'image/png,image/jpeg,image/webp'}"></label>${button('library',icon('folder')+'从资产库选用')}`:''}
  <details><summary>位置与分组（也可用方向键移动）</summary><div class="grid2"><div class="field"><label>X</label><input type="number" data-canvas-field="x" value="${n.x}"></div><div class="field"><label>Y</label><input type="number" data-canvas-field="y" value="${n.y}"></div></div>${n.kind!=='group'?`<label>所属分组<select data-canvas-field="group_id"><option value="">无</option>${graph.nodes.filter(g=>g.kind==='group').map(g=>`<option value="${g.id}" ${n.data.group_id===g.id?'selected':''}>${esc(g.title)}</option>`).join('')}</select></label>`:''}</details>
  <div class="rule"></div><strong>连接</strong><div class="row"><select id="canvas-source" aria-label="连接来源"><option value="">选择输入节点</option>${graph.nodes.filter(s=>s.id!==n.id&&s.kind!=='group').map(s=>`<option value="${s.id}">${esc(s.title)}</option>`).join('')}</select>${button('connect','连接')}</div><div class="canvas-connections">${outgoing.map(e=>`<div><span>${esc(graph.nodes.find(s=>s.id===e.source)?.title)} → ${esc(graph.nodes.find(s=>s.id===e.target)?.title)}</span><button class="ghost small" data-canvas="unlink" data-source="${e.source}" data-target="${e.target}" aria-label="移除连线">${icon('close')}</button></div>`).join('')||'<small>尚未连接</small>'}</div>
  ${['script','shot','image','video'].includes(n.kind)?`<div class="rule"></div><details><summary>模型与服务</summary><div class="field"><label>${n.kind==='script'||n.kind==='shot'?'文字模型':n.kind==='image'?'图片服务':'视频服务'}</label>${providerSelect(n.kind==='script'||n.kind==='shot'?'text':n.kind)}</div></details><button class="primary full" data-canvas="generate" ${busy||producing?'disabled':''}>${icon(producing?'clock':generated?'refresh':'spark')}${producing?'制作中':(generated?'重新'+genName:genName)}</button>${n.kind==='script'?button('import-results','将生成的分镜添加到画布',!n.data.episode_id):''}<p class="help">${n.kind==='script'||n.kind==='shot'?'由创作助手选择技能并记录操作，结果写入对应分镜。':'使用已有生成接口与任务队列，完成后刷新到节点。'}${n.data.segment_id?'已关联项目镜头。':''}</p>`:''}
  ${n.data.job_id?`<p class="help">${esc(jobState(n))}</p>${button('job','查看任务与错误')}`:''}<div class="row wrap">${button('duplicate',icon('plus')+'复制')}${button('group',icon('folder')+'分组')}${button('delete',icon('trash')+'删除',busy)}</div>`;if(resetScroll)panel.scrollTop=0;
 }
 function add(kind){const previous=node();history.record(graph);const el=document.querySelector('#canvas-viewport'),point=worldPoint(graph.viewport,(el?.clientWidth||700)/2-120,(el?.clientHeight||500)/2-100),n=newNode(kind,previous?previous.x+330:Math.round(point.x),previous?previous.y:Math.round(point.y));graph.nodes.push(n);selected=new Set([n.id]);changed();paint();}
 async function generate(){
  const n=node();if(!n||busy)return;busy=true;pending.add(n.id);inspector();
  try{
   await flush();await save();const project=await api(`/projects/${pid}/workflow`);setProject(project);
   const result=await api(`/projects/${pid}/canvas/prepare/${n.id}`,'POST',{revision:graph.revision,project_revision:project.revision});
   setProject(result.project);state().dirty=false;graph=result.canvas;seq=saved=0;history.clear();
   const job=result.payload.kind==='text'?await submitAgentAction(api,result.project,result.payload):await api(`/projects/${pid}/jobs`,'POST',result.payload);
   const current=graph.nodes.find(x=>x.id===n.id);current.data.job_id=job.id;current.data.submitted_text=current.data.text||'';state().jobs=[job,...state().jobs.filter(j=>j.id!==job.id)];changed();await flush();paint();toast('任务已提交，完成后自动刷新节点');
  }finally{busy=false;pending.delete(n.id);inspector();}
 }
 async function importProject(episodeId){
  await save();setProject(await api(`/projects/${pid}/workflow`));const p=state().project,episodes=p.outputs.script?.episodes||[];
  if(!episodeId){dialog('导入当前作品的剧本、分镜与资产',`<p class="help">选择一集，将已有内容放到画布；不会重新生成或修改原内容。</p><select id="canvas-import-episode">${episodes.map(ep=>`<option value="${ep.id}">${esc(ep.title)}</option>`).join('')||'<option value="">作品暂无分集</option>'}</select>`,`<button data-canvas="import-confirm" class="primary">导入所选分集与资产</button>`);return;}
  const ep=episodes.find(ep=>ep.id===episodeId);if(!ep)return;
  const segs=p.segments.filter(s=>s.episode_id===ep.id),assets=p.assets.filter(a=>segs.some(s=>[...(s.character_ids||[]),...(s.prop_ids||[]),s.location_id].includes(a.id)));
  if(graph.nodes.length+1+segs.length*3+assets.length>500)throw Error('节点数量超过 500，请分开整理画布');
  history.record(graph);const base=graph.nodes.length?Math.max(...graph.nodes.map(n=>n.y))+480:50;
  const script=graph.nodes.find(n=>n.kind==='script'&&n.data.episode_id===ep.id)||newNode('script',40,base);script.title=ep.title;script.data={...script.data,text:ep.scenes.map(s=>s.action).join('\n\n'),episode_id:ep.id};if(!graph.nodes.includes(script))graph.nodes.push(script);
  const refs=[];assets.forEach((a,i)=>{let n=graph.nodes.find(n=>n.data.asset_id===a.id&&n.kind==='asset');if(!n){n=newNode('asset',40,base+240+i*220);n.title=a.name;n.data={asset_id:a.id,asset_kind:a.kind,text:a.description||'',file:a.references?.at(-1)?.file};graph.nodes.push(n);}refs.push(n);});
  segs.forEach((s,i)=>{let shot=graph.nodes.find(n=>n.kind==='shot'&&n.data.segment_id===s.id);if(shot)return;shot=newNode('shot',370,base+i*290);shot.title=s.title;shot.data={segment_id:s.id,episode_id:ep.id,duration:s.duration,text:s.prompt||s.shots.map(x=>x.action).join('\n'),dialogue:s.dialogue_text||s.shots.map(x=>x.dialogue).filter(Boolean).join('\n')};graph.nodes.push(shot);link(script.id,shot.id);for(const ref of refs)if([...(s.character_ids||[]),...(s.prop_ids||[]),s.location_id].includes(ref.data.asset_id))link(ref.id,shot.id);
   const img=newNode('image',700,base+i*290);img.title=s.title+' · 图片';img.data={segment_id:s.id,text:s.image_prompt||'',file:s.images?.find(x=>x.id===s.current_image)?.file};graph.nodes.push(img);link(shot.id,img.id);
   const video=newNode('video',1030,base+i*290);video.title=s.title+' · 视频';video.data={segment_id:s.id,duration:s.duration,text:s.prompt||'',file:s.versions?.find(x=>x.id===s.current_version)?.file};graph.nodes.push(video);link(s.continuity?shot.id:img.id,video.id);
  });closeDialog();changed();paint();fit();toast('已有剧本、分镜与引用资产已添加到画布');
 }
 function fit(){const vp=document.querySelector('#canvas-viewport');if(!vp||!graph.nodes.length)return;const x=Math.min(...graph.nodes.map(n=>n.x)),y=Math.min(...graph.nodes.map(n=>n.y)),right=Math.max(...graph.nodes.map(n=>n.x+dimensions(n).w)),bottom=Math.max(...graph.nodes.map(n=>n.y+dimensions(n).h));const zoom=Math.max(.2,Math.min(1,(vp.clientWidth-90)/(right-x),(vp.clientHeight-90)/(bottom-y)));graph.viewport={x:45-x*zoom,y:45-y*zoom,zoom};changed();transform();}
 async function library(){
  const rows=await api('/library');dialog('从资产库选用',`<p class="help">图片可作首帧或参考资产，声音样本用于可选的角色音色绑定。</p><div class="canvas-library">${rows.map(a=>`<button data-canvas="library-pick" data-id="${esc(a.id)}">${icon(a.kind==='audio'?'mic':'image')}<span>${esc(a.name)}</span><small>${esc(a.kind)}</small></button>`).join('')||'<p>资产库暂无素材，请先上传。</p>'}</div>`);}
 async function selectLibrary(id){
  const a=await api('/library/'+id),v=(a.versions?.find(v=>v.version===a.version)||a.versions?.at(-1))?.content||a;const file=v.file||v.references?.[0]?.file;
  if(!file)throw Error('该资产没有可用素材');history.record(graph);let n=node();const kind=a.kind==='audio'?'audio':a.kind==='video'?'video':['character','location','prop'].includes(a.kind)?'asset':'image';
  if(!n||!['image','asset','audio','video'].includes(n.kind)){n=newNode(kind,100,100);graph.nodes.push(n);selected=new Set([n.id]);}
  if((n.kind==='audio')!==(kind==='audio')||(n.kind==='video')!==(kind==='video'))throw Error('素材类型与节点不匹配，请选择对应节点');
  if(n.kind==='asset'&&!n.data.asset_id&&['character','location','prop'].includes(a.kind)){
   await save();const result=await api(`/library/${id}/reuse`,'POST',{project_id:pid,version:a.version});setProject(result.project);n.data.asset_id=result.asset_id;
  }
  await adoptFile(n,file,{library_id:id,library_version:a.version});
  n.title=a.name;n.data.file=file;if(n.kind==='asset')n.data.asset_kind=['character','location','prop'].includes(a.kind)?a.kind:'prop';closeDialog();changed();paint();
 }
 async function adoptFile(n,file,provenance={}){
  if(!n.data.asset_id&&!n.data.segment_id)return;
  await save();const p=await api(`/projects/${pid}/workflow`);setProject(p);
  if(n.kind==='audio'&&n.data.asset_id){
   const asset=p.assets.find(a=>a.id===n.data.asset_id);asset.voice=file;delete asset.voice_library_id;delete asset.voice_library_version;
   if(provenance.library_id){asset.voice_library_id=provenance.library_id;asset.voice_library_version=provenance.library_version;}
   setProject(await api(`/projects/${pid}`,'PUT',p));
  }else if(n.kind==='video'&&n.data.segment_id){setProject(await api(`/projects/${pid}/import-video/${n.data.segment_id}`,'POST',{file}));}
  else if(['image','asset'].includes(n.kind)){setProject(await api(`/projects/${pid}/workflow/adopt-image`,'POST',{revision:p.revision,target_id:n.data.asset_id||n.data.segment_id,file,...provenance}));}
  state().dirty=false;
 }
 function exportGraph(){const blob=new Blob([JSON.stringify({format:'comic-studio-canvas-v1',...graph},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=state().project.name+'-画布.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 async function click(ev){
  const el=ev.target.closest('[data-canvas],[data-port]');if(!el)return;
  if(el.dataset.port){if(busy||performance.now()<suppressPortClickUntil)return;clickPort(el.closest('[data-node]').dataset.node,el.dataset.port);return;}
  const action=el.dataset.canvas;if(busy&&action!=='job')throw Error('正在提交任务，请稍候编辑');if(action.startsWith('add-')){add(action.slice(4));return;}
  if(action==='generate'){await generate();return;}
  if(action==='import-project'){await importProject();return;}
  if(action==='import-confirm'){await importProject(document.querySelector('#canvas-import-episode').value);return;}
  if(action==='import-results'){await importProject(node()?.data.episode_id);return;}
  if(action==='library'){await library();return;}
  if(action==='library-pick'){await selectLibrary(el.dataset.id);return;}
  if(action==='export'){await flush();exportGraph();return;}
  if(action==='job'){const job=await api('/jobs/'+node().data.job_id);dialog('制作任务',`<p>${esc(job.status)}</p><pre class="canvas-task">${esc(job.error||'')+'\n'+esc(JSON.stringify(job.logs||job.log||[],null,2))}</pre>`);return;}
  if(action==='assistant'){const rows=await api(`/projects/${pid}/assistant`);dialog('当前作品 · 助手记录',`<div class="canvas-task">${rows.map(m=>`<p><strong>${esc(m.message||m.request||'制作记录')}</strong></p><p>${esc(m.reply||'')}</p>`).join('')||'<p>暂无对话记录。通过生成按钮执行的文字任务也会记录在这里。</p>'}</div>`);return;}
  if(action==='fit'){fit();return;}
  if(action==='zoom-in'||action==='zoom-out'){const vp=document.querySelector('#canvas-viewport');graph.viewport=zoomAt(graph.viewport,action==='zoom-in'?1.2:1/1.2,vp.clientWidth/2,vp.clientHeight/2);changed();transform();return;}
  if(action==='undo'||action==='redo'){const next=history[action](graph);if(next){const revision=graph.revision;graph={...next,revision};selected=new Set();changed();paint();}return;}
  if(action==='restore'){history.record(graph);graph={...draft,revision:graph.revision};draft=null;changed();render();return;}
  if(action==='discard-draft'){localStorage.removeItem(key());draft=null;render();return;}
  history.record(graph);
  if(action==='delete'){if(busy)throw Error('正在提交制作任务，请稍后再删除');removeNodes(graph,selected);selected=new Set();}
  if(action==='duplicate'){for(const n of graph.nodes.filter(n=>selected.has(n.id))){const copy=structuredClone(n);copy.id=newId();copy.x+=30;copy.y+=30;for(const key of ['segment_id','episode_id','asset_id','job_id','canvas_managed'])delete copy.data[key];graph.nodes.push(copy);}}
  if(action==='group'){const nodes=graph.nodes.filter(n=>selected.has(n.id)&&n.kind!=='group');if(nodes.length){const g=newNode('group',Math.min(...nodes.map(n=>n.x))-25,Math.min(...nodes.map(n=>n.y))-60);g.data.width=Math.max(...nodes.map(n=>n.x+dimensions(n).w))-g.x+25;g.data.height=Math.max(...nodes.map(n=>n.y+dimensions(n).h))-g.y+25;graph.nodes.push(g);for(const n of nodes)n.data.group_id=g.id;selected=new Set([g.id]);}}
  if(action==='connect'){const source=document.querySelector('#canvas-source').value;if(!source||!node())throw Error('请选择输入节点');link(source,node().id);}
  if(action==='unlink')graph.edges=graph.edges.filter(e=>e.source!==el.dataset.source||e.target!==el.dataset.target);
  changed();paint();
 }
 async function fileChange(ev){const el=ev.target;if(!el.dataset.canvasFile)return;const files=[...el.files];if(!files.length)return;const target=node();
  if(el.dataset.canvasFile==='graph'){await flush();const imported=JSON.parse(await files[0].text());if(!Array.isArray(imported.nodes)||!Array.isArray(imported.edges))throw Error('不是有效画布文件');const normalized=await api(`/projects/${pid}/canvas`,'PUT',{...imported,revision:graph.revision});history.record(graph);graph=normalized;seq=saved=0;paint();toast('画布已导入');return;}
  history.record(graph);
  for(const file of files){
   if(el.dataset.canvasFile==='text'){const n=newNode('script',100,100+graph.nodes.length*15);n.title=file.name;n.data.text=await file.text();graph.nodes.push(n);selected=new Set([n.id]);changed();continue;}
   const kind=file.type.startsWith('audio/')?'audio':file.type.startsWith('video/')?'video':file.type.startsWith('image/')?'image':null;if(!kind)throw Error('请选择图片、声音或视频素材');
   let n=el.dataset.canvasFile==='node'?target:null;if(n&&((n.kind==='audio')!==(kind==='audio')||(n.kind==='video')!==(kind==='video')))throw Error('素材类型与当前节点不匹配');
   const f=new FormData();f.append('file',file);const result=await api('/media/upload','POST',f);
   if(!n){n=newNode(kind,100,100+graph.nodes.length*15);n.title=file.name;graph.nodes.push(n);}await adoptFile(n,result.file);n.data.file=result.file;selected=new Set([n.id]);changed();
  }paint();el.value='';
 }
 function input(ev){if(busy)return;const field=ev.target.dataset.canvasField,n=node();if(!field||!n)return;
  if(ev.type==='input'&&ev.target.tagName==='SELECT')return;
  if(ev.target.dataset.historyRecorded!=='yes'){history.record(graph);ev.target.dataset.historyRecorded='yes';}
  const value=['x','y','duration'].includes(field)?Number(ev.target.value):ev.target.value;if(typeof value==='number'&&!Number.isFinite(value))return;
  if(['x','y','title'].includes(field))n[field]=value;else n.data[field]=value;
  if(field==='duration')n.data.duration_override=true;if(field==='dialogue')n.data.dialogue_override=true;changed();const card=document.querySelector(`[data-node="${n.id}"]`);if(card){card.querySelector('.canvas-node-title').textContent=n.title;card.style.left=n.x+'px';card.style.top=n.y+'px';if(field==='text'&&card.querySelector('.canvas-node-preview p'))card.querySelector('.canvas-node-preview p').textContent=value.slice(0,150);}wires();
 }
 function linkPreview(ev){
  const vp=document.querySelector('#canvas-viewport'),svg=document.querySelector('#canvas-wires'),n=graph.nodes.find(n=>n.id===drag.id);if(!vp||!svg||!n)return;
  const rect=vp.getBoundingClientRect(),point=worldPoint(graph.viewport,ev.clientX-rect.left,ev.clientY-rect.top),d=dimensions(n),output=drag.port==='output';
  let path=svg.querySelector('.canvas-wire-preview');if(!path){path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('class','canvas-wire-preview');svg.append(path);}
  path.setAttribute('d',output?curvePath(n.x+d.w,n.y+d.h/2,point.x,point.y):curvePath(point.x,point.y,n.x,n.y+d.h/2));
  document.querySelectorAll('.canvas-port.drop-target').forEach(p=>p.classList.remove('drop-target'));
  const target=document.elementFromPoint(ev.clientX,ev.clientY)?.closest('[data-port]');if(target&&target.dataset.port!==drag.port&&target.closest('[data-node]')?.dataset.node!==drag.id)target.classList.add('drop-target');
 }
 function pointerDown(ev){if(busy)return;const viewport=document.querySelector('#canvas-viewport'),port=ev.target.closest('[data-port]');
  if(port&&ev.button===0){drag={mode:'link',id:port.closest('[data-node]').dataset.node,port:port.dataset.port,pointerId:ev.pointerId,x:ev.clientX,y:ev.clientY,moved:false};viewport.setPointerCapture(ev.pointerId);port.classList.add('connecting');viewport.focus();ev.preventDefault();return;}
  if(ev.target.closest('button,input,textarea,select,a,video,audio'))return;const card=ev.target.closest('[data-node]'),id=card?.dataset.node;
  if(ev.button===1||space||(!card&&ev.button===0)){drag={mode:'pan',x:ev.clientX,y:ev.clientY,view:{...graph.viewport}};viewport.setPointerCapture(ev.pointerId);ev.preventDefault();return;}
  if(id){if(ev.shiftKey){selected.has(id)?selected.delete(id):selected.add(id);}else if(!selected.has(id))selected=new Set([id]);paint();if(ev.target.closest('.canvas-node-header')){history.record(graph);const ids=new Set(selected);for(const g of graph.nodes.filter(n=>ids.has(n.id)&&n.kind==='group'))for(const n of graph.nodes)if(n.data.group_id===g.id)ids.add(n.id);drag={mode:'move',x:ev.clientX,y:ev.clientY,nodes:graph.nodes.filter(n=>ids.has(n.id)).map(n=>({id:n.id,x:n.x,y:n.y}))};viewport.setPointerCapture(ev.pointerId);}viewport.focus();ev.preventDefault();}else{selected=new Set();paint();}}
 function pointerMove(ev){if(!drag)return;const dx=ev.clientX-drag.x,dy=ev.clientY-drag.y;if(drag.mode==='link'){if(Math.hypot(dx,dy)>4)drag.moved=true;if(drag.moved){linkPreview(ev);document.querySelector('#canvas-link-tip').textContent='拖到另一节点的'+(drag.port==='output'?'输入':'输出')+'圆点后松开；Esc 取消';}return;}if(drag.mode==='pan'){graph.viewport.x=drag.view.x+dx;graph.viewport.y=drag.view.y+dy;transform();}else{for(const original of drag.nodes){const n=graph.nodes.find(n=>n.id===original.id);n.x=Math.round(original.x+dx/graph.viewport.zoom);n.y=Math.round(original.y+dy/graph.viewport.zoom);const card=document.querySelector(`[data-node="${n.id}"]`);if(card){card.style.left=n.x+'px';card.style.top=n.y+'px';}}wires();}}
 function pointerUp(ev,cancelled=false){
  if(!drag)return;const ended=drag;drag=null;
  if(ended.mode==='link'){
   const vp=document.querySelector('#canvas-viewport');if(vp?.hasPointerCapture(ended.pointerId))vp.releasePointerCapture(ended.pointerId);
   document.querySelector('.canvas-wire-preview')?.remove();document.querySelectorAll('.canvas-port.connecting,.canvas-port.drop-target').forEach(p=>p.classList.remove('connecting','drop-target'));document.querySelector('#canvas-link-tip').textContent='';
   suppressPortClickUntil=performance.now()+250;
   if(!ended.moved&&!cancelled){try{clickPort(ended.id,ended.port)}catch(e){toast(e.message,true)}return;}
   linkFrom=null;
   if(!cancelled&&ev){const port=document.elementFromPoint(ev.clientX,ev.clientY)?.closest('[data-port]');if(port&&port.dataset.port!==ended.port){const id=port.closest('[data-node]').dataset.node;try{finishLink(ended.port==='output'?ended.id:id,ended.port==='output'?id:ended.id)}catch(e){toast(e.message,true)}}}
   paint();return;
  }changed();inspector();
 }
 function afterRender(){if(!active())return;const root=document.querySelector('.canvas-page');root.addEventListener('click',guarded(click));root.addEventListener('input',input);root.addEventListener('change',guarded(async e=>{input(e);await fileChange(e)}));root.addEventListener('focusout',e=>{if(e.target.dataset)e.target.dataset.historyRecorded='';});
  const vp=document.querySelector('#canvas-viewport');vp.addEventListener('pointerdown',pointerDown);vp.addEventListener('pointermove',pointerMove);vp.addEventListener('pointerup',pointerUp);vp.addEventListener('pointercancel',e=>pointerUp(e,true));vp.addEventListener('wheel',e=>{e.preventDefault();if(busy||drag)return;const rect=vp.getBoundingClientRect();graph.viewport=zoomAt(graph.viewport,Math.exp(-e.deltaY*.001),e.clientX-rect.left,e.clientY-rect.top);changed();transform();},{passive:false});paint();
 }
 document.addEventListener('click',guarded(e=>{if(active()&&e.target.closest('dialog [data-canvas]'))return click(e);}));
 document.addEventListener('keydown',guarded(async e=>{if(!active()||e.target.closest('dialog')||e.target.isContentEditable||['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))return;if(e.key===' '){space=true;e.preventDefault();}if(e.key==='Escape'){pointerUp(null,true);linkFrom=null;paint();}if((e.ctrlKey||e.metaKey)&&['z','y'].includes(e.key.toLowerCase())){e.preventDefault();await click({target:{closest:()=>({dataset:{canvas:e.key.toLowerCase()==='y'||e.shiftKey?'redo':'undo'}})}});return;}if(e.key==='Delete'||e.key==='Backspace'){e.preventDefault();await click({target:{closest:()=>({dataset:{canvas:'delete'}})}});}if(e.key.startsWith('Arrow')&&selected.size){e.preventDefault();history.record(graph);for(const n of graph.nodes.filter(n=>selected.has(n.id))){n.x+=({ArrowLeft:-1,ArrowRight:1}[e.key]||0)*(e.shiftKey?30:10);n.y+=({ArrowUp:-1,ArrowDown:1}[e.key]||0)*(e.shiftKey?30:10);}changed();paint();}}));
 document.addEventListener('keyup',e=>{if(e.key===' ')space=false;});window.addEventListener('blur',()=>{space=false;pointerUp(null,true);});
 async function poll(){
  if(!active()||busy||drag||saving||seq!==saved||document.querySelector('dialog'))return;
  const completed=graph.nodes.filter(n=>n.data.job_id&&state().jobs.some(j=>j.id===n.data.job_id&&j.status==='succeeded')&&n.data.completed_job_id!==n.data.job_id);
  if(completed.length){const id=pid;const [project,result]=await Promise.all([api(`/projects/${id}/workflow`),api(`/projects/${id}/canvas`)]);if(!active()||pid!==id||saving||seq!==saved||state().dirty)return;
   if(result.revision!==graph.revision){error='画布已有更新，请重新打开';status();return;}
   setProject(project);for(const n of completed){const fresh=result.nodes.find(x=>x.id===n.id);if(fresh?.data.file)n.data.file=fresh.data.file;const segment=project.segments.find(s=>s.id===n.data.segment_id);if(n.kind==='shot'&&segment&&(n.data.text||'')===(n.data.submitted_text||''))n.data.text=segment.prompt;n.data.completed_job_id=n.data.job_id;}changed();await flush();for(const n of completed.filter(n=>n.kind==='script'&&n.data.episode_id))await importProject(n.data.episode_id);paint(!document.querySelector('#canvas-inspector :focus'));}
  else{document.querySelectorAll('.canvas-node').forEach(card=>{const n=graph.nodes.find(n=>n.id===card.dataset.node);card.querySelector('header small').textContent=jobState(n);});const n=node();if(inspectedJob!==(n?.id||'')+':'+(n?jobState(n):'')&&!document.querySelector('#canvas-inspector :focus'))inspector();}
 }
 return {view,afterRender,open,refresh,create,createProject,flush,poll,beforeAssistant,assistantResult,isDirty:()=>seq!==saved,returnProject:async()=>{await flush();await openProject(pid);}};
}
