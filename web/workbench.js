import {assistantIcon as agentIcon} from './assistant-icons.js?v=20261008-all-icons';
import {usableSkills,skillOptions} from './skill-selection.js?v=20261007-merged3';
import {createWorkflowUI} from './workflow-ui.js?v=20261016-manual-assets';
const AREAS = [
  ['script','剧本创作','book'],['assets','资产准备','folder'],['storyboard','分镜设计','play'],
  ['images','图片制作','image'],['video','视频制作','film'],['assembly','成片导出','download']
];
const GROUP = {direction:'script',characters:'script',world:'script',novel:'script',scene_plan:'script',script:'script',assets:'assets',performance:'storyboard',storyboard:'storyboard',video:'video',assembly:'assembly'};
const LABELS = {title:'标题',prompt:'画面描述',duration:'时长',size:'景别',camera:'运镜',action:'动作',dialogue:'对白',sound:'声音',text:'台词',description:'描述',content:'正文',summary:'摘要',logline:'一句话故事',conflict:'冲突',synopsis:'梗概'};

export function createProductionWorkbench(ctx) {
  const {state,project:p,esc:e,icon,field,api,save,set,render,navigate,toast,dialog,closeDialog,generate,views,assetBindings} = ctx;
  const s = () => state();
  let opened = localStorage.getItem('comic-assistant-open') === 'true';
  let inspectorTab='info', shotIndex=0, messages=[], busy=false, input='', error='', assetTarget=null,previewFit='cover';
  let loadedProject=null, loadSequence=0, memoryDraft=null, projectMemory=null, activeTopic='main';
  const buttonTimers=new Map();
  const flow = createWorkflowUI(ctx);
  const area = flow.area;
  const episodes = flow.episodes, episode = flow.episode, segments = flow.segments, current = flow.current;
  const number = x => String(segments().indexOf(x)+1).padStart(2,'0');
  const media = file => '/media/'+String(file).split('/').map(encodeURIComponent).join('/');
  const refs = segment => p().assets.filter(a=>(segment?.character_ids||[]).includes(a.id)||(segment?.prop_ids||[]).includes(a.id)||a.id===segment?.location_id);
  function picture(segment) {
    if(!segment)return null;
    const img=(segment.images||[]).find(x=>x.id===segment.current_image);
    if(img)return {file:img.file,label:'镜头参考图'};
    const v=segment.versions?.find(v=>v.id===segment.current_version);
    if(v?.tail)return {file:v.tail,label:'选用视频尾帧'};
    const location=refs(segment).find(a=>a.kind==='location'&&a.references?.length);
    const a=location||refs(segment).find(a=>a.references?.length);
    return a?{file:a.references.at(-1).file,label:location?'场景参考图':'资产参考图'}:null;
  }
  function imageHTML(segment,cls='') {
    const pic=picture(segment);
    return pic?`<img class="${cls}" src="${e(media(pic.file))}" alt="${e(segment.title)} · ${e(pic.label)}">`:`<span class="wb-media-missing">${icon('image')}<span>待补参考图</span></span>`;
  }
  function scope(){return s().page==='canvas'?(s().canvasScope||{stage:'storyboard',workspace:'storyboard'}):flow.assistantScope();}
  function scopeTitle(sc=scope()) {
    if(sc.canvas_node_title)return '画布 · '+sc.canvas_node_title;
    if(sc.target_ids?.length>1){const names=sc.target_ids.map(id=>[...p().assets,...p().segments].find(x=>x.id===id)).filter(Boolean).map(x=>x.name||x.title);return `已选 ${sc.target_ids.length} 个对象 · ${names.slice(0,2).join('、')}${names.length>2?'等':''}`;}
    const seg=p().segments.find(x=>x.id===sc.target_id);
    if(seg){const list=p().segments.filter(x=>x.episode_id===seg.episode_id);return `第${Math.max(1,episodes().findIndex(x=>x.id===seg.episode_id)+1)}集 · 镜头${String(list.indexOf(seg)+1).padStart(2,'0')}`;}
    const asset=p().assets.find(x=>x.id===sc.target_id);
    if(asset)return asset.name;
    const chapter=p().outputs.novel?.chapters.find(x=>x.id===sc.target_id);
    return chapter?.title||episode()?.title||'故事设定';
  }
  async function load(){
    flow.load();
    if(loadedProject===p().id)return;
    const id=p().id,seq=++loadSequence; messages=[]; input='';error=''; assetTarget=null;shotIndex=0;
    activeTopic=localStorage.getItem('comic-assistant-topic-'+id)||'main';
    const [result,memory]=await Promise.all([api(`/projects/${id}/assistant`),api(`/projects/${id}/assistant-memory`)]);
    if(seq===loadSequence&&p()?.id===id)projectMemory=memory;
    if(seq===loadSequence&&p()?.id===id){messages=result;loadedProject=id;}
  }
  function sidebar(){return flow.sidebar();}
  function header(){return flow.header();}
  function episodeRail(){return `<aside class="wb-episodes"><div class="wb-rail-head"><strong>分集列表</strong><button class="small ghost" data-wb="add-episode" aria-label="添加分集">${icon('plus')}</button></div>${episodes().map((ep,i)=>{const seg=p().segments.find(x=>x.episode_id===ep.id);return `<button class="wb-episode ${i===s().episode?'selected':''}" data-wb-episode="${i}"><div class="wb-episode-cover">${imageHTML(seg)}</div><div><small>第${i+1}集</small><strong>${e(ep.title.replace(/^第\s*\d+集\s*[·：:]?\s*/,''))}</strong><small>${p().segments.filter(x=>x.episode_id===ep.id).length}个镜头</small></div></button>`;}).join('')||'<p class="help wb-no-episodes">先编辑分集剧本，也可手动添加分集。</p>'}<button class="ghost small full" data-wb-area="script">${icon('edit')}编辑分集剧本</button></aside>`;}
  function shotStrip(){return `<section class="wb-strip"><div class="row between"><h3>镜头列表 <small>本集${segments().length}镜 · ${segments().reduce((n,x)=>n+Number(x.duration),0)}秒</small></h3><button class="small ghost" data-wb="add-segment">${icon('plus')}镜头</button></div><div class="wb-thumbnails">${segments().map(x=>`<button class="wb-shot ${current()?.id===x.id?'selected':''}" data-wb-segment="${e(x.id)}"><div class="wb-shot-image">${imageHTML(x)}</div><div><strong>${number(x)}</strong><small>${x.duration}秒</small></div><p>${e(x.title.replace(/^\d+\s*[·.:：]?\s*/,''))}</p></button>`).join('')}</div></section>`;}
  function inspector(segment){
    const i=p().segments.indexOf(segment);shotIndex=Math.min(shotIndex,Math.max(0,segment.shots.length-1));
    const prefix=`segments.${i}.shots.${shotIndex}`;
    return `<section class="wb-shot-inspector"><div class="wb-tabs"><button class="${inspectorTab==='info'?'active':''}" data-wb-tab="info">镜头信息</button><button class="${inspectorTab==='assets'?'active':''}" data-wb-tab="assets">出镜资产</button></div>${inspectorTab==='assets'?`<div class="wb-reference-list">${refs(segment).map(a=>`<button data-asset="${e(a.id)}">${a.references?.length?`<img src="${e(media(a.references.at(-1).file))}" alt="${e(a.name)}">`:icon(a.kind==='character'?'user':'folder')}<span>${e(a.name)}</span><small>${a.references?.length?'已有参考':'待补参考'}</small></button>`).join('')||'<p class="help">还没有关联资产</p>'}</div><details class="wb-advanced"><summary>编辑资产关联</summary>${assetBindings(segment,i)}</details>`:`${field('时长 / 秒',`segments.${i}.duration`,'number')}<label for="wb-inner-shot">内部镜号</label><select id="wb-inner-shot">${segment.shots.map((x,j)=>`<option value="${j}" ${j===shotIndex?'selected':''}>镜号${j+1} · ${x.start}–${x.end}秒${x.dialogue?' · 有对白':''}</option>`).join('')}</select>${field('景别',prefix+'.size')}${field('运镜',prefix+'.camera')}${field('画面描述',prefix+'.action','textarea')}${field('对白',prefix+'.dialogue','textarea')}${field('声音',prefix+'.sound')}<details class="wb-advanced"><summary>提示词、时序与衔接</summary>${field('制作提示词',`segments.${i}.prompt`,'textarea')}${field('开始 / 秒',prefix+'.start','number')}${field('结束 / 秒',prefix+'.end','number')}${field('上一片段',`segments.${i}.previous_id`,'select','',{options:[['','不衔接'],...p().segments.filter(x=>x.id!==segment.id).map(x=>[x.id,x.title])]})}<label class="check"><input type="checkbox" data-bind="segments.${i}.continuity" ${segment.continuity?'checked':''}>衔接前段尾帧</label><button class="small full" data-action="check-storyboard">${icon('check')}校验分镜</button><button class="ghost small full" data-action="edit-json" data-json="storyboard">高级结构编辑</button></details>`}</section>`;
  }
  function storyboard(){
    const segment=current();
    if(!segment)return `<div class="wb-empty-stage"><h1>分镜设计</h1><p>先准备当前集的剧本，再拆成镜头。已有分镜也可以手动导入。</p><div class="row"><button data-action="refine" class="primary">${icon('spark')}生成分镜建议稿</button><button data-wb="add-segment">${icon('plus')}手动添加镜头</button><button data-action="edit-json" data-json="storyboard">导入分镜结构</button></div></div>`;
    const i=p().segments.indexOf(segment),pic=picture(segment);
    return `<div class="wb-stage-title"><h1>分镜设计 · 镜头${number(segment)}</h1><div class="row"><button class="small" data-wb="duplicate">${icon('plus')}复制镜头</button><button id="save-project" class="primary small" data-action="save">${icon('save')}保存分镜</button>${!opened?`<button class="small" data-wb="assistant-toggle">${icon('spark')}创作助手</button>`:''}</div></div><div class="wb-title-field"><label for="wb-segment-name">镜头名称</label><input id="wb-segment-name" data-bind="segments.${i}.title" value="${e(segment.title)}"></div><div class="wb-editor-grid"><div class="wb-preview"><span class="wb-preview-label">${e(pic?.label||'镜头参考')}</span>${pic?imageHTML(segment)+`<button class="wb-preview-fit small" data-wb="preview-fit">适应 / 填充</button>`:`<div class="wb-preview-empty">${icon('image')}<h3>为这个镜头补充参考画面</h3><p>可上传已有图片，或到图片制作工作区生成。</p><label class="wb-upload-button">${icon('plus')}上传镜头图片<input type="file" data-wb-upload="${e(segment.id)}" accept="image/png,image/jpeg,image/webp"></label></div>`}</div>${inspector(segment)}</div>${shotStrip()}<div class="wb-stage-footer"><button class="primary" data-wb-area="images">${icon('image')}前往图片制作 ${icon('arrow')}</button><button class="ghost small" data-wb-tab="assets">查看本镜资产</button></div>`;
  }
  function modelControls(kind){return `<details class="wb-model-controls"><summary>制作参数 · ${e(p().model_bindings?.[kind]||'尚未选择模型')}</summary>${ctx.providerSelect(kind)}${kind==='text'?`<div class="field"><label>当前任务模板</label><select data-bind="bindings.skill_${s().stage}">${skillOptions(s().skills,s().stage,p().bindings['skill_'+s().stage],e)}</select></div>`:''}<button class="ghost small" data-page="settings" data-settings-section="api">${icon('settings')}模型 API 设置</button></details>`;}
  function images(){const segment=current();return `<div class="wb-stage-title"><div><h1>图片制作</h1><p class="help">素材设定图与镜头图片分别保留版本，由你选择采用。</p></div>${!opened?`<button data-wb="assistant-toggle">${icon('spark')}创作助手</button>`:''}</div>${modelControls('image')}<div class="wb-image-sections"><section><div class="panelhead"><h3>当前镜头图片 ${segment?'· '+number(segment):''}</h3>${segment?`<div class="row"><label class="wb-upload-button small">${icon('plus')}上传<input type="file" data-wb-upload="${e(segment.id)}" accept="image/png,image/jpeg,image/webp"></label><button class="primary small" data-wb="image-generate">${icon('spark')}生成当前镜头图片</button></div>`:''}</div>${segment?`<p class="help mb">${e(segment.prompt)}</p><div class="wb-image-versions">${(segment.images||[]).map(x=>`<article><img src="${e(media(x.file))}" alt="${e(segment.title)}图片版本"><div class="row between"><small>${e(x.created_at||'')} · ${x.source==='upload'?'上传素材':'生成结果'}</small><button class="small ${segment.current_image===x.id?'selected':''}" data-wb-image="${e(x.id)}">${segment.current_image===x.id?'当前采用':'采用此图'}</button></div></article>`).join('')||'<div class="wb-empty-media">暂无镜头图片，可生成或上传已有图片。</div>'}</div>${shotStrip()}`:'<p class="help">先到分镜设计添加镜头。</p>'}</section><section><h3 class="mb">资产设定图</h3>${views.assets()}${ctx.libraryMaterials()}</section><section><h3>图片任务</h3>${imageJobs()}</section></div>`;}
  function imageJobs(){const jobs=s().jobs.filter(x=>x.project_id===p().id&&x.kind==='image');return jobs.map(j=>`<article class="wb-image-job"><div class="row between"><strong>${e(p().segments.find(x=>x.id===j.target_id)?.title||p().assets.find(x=>x.id===j.target_id)?.name||'图片任务')}</strong>${ctx.badge(j.status)}</div><p>${e(j.error||j.logs?.at(-1)?.message||'已进入任务队列')}</p><button class="small ghost" data-page="queue">查看任务详情</button></article>`).join('')||'<p class="help">提交后会显示真实任务进度。</p>';}
  function generic(){
    const group=area(),stage=s().stage;
    const tabs=group==='script'?[['direction','故事设定'],['characters','人物档案'],['world','世界规则'],['script','分集剧本'],['novel',p().entry==='novel'?'导入小说':'可选小说']]:group==='storyboard'?[['storyboard','分镜设计'],['performance','表演设计']]:[];
    return `<div class="wb-stage-title"><h1>${AREAS.find(x=>x[0]===group)?.[1]||'制作工作区'}</h1><div class="row"><button id="save-project" data-action="save" class="primary small">${icon('save')}保存</button>${!opened?`<button class="small" data-wb="assistant-toggle">${icon('spark')}创作助手</button>`:''}</div></div>${tabs.length?`<nav class="wb-subtabs">${tabs.map(([id,title])=>`<button data-stage="${id}" class="${stage===id?'active':''}">${title}</button>`).join('')}</nav>`:''}${modelControls(['video','assembly'].includes(stage)?'video':stage==='assets'?'image':'text')}${['direction','characters','world','novel','script','performance'].includes(stage)?`<div class="wb-stage-actions"><button data-action="refine">${icon('spark')}生成本阶段建议稿</button><button class="ghost small" data-action="history">${icon('clock')}历史版本</button><button class="ghost small" data-action="project-settings">${icon('settings')}项目设定</button></div>`:''}${stage==='video'&&current()?field('视频输入方式',`segments.${p().segments.indexOf(current())}.input_mode`,'select','镜头图片模式使用选用图；资产参考模式使用角色、场景与道具。服务能力与参考数量仍会校验。',{options:[['','角色 / 场景资产参考'],['shot_image','当前镜头图片参考']]}):''}${stage==='assets'?views.assets().replace('data-action="batch-image"','data-wb-area="images"').replace('批量出图','前往图片制作'):views[stage]?.()||''}${stage==='assets'?ctx.libraryMaterials():''}`;
  }
  const visibleMessages=()=>messages.filter(m=>(m.topic_id||'main')===activeTopic);
  window.addEventListener('studio-agent-action',async event=>{
    const detail=event.detail;
    if(detail.phase==='end'){clearInterval(buttonTimers.get(detail.requestId));buttonTimers.delete(detail.requestId);return;}
    if(p()?.id!==detail.projectId)return;
    if(detail.phase==='start'){
      activeTopic=localStorage.getItem('comic-assistant-topic-'+p().id)||'main';
      const id=p().id;
      const timer=setInterval(async()=>{try{const updated=await api(`/projects/${id}/assistant`);if(p()?.id===id){messages=updated;const panel=document.querySelector('.wb-assistant-scroll');if(panel)panel.innerHTML=visibleMessages().map(messageHTML).join('');}}catch{}},2500);
      buttonTimers.set(detail.requestId,timer);render();
    }else if(detail.phase==='result'&&detail.message){messages=messages.filter(m=>m.id!==detail.message.id);messages.push(detail.message);render();}
  });
  const avatar=()=>`<span class="wb-agent-avatar" aria-hidden="true"><img src="/assets/assistant/robot-3d.png?v=20261008-icons" alt="" width="80" height="80"></span>`;
  function sameScope(m){return JSON.stringify(m.scope)===JSON.stringify(scope());}
  function toolHTML(m){return m.tool_trace?.length?`<details class="wb-agent-tools" ${m.status==='running'?'open':''}><summary>执行过程 · ${m.tool_trace.length}项工具</summary>${m.tool_trace.map(t=>{const labels={read_project:'读取项目',read_object:'读取内容',read_skill:'读取技能',search_skills:'搜索技能',inspect:'检查项目',list_jobs:'查询任务',wait_job:'等待任务',remember:'保存记忆',execute_text_action:'执行文本任务',start_task:'提交制作',retry_job:'重试任务',cancel_job:'停止任务'};const job=t.result?.id&&s().jobs.find(j=>j.id===t.result.id);return `<div class="wb-agent-tool"><strong>${e(labels[t.name]||t.name)}</strong><span>${e(t.status==='running'?'进行中':t.status==='failed'?'未执行成功':'已执行')}</span>${t.error?`<p>${e(t.error)}</p>`:''}${t.result?.id&&t.result?.status?`<p>任务 ${e(t.result.id)} · ${e(job?.status||t.result.status)}</p>`:''}</div>`;}).join('')}</details>`:'';}
  function messageHTML(m){return `<article class="wb-conversation" data-assistant-message="${e(m.id)}"><div class="wb-user-message">${e(m.request)}</div><div class="wb-agent-response">${avatar()}<div class="wb-assistant-reply"><div class="wb-reply-heading">${e(({failed:"处理未完成",cancelled:"已停止处理",interrupted:"处理已中断",running:"正在处理",pending:"已准备建议稿"})[m.status]||"创作助手")}</div><p>${e(m.reply).replaceAll('\n','<br>')}</p>${toolHTML(m)}${m.changes?.length?`<section class="wb-draft"><h3>${icon('spark')}建议稿 <small>${m.changes.length}处修改</small></h3>${m.changes.map(c=>`<div class="wb-diff"><label>${e(LABELS[c.path.split('.').at(-1)]||'内容')}</label><div><small>原内容</small><p>${e(c.before)}</p></div><div class="wb-diff-after"><small>建议内容</small><p>${e(c.value)}</p></div></div>`).join('')}<div class="wb-draft-scope"><strong>当前修改：${e(scopeTitle(m.scope))}</strong>只包含上方列出的${m.changes.length}处修改，其他内容保持原样。</div>${m.status==='pending'?`<div class="row"><button class="primary" data-wb-apply="${e(m.id)}">${icon('check')}采用修改</button><button data-wb-discard="${e(m.id)}">${icon('close')}放弃</button></div>`:`<div class="wb-draft-status">${m.status==='applied'?'已采用 · 原内容保存在历史版本':'已放弃 · 保留原内容'}</div>`}</section>`:''}</div></div></article>`;}
  function assistant(){const selected=visibleMessages();const memories=projectMemory?.entries||[];return `<aside class="wb-assistant" aria-label="创作智能体"><div class="wb-assistant-head"><div class="wb-agent-brand">${avatar()}<div><h2>创作智能体</h2><small>${e(p().title||p().name||'当前项目')} · 当前项目</small></div></div><div class="wb-agent-header-actions"><button class="ghost small" data-wb="agent-history">${agentIcon('history')}对话记录</button><button class="ghost small" data-wb="agent-new-topic" ${busy?'disabled':''}>${agentIcon('message-square-plus')}新话题</button><button class="ghost small" data-wb="assistant-toggle" aria-label="收起创作智能体">${agentIcon('x')}</button></div></div><button class="wb-agent-memory" data-wb="agent-memory">${agentIcon('brain-circuit')}<strong>项目记忆 <span>${memories.length}条</span></strong><small>${e(memories.map(x=>x.key).join(' · ')||'保存你的创作要求')}</small>${agentIcon('chevron-right')}</button><div class="wb-agent-context"><span>当前范围：${e(scopeTitle())}</span><button class="ghost small" data-wb="scope">更换范围</button></div><div class="wb-assistant-scroll">${selected.length?selected.map(messageHTML).join(''):`<div class="wb-assistant-intro">${avatar()}<h3>一起完成你的创作</h3><p>从当前内容开始检查，或告诉我下一步要做什么。</p><div class="wb-agent-welcome-note">我可以按需读取技能、记住项目要求，并执行你明确提出的制作任务。</div></div>`}${busy?'<p class="wb-assistant-loading" role="status">正在读取信息或执行工具…</p>':''}${error?`<div class="notice error" role="alert">${e(error)}</div>`:''}</div><div class="wb-assistant-shortcuts"><button class="small ghost" data-wb="check-current" ${busy?'disabled':''}>${agentIcon('clipboard-check')}检查当前内容</button><button class="small ghost" data-wb="agent-prompt" ${busy?'disabled':''}>${agentIcon('sparkles')}填写提示词请求</button><button class="small ghost" data-action="project-tasks">${agentIcon('list-checks')}查看任务</button></div><form id="wb-assistant-form"><label class="sr-only" for="wb-assistant-input">描述需要的帮助</label><textarea id="wb-assistant-input" placeholder="描述任务，或告诉我需要记住的要求…" ${busy?'disabled':''}>${e(input)}</textarea><div class="row between"><div class="wb-agent-composer-tools"><button type="button" class="ghost small" data-wb="assistant-model" aria-label="选择助手模型">${e(p().model_bindings?.text||'项目文字模型')}${agentIcon('chevron-down')}</button><button type="button" class="ghost small" data-wb="assistant-model">${agentIcon('library-big')}技能设置</button></div>${busy?'<button type="button" class="small ghost" data-wb="agent-stop">停止处理</button>':`<button class="wb-agent-send primary" type="submit" aria-label="发送消息">${agentIcon('send')}</button>`}</div></form></aside>`;}

  function view(){return flow.view(opened?assistant():'');}
  async function selectArea(next){return flow.selectArea(next);}
  function dirty(){const el=document.querySelector('#wb-save-state');if(el){el.classList.add('dirty');el.innerHTML=icon('edit')+'有未保存修改';}}
  async function send(mode='chat',message=input){
    if(busy)return;
    if(!message.trim())throw Error('先描述你需要的帮助');
    if(s().page==='canvas')await ctx.beforeCanvasAssistant();
    await save();busy=true;error='';const id=p().id,sc=scope(),requestId=crypto.randomUUID();render();
    const progressTimer=setInterval(async()=>{try{const updated=await api(`/projects/${id}/assistant`);if(busy&&p()?.id===id){messages=updated;const panel=document.querySelector('.wb-assistant-scroll');if(panel)panel.innerHTML=visibleMessages().map(messageHTML).join('')+'<p role="status">正在处理…</p>';}}catch{}},2500);
    try{const result=await api(`/projects/${id}/assistant`,'POST',{message,scope:sc,mode,auto_apply:sc.workspace==='storyboard',request_id:requestId,topic_id:activeTopic});if(p()?.id===id){messages=messages.filter(m=>m.id!==result.id);messages.push(result);input='';projectMemory=await api(`/projects/${id}/assistant-memory`);if(result.status==='applied'&&!s().dirty){const updated=await api(`/projects/${id}/workflow`);if(p()?.id===id&&!s().dirty){s().project=updated;s().projects=s().projects.map(x=>x.id===id?updated:x);}}if(s().page==='canvas')await ctx.onCanvasAssistantResult(result);}}
    catch(err){if(p()?.id===id)error=err.message;}
    finally{clearInterval(progressTimer);busy=false;render();document.querySelector('.wb-assistant-scroll')?.scrollTo(0,999999);}
  }
  async function applyDraft(id){await save();const updated=await api(`/projects/${p().id}/assistant/${id}/apply`,'POST',{revision:p().revision});s().project=updated;s().dirty=false;s().projects=s().projects.map(x=>x.id===updated.id?updated:x);messages=await api(`/projects/${p().id}/assistant`);render();toast('已采用当前范围的修改，原版本保留');}
  async function command(name){
    const segment=current();
    if(name==='assistant-toggle'){opened=!opened;localStorage.setItem('comic-assistant-open',String(opened));render();}
    else if(name==='agent-new-topic'){if(busy)return;activeTopic=crypto.randomUUID();localStorage.setItem('comic-assistant-topic-'+p().id,activeTopic);input='';error='';render();document.querySelector('#wb-assistant-input')?.focus();}
    else if(name==='agent-history'){const topics=[...new Set(messages.map(m=>m.topic_id||'main'))];dialog('对话记录',`<div class="wb-agent-history">${topics.reverse().map(id=>{const list=messages.filter(m=>(m.topic_id||'main')===id);return `<button class="ghost full" data-wb="agent-topic:${e(id)}"><strong>${e(list[0]?.request||'新话题')}</strong><small>${e(list.at(-1)?.created_at||'')} · ${list.length}轮对话</small></button>`;}).join('')||'<p class="help">还没有对话记录。</p>'}</div>`,'<button data-action="close-dialog">关闭</button>');}
    else if(name.startsWith('agent-topic:')){if(busy)throw Error('请等待当前对话完成');activeTopic=name.slice(12);localStorage.setItem('comic-assistant-topic-'+p().id,activeTopic);closeDialog();render();}
    else if(name==='agent-prompt'){const sc=scope();input=sc.target_ids?.length>1?'为当前所选对象生成生图提示词。':sc.stage==='assets'?(sc.target_id?'为当前资产生成生图提示词。':'为本集出场人物生成生图提示词。'):'为当前镜头生成生图提示词。';render();document.querySelector('#wb-assistant-input')?.focus();}
    else if(name==='agent-stop'){await api(`/projects/${p().id}/assistant/stop`,'POST',{});toast('已停止助手，已提交任务保留在任务面板');}
    else if(name==='agent-memory'){
      memoryDraft=await api(`/projects/${p().id}/assistant-memory`);memoryDraft.project_id=p().id;
      dialog('项目长期记忆',`<p class="help">跨工作区和重启后保留，生成任务会读取这些规则。当前明确要求优先。</p><div id="agent-memory-entries">${memoryDraft.entries.map(x=>`<section class="wb-memory-row"><label>${e(x.key)}</label><textarea data-memory-key="${e(x.key)}" maxlength="500">${e(x.text)}</textarea><button class="small ghost" data-memory-delete>删除这条</button></section>`).join('')||'<p class="help">还没有保存记忆。可以在对话中说“记住：……”。</p>'}</div><label for="agent-memory-key">新增记忆名称</label><input id="agent-memory-key" maxlength="60"><label for="agent-memory-text">内容</label><textarea id="agent-memory-text" maxlength="500"></textarea>`,'<button data-action="close-dialog">取消</button><button class="primary" data-wb="memory-save">保存记忆</button>');
    } else if(name==='memory-save'){
      const entries=[...document.querySelectorAll('[data-memory-key]')].map(el=>({key:el.dataset.memoryKey,text:el.value}));
      const key=document.querySelector('#agent-memory-key').value.trim(),text=document.querySelector('#agent-memory-text').value.trim();
      if(key||text)entries.push({key,text});
      if(memoryDraft.project_id!==p().id)throw Error('项目已切换，请重新打开记忆');
      memoryDraft=await api(`/projects/${p().id}/assistant-memory`,'PUT',{revision:memoryDraft.revision,entries});projectMemory=memoryDraft;closeDialog();render();toast('项目记忆已保存');
    }
    else if(name==='assistant-model'){
      const stage=['production_setup','source'].includes(scope().stage)?'direction':scope().stage==='assets'?'characters':scope().stage==='video'?'storyboard':scope().stage;
      dialog('创作助手 · 模型与模板',`<div id="wb-assistant-model-dialog"><label>文字渠道与模型</label>${ctx.providerSelect('text')}<label class="mt">当前任务模板</label><select data-bind="bindings.skill_${e(stage)}">${skillOptions(s().skills,stage,p().bindings['skill_'+stage],e)}</select><p class="help mt">沿用模型 API 设置中的渠道、密钥与多模型列表。</p><button class="ghost small mt" data-page="settings" data-settings-section="api">模型 API 设置</button></div>`,'<button class="primary" data-wb="model-save">保存选择</button>');
    }else if(name==='model-save'){await save();closeDialog();render();}
    else if(name==='preview-fit'){previewFit=previewFit==='cover'?'contain':'cover';document.querySelector('.wb-preview>img').style.objectFit=previewFit;}
    else if(name==='duplicate'){
      await save();if(!segment)return;
      const next=structuredClone(segment);next.id='segment_'+crypto.randomUUID().replaceAll('-','').slice(0,12);next.title=segment.title+'（副本）';next.versions=[];next.current_version=null;next.images=[];next.current_image=null;next.status='draft';
      p().segments.splice(p().segments.indexOf(segment)+1,0,next);s().selected=next.id;s().dirty=true;await save();render();
    } else if(name==='add-segment'){
      if(!episode())throw Error('请先添加分集或整理分集剧本');
      const next={id:'segment_'+crypto.randomUUID().replaceAll('-','').slice(0,12),title:'新镜头',episode_id:episode().id,scene_id:episode().scenes?.[0]?.id||'',duration:8,character_ids:[],variant_ids:[],location_id:'',prop_ids:[],previous_id:null,continuity:false,tail_shot:true,seed:42,prompt:'',shots:[{start:0,end:7,size:'中景',camera:'固定',action:'',dialogue:'',sound:''},{start:7,end:8,size:'中全景',camera:'固定',action:'关系镜：完整人物站位与朝向',dialogue:'',sound:''}],status:'draft',versions:[],current_version:null};
      p().segments.push(next);s().selected=next.id;shotIndex=0;s().dirty=true;await save();render();
    } else if(name==='add-episode'){
      dialog('添加分集','<label for="wb-new-episode-title">分集名称</label><input id="wb-new-episode-title" placeholder="例如：第2集 · 雾中的访客">','<button data-action="close-dialog">取消</button><button class="primary" data-wb="create-episode">添加分集</button>');
    } else if(name==='create-episode'){
      const title=document.querySelector('#wb-new-episode-title').value.trim();if(!title)throw Error('请填写分集名称');await save();p().outputs.script=p().outputs.script||{episodes:[]};p().outputs.script.episodes.push({id:'episode_'+crypto.randomUUID().replaceAll('-','').slice(0,12),title,scenes:[]});s().episode=p().outputs.script.episodes.length-1;s().dirty=true;await save();closeDialog();render();
    } else if(name==='image-generate'){
      if(!segment)throw Error('先选择镜头');await generate('image',{stage:'storyboard',target_id:segment.id});render();
    } else if(name==='scope'){
      const targets=s().stage==='novel'?(p().outputs.novel?.chapters||[]).map(x=>[x.id,x.title]):s().stage==='characters'?(p().outputs.characters?.characters||[]).map(x=>[x.id,x.name]):['script','scene_plan'].includes(s().stage)?episodes().map(x=>[x.id,x.title]):area()==='assets'?p().assets.map(x=>[x.id,x.name]):[...segments().map(x=>[x.id,`镜头${number(x)} · ${x.title}`]),...(area()==='images'?p().assets.map(x=>[x.id,`资产 · ${x.name}`]):[])];
      if(!targets.length){toast('先在左侧工作区选中章节、镜头或资产');return;}
      dialog('选择助手协助范围',`<label for="wb-scope-target">只协助选中的对象</label><select id="wb-scope-target">${targets.map(([id,title])=>`<option value="${e(id)}" ${scope().target_id===id?'selected':''}>${e(title)}</option>`).join('')}</select>`,'<button data-action="close-dialog">取消</button><button class="primary" data-wb="scope-set">使用这个范围</button>');
    } else if(name==='scope-set'){
      const id=document.querySelector('#wb-scope-target').value;await save();
      if(s().stage==='novel')s().chapter=p().outputs.novel.chapters.findIndex(x=>x.id===id);
      else if(['script','scene_plan'].includes(s().stage))s().episode=episodes().findIndex(x=>x.id===id);
      else if(p().assets.some(x=>x.id===id))assetTarget=id;
      else{assetTarget=null;s().selected=id;}
      closeDialog();render();
    } else if(name==='check-current'){await send('check','检查当前内容的结构与关键引用，指出还缺少什么。');}
    else if(name==='rewrite-dialogue'){input='只把当前镜头的对白缩短，保留画面和人物。';document.querySelector('#wb-assistant-input').value=input;document.querySelector('#wb-assistant-input').focus();}
  }
  document.addEventListener('submit',async event=>{
    if(event.target.id!=='wb-assistant-form')return;event.preventDefault();input=document.querySelector('#wb-assistant-input').value;
    try{await send();}catch(err){toast(err.message,true);}
  });
  document.addEventListener('input',event=>{if(event.target.id==='wb-assistant-input')input=event.target.value;if(s().page==='project'&&event.target.dataset.bind)dirty();});
  document.addEventListener('change',async event=>{
    const el=event.target;
    try{
      if(el.id==='wb-inner-shot'){shotIndex=Number(el.value);render();}
      if(el.dataset.channelKind&&document.querySelector('#wb-assistant-model-dialog'))await command('assistant-model');
      if(el.dataset.wbUpload&&el.files[0]){
        await save();const id=el.dataset.wbUpload,form=new FormData();form.append('file',el.files[0]);const result=await api('/media/upload','POST',form);
        if(!/\.(png|jpe?g|webp)$/i.test(result.file))throw Error('请选择图片文件');
        const seg=p().segments.find(x=>x.id===id);if(!seg)throw Error('这个镜头已不存在');
        const img={id:'shotimg_'+crypto.randomUUID().replaceAll('-','').slice(0,12),file:result.file,created_at:new Date().toLocaleString('zh-CN'),source:'upload'};
        (seg.images||=([])).push(img);seg.current_image=img.id;s().dirty=true;await save();render();toast('镜头图片已上传并采用');
      }
    }catch(err){toast(err.message,true);}
  });
  document.addEventListener('click',async event=>{
    const memoryDelete=event.target.closest('[data-memory-delete]');if(memoryDelete){memoryDelete.closest('.wb-memory-row').remove();return;}
    const assetButton=event.target.closest('[data-asset]');
    if(assetButton&&s().page==='project'){assetTarget=assetButton.dataset.asset;if(opened)render();}
    const el=event.target.closest('[data-wb],[data-wb-area],[data-wb-episode],[data-wb-segment],[data-wb-tab],[data-wb-apply],[data-wb-discard],[data-wb-image]');
    if(!el||el.disabled)return;
    el.disabled=true;
    try{
      if(el.dataset.wbArea)await selectArea(el.dataset.wbArea);
      else if(el.dataset.wbEpisode!==undefined){await save();s().episode=Number(el.dataset.wbEpisode);s().selected=null;shotIndex=0;render();}
      else if(el.dataset.wbSegment){s().selected=el.dataset.wbSegment;shotIndex=0;render();}
      else if(el.dataset.wbTab){inspectorTab=el.dataset.wbTab;render();}
      else if(el.dataset.wbApply)await applyDraft(el.dataset.wbApply);
      else if(el.dataset.wbDiscard){const result=await api(`/projects/${p().id}/assistant/${el.dataset.wbDiscard}/discard`,'POST',{});messages=messages.map(x=>x.id===result.id?result:x);render();}
      else if(el.dataset.wbImage){current().current_image=el.dataset.wbImage;s().dirty=true;await save();render();}
      else await command(el.dataset.wb);
    }catch(err){toast(err.message,true);}finally{if(el.isConnected)el.disabled=false;}
  });
  return {assistantView:()=>opened?assistant():'',taskLocks:flow.taskLocks,area,sidebar,header,view,load,current,segments,episode,selectArea,dirty,refreshProgress:flow.refreshProgress,stage:()=>({novel:'novel',script:'script',storyboard:'storyboard',prompts:'storyboard',images:'assets',video:'video',assembly:'assembly'}[area()]||'novel')};
}
