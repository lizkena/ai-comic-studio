/* Pure canvas semantics shared by the UI and regression tests. */
(function(root){
 const roles=['text','split','character','location','prop','shot','txt2img','video','audio','compose'];
 function kind(n){return ['character','location','prop','shot','txt2img'].includes(n?.studioKind)?'image':['image',...roles].includes(n?.studioKind)?n.studioKind:n?.type==='smart-prompt'?'text':n?.type==='smart-minimax'?'compose':n?.type==='smart-image'?((n.images||[]).some(m=>m.kind==='video')?'video':(n.images||[]).some(m=>m.kind==='audio')?'audio':'image'):null;}
 function nodeRole(n){if(kind(n)!=='image')return kind(n);if(['character','location','prop','shot','txt2img'].includes(n.studioKind))return n.studioKind;return ['character','location','prop'].includes(n.studioImagePurpose)?n.studioImagePurpose:'shot';}
 function upgrade(n){if(kind(n)==='image'){n.studioKind=nodeRole(n);n.studioImagePurpose=n.studioKind;if(['图片','Image','Upload'].includes(n.title))n.title=n.studioKind==='character'?'角色卡':'镜头卡';}if(n.studioKind==='audio'&&n.title==='音色')n.title='音频';return n;}
 function identitySpec(parent,nodes){
  if(nodeRole(parent)!=='character')throw Error('请从角色卡拆分身份卡');
  const used=new Set(nodes.filter(n=>n.studioIdentityParentId===parent.id).map(n=>n.studioIdentityName));
  let number=1;while(used.has('身份'+number))number++;
  const name='身份'+number;
  return {studioKind:'character',studioImagePurpose:'character',studioIdentityParentId:parent.id,
   studioIdentityRootId:parent.studioIdentityRootId||parent.id,studioIdentityName:name,
   studioCharacter:parent.studioCharacter||'',title:(parent.studioCharacter||parent.title||'角色')+' · '+name,
   studioProvider:parent.studioProvider||'',studioModel:parent.studioModel||'',studioRatio:parent.studioRatio||'16:9',
   studioVoiceNodeId:parent.studioVoiceNodeId||'',...(parent.studioVoice?{studioVoice:JSON.parse(JSON.stringify(parent.studioVoice))}:{}),
   studioPrompt:'',images:[],w:460,h:820};
 }
 function defaultIdentitySpec(parent,nodes){
  const spec=identitySpec(parent,nodes);
  return {...spec,studioIdentityDefault:true,studioIdentityName:'默认身份',
   title:(parent.studioCharacter||parent.title||'角色')+' · 默认身份',
   images:JSON.parse(JSON.stringify((parent.images||[]).filter(m=>(m.kind||'image')==='image')))};
 }
 function identityRequest(node,nodes,edges){
  const parent=nodes.find(n=>n.id===node.studioIdentityParentId);
  if(!parent||nodeRole(parent)!=='character')throw Error('来源角色卡已删除，请重新绑定来源');
  if(!edges.some(e=>e.from===parent.id&&e.to===node.id&&e.kind!=='flow'))throw Error('请连接来源角色卡');
  if(!(parent.images||[]).some(m=>(m.kind||'image')==='image'))throw Error('来源角色卡尚无图片，请先生成或选用角色图片');
  const b=inputs(node,nodes,edges);
  if(!b.prompt.trim())throw Error('请填写本身份的服装或状态变化，或连接描述文本');
  const refs=b.images.map((m,i)=>`图${i+1}：${m.nodeId===parent.id?'角色身份基准，只保留同一人的脸型、五官、体态与年龄。':'服装或状态参考，只参考用户指定的服装、材质、配饰或状态，不替换人物身份。'}`).join('\n');
  return {...b,prompt:`为同一角色制作独立身份造型「${node.studioIdentityName||'未命名身份'}」。\n${refs}\n本身份的变化要求：\n${b.prompt}\n仅改变用户要求的服装、配饰或状态，保持人物身份一致。构图、背景与视图数量按用户要求生成。`};
 }
 function inputs(node,nodes,edges){
  const byId=new Map(nodes.map(n=>[n.id,n])),visited=new Set(),texts=[],images=[],audios=[],videos=[];
  function walk(n){if(!n||visited.has(n.id))return;visited.add(n.id);const k=kind(n);
   if(['text','split'].includes(k)){if(!n.studioDetachedText)for(const e of edges.filter(e=>e.to===n.id))walk(byId.get(e.from));if(n.text?.trim())texts.push(n.text.trim());return;}
   const assetRole=nodeRole(n),asset=['character','location','prop'].includes(assetRole),character=assetRole==='character';
   if(n.studioIdentityParentId && !(n.images||[]).some(m=>(m.kind||'image')==='image'))throw Error('身份卡「'+(n.studioIdentityName||n.title)+'」尚无图片，请先生成或选用该身份图片');
   if(character&&(n.images||[]).length&&!n.studioCharacter?.trim())throw Error('请填写角色参考图的角色名称');
   if(character){
    const voice=n.studioVoiceNodeId?byId.get(n.studioVoiceNodeId):null;
    const samples=voice?(voice.images||[]).filter(m=>m.kind==='audio').slice(0,1):n.studioVoice?[n.studioVoice]:[];
    if(samples.length&&!n.studioCharacter?.trim())throw Error('请填写绑定音色的角色名称');
    for(const m of samples)audios.push({...m,kind:'audio',nodeId:n.id,name:n.studioCharacter||n.title});
   }
   if(k==='image'&&!asset&&!node.studioIdentityParentId){for(const e of edges.filter(e=>e.to===n.id)){const upstream=byId.get(e.from);if(['text','split'].includes(kind(upstream))||['character','location','prop'].includes(nodeRole(upstream)))walk(upstream);}if(n.studioPrompt?.trim())texts.push(n.studioPrompt.trim());}
    for(const m of n.images||[]){const ref={...m,nodeId:n.id,name:n.studioIdentityParentId?((n.studioCharacter||'角色')+' · '+n.studioIdentityName):character||k==='audio'?(n.studioCharacter||n.title||m.name):n.title||m.name,...(asset?{image_purpose:assetRole}:{}),...(character?{role:'character',character_name:n.studioCharacter||n.title,image_purpose:'character'}:{}),...(n.studioIdentityParentId?{identity_id:n.id,identity_name:n.studioIdentityName}:{})};const mk=m.kind||'image';if(mk==='image')images.push(ref);if(mk==='audio')audios.push(ref);if(mk==='video')videos.push(ref);}
  }
  for(const e of edges.filter(e=>e.to===node.id))walk(byId.get(e.from));
  const unique=a=>a.filter((m,i)=>a.findIndex(x=>x.url===m.url&&x.nodeId===m.nodeId)===i);
  const mapped=unique(images).map(m=>({...m,role:m.image_purpose==='character'?'character':['location','prop'].includes(m.image_purpose)?'reference':node.studioRefRoles?.[m.nodeId+':'+m.url]||'reference'}));
  if(!node.studioIdentityParentId){
   const characters=new Map();
   for(const ref of mapped.filter(m=>m.role==='character')){
    const previous=characters.get(ref.character_name);
    if(previous&&previous.nodeId!==ref.nodeId&&(previous.identity_id||ref.identity_id))throw Error('同一角色连接了多套身份造型，请只保留本镜头要用的一张身份卡');
    characters.set(ref.character_name,ref);
   }
  }
  if(mapped.filter(m=>m.role==='first_frame').length>1)throw Error('只能选择一张首帧图片');
  if(mapped.filter(m=>m.role==='last_frame').length>1)throw Error('只能选择一张尾帧图片');
  return {prompt:kind(node)==='video'&&node.studioVideoPrepared?String(node.studioVideoPrompt||''):[...new Set(texts),node.studioPrompt?.trim()].filter(Boolean).join('\n\n'),images:mapped,audios:unique(audios),videos:unique(videos)};
 }
 function videoReferences(b){return [...b.images,...b.audios,...b.videos].map((m,i)=>{const category=m.kind==='audio'?'audio':m.kind==='video'?'video':m.role==='character'?'character':['location','prop'].includes(m.image_purpose)?m.image_purpose:'shot';const label={character:'人物',location:'场景',prop:'道具',shot:'镜头图',audio:'音色',video:'视频'}[category];return {...m,category,refId:'R'+(i+1),token:`【${label}:${m.name||'素材'}·R${i+1}】`};});}
 function videoState(n,nodes,edges){const source=inputs({...n,studioVideoPrepared:false},nodes,edges);const refs=videoReferences(source);const signature=JSON.stringify({prompt:source.prompt,refs:refs.map(m=>[m.nodeId,m.url,m.name,m.category,m.role]),duration:n.studioDuration||8,ratio:n.studioRatio||'16:9',provider:n.studioProvider||'',model:n.studioModel||'',resolution:n.studioResolution||'720p',generate_audio:n.studioGenerateAudio!==false,watermark:!!n.studioWatermark});const ready=!!n.studioVideoPrepared&&n.studioVideoSource===signature;return {source,refs,signature,ready,label:ready?(n.studioJobId?'重新生成视频':'生成视频'):(n.studioVideoPrepared?'重新整理提示词':'整理提示词')};}
 function validateVideoPrompt(text,refs){if(typeof text!=='string'||!text.trim())throw Error('完整视频提示词不能为空');for(const token of text.match(/【[^\n【】]*·R\d+】/g)||[])if(!refs.some(r=>r.token===token))throw Error('提示词引用与连接素材不一致，请重新整理提示词');return text.trim();}
 function validatePlan(plan,nodes,edges,request){
  if(!plan||!Array.isArray(plan.operations)||plan.operations.length>30)throw Error('助手返回的画布操作格式无效');
  if(plan.reply!==undefined&&(typeof plan.reply!=='string'||plan.reply.length>4000))throw Error('助手说明格式无效');
  const ids=new Set(nodes.map(n=>n.id)),kinds=new Map(nodes.map(n=>[n.id,kind(n)])),nodeRoles=new Map(nodes.map(n=>[n.id,n.studioKind])),graph=edges.map(e=>({...e})),out=[];
  const generates=/生成|制作|导出|合成|重做|render|generate/i.test(request);
  for(const raw of plan.operations){
   let op=raw;
   const actions=['create','update','connect','generate'];
   if(raw&&typeof raw==='object'&&!Array.isArray(raw)){
    const wrapped=actions.filter(key=>Object.prototype.hasOwnProperty.call(raw,key));
    if(wrapped.length){
     if(wrapped.length!==1||Object.keys(raw).length!==1)throw Error('助手操作不能混用多种格式');
     const action=wrapped[0],fields=raw[action];
     if(!fields||typeof fields!=='object'||Array.isArray(fields)||fields.action!==undefined)throw Error('助手操作字段格式无效');
     op={...fields,action};
     // Older agent replies redundantly marked every new media node as a shot.
     // Explicit card types determine their purpose; updates remain strict.
     if(action==='create'&&op.image_purpose==='shot'&&['location','prop'].includes(op.kind))op.image_purpose=op.kind;
     if(action==='create'&&op.image_purpose==='shot'&&['video','audio','compose'].includes(op.kind))delete op.image_purpose;
    }
   }
   if(!op||!['create','update','connect','generate'].includes(op.action))throw Error('助手包含不支持的操作');
   if(op.action==='create'){if(![...roles,'image'].includes(op.kind)||typeof op.id!=='string'||!/^agent_[a-zA-Z0-9_-]{1,60}$/.test(op.id)||ids.has(op.id))throw Error('助手创建节点的标识或类型无效');if(ids.size>=1000)throw Error('画布节点已达到上限');ids.add(op.id);kinds.set(op.id,kind({studioKind:op.kind}));}
   else if(op.action==='connect'){
    if(!ids.has(op.from)||!ids.has(op.to)||op.from===op.to)throw Error('助手连线引用无效');
    const visit=(id,seen=new Set())=>{if(id===op.from)return true;if(seen.has(id))return false;seen.add(id);return graph.filter(e=>e.from===id).some(e=>visit(e.to,seen));};
    if(visit(op.to))throw Error('助手连线会形成循环');if(graph.some(e=>e.from===op.from&&e.to===op.to))continue;graph.push({from:op.from,to:op.to,kind:'input'});
   }else if(!ids.has(op.id))throw Error('助手目标节点不存在');
   if(op.action==='generate'){const k=kinds.get(op.id);if(!['text','split','image','video','compose'].includes(k))throw Error('该节点不支持生成');if(!generates&&!(['text','split'].includes(k)&&/拆|优化|改写|润色/.test(request)))throw Error('未明确要求生成，助手不能启动生成任务');}
   for(const key of ['text','title','prompt','character'])if(op[key]!==undefined&&(typeof op[key]!=='string'||op[key].length>100000))throw Error('助手字段内容无效');
   if(op.duration!==undefined&&(!Number.isFinite(op.duration)||op.duration<1||op.duration>120))throw Error('助手时长参数无效');
   if(op.ratio!==undefined&&!['16:9','9:16','1:1','4:3','3:4'].includes(op.ratio))throw Error('助手比例参数无效');
   if(op.image_purpose!==undefined&&(!['shot','character','location','prop'].includes(op.image_purpose)||kinds.get(op.id)!=='image'))throw Error('助手图片用途无效');
   if(op.action==='create')nodeRoles.set(op.id,op.kind);
   if(op.image_purpose!==undefined&&['character','location','prop','shot'].includes(nodeRoles.get(op.id))&&op.image_purpose!==nodeRoles.get(op.id))throw Error('角色卡和镜头卡是独立节点，不能切换用途');
   out.push(op);
  }return out;
 }
 const api={kind,nodeRole,upgrade,identitySpec,defaultIdentitySpec,identityRequest,inputs,videoReferences,videoState,validateVideoPrompt,validatePlan,roles};root.StudioNodeModel=api;
 if(typeof module!=='undefined')module.exports=api;
})(globalThis);
