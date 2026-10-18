import {createChannelModels} from './channel-models.js?v=20261005-lingquan';
// Independent settings view: each modality has its own providers and official presets.
export function createServiceSettings({state, esc, icon, ff, sel, uid, dialog, closeDialog, api, render, toast}) {
  const channelModels=createChannelModels({state,esc,icon,render,dialog,closeDialog,toast});
  const kinds = {text: ['文本', 'book', '灵感、小说、剧本与分镜文字'], image: ['图片', 'image', '角色、场景、道具与白模'], video: ['视频', 'film', '镜头生成、参考素材与本地 H3']};
  const catalog = () => state().provider_presets || {items: [], protocols: {}};
  const selectedKind = () => state().providerKind || 'text';
  const presetFor = p => catalog().items.find(x => x.id === p.preset_id);
  const protocols = kind => catalog().protocols[kind] || {};
  const docs = preset => preset ? `<a class="help official-doc" href="${esc(preset.docs_url)}" target="_blank" rel="noopener">${preset.category==='third_party'?'平台文档':'官方文档'} ${icon('link')}</a>` : '';

  const channelLabel = protocol => ({openai:'OPENAI',ark:'ARK',dashscope:'DASHSCOPE',jimeng:'AK / SK',comfy:'LOCAL',lingquan:'LINGQUAN','json-video':'JSON'}[protocol] || protocol);
  const brand = x => {const id=x.id || x.preset_id || '';return id.includes('lingquan')?'灵泉 AI':id.includes('ark')?'火山引擎':id.includes('qwen')||id.includes('wan')?'通义千问':id.includes('mimo')?'小米 MiMo':id.includes('deepseek')?'DeepSeek':id.includes('glm')?'智谱 GLM':id.includes('kimi')?'Kimi':id.includes('minimax')?'MiniMax':id.includes('jimeng')?'即梦':id.includes('comfy')?'本地 H3':x.name};
  function platformLogo(x) {
    const id=(x.preset_id || x.id || '').split('-')[0],name=id==='wan'?'qwen':id;
    if(name==='kimi')return '<img class="platform-logo logo-dark" src="/assets/platforms/kimi-dark.png" alt=""><img class="platform-logo logo-light" src="/assets/platforms/kimi-light.png" alt="">';
    return ['qwen','mimo','deepseek','ark','glm','minimax','jimeng'].includes(name)?`<img class="platform-logo" src="/assets/platforms/${name}.png" alt="">`:icon(x.defaults?.protocol==='comfy'?'chip':'link');
  }
  function platformEntry(x,key,saved,info) {
    const accounts=saved.filter(p=>p.preset_id===x.id),current=accounts.find(p=>key==='saved:'+p.id)||accounts[0];
    const target=current?'saved:'+current.id:'preset:'+x.id,active=key==='preset:'+x.id||accounts.some(p=>key==='saved:'+p.id);
    const subtitle=info[0]==='视频'?x.name.split(' · ')[1]:'';
    return `<button class="platform-brand ${active?'active':''}" data-action="provider-platform" data-key="${esc(target)}" ${active?'aria-current="true"':''}><span class="platform-brandmark brand-${esc(x.id.split('-')[0])}" aria-hidden="true">${platformLogo(x)}</span><span class="platform-brand-text"><strong>${esc(brand(x))}</strong>${subtitle?`<small>${esc(subtitle)}</small>`:''}</span>${accounts.length?`<span class="platform-configured">${accounts.length} 个渠道</span>`:''}</button>`;
  }
  function selection() {
    const kind=selectedKind(),s=state(),presets=catalog().items.filter(x=>x.kind===kind),saved=s.settings.providers;
    const candidates=[...saved.map(x=>'saved:'+x.id),...presets.map(x=>'preset:'+x.id),'custom:'+kind];
    if(!candidates.includes(s.platformSelection))s.platformSelection=candidates[0] || 'custom';
    return s.platformSelection;
  }
  function view(embedded = false) {
    const s=state(),kind=selectedKind(),info=kinds[kind],saved=s.settings.providers,presets=catalog().items.filter(x=>x.kind===kind),key=selection();
    const selected=key.startsWith('saved:')?saved.find(x=>key==='saved:'+x.id):null;
    const preset=key.startsWith('preset:')?presets.find(x=>key==='preset:'+x.id):presetFor(selected || {});
    const result=s.connectionResults?.[key];
    const body=open(selected?.id || null,preset?.id || null,true);
    const custom=saved.filter(x=>!presetFor(x));
    const thirdPresets=presets.filter(x=>x.category==='third_party');
    const officialPresets=presets.filter(x=>x.category!=='third_party');
    return `<${embedded?'section':'main'} class="${embedded?'settings-subcontent':'content settings-content'}"><div class="stagehead"><div><div class="eyebrow mb">MODEL CONNECTIONS</div><h2>模型 API</h2><p class="help">选择平台与渠道，拉取模型、测试连接，再保存配置。</p></div></div>
    <div class="service-tabs" role="tablist" aria-label="API 服务类型">${Object.entries(kinds).map(([k,[name,symbol]])=>`<button role="tab" id="service-tab-${k}" aria-controls="service-panel" aria-selected="${k===kind}" tabindex="${k===kind?0:-1}" data-action="provider-tab" data-kind="${k}">${icon(symbol)}${name}<span class="tab-count">${s.settings.providers.filter(x=>(x.models||[{kind:x.kind}]).some(m=>m.kind===k)).length}</span></button>`).join('')}</div>
    <section id="service-panel" role="tabpanel" aria-labelledby="service-tab-${kind}" class="platform-layout"><nav class="platform-rail" aria-label="平台列表"><h3 class="platform-label">${kind==='video'?'官方 / 本地渠道':'官方渠道'}</h3><div class="platform-presets">${officialPresets.map(x=>platformEntry(x,key,saved,info)).join('')}</div>
    <div class="platform-third-party"><h3 class="platform-label">第三方 / 自定义渠道</h3>${thirdPresets.map(x=>platformEntry(x,key,saved,info)).join('')}${custom.length?`<div class="platform-saved">${custom.map(x=>`<button class="platform-account ${key==='saved:'+x.id?'active':''}" data-action="provider-platform" data-key="saved:${esc(x.id)}"><span class="platform-key" aria-hidden="true">${platformLogo(x)}</span><span class="platform-account-text"><strong>${esc(x.name)}</strong><small>${esc(x.base_url)}</small></span><span class="protocol-pill">${esc(channelLabel(x.protocol))}</span></button>`).join('')}</div>`:''}
    <button class="platform-add ${key==='custom:'+kind?'active':''}" data-action="provider-new">${icon('plus')}添加第三方渠道</button><p class="help platform-footnote">支持土豆中转等服务<br>同一渠道共用地址与密钥<br>模型按用途分类</p></div></nav>
    <div class="platform-config ${!preset?'custom-channel-config':''}"><div class="platform-config-head"><div><h2>${esc(selected?.name || preset?.name || '添加第三方渠道')}</h2><p class="help">${selected?'编辑已保存的渠道':preset?'填写后保存为自己的渠道':'填写中转服务地址与密钥，模型可拉取或手动填写。'}</p></div><span class="protocol-pill">${esc(channelLabel(selected?.protocol || preset?.defaults.protocol || s.inlineProvider.protocol))}</span></div>
    <div class="field" ${key.startsWith('custom:')?'hidden':''}><label for="platform-channel">选择渠道</label><select id="platform-channel">${saved.map(x=>`<option value="saved:${esc(x.id)}" ${key==='saved:'+x.id?'selected':''}>已保存 · ${esc(x.name)}</option>`).join('')}${presets.map(x=>`<option value="preset:${esc(x.id)}" ${key==='preset:'+x.id?'selected':''}>预设 · ${esc(x.name)}</option>`).join('')}<option value="custom:${kind}" ${key==='custom:'+kind?'selected':''}>第三方 / 自定义渠道</option></select></div>
    ${body}${result?`<div class="notice ${result.error?'error':'info'} connection-result" role="status"><strong>${esc(result.title)}</strong><p>${esc(result.message)}</p>${result.missing_nodes?.length?`<p>缺少节点：${result.missing_nodes.map(esc).join('、')}</p>`:''}${result.missing_models?.length?`<p>缺少模型：${result.missing_models.map(esc).join('、')}</p>`:''}</div>`:''}</div></section>
    <details class="panel mt media-tools"><summary>本地媒体工具 · FFmpeg / FFprobe</summary><p class="help mb mt">用于视频校验、尾帧抽取和成片拼接，留空使用内置工具。</p><div class="grid2"><div class="field"><label for="ffmpeg-path">FFmpeg 路径</label><input id="ffmpeg-path" value="${esc(s.toolDraft?.ffmpeg ?? s.settings.ffmpeg)}"></div><div class="field"><label for="ffprobe-path">FFprobe 路径</label><input id="ffprobe-path" value="${esc(s.toolDraft?.ffprobe ?? s.settings.ffprobe)}"></div></div><button data-action="save-tools">${icon('save')}保存工具配置</button></details></${embedded?'section':'main'}>`;
  }

  function open(ident = null, presetId = null, inline = false) {
    const s = state(), template = catalog().items.find(x => x.id === presetId);
    const existing = s.settings.providers.find(x => x.id === ident);
    const kind = existing?.kind || template?.kind || selectedKind();
    const provider = structuredClone(existing || {id: uid('provider'), name: '', kind, protocol: kind === 'video' ? 'json-video' : 'openai', base_url: '', model: '',
      mapping: {prompt: {node:'138',input:'value'}, duration: {node:'132',input:'value'}, seed: {node:'129',input:'noise_seed'}, images:[],audio:[],output_node:'92'},
      contract: {submit_path:'/videos',poll_path:'/videos/{id}',id_path:'id',status_path:'status',result_path:'url',fields:{model:'model',prompt:'prompt',duration:'duration',ratio:'ratio',references:'references'},success_states:['succeeded','completed'],failure_states:['failed','cancelled']},
      ...(template ? {...template.defaults, preset_id: template.id} : {})});
    if (inline) {
      const previous=s.inlineProvider;
      if (!ident && previous?.selection===s.platformSelection) provider.id=previous.id;
      s.inlineProvider={...provider,selection:s.platformSelection};
    } else s.editProvider = provider;
    let inlineHtml='';
    const show=(title,body,footer,wide)=>{if(inline){inlineHtml=body.replaceAll('id="provider-form"','id="platform-provider-form"').replaceAll('id="form-','id="platform-form-').replaceAll('for="form-','for="platform-form-').replaceAll('id="workflow-file"','id="platform-workflow-file"').replaceAll('for="workflow-file"','for="platform-workflow-file"').replaceAll('id="provider-models"','id="platform-provider-models"').replaceAll('id="api-key-fields"','id="platform-api-key-fields"').replaceAll('id="ak-fields"','id="platform-ak-fields"').replaceAll('id="workflow-fields"','id="platform-workflow-fields"').replaceAll('id="contract-fields"','id="platform-contract-fields"')+`<div class="platform-form-actions"><button data-action="provider-probe">${icon('link')}测试连接</button><button class="primary" data-action="provider-save">${icon('save')}保存渠道</button></div>`;}else dialog(title,body,footer,wide);};
    const preset = presetFor(provider), protocolList = Object.entries(protocols(kind));
    const ak = provider.protocol === 'jimeng', custom = !preset;
    show(`${ident ? '编辑' : '添加'}${kinds[kind][0]}服务`, `<form id="provider-form"><input type="hidden" name="kind" value="${kind}">
      ${preset ? `<div class="notice info mb"><strong>${esc(preset.name)}</strong><p>${esc(preset.note)}</p>${docs(preset)}</div>` : ''}
      ${ff('name','服务名称',provider.name)}
      ${custom ? sel('protocol','调用协议',protocolList,provider.protocol) : `<input type="hidden" name="protocol" value="${esc(provider.protocol)}"><p class="help mb">调用方式：${esc(protocols(kind)[provider.protocol])}</p>`}
      ${ff('base_url','API 基础地址',provider.base_url,'url',preset?.category==='third_party'?'灵泉基础地址为 https://api.lk888.ai；带 /v1 的地址也会自动处理。':custom?'填写该渠道提供的基础地址，可包含 /v1；不要追加 /chat/completions。':kind === 'text' ? '填官方基础地址，不需要追加 /chat/completions。地址和密钥需属于同一地域。' : '已按对应通道预填；可按官方控制台修改地域地址。')}
      <section id="api-key-fields" ${ak ? 'hidden' : ''}>${ff('api_key',provider.has_key?'API Key（留空保留已保存密钥）':'API Key','','password',provider.has_key ? '密钥已加密保存。' : provider.protocol === 'comfy' ? '本地免密服务可以留空。' : custom?'填写该第三方渠道的 API Key，密钥加密保存在本机。':'填写该平台的 API Key。')}${provider.has_key?'<label class="check mb"><input type="checkbox" name="clear_key">清除已保存的 API Key</label>':''}</section>
      <section id="ak-fields" ${ak ? '' : 'hidden'}><div class="grid2">${ff('access_key','Access Key（AK）','','password',provider.has_ak ? 'AK 已保存，留空保留。' : '火山引擎访问密钥。')}${ff('secret_key','Secret Key（SK）','','password',provider.has_sk ? 'SK 已保存，留空保留。' : '与 AK 对应的 Secret Key。')}</div><label class="check mb"><input type="checkbox" name="clear_access_keys">清除已保存的 AK / SK</label></section>
      ${inline?channelModels.view(provider):ff('model','Model ID',provider.model)}
      ${kind === 'image' ? ff('size','图片尺寸',provider.size || '1024x1024','text','按模型限制填写，如 2048x2048；千问使用 1024*1024。') : ''}
      <section id="workflow-fields" ${provider.protocol === 'comfy' ? '' : 'hidden'}><div class="notice info mb">导入 ComfyUI 的 API 格式工作流，并确认提示词、时长、种子、素材和视频输出节点。</div><label for="workflow-file">选择 API 工作流 JSON 文件</label><input type="file" id="workflow-file" accept=".json">${ff('workflow','API 工作流 JSON',JSON.stringify(provider.workflow || {},null,2),'textarea')}${ff('mapping','字段映射 JSON',JSON.stringify(provider.mapping || {},null,2),'textarea','图片 / 音频槽位格式：{"node":"137","input":"image"}；output_node 为保存视频的节点 ID。')}</section>
      <section id="contract-fields" ${provider.protocol === 'json-video' || channelModels.entries().some(m=>m.protocol==='json-video') ? '' : 'hidden'}><details><summary>视频请求 / 响应映射</summary>${ff('contract','异步 API 请求 / 响应映射',JSON.stringify(provider.contract || {},null,2),'textarea','支持点号字段路径。references 为 purpose 和 data URL 数组；请按该中转渠道的视频接口配置。')}</details></section>
      <details><summary>高级设置与费用</summary>${kind === 'text' ? `<div class="grid2 mt">${ff('max_tokens','最大输出 Tokens',provider.max_tokens || 6000,'number')}${ff('temperature','温度',provider.temperature ?? .75,'number')}</div><label class="check mb"><input type="checkbox" name="json_mode" ${provider.json_mode ? 'checked' : ''}>使用 JSON mode（需模型支持）</label>` : ''}<div class="grid2 mt">${ff('unit_price','手动单价（未知留空）',provider.unit_price ?? '','number')}${sel('price_unit','单价单位',[['request','每次请求'],['second','每秒视频']],provider.price_unit || 'request')}${sel('currency','货币',[['CNY','人民币 CNY'],['USD','美元 USD']],provider.currency || 'CNY')}</div>
      ${kind === 'text' ? `${sel('auth_header','密钥请求头',[['bearer','Authorization: Bearer'],['api-key','api-key']],provider.auth_header || 'bearer')}${sel('token_field','输出上限字段',[['max_tokens','max_tokens'],['max_completion_tokens','max_completion_tokens']],provider.token_field || 'max_tokens')}${ff('text_options','官方可选参数 JSON',JSON.stringify(provider.text_options || {},null,2),'textarea','支持 thinking、enable_thinking、reasoning_effort、reasoning_split。')}` : ''}
      ${kind === 'video' ? `<div class="grid2">${ff('min_duration','最短时长 / 秒',provider.capabilities?.min_duration ?? .5,'number')}${ff('max_duration','最长时长 / 秒',provider.capabilities?.max_duration ?? 15,'number')}</div><label class="check mb"><input type="checkbox" name="audio_reference" ${provider.capabilities?.audio_reference ? 'checked' : ''}>接受声音参考</label><p class="help">${provider.capabilities?.durations ? '可用时长：' + provider.capabilities.durations.join(' / ') + ' 秒。' : ''}${provider.capabilities?.max_images != null ? '最多 ' + provider.capabilities.max_images + ' 张参考图。' : ''}</p>` : ''}</details>
    </form>`, `<button data-action="close-dialog">取消</button><button class="primary" data-action="provider-save">${icon('save')}保存服务</button>`, true);
    if(inline)return inlineHtml;
    document.querySelector('dialog #form-name').focus();
  }

  function protocolChanged(form = null) {
    form=form || document.querySelector('dialog #provider-form') || document.getElementById('platform-provider-form');
    const protocol=form.elements.protocol.value;
    const models=form.id==='platform-provider-form'?channelModels.entries():[];
    for (const [id, show] of [['workflow-fields',protocol === 'comfy'||models.some(m=>m.protocol==='comfy')],['contract-fields',protocol === 'json-video'||models.some(m=>m.protocol==='json-video')],['api-key-fields',protocol !== 'jimeng'],['ak-fields',protocol === 'jimeng'||models.some(m=>m.protocol==='jimeng')]]) form.querySelector('#'+(form.id==='platform-provider-form'?'platform-':'')+id).hidden = !show;
  }

  function readForm(form, requireModel = true) {
    const s=state();
    const f = new FormData(form), provider = {...(form.id==='platform-provider-form'?s.inlineProvider:s.editProvider)};
    delete provider.selection;
    for (const key of ['name','kind','protocol','base_url','model','api_key','access_key','secret_key','price_unit','currency']) provider[key] = String(f.get(key) || '').trim();
    for (const key of ['clear_key','clear_access_keys','json_mode']) provider[key] = f.has(key);
    provider.unit_price = f.get('unit_price') === '' ? null : Number(f.get('unit_price'));
    if (provider.unit_price != null && (!Number.isFinite(provider.unit_price) || provider.unit_price < 0)) throw Error('单价应为非负数');
    if (!provider.name || !provider.base_url) throw Error('请填写服务名称与地址');
    if(form.id==='platform-provider-form'){channelModels.capture();if(channelModels.entries().some(m=>m.lingquan_params_invalid||m.lingquan_params&&(!m.lingquan_params||typeof m.lingquan_params!=='object'||Array.isArray(m.lingquan_params))))throw Error('模型参数须为有效 JSON 对象');provider.models=structuredClone(channelModels.entries());provider.model=provider.models.find(m=>m.kind===provider.kind)?.id || provider.models[0]?.id || '';if(requireModel&&provider.protocol!=='comfy'&&(!provider.models.length||provider.models.some(m=>!m.id)))throw Error('请至少添加一个模型，并填写每个模型的 ID');}
    if (requireModel && provider.protocol !== 'comfy' && !provider.model) throw Error('请填写模型 ID');
    if (provider.kind === 'text') {
      provider.max_tokens = Number(f.get('max_tokens')); provider.temperature = Number(f.get('temperature'));
      if (!Number.isInteger(provider.max_tokens) || provider.max_tokens < 1 || provider.temperature < 0 || provider.temperature > 2) throw Error('请填写有效的 Tokens 上限和温度（0–2）');
      provider.auth_header = f.get('auth_header'); provider.token_field = f.get('token_field');
      provider.text_options = JSON.parse(f.get('text_options'));
      if (!provider.text_options || typeof provider.text_options !== 'object' || Array.isArray(provider.text_options)) throw Error('官方可选参数应为 JSON 对象');
    }
    if (provider.kind === 'image') provider.size = String(f.get('size')).trim();
    if (provider.kind === 'video') {
      provider.capabilities = {...provider.capabilities, min_duration:Number(f.get('min_duration')),max_duration:Number(f.get('max_duration')),audio_reference:f.has('audio_reference')};
      if (provider.capabilities.min_duration <= 0 || provider.capabilities.max_duration < provider.capabilities.min_duration) throw Error('视频时长范围无效');
    }
    if (provider.protocol === 'comfy'||provider.models?.some(m=>m.protocol==='comfy')) {provider.workflow = JSON.parse(f.get('workflow')); provider.mapping = JSON.parse(f.get('mapping'));}
    if (provider.protocol === 'json-video' || channelModels.entries().some(m=>m.protocol==='json-video')) provider.contract = JSON.parse(f.get('contract'));
    return provider;
  }
  async function save() {
    const s=state(),form=document.querySelector('dialog #provider-form') || document.getElementById('platform-provider-form');
    if(!form.reportValidity())return;
    const provider=readForm(form);
    const next = structuredClone(s.settings), index = next.providers.findIndex(x => x.id === provider.id);
    if (index < 0) next.providers.push(provider); else next.providers[index] = provider;
    s.settings = await api('/settings','PUT',next); s.providerKind = provider.kind;
    if(form.id==='platform-provider-form'){delete s.channelModelDrafts?.[s.platformSelection];delete s.platformDrafts?.[s.platformSelection];s.platformSelection='saved:'+provider.id;}
    closeDialog(); render(); toast('渠道已保存，可在创作项目中选择');
  }

  function captureDraft() {
    const form=document.getElementById('platform-provider-form');if(!form)return;
    channelModels.capture();
    const fields={};for(const el of form.elements){if(!el.name || el.type==='file')continue;fields[el.name]=el.type==='checkbox'?el.checked:el.value;}
    const s=state();s.platformDrafts ||= {};fields.models=structuredClone(channelModels.entries());s.platformDrafts[s.platformSelection]=fields;
  }
  function afterRender() {
    const form=document.getElementById('platform-provider-form');if(!form)return;
    const values=state().platformDrafts?.[state().platformSelection];
    if(values)for(const el of form.elements){if(el.name in values){if(el.type==='checkbox')el.checked=values[el.name];else if(el.type!=='file')el.value=values[el.name];}}

    protocolChanged(form);
  }
  function selectPlatform(key){captureDraft();state().platformSelection=key;render();}
  function newPlatform(){selectPlatform('custom:'+selectedKind());}
  async function requestConnection(mode) {
    const s=state(),form=document.getElementById('platform-provider-form');captureDraft();
    const key=s.platformSelection,provider=readForm(form, false),fingerprint=JSON.stringify(s.platformDrafts[key]);
    // Model discovery and connection checks do not require choosing a model first.
    s.connectionResults ||= {};
    try{
      toast(mode==='models'?'正在拉取模型…':'正在测试连接…');
      const result=await api('/providers/'+(mode==='models'?'models':'probe'),'POST',provider);
      if(JSON.stringify(s.platformDrafts[key])!==fingerprint){toast('配置已修改，请按当前配置重新检查');return;}
      if(mode==='models'){s.modelLists ||= {};s.modelLists[key]=result;}
      s.connectionResults[key]={...result,error:!result.ok&&result.source!=='preset',title:mode==='models'?'模型拉取结果':'连接测试结果'};
    }catch(error){if(JSON.stringify(s.platformDrafts[key])!==fingerprint)return;s.connectionResults[key]={error:true,title:mode==='models'?'模型拉取失败':'连接测试失败',message:error.message};}
    if(s.page==='settings'&&s.settingsSection==='api'&&s.platformSelection===key)render();
  }
  function invalidateResult(el) {
    const s=state(),key=s.platformSelection;
    if(s.connectionResults)delete s.connectionResults[key];
    document.querySelector('.connection-result')?.remove();
    if(['base_url','api_key','access_key','secret_key','protocol','auth_header','clear_key','clear_access_keys'].includes(el.name)){
      if(s.modelLists)delete s.modelLists[key];

    }
  }
  document.addEventListener('input',event=>{if(event.target.closest('#platform-provider-form')){captureDraft();invalidateResult(event.target);}});
  document.addEventListener('change',event=>{
    if(event.target.id==='platform-channel')selectPlatform(event.target.value);
    if(event.target.id==='platform-workflow-file'&&event.target.files[0])event.target.files[0].text().then(text=>{const form=event.target.closest('form');if(form?.isConnected){form.elements.workflow.value=text;captureDraft();}}).catch(error=>toast(error.message,true));
    if(event.target.closest('#platform-provider-form')){captureDraft();invalidateResult(event.target);if(event.target.closest('.channel-model-row'))protocolChanged(event.target.closest('form'));}
  });
  function tab(kind, focus = false) {
    if (!kinds[kind]) return;
    state().toolDraft = {ffmpeg:document.getElementById('ffmpeg-path')?.value ?? state().settings.ffmpeg, ffprobe:document.getElementById('ffprobe-path')?.value ?? state().settings.ffprobe};
    captureDraft();state().providerKind = kind; render();
    for (const key of ['ffmpeg','ffprobe']) document.getElementById(key + '-path').value = state().toolDraft[key] || '';
    if (focus) document.getElementById('service-tab-' + kind).focus();
  }
  document.addEventListener('keydown', event => {
    if (!event.target.matches('.service-tabs [role="tab"]') || !['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    event.preventDefault(); const keys = Object.keys(kinds), index = keys.indexOf(selectedKind());
    tab(event.key === 'Home' ? keys[0] : event.key === 'End' ? keys.at(-1) : keys[(index + (event.key === 'ArrowRight' ? 1 : 2)) % 3], true);
  });
  return {view, open, save, tab, protocolChanged, afterRender, selectPlatform, newPlatform, requestConnection};
}
