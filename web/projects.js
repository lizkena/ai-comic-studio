export function createProjectManager(ctx) {
  const {state, api, esc:e, icon, ff, sel, dialog, closeDialog, render, toast, openProject} = ctx;
  const $ = q => document.querySelector(q);
  const s = state;
  const entries = [
    ['idea','一句灵感','spark','从故事方向开始'],
    ['novel','导入小说','book','原文章节 → 改编剧本'],
    ['script','作者剧本','edit','已有剧本 → 资产与分镜']
  ];
  let mode='idea', inputs={}, uploadSequence=0, importing=false, trash=[], target=null, trashSearch='', mutating=false;
  const presets = key => s().creation_presets?.[key==='genre'?'genres':'styles']||[];
  const entry = () => entries.find(x=>x[0]===mode);

  function entryBody() {
    const saved=inputs[mode]||{};
    const source=ff('source',mode==='idea'?'灵感描述':mode==='novel'?'小说原文':'作者剧本正文',(saved.previewLimited?saved.source.slice(0,50000):saved.source)||'','textarea');
    if(mode==='idea')return `<div class="pm-entry-hint">${icon('spark')}先明确故事方向，再完善人物、世界与剧本。</div>${source}<p class="help">写下人物、处境或一个有趣的设定即可；这里不导入文件。</p>`;
    if(mode==='novel')return `<div class="pm-entry-hint">${icon('book')}保留导入的原文章节，之后再选择改编为分集剧本。</div><label class="pm-novel-import" for="import-text-file">${icon('download')}<strong>选择小说文件</strong><span>TXT / Markdown / DOCX · 最大50MB</span><input type="file" id="import-text-file" accept=".txt,.md,.docx"></label><p id="pm-import-state" class="help" role="status">也可在下方粘贴小说原文。</p>${source}<p id="pm-chapter-count" class="help"></p>${sel('adaptation_mode','改编方式',[['faithful','忠于原著：保留主线、人物与关键事件'],['moderate','适度改编：调整节奏，保留核心剧情']],saved.adaptation_mode||'faithful')}`;
    return `<div class="pm-entry-hint">${icon('edit')}保留作者的剧情和对白，整理场次后准备资产与分镜；跳过小说创作。</div>${sel('source_format','剧本格式',[['text','剧本文本：粘贴场景、动作与对白'],['json','结构化 JSON：直接导入分集和场次']],saved.source_format||'text')}${source}<p class="help" id="pm-script-format-note">文本剧本创建后可手动整理或调用模型整理；创建作品不会自动调用模型。</p>`;
  }
  function presetField(key, title, value) {
    return `<div class="pm-preset-field">${sel(key+'_preset',title,[...presets(key).map(x=>[x.id,x.name]),['custom','自定义…']],value)}<div id="pm-${key}-custom" hidden>${ff(key,'自定义'+title,'')}</div><p id="pm-${key}-note" class="help pm-preset-note"></p></div>`;
  }
  function updatePreset(key) {
    const selected=$('#form-'+key+'_preset')?.value;
    if(!selected)return;
    $('#pm-'+key+'-custom').hidden=selected!=='custom';
    $('#pm-'+key+'-note').textContent=selected==='custom'?'填写的内容将传入后续生成流程。':presets(key).find(x=>x.id===selected)?.guidance||'';
  }
  function updateEntryInfo() {
    const box=$('#form-source');if(!box)return;
    box.placeholder=mode==='idea'?'例如：一名邮递员在雾港收到来自未来的信。':mode==='novel'?'上传小说后在这里预览，也可以直接粘贴原文。':$('#form-source_format')?.value==='json'?'{"episodes":[{"title":"第1集","scenes":[...]}]}':'第1集\n场景：旧邮局，日，内\n动作：林舟推门进入。\n林舟：这封信，是写给我的？';
    box.readOnly=mode==='novel'&&!!inputs.novel?.previewLimited;
    const count=$('#pm-chapter-count');
    if(count){const text=(inputs.novel?.previewLimited?inputs.novel.source:box.value).trim();const parts=text.split(/(?=^(?:第[一二三四五六七八九十百千\d]+[章回]|#{1,3}\s))/m).filter(x=>x.trim());count.textContent=text?`已读入 ${text.length} 字 · ${parts.length} 个章节，原文保留，可创建后编辑。`:'';}
    const note=$('#pm-script-format-note');if(note)note.textContent=$('#form-source_format').value==='json'?'JSON 需包含 episodes 及各集非空 scenes；校验通过后直接进入分集剧本。':'文本剧本创建后可手动整理或调用模型整理；创建作品不会自动调用模型。';
    $('#pm-create-button').innerHTML=icon('arrow')+({idea:'创建并设置故事方向',novel:'导入小说并创建',script:'创建剧本作品'}[mode]);
  }
  function newProject() {
    mode='idea';inputs={};importing=false;uploadSequence++;
    dialog('开始一个新作品',`<form id="new-project-form" class="pm-create-form"><div class="radiogrid pm-entry-tabs">${entries.map(([id,name,sym,hint])=>`<label><input type="radio" name="entry" value="${id}" ${id===mode?'checked':''}><span>${icon(sym)}<strong>${name}</strong><small>${hint}</small></span></label>`).join('')}</div>${ff('name','作品名称','','text')}<section id="pm-entry-body" data-entry="idea">${entryBody()}</section><div class="pm-preset-heading"><h3>创作预设</h3><p class="help">类型影响剧情和人物；画风影响角色、参考图、分镜与视频提示词。</p></div><div class="grid2">${presetField('genre','故事类型','suspense')}${presetField('style','视觉风格','cinematic_guofeng')}</div><div class="grid2">${sel('ratio','画面比例',[['16:9','16:9 横屏'],['9:16','9:16 竖屏'],['1:1','1:1 方形']],'16:9')}<p class="help">总时长由 AI 根据剧情自行判断。</p></div><p class="help pm-creation-note">创建仅保存输入和预设。后续制作由你操作，助手不会自动接管。</p></form>`,`<button data-action="close-dialog">取消</button><button id="pm-create-button" class="primary" data-action="create-project">创建并设置故事方向</button>`,true);
    $('dialog').classList.add('pm-create-dialog');updatePreset('genre');updatePreset('style');updateEntryInfo();
  }
  async function create() {
    if(importing)throw Error('小说文件仍在读取，请稍候');
    const f=new FormData($('#new-project-form')), source=String(mode==='novel'&&inputs.novel?.previewLimited?inputs.novel.source:f.get('source')||'').trim();
    if(!source)throw Error(mode==='idea'?'请填写灵感描述':mode==='novel'?'请上传或粘贴小说原文':'请粘贴作者剧本');
    const settings={ratio:f.get('ratio'),adaptation_mode:f.get('adaptation_mode')||'faithful'};
    for(const key of ['genre','style']){settings[key+'_preset']=f.get(key+'_preset');settings[key]=settings[key+'_preset']==='custom'?String(f.get(key)||'').trim():presets(key).find(x=>x.id===settings[key+'_preset'])?.name;if(!settings[key])throw Error('请填写自定义'+(key==='genre'?'故事类型':'视觉风格'));}
    const p=await api('/projects','POST',{entry:mode,name:f.get('name'),source,source_format:f.get('source_format')||'text',settings});
    s().projects.unshift(p);closeDialog();await openProject(p.id);toast('作品已创建，输入与预设已保存');
  }
  function cards(projects) {
    return projects.map(p=>`<article class="projectcard-shell"><button class="projectcard" data-project="${e(p.id)}"><div class="projectposter"><span class="badge">${e(p.settings.ratio)} · ${e(p.settings.genre)}</span>${p.sample?'<span class="badge orange">示例</span>':''}</div><div class="projectdetails"><h3>${e(p.name)}</h3><p>${e((p.source||'').slice(0,500))}</p><div class="row between"><small>${e(p.updated_at.slice(5,16))}</small><span class="badge green">${Object.values(p.stage_status).filter(x=>x==='confirmed').length} 阶段已确认</span></div></div></button><button class="pm-menu-trigger" data-action="project-menu" data-id="${e(p.id)}" aria-label="${e(p.name)}的更多操作" aria-expanded="false">${icon('ellipsis')}</button></article>`).join('')+`<button class="createcard" data-action="new-project">${icon('plus')}<h3>新的故事，从这里开始</h3><p class="help">输入灵感 / 导入小说 / 作者剧本</p></button>`;
  }
  function menu(el) {
    const existing=el.parentElement.querySelector('.pm-menu');document.querySelectorAll('.pm-menu').forEach(x=>x.remove());document.querySelectorAll('.pm-menu-trigger').forEach(x=>x.setAttribute('aria-expanded','false'));if(existing)return;
    el.setAttribute('aria-expanded','true');el.parentElement.insertAdjacentHTML('beforeend',`<div class="pm-menu"><button data-project="${e(el.dataset.id)}">${icon('folder')}打开作品</button><button class="pm-trash-action" data-action="project-trash" data-id="${e(el.dataset.id)}">${icon('trash')}移入回收站</button></div>`);
  }
  async function refresh() {
    const d=await api('/projects');s().projects=d.projects;s().trash_count=d.trash_count;render();
  }
  async function confirmTrash(id) {
    target=s().projects.find(p=>p.id===id);
    if(!target)throw Error('作品已不存在，请刷新列表');
    dialog('移入回收站',`<p>将“${e(target.name)}”移入回收站？</p><p class="help mt">项目、历史和素材会保留，可随时恢复。存在排队或执行中任务时，请先停止任务。</p>`,`<button data-action="close-dialog">取消</button><button class="primary" data-action="project-trash-confirm">${icon('trash')}移入回收站</button>`);
  }
  async function moveToTrash() {
    if(mutating)return;mutating=true;
    const buttons=[...document.querySelectorAll('dialog .dialogfoot button')];buttons.forEach(b=>b.disabled=true);
    try{await api('/projects/'+target.id+'/trash','POST',{revision:target.revision,summary:true});s().jobs=s().jobs.filter(j=>j.project_id!==target.id);closeDialog();await refresh();toast('作品已移入回收站，可恢复');}
    finally{mutating=false;buttons.forEach(b=>b.disabled=false);}
  }
  function trashRows() {
    const rows=trash.filter(x=>!trashSearch||x.name.toLowerCase().includes(trashSearch.toLowerCase()));
    return rows.length?rows.map(x=>`<article class="pm-trash-row"><div class="pm-trash-thumbnail">${icon('book')}</div><div class="pm-trash-detail"><h3>${e(x.name)}</h3><p>${e(x.settings.genre)} · ${e(x.settings.ratio)}</p><small>删除于 ${e(x.deleted_at)} · ${x.segment_count} 个镜头</small></div><div class="row"><button data-action="trash-restore" data-id="${e(x.id)}">${icon('refresh')}恢复作品</button><button class="danger" data-action="trash-purge" data-id="${e(x.id)}">${icon('trash')}永久删除</button></div></article>`).join(''):`<div class="pm-trash-empty">${icon('trash')}<h3>${trashSearch?'没有匹配的作品':'回收站是空的'}</h3><p class="help">${trashSearch?'试试其他作品名称。':'移入回收站的作品会出现在这里。'}</p></div>`;
  }
  async function openTrash(reset=true) {
    if(reset)trashSearch='';trash=await api('/recycle-bin');
    dialog('回收站',`<section class="pm-trash"><p class="help mb">已删除的作品保留在这里，可随时恢复。</p><div class="pm-trash-toolbar"><span>${trash.length} 个作品</span><input id="pm-trash-search" aria-label="搜索回收站作品" placeholder="搜索回收站作品…" value="${e(trashSearch)}"><button class="danger" data-action="trash-empty" ${trash.length?'':'disabled'}>${icon('trash')}清空回收站</button></div><div id="pm-trash-list">${trashRows()}</div><div class="notice info mt">移入回收站不会立即清除项目与素材；永久删除需再次确认。</div></section>`,`<button data-action="close-dialog">关闭</button>`,true);
  }
  async function restore(id) {
    const p=trash.find(x=>x.id===id);await api('/recycle-bin/'+id+'/restore','POST',{revision:p.revision,summary:true});await refresh();await openTrash(false);toast('作品已恢复至作品空间');
  }
  function confirmPurge(id) {
    const selected=id?trash.filter(x=>x.id===id):trash.slice();if(!selected.length)return;
    target=selected;
    dialog(id?'永久删除作品':'清空回收站',`<p>${id?'永久删除“'+e(selected[0].name)+'”？':'永久删除回收站中的 '+selected.length+' 个作品？'}</p><div class="notice error mt">此操作无法恢复。将删除作品、历史和任务记录，并清理只属于这些作品的本地素材；全局资产库和其他作品引用的素材会保留。</div>`,`<button data-action="trash-back">取消</button><button class="danger" data-action="trash-purge-confirm">${icon('trash')}${id?'永久删除':'确认清空'}</button>`);
  }
  async function purge() {
    const items=target;const result=items.length===1?await api('/recycle-bin/'+items[0].id,'DELETE',{confirm:true,revision:items[0].revision}):await api('/recycle-bin/empty','POST',{confirm:true,ids:items.map(x=>x.id),revisions:Object.fromEntries(items.map(x=>[x.id,x.revision]))});
    await refresh();await openTrash(false);toast(`已永久删除 ${result.deleted} 个作品`+(result.retained_files?'；部分被占用素材未清理':''));
  }
  document.addEventListener('change',async event=>{
    const el=event.target;if(!el.closest('#new-project-form'))return;
    if(el.name==='entry'){
      const f=new FormData($('#new-project-form'));inputs[mode]={source:inputs[mode]?.previewLimited?inputs[mode].source:f.get('source')||'',previewLimited:!!inputs[mode]?.previewLimited,source_format:f.get('source_format'),adaptation_mode:f.get('adaptation_mode')};
      mode=el.value;uploadSequence++;importing=false;$('#pm-create-button').disabled=false;$('#pm-entry-body').innerHTML=entryBody();$('#pm-entry-body').dataset.entry=mode;updateEntryInfo();
    }
    if(el.name==='genre_preset'||el.name==='style_preset')updatePreset(el.name.split('_')[0]);
    if(el.name==='source_format')updateEntryInfo();
    if(el.id==='import-text-file'&&el.files[0]){
      const sequence=++uploadSequence;importing=true;$('#pm-create-button').disabled=true;$('#pm-import-state').textContent='正在读取小说文件…';
      try{const file=el.files[0];if(!file.size)throw Error('文件为空，请确认文件已下载完成后重新选择');if(file.size>50*1024**2)throw Error('文档最大50MB');const f=new FormData();f.append('file',file);const result=await api('/import/text','POST',f);if(mode!=='novel'||sequence!==uploadSequence||!$('#new-project-form'))return;if(typeof result.text!=='string'||!result.text.trim())throw Error('文件中没有小说正文，请检查文件内容后重新选择');const form=$('#new-project-form');const previewLimited=result.text.length>50000;inputs.novel={...(inputs.novel||{}),source:result.text,previewLimited};form.querySelector('#form-source').value=previewLimited?result.text.slice(0,50000):result.text;if(!form.querySelector('#form-name').value)form.querySelector('#form-name').value=result.name.replace(/\.[^.]+$/,'');updateEntryInfo();$('#pm-import-state').textContent='已读入：'+result.name+(inputs.novel.previewLimited?' · 原文已完整保留，预览显示前5万字；创建时导入全文。':'');}
      catch(error){if(sequence===uploadSequence){if($('#pm-import-state'))$('#pm-import-state').textContent=error.message;toast(error.message,true);}}
      finally{if(sequence===uploadSequence){importing=false;if($('#pm-create-button'))$('#pm-create-button').disabled=false;}}
    }
  });
  document.addEventListener('input',event=>{if(event.target.id==='form-source'&&$('#new-project-form'))updateEntryInfo();if(event.target.id==='pm-trash-search'){trashSearch=event.target.value;$('#pm-trash-list').innerHTML=trashRows();}});
  document.addEventListener('click',event=>{if(!event.target.closest('.pm-menu,.pm-menu-trigger')){document.querySelectorAll('.pm-menu').forEach(x=>x.remove());document.querySelectorAll('.pm-menu-trigger').forEach(x=>x.setAttribute('aria-expanded','false'));}});
  document.addEventListener('keydown',event=>{if(event.key==='Escape')document.querySelectorAll('.pm-menu').forEach(x=>x.remove());});
  return {newProject,create,cards,menu,confirmTrash,moveToTrash,openTrash,restore,confirmPurge,purge};
}
