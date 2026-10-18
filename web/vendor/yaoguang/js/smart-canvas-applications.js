/* Image output ports create persistent application nodes using existing canvas APIs. */
const SMART_APPLICATIONS = [
    {id:'describe', title:'反推提示词', icon:'file-text', hint:'提取这张图的构图、材质与光影', role:'reference', text:true, prompt:'分析参考图，输出可用于重新生成相似视觉效果的中文提示词。描述主体、构图、视角、材质、光影、配色和背景；不要编造看不清的文字或产品信息。'},
    {id:'generate', title:'图生图', icon:'image', hint:'以参考图片和提示词生成新画面', role:'reference', prompt:'以参考图为视觉依据，按补充要求生成新的高质量图片。保留用户指定的主体特征。'},
    {id:'detail', title:'一键详情', icon:'panels-top-left', hint:'围绕产品制作连贯的详情页图组', role:'product', prompt:'制作产品详情页的一个独立画面。保持产品结构、标志、颜色和材质准确；用清楚的视觉层级呈现真实产品信息，不编造卖点、认证、参数或评价。'},
    {id:'transfer', title:'产品迁移', icon:'arrow-right-left', hint:'将产品放入另一张场景参考图', role:'product', second:'scene', prompt:'把产品图中的产品放入场景参考图，保持产品结构、标志、材质和颜色。匹配场景的透视、光线、尺度、接触阴影和反射。'},
    {id:'compose', title:'场景合成', icon:'layers', hint:'以这张图为场景，加入产品', role:'scene', second:'product', prompt:'以场景图作为环境，将产品图中的产品自然合成到场景中。保留场景主要构图，保持产品真实结构与品牌细节，统一透视、光向、比例与阴影。'},
    {id:'repair', title:'细节修复', icon:'sparkles', hint:'结合图片标记，修复指定细节', role:'product', prompt:'根据补充要求和图片标记进行局部细节修复。保留未指定区域、整体构图、产品结构、标志、文字与颜色，避免重绘整个产品。'},
    {id:'retouch', title:'产品精修', icon:'wand-sparkles', hint:'清理瑕疵，改善光影与材质', role:'product', skill:'curated-product-retouch', prompt:'对产品原图进行自然商业精修：清理灰尘和拍摄污点，校正曝光与白平衡，改善反光、边缘和背景，保留真实材质、产品比例、结构、标志和标签文字。'},
    {id:'relight', title:'重新打光', icon:'sun', hint:'将产品图交给 AI 重新打光，可补充提示词', role:'product', prompt:'请为这张产品渲染图重新打光。保留产品外观、结构、材质、标志、原构图和背景，只调整光照、高光、反射与阴影。输出一张重新打光后的成品图，不添加新文字或拼接对比图。'},
    {id:'layout', title:'版式复刻', icon:'copy', hint:'提炼参考版式，换入你的产品', role:'template', second:'product', prompt:'提炼版式参考图的布局节奏、留白、配色和文字层级，使用产品图重建原创画面。保留产品本体，不照搬参考图的商标、独有素材或未经证实的宣传信息。'}
];
// Keep legacy definitions for saved canvases; offer only the current creation tools.
const SMART_APPLICATION_CREATION_IDS = new Set(['describe', 'generate']);
const SMART_APP_ROLE_LABELS = {product:'产品图', reference:'参考图', scene:'场景图', template:'版式参考'};
let smartApplicationMenuState = null;
let smartApplicationSkills = [];

function smartApplicationDefinition(node){
    return SMART_APPLICATIONS.find(item => item.id === node?.application) || SMART_APPLICATIONS[1];
}
function smartApplicationInputs(node){
    const roles = {product:[], reference:[], scene:[], template:[], text:[]};
    const definition = smartApplicationDefinition(node);
    inputNodesFor(node).forEach(source => {
        if(source.type === 'smart-prompt'){
            if(source.text?.trim()) roles.text.push(source.text.trim());
            return;
        }
        const role = node.appInputRoles?.[source.id] || (source.id === node.appSourceId ? definition.role : 'reference');
        let images = imageRefsOnly(imagesForNode(source));
        if(source.id === node.appSourceId && Number.isInteger(node.appSourceImageIndex)) images = images.filter(image => image.imageIndex === node.appSourceImageIndex);
        images = images.filter(image => !(node.appExcludedImages || []).includes(`${source.id}|${image.imageIndex}|${image.url}`));
        (roles[role] || roles.reference).push(...images.map(image => ({...image, appSourceId:source.id})));
    });
    Object.entries(node.appUploads || {}).forEach(([role, images]) => {
        if(roles[role] && role !== 'text') roles[role].push(...imageRefsOnly(images || []));
    });
    for(const role of Object.keys(roles)) if(role !== 'text') roles[role] = uniqueReferenceImages(roles[role]).slice(0, 20);
    if(node.application === 'compose'){
        const o=smartApplicationOptions(node); roles.product=roles.product.sort((a,b)=>(o.layers[a.url]?.order || 0)-(o.layers[b.url]?.order || 0));
    }
    return roles;
}
function smartApplicationRequest(node, roles, screen=0){
    const definition = smartApplicationDefinition(node);
    const refs = [], descriptions = [];
    for(const role of ['product','scene','template','reference']){
        (role==='product' && node.application==='compose' ? appVisibleProducts(node,roles) : roles[role] || []).forEach(image => {
            if(refs.length >= SMART_REFERENCE_IMAGE_MAX) return;
            refs.push({...image, role:`image_${refs.length + 1}`});
            descriptions.push(`图${refs.length}是${SMART_APP_ROLE_LABELS[role]}。`);
        });
    }
    const prompt = [definition.prompt, descriptions.join('\n'), smartApplicationTaskInstructions(node,roles,screen), node.productName ? `产品名称：${node.productName}` : '',
        roles.text.length ? `连接的文字要求：\n${roles.text.join('\n\n')}` : '',
        node.appPrompt ? `补充要求：${node.appPrompt}` : '',
        `输出语言：${node.appLanguage || '中文'}；图中文字：${node.appTypography || '少量文字'}。`,
        definition.id === 'detail' ? `用途：${node.appPlatform || '通用电商'}。生成第${screen + 1}/${Math.max(1, Math.min(8, Number(node.appCount) || 1))}屏，仅交付这一屏完整图片，不能把多屏拼成一张。${node.appPlan ? `\n整套策划：\n${node.appPlan}` : '\n依次组织：产品主视觉、已确认卖点、可见细节、使用场景、结构展示、品牌收尾；未提供的参数不编造。'}` : ''
    ].filter(Boolean).join('\n\n');
    (node.appGuideRefs || []).forEach(image=>refs.push({...image,role:`image_${refs.length+1}`}));
    const request = {prompt, displayPrompt:node.appPrompt || definition.title, refs};
    const enhanced=node.application==='generate' ? request : window.YaoguangCanvas?.enhanceRequest(node, request) || request;
    enhanced.prompt += `\n\n最终任务约束（优先于 Skills 的通用风格建议）：执行「${definition.title}」，严格执行节点选项；Skills 仅帮助提升质量，不能改变任务、图片角色、选区、文字内容、数量或布局约束。\n${smartApplicationTaskInstructions(node,roles,screen)}`;
    return enhanced;
}
function decorateSmartApplicationPorts(el, node){
    if(!isSmartImageNode(node) || !imageRefsOnly(node.images || []).length) return;
    const port = el.querySelector('[data-port="out"]');
    if(!port) return;
    port.classList.add('application-output-port');
    port.setAttribute('role','button');
    port.setAttribute('tabindex','0');
    port.setAttribute('aria-label','拖出或点击，创建图片应用节点');
    port.title = '左键拖出应用 · 点击选择应用';
    port.addEventListener('keydown', event => {
        if(!['Enter',' '].includes(event.key)) return;
        event.preventDefault(); event.stopPropagation();
        const rect = nodeRect(node), bounds = port.getBoundingClientRect();
        openSmartApplicationMenu(node.id, {x:rect.x + rect.width + 100, y:rect.y}, {clientX:bounds.right + 70, clientY:bounds.top});
    });
}
function closeSmartApplicationMenu(restoreFocus=false){
    const sourceId = smartApplicationMenuState?.sourceId;
    document.getElementById('smartApplicationMenu')?.remove();
    document.getElementById('smartApplicationMenuWire')?.remove();
    smartApplicationMenuState = null;
    if(restoreFocus && sourceId) world.querySelector(`.image-node[data-id="${CSS.escape(sourceId)}"] .application-output-port`)?.focus();
}
function openSmartApplicationMenu(sourceId, point, event){
    closeSmartApplicationMenu();
    const source = nodes.find(node => node.id === sourceId);
    if(!source) return;
    smartApplicationMenuState = {sourceId, point};
    const menu = document.createElement('div');
    menu.id = 'smartApplicationMenu'; menu.className = 'smart-application-menu';
    menu.setAttribute('role','menu'); menu.setAttribute('aria-label','引用图片创建应用');
    menu.innerHTML = '<div class="application-menu-heading">引用该图片创建<button type="button" aria-label="关闭应用菜单" data-app-close>×</button></div>' + SMART_APPLICATIONS.filter(item => SMART_APPLICATION_CREATION_IDS.has(item.id)).map(item => `<button type="button" role="menuitem" data-application="${item.id}"><span class="application-menu-icon"><i data-lucide="${item.icon}"></i></span><span><strong>${item.title}</strong><small>${item.hint}</small></span></button>`).join('');
    document.body.appendChild(menu);
    const left = Math.max(12, Math.min(event.clientX + 12, innerWidth - menu.offsetWidth - 12));
    const top = Math.max(12, Math.min(event.clientY - 60, innerHeight - menu.offsetHeight - 12));
    menu.style.left = `${left}px`; menu.style.top = `${top}px`;
    const sourceEl = world.querySelector(`.image-node[data-id="${CSS.escape(sourceId)}"]`);
    const bounds = sourceEl?.getBoundingClientRect();
    if(bounds){
        const sx = bounds.right, sy = bounds.top + bounds.height / 2, ty = Math.max(top + 24, Math.min(sy, top + menu.offsetHeight - 24));
        const wire = document.createElementNS('http://www.w3.org/2000/svg','svg');
        wire.id = 'smartApplicationMenuWire'; wire.setAttribute('class','application-menu-wire');
        const curve = Math.max(40, Math.abs(left - sx) / 2);
        wire.innerHTML = `<path d="M${sx},${sy} C${sx + curve},${sy} ${left - curve},${ty} ${left},${ty}"/>`;
        document.body.appendChild(wire);
    }
    menu.addEventListener('mousedown', event => event.stopPropagation());
    menu.addEventListener('click', event => {
        if(event.target.closest('[data-app-close]')) return closeSmartApplicationMenu(true);
        const button = event.target.closest('[data-application]');
        if(!button || !smartApplicationMenuState) return;
        const state = smartApplicationMenuState;
        closeSmartApplicationMenu();
        createSmartApplicationNode(state.sourceId, button.dataset.application, state.point);
    });
    menu.addEventListener('keydown', event => {
        if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key)) return;
        event.preventDefault(); event.stopPropagation();
        const buttons = [...menu.querySelectorAll('[role="menuitem"]')], index = buttons.indexOf(document.activeElement);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
        buttons[next]?.focus();
    });
    window.lucide?.createIcons(); menu.querySelector('[role="menuitem"]')?.focus();
}
function createSmartApplicationNode(sourceId, application, point, options={}){
    if(!SMART_APPLICATION_CREATION_IDS.has(application)) return null;
    const definition = SMART_APPLICATIONS.find(item => item.id === application);
    if(!definition || !nodes.some(node => node.id === sourceId)) return null;
    if(!options.skipUndo)pushUndo();
    const node = {id:uid('app'), type:'smart-application', application, title:definition.title, x:point.x, y:point.y, w:640, h:1040,
        images:[], appSourceId:sourceId, appInputRoles:{[sourceId]:definition.role}, appUploads:{}, appPrompt:'', productName:'',
        appCount:application === 'detail' ? 6 : 1, appLanguage:'中文', appTypography:application === 'detail' ? '带字排版' : '少量文字',
        appIntensity:'自然精修', appPlatform:'通用电商', runSettings:cloneSmartSettings(settings), created_at:Date.now()};
    if(selectedImage.nodeId === sourceId && selectedImage.index >= 0) node.appSourceImageIndex = selectedImage.index;
    const provider = imageProviders().find(item => item.id === settings.provider_id) || imageProviders().find(item=>item.has_key) || imageProviders()[0];
    if(provider) Object.assign(node.runSettings, {engine:'api', apiKind:'image', provider_id:provider.id, model:providerImageModels(provider.id).includes(settings.model) ? settings.model : providerImageModels(provider.id)[0], count:1});
    smartApplicationOptions(node);
    if(application==='relight')node.appTypography='不添加文字';
    if(['generate','detail','layout','relight'].includes(application))node.runSettings.ratio='auto';
    node.appChatProvider = chatApiProviders().find(item=>item.id===settings.provider_id)?.id || chatApiProviders().find(item=>item.has_key)?.id || resolveChatProviderId(); node.appChatModel = resolveChatModel('', node.appChatProvider);
    const deepseek=chatApiProviders().find(p=>p.has_key && (p.chat_models || []).some(m=>/deepseek/i.test(m)));
    if(deepseek){node.appChatProvider=deepseek.id;node.appChatModel=(deepseek.chat_models || []).find(m=>m==='deepseek-flash') || resolveChatModel('',deepseek.id);}
    nodes.push(node); connectInputNode(sourceId, node.id);
    if(options.select!==false){selectedId = node.id; selectedIds = [node.id]; selectedImage = {nodeId:'',index:-1};}
    if(options.render!==false)render();
    scheduleSave();
    // Load the existing local skill snapshot without executing upstream scripts.
    fetch('/api/local-skills').then(r => r.ok ? r.json() : Promise.reject(new Error('读取 Skills 失败'))).then(data => {
        smartApplicationSkills = data.skills || [];
        if(!nodes.includes(node)) return;
        const skill = smartApplicationSkills.find(item => item.id === definition.skill);
        if(skill && !node.localSkill && !node.appSkillTouched && !node.running) node.localSkill = {id:skill.id,name:skill.name,description:skill.description,content:skill.content};
        render(); scheduleSave();
    }).catch(() => {});
    return node;
}
function smartImageGenerationTarget(source){
    if(!source || !isSmartImageNode(source) || source.pending || source.running || !imageRefsOnly(source.images || []).length)return null;
    const index=selectedImage.nodeId===source.id && selectedImage.index>=0?selectedImage.index:null;
    return nodes.find(node=>node.type==='smart-application' && node.application==='generate' && node.appSourceId===source.id &&
        (Number.isInteger(node.appSourceImageIndex)?node.appSourceImageIndex:null)===index &&
        (canvas.connections || []).some(c=>c.from===source.id && c.to===node.id && c.kind==='input')) || null;
}
function smartApplicationSelect(label, field, values, value){
    return `<label class="application-field"><span>${escapeHtml(label)}</span><select data-app-field="${field}">${values.map(item => {const pair = Array.isArray(item) ? item : [item,item]; return `<option value="${escapeHtml(String(pair[0]))}" ${pair[2]?'disabled':''} ${String(pair[0]) === String(value) ? 'selected' : ''}>${escapeHtml(String(pair[1]))}</option>`;}).join('')}</select></label>`;
}
function smartApplicationBodyHtml(node){
    const definition=smartApplicationDefinition(node), inputs=smartApplicationInputs(node);
    return `<section class="application-card application-${node.application}"><header class="application-node-header"><i data-lucide="${definition.icon}"></i><div><strong>${definition.title}</strong><small>${definition.hint}</small></div><button type="button" class="application-close" data-app-delete aria-label="删除应用节点">×</button></header><div class="application-form">
        ${appTaskBodyHtml(node,inputs)}<div class="application-picker" hidden></div>
        ${node.appStatus ? `<p class="application-status" role="status">${escapeHtml(node.appStatus)}</p>` : ''}
        </div><div class="application-settings">${definition.text ? '' : appImageModelsHtml(node)}
        <div class="application-footer"><small>${definition.text?'输出：文本节点':node.application==='generate'?'输出：图片':'先审核生成内容 · 确认后生图'}</small><button type="button" class="application-run" data-app-run ${node.running ? 'disabled' : ''}>${node.running ? '处理中…' : node.application==='generate'?'生成':definition.text ? SMART_APP_ACTIONS[node.application] : '整理并审核'}<i data-lucide="arrow-right"></i></button></div>
        </div></section>`;
}
function bindSmartApplicationControls(el, node){
    if(node.application==='generate'){
        const card=el.querySelector('.application-card');
        const fit=()=>{
            if(!el.isConnected || !card)return;
            const height=Math.ceil(card.offsetHeight)+2;
            if(height>0 && Math.abs((node.h || 0)-height)>1){
                node.h=height; renderConnections(); renderMinimap(); scheduleSave();
            }
        };
        const observer=new ResizeObserver(()=>{if(el.isConnected)fit();else observer.disconnect();});
        if(card)observer.observe(card);
        requestAnimationFrame(fit);
    }
    el.querySelectorAll('input,textarea,select,button,.application-picker').forEach(control => {
        control.addEventListener('mousedown',event => event.stopPropagation());
        control.addEventListener('click',event => event.stopPropagation());
        control.addEventListener('keydown',event => event.stopPropagation());
        control.addEventListener('dblclick',event => event.stopPropagation());
        control.addEventListener('wheel',event => event.stopPropagation(),{passive:true});
    });
    el.querySelector('.application-form')?.addEventListener('wheel',event => event.stopPropagation(),{passive:true});
    el.querySelectorAll('[data-app-field]').forEach(control => {
        const field = control.dataset.appField;
        if(node.running)control.disabled=true;
        control.addEventListener(control.matches('input,textarea') ? 'input' : 'change',() => {
            if(node.running)return;
            node.runSettings ||= cloneSmartSettings(settings);
            if(field === 'provider'){
                if(control.value === '__current'){
                    const ratio=node.runSettings.ratio;
                    node.runSettings=cloneSmartSettings(settings);
                    if(ratio !== undefined)node.runSettings.ratio=ratio;
                }
                else Object.assign(node.runSettings,{engine:'api',apiKind:'image',provider_id:control.value,model:providerImageModels(control.value)[0] || ''});
            } else if(field.startsWith('option:')){
                const key=field.slice(7),o=smartApplicationOptions(node);
                o[key]=control.type==='checkbox'?control.checked:control.type==='range'?Number(control.value):control.value;
                if(['layerScale','layerX','layerY'].includes(key) && o.activeLayer){
                    const layer=o.layers[o.activeLayer] ||= {};
                    if(!layer.locked)layer[key==='layerScale'?'scale':key==='layerX'?'x':'y']=key==='layerScale'?Number(control.value):Number(control.value)/100;
                }
                if(control.type==='range'){control.nextElementSibling.textContent=control.value+(key==='brush'?' px':key==='feather'?' px':'%');const overlay=el.querySelector('[data-app-overlay]');if(overlay)appPaintOverlay(overlay,node,smartApplicationInputs(node));}
            } else if(['model','ratio','resolution'].includes(field)) node.runSettings[field] = control.value;
            else if(field === 'skill'){
                node.appSkillTouched=true;
                const skill = smartApplicationSkills.find(item => item.id === control.value);
                if(skill) node.localSkill = {id:skill.id,name:skill.name,description:skill.description,content:skill.content};
                else delete node.localSkill;
            } else node[field] = field === 'appCount' ? Number(control.value) : control.value;
            if(field === 'appChatProvider') node.appChatModel = resolveChatModel('',node.appChatProvider);
            scheduleSave();
            if(['provider','appChatProvider','appCount','option:colorMode','option:placement'].includes(field)) render();
        });
    });
    bindSmartApplicationOptionControls(el,node);
    el.querySelector('[data-app-delete]')?.addEventListener('click',() => {if(node.running) return toast('任务进行中，请等待完成后删除应用节点'); deleteNode(node.id);});
    el.querySelector('[data-app-run]')?.addEventListener('click',() => runSmartApplication(node.id));
    el.querySelector('[data-app-plan]')?.addEventListener('click',() => planSmartApplication(node.id));
    el.querySelector('[data-app-text]')?.addEventListener('click',() => {
        pushUndo();
        const textNode = createPromptNode(Math.max(0,node.x - 390),node.y + 300,{skipUndo:true});
        textNode.text = ''; connectInputNode(textNode.id,node.id); selectedId = node.id; selectedIds = [node.id]; render(); scheduleSave();
    });
    el.querySelectorAll('[data-app-add]').forEach(button => button.addEventListener('click',() => showSmartApplicationPicker(el,node,button.dataset.appAdd)));
    el.querySelectorAll('[data-app-remove-role]').forEach(button => button.addEventListener('click',() => {
        const role = button.dataset.appRemoveRole, image = smartApplicationInputs(node)[role][Number(button.dataset.appRemoveIndex)];
        if(!image) return; pushUndo();
        if(image.appSourceId){
            node.appExcludedImages = [...(node.appExcludedImages || []), `${image.appSourceId}|${image.imageIndex}|${image.url}`];
            if(!smartApplicationInputs(node)[role].some(item => item.appSourceId === image.appSourceId)){
                canvas.connections = (canvas.connections || []).filter(connection => !(connection.to === node.id && connection.from === image.appSourceId && connection.kind === 'input'));
                node.inputNodeIds = (node.inputNodeIds || []).filter(id => id !== image.appSourceId);
            }
        } else node.appUploads[role] = (node.appUploads[role] || []).filter(item => item.url !== image.url);
        render(); scheduleSave();
    }));
}
function showSmartApplicationPicker(el,node,role){
    const picker = el.querySelector('.application-picker');
    const candidates = nodes.filter(source => source.id !== node.id && isSmartImageNode(source) && imageRefsOnly(source.images || []).length);
    picker.innerHTML = `<div class="application-picker-head"><strong>添加${SMART_APP_ROLE_LABELS[role]}</strong><button type="button" data-picker-close aria-label="关闭图片选择">×</button></div><button type="button" class="application-upload">上传本地图片</button><div class="application-picker-list">${candidates.map(source => `<button type="button" data-picker-node="${escapeHtml(source.id)}"><img src="${escapeHtml(imageRefsOnly(source.images)[0].url)}" alt=""><span>${escapeHtml(source.title || source.images[0].name || '画布图片')}</span></button>`).join('') || '<small>画布中还没有其他图片</small>'}</div>`;
    picker.hidden = false;
    picker.querySelector('[data-picker-close]').onclick = () => {picker.hidden = true;};
    picker.querySelectorAll('[data-picker-node]').forEach(button => {button.onclick = () => {
        const source = nodes.find(item => item.id === button.dataset.pickerNode);
        if(!source) return;
        if(smartApplicationInputs(node)[role].length + imageRefsOnly(source.images || []).length > 20) return toast('每类参考图最多 20 张');
        pushUndo(); node.appInputRoles ||= {}; node.appInputRoles[source.id] = role;
        node.appExcludedImages = (node.appExcludedImages || []).filter(key => !key.startsWith(`${source.id}|`));
        connectInputNode(source.id,node.id); render(); scheduleSave();
    };});
    picker.querySelector('.application-upload').onclick = () => {
        const input = document.createElement('input'); input.type = 'file'; input.accept = 'image/*'; input.multiple = true;
        input.onchange = async () => {
            try {
                const limit = 20 - smartApplicationInputs(node)[role].length;
                if(limit <= 0) return toast('每类参考图最多 20 张');
                const uploaded = await uploadFiles([...input.files].filter(file => file.type.startsWith('image/')).slice(0,limit));
                if(!nodes.includes(node) || !uploaded.length) return;
                pushUndo(); node.appUploads ||= {}; node.appUploads[role] = [...(node.appUploads[role] || []), ...uploaded]; render(); scheduleSave();
            } catch(error){toast(error.message || '上传失败');}
        }; input.click();
    };
}
async function smartApplicationChat(node,message,refs){
    const provider = node.appChatProvider || resolveChatProviderId(), model = node.appChatModel || resolveChatModel('',provider);
    if(!chatApiProviders().some(p=>p.id===provider))throw new Error('所选文本平台不可用，请重新选择');
    if(!chatApiProviders().length) throw new Error('请先在设置中配置支持图片理解的文字模型');
    const response = await fetch('/api/canvas-llm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,messages:[],images:refs.map(image => image.url),videos:[],provider,model,system_prompt:`你是严谨的商业视觉设计师。只描述可见事实，不编造产品参数、认证与卖点。本次节点的明确选项优先于 Skills 中的通用偏好。必须使用${node.appLanguage==='英文'?'English，所有标题与正文都使用英文':'中文'}回答。遵守当前任务要求的输出格式；如果要求 JSON，只返回有效 JSON，不添加代码围栏或说明。`})});
    if(!response.ok) throw new Error(await response.text());
    const result = await response.json();
    if(!result.text?.trim()) throw new Error('文字模型未返回有效内容');
    return result.text.trim();
}
async function planSmartApplication(nodeId){
    const node = nodes.find(item => item.id === nodeId);
    if(!node || node.running) return;
    const inputs = smartApplicationInputs(node);
    if(!inputs.product.length) return toast('请先添加产品图');
    node.running = true; node.appPlanning = true; node.appStatus = '正在规划每屏主题…'; render();
    try {
        const request = smartApplicationRequest(node,inputs);
        const textOnly=node.appChatModel==='deepseek-v4-pro';
        node.appPlan = await smartApplicationChat(node,`${textOnly?'仅根据以下用户提供的文字需求策划；你没有看到产品图片，禁止推断外观、参数或认证。':'根据图片和以下需求'}，规划${node.appCount}屏产品详情图。只返回 JSON 字符串数组，每个元素包含一屏的主题、短标题、构图和需要的真实信息；未知参数标注待补充。不要生成图片。\n${request.prompt}`,textOnly?[]:request.refs);
        const raw=node.appPlan.replace(/^```(?:json)?\s*|\s*```$/g,'').trim();
        let screens;try{screens=JSON.parse(raw);}catch(_){screens=node.appPlan.split(/\n(?=\s*(?:\d+[.、）)]|第.+屏))/).map(s=>s.trim()).filter(Boolean);}
        if(!Array.isArray(screens)||screens.length!==Number(node.appCount))throw new Error('策划屏数与所选数量不一致，请调整策划后重试');
        smartApplicationOptions(node).screens=screens.map(s=>typeof s==='string'?s:JSON.stringify(s));
        node.appStatus = '策划已填入，可逐屏编辑后生成。';
    } catch(error){node.appStatus = `策划失败：${String(error.message).slice(0,240)}`; toast(node.appStatus);}
    finally {node.running = false; node.appPlanning = false; render(); scheduleSave();}
}
function smartReviewSignature(node, inputs){
    const fields = Object.fromEntries(Object.entries(node).filter(([key]) =>
        (key.startsWith('app') && !['appStatus','appResult','appLastOutput','appBatchId','appBatchCount','appGuideRefs','appPlanning','appMaskUrl','appMaskSource'].includes(key)) ||
        ['application','runSettings','localSkill','productName'].includes(key)));
    const canonical=value=>Array.isArray(value)?value.map(canonical):value && typeof value==='object'?
        Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
    return JSON.stringify(canonical({fields,inputs}));
}
async function prepareSmartApplicationReview(node, inputs, run, ratioPreset){
    node.running=true; node.appStatus='正在整理生成审核…'; render();
    try {
        smartApplicationOptions(node);
        const signature=smartReviewSignature(node,inputs), jobs=[];
        const count=node.application==='transfer'?inputs.scene.length:['compose','retouch','repair','layout','relight'].includes(node.application)?1:Math.max(1,Math.min(8,Number(node.appCount)||1));
        for(let index=0;index<count;index++){
            const currentInputs=node.application==='transfer'?{...inputs,scene:[inputs.scene[index]]}:inputs;
            node.appGuideRefs=await smartApplicationPrepareGuides(node,currentInputs);
            if(!nodes.includes(node))return;
            const request=smartApplicationRequest(node,currentInputs,index);
            if(ratioPreset)request.prompt+=`\n画幅要求：${ratioPreset.label}，宽高比 ${ratioPreset.ratio}。按这个横向画幅组织完整构图，不添加边框或留白来模拟比例。`;
            const o=smartApplicationOptions(node), jobRun=cloneSmartSettings(run);
            jobRun.applicationContext={type:node.application,source_url:currentInputs.product[0]?.url||'',mask_url:node.appMaskUrl||'',protect:o.protect!==false,feather:o.feather||0,background:o.background||'原图'};
            jobs.push(JSON.parse(JSON.stringify({request,run:jobRun})));
        }
        if(signature!==smartReviewSignature(node,inputs))return toast('整理过程中参数发生变化，请重新整理');
        pushUndo();
        let review=nodes.find(item=>item.type==='smart-review' && item.reviewSourceId===node.id && !item.reviewSubmitted);
        if(!review){
            review={id:uid('review'),type:'smart-review',images:[],reviewSourceId:node.id,x:(node.x||0)+(node.w||640)+100,y:node.y||0,w:600,h:920};
            nodes.push(review); addConnection(node.id,review.id,'flow');
        }
        Object.assign(review,{reviewJobs:jobs,reviewSignature:signature,reviewTitle:smartApplicationDefinition(node).title,reviewSkill:node.localSkill?.name||'未选择',reviewStatus:'等待审核 · 尚未提交生图',reviewSubmitted:false,reviewUpdatedAt:Date.now()});
        node.appStatus='已整理到右侧审核节点，确认后才会生图。';
        selectedId=review.id; selectedIds=[review.id];
    } catch(error){node.appStatus=`整理失败：${error.message}`; toast(node.appStatus);}
    finally {node.running=false;delete node.appGuideRefs;render();scheduleSave();}
}
function smartReviewBodyHtml(node){
    const locked=node.running || node.reviewSubmitted;
    const providerLabel=run=>typeof apiProviders!=='undefined'?(apiProviders.find(p=>p.id===run.provider_id)?.name || run.provider_id || run.engine || ''):(run.provider_id || run.engine || '');
    const ratioLabel=run=>run.customRatio || ({square:'1:1',portrait43:'3:4',landscape43:'4:3',story:'9:16',wide:'16:9'}[run.ratio]) || run.ratio || '自动';
    return `<section class="application-card review-card"><header class="application-node-header"><i data-lucide="clipboard-check"></i><div><strong>生成审核</strong><small>${escapeHtml(node.reviewTitle||'')} · 临时节点</small></div><button type="button" class="application-close" data-review-delete aria-label="删除审核节点">×</button></header>
    <div class="application-form"><p class="application-status">所有提示词已包含节点选项、连接文字与 Skills 内容。可编辑后确认提交。</p>
    ${(node.reviewJobs||[]).map((job,index)=>`<article class="review-job"><h3>画面 ${index+1} / ${node.reviewJobs.length}</h3><dl class="review-parameters"><dt>平台 / 模型</dt><dd>${escapeHtml(providerLabel(job.run))} / ${escapeHtml(job.run.model||'工作流')}</dd><dt>Skills</dt><dd>${escapeHtml(node.reviewSkill)}</dd><dt>比例 / 画质</dt><dd>${escapeHtml(ratioLabel(job.run))} / ${escapeHtml(job.run.resolution||'自动')} · ${escapeHtml(job.run.quality||'auto')}</dd></dl>
    <div class="review-refs">${job.request.refs.map((ref,i)=>`<a href="${escapeHtml(ref.url)}" target="_blank" rel="noopener"><img src="${escapeHtml(ref.url)}" alt="参考图 ${i+1}"/><span>图${i+1}${ref.applicationGuide?' · 选区/布局指引':''}</span></a>`).join('')}</div>
    <label class="review-prompt-label" for="${node.id}-prompt-${index}">最终提交提示词</label><textarea id="${node.id}-prompt-${index}" class="review-prompt" data-review-prompt="${index}" ${locked?'disabled':''}>${escapeHtml(job.request.prompt)}</textarea>
    <button type="button" data-review-copy="${index}">复制提示词</button><details><summary>参考图与生成参数</summary><pre>${escapeHtml(JSON.stringify({references:job.request.refs,settings:job.run},null,2))}</pre></details></article>`).join('')}
    </div><div class="application-settings"><p class="application-status" role="status">${escapeHtml(node.reviewStatus||'等待审核')}</p><div class="application-footer"><button type="button" data-review-refresh ${locked?'disabled':''}>重新整理</button><button type="button" class="application-run" data-review-confirm ${locked?'disabled':''}>${node.running?'生成中…':node.reviewSubmitted?'已确认提交':'确认并生成'}</button></div></div></section>`;
}
function bindSmartReviewControls(el,node){
    el.querySelectorAll('button,textarea,a,details,.application-form').forEach(control=>{
        for(const event of ['mousedown','click','dblclick','keydown','wheel'])control.addEventListener(event,e=>e.stopPropagation());
    });
    el.querySelectorAll('[data-review-prompt]').forEach(control=>control.addEventListener('input',()=>{
        node=nodes.find(item=>item.id===node.id)||node;
        if(node.running||node.reviewSubmitted)return;
        node.reviewJobs[Number(control.dataset.reviewPrompt)].request.prompt=control.value;node.reviewUpdatedAt=Date.now();scheduleSave();
    }));
    el.querySelectorAll('[data-review-copy]').forEach(control=>control.addEventListener('click',async()=>{
        try {await navigator.clipboard.writeText(node.reviewJobs[Number(control.dataset.reviewCopy)].request.prompt);toast('提示词已复制');}
        catch {toast('复制失败，请选中提示词手动复制');}
    }));
    el.querySelector('[data-review-delete]')?.addEventListener('click',()=>{if(node.running)return toast('请等待当前任务处理完成');deleteNode(node.id);});
    el.querySelector('[data-review-refresh]')?.addEventListener('click',()=>runSmartApplication(node.reviewSourceId));
    el.querySelector('[data-review-confirm]')?.addEventListener('click',()=>runSmartApplication(node.reviewSourceId,node));
}
async function runSmartApplication(nodeId, approvedReview=null){
    let node = nodes.find(item => item.id === nodeId);
    if(!node){if(approvedReview)toast('上游应用节点已删除，请重新创建应用');return;}
    if(node.running) return;
    const definition = smartApplicationDefinition(node), inputs = smartApplicationInputs(node);
    if(!inputs[definition.role].length) return toast(`请添加${SMART_APP_ROLE_LABELS[definition.role]}`);
    if(definition.second && !inputs[definition.second].length) return toast(`还需要${SMART_APP_ROLE_LABELS[definition.second]}，点击对应行的 ＋ 添加`);
    if(node.application==='compose' && !appVisibleProducts(node,inputs).length)return toast('请至少显示一个产品图层');
    const totalRefs = ['product','scene','template','reference'].reduce((sum,role) => sum + inputs[role].length,0);
    if(totalRefs > SMART_REFERENCE_IMAGE_MAX) return toast(`本次参考图合计最多 ${SMART_REFERENCE_IMAGE_MAX} 张，请移除多余图片`);
    const run = cloneSmartSettings(node.runSettings || settings); run.count = 1;
    if(node.runSettings?.ratio == null && ['generate','detail','layout','relight'].includes(node.application))run.ratio='auto';
    if(run.ratio === 'auto'){
        // Auto disables the node's shape override, including stale custom sizes.
        ['customRatio','customSize','customWidth','customHeight'].forEach(key => delete run[key]);
    }
    const ratioPreset = smartApplicationRatioPreset(run.ratio);
    if(ratioPreset){
        run.ratio='custom'; run.customRatio=ratioPreset.ratio;
        // A platform preset describes a composition ratio; the quality control
        // still chooses its pixel resolution. Discard unrelated custom sizes.
        if(run.resolution==='custom' || run.resolution==='auto')run.resolution='2k';
        run.customSize='';
    }
    const ratioNames={'1:1':'square','3:4':'portrait43','4:3':'landscape43','9:16':'story','16:9':'wide'};
    run.ratio=ratioNames[run.ratio] || run.ratio;
    if(!run.ratio){
        const source = inputs[node.application==='transfer'?'scene':definition.role][0];
        const width = Number(source?.natural_w || source?.width || source?.w || source?.original_w), height = Number(source?.natural_h || source?.height || source?.h || source?.original_h);
        if(width > 0 && height > 0){
            run.ratio = 'custom'; run.customRatio = `${width}:${height}`;
            const maxEdge = run.resolution === '4k' ? 3840 : run.resolution === '1k' ? 1536 : 2048;
            const factor = maxEdge / Math.max(width,height);
            run.customWidth = Math.round(width * factor / 8) * 8; run.customHeight = Math.round(height * factor / 8) * 8;
            run.customSize = `${run.customWidth}x${run.customHeight}`;
        }
    }
    if(!definition.text && run.apiKind === 'video') return toast('请选择图像平台和图像模型');
    if(!definition.text && typeof apiProviders!=='undefined' && apiProviders.some(p=>p.id===run.provider_id && p.enabled===false))return toast('原图像平台已暂时禁用，请选择其他可用平台和模型');
    if(!definition.text && isApiLikeEngine(run.engine) && (!run.provider_id || !run.model)) return toast('请先配置并选择图像平台和模型');
    if(node.application==='repair' && (!smartApplicationOptions(node).strokes.length || !(node.appPrompt?.trim() || inputs.text.length)))return toast('请先选择修复区域并描述修改要求');
    if(!definition.text && (node.application!=='generate' || approvedReview)){
        if(!approvedReview)return prepareSmartApplicationReview(node,inputs,run,ratioPreset);
        if(!nodes.includes(approvedReview)||approvedReview.reviewSourceId!==nodeId||approvedReview.running||approvedReview.reviewSubmitted)return;
        if(approvedReview.reviewSignature!==smartReviewSignature(node,inputs)){
            approvedReview.reviewStatus='上游参数或参考图已变更，请重新整理后审核';render();scheduleSave();return toast(approvedReview.reviewStatus);
        }
        if(!approvedReview.reviewJobs?.length || approvedReview.reviewJobs.some(job=>!job.request.prompt.trim()))return toast('每张画面的提示词都不能为空');
        approvedReview.running=true;approvedReview.reviewSubmitted=true;approvedReview.reviewUpdatedAt=Date.now();approvedReview.reviewStatus='已确认，正在提交审核内容…';
    }
    node.running = true; node.appBatchId=uid('appbatch'); node.appStatus = '正在准备…'; render(); scheduleSave();
    let output = null;
    try {
        if(definition.text){
            const request = smartApplicationRequest(node,inputs);
            const text = await smartApplicationChat(node,request.prompt,request.refs);
            if(!nodes.includes(node)) return;
            pushUndo();
            output = createPromptNode(node.x + 660,node.y,{skipUndo:true,select:false}); node.appResult=text; output.text = text; output.w = 360; output.h = 380;
            addConnection(node.id,output.id,'flow'); node.appStatus = '已生成可编辑的提示词节点。';
        } else {
            const generationJobs = approvedReview ? (node.application==='generate'?approvedReview.reviewJobs.slice(0,1):approvedReview.reviewJobs) : Array.from({length:1},(_,index)=>{
                const request=smartApplicationRequest(node,inputs,index);
                if(ratioPreset)request.prompt+=`\n画幅要求：${ratioPreset.label}，宽高比 ${ratioPreset.ratio}。`;
                return {request,run:cloneSmartSettings(run)};
            });
            const count = generationJobs.length;
            node.appBatchCount=count;
            for(let index=0; index<count; index++){
                if(!nodes.includes(node)) break;
                node.appStatus = `正在生成 ${index + 1} / ${count}…`;
                const currentInputs=node.application==='transfer'?{...inputs,scene:[inputs.scene[index]]}:inputs;
                const request = generationJobs[index].request;
                Object.assign(run,cloneSmartSettings(generationJobs[index].run));
                const meta = {...snapshotRunMeta(request.prompt,node.id,request.displayPrompt,request.refs),settings:run};
                pushUndo(); output = createPendingOutputFromSource(approvedReview || node,1,meta,{connectSource:false,selectOutput:false,refs:request.refs});
                output.runSettings = cloneSmartSettings(run); output.applicationSource = node.application;
                output.applicationBatchId=node.appBatchId;
                render(); scheduleSave();
                const log = smartRunSnapshot(node,request.prompt,request.refs,'image'), started = nowMs();
                if(isApiLikeEngine(run.engine)){
                    const tasks = await runApiGeneration(request.prompt,request.refs,run);
                    if(!nodes.some(item=>item.id===nodeId))return;
                    if(!nodes.some(item=>item.id===output.id))continue;
                    output.pendingTasks = tasks.taskIds.map(taskId => ({taskId,kind:'image',providerId:tasks.providerId,model:tasks.model}));
                    await saveCanvas();
                    await resumeSmartPendingNode(output,{run:log,runLogStart:started});
                    if(!nodes.some(item=>item.id===nodeId))return;
                    if(!nodes.some(item=>item.id===output.id))continue;
                    node = nodes.find(item=>item.id===nodeId) || node;
                    output = nodes.find(item=>item.id===output.id) || output;
                    if(smartRecoverableImageTask(output) || output.jimengPending){node.appStatus = '任务已提交，可在结果节点查询进度。'; break;}
                    if(!output.images?.length) throw new Error('未返回有效图片，可查看结果节点任务状态');
                } else {
                    const result = await generateUrlsForCurrentSettings(node,request.prompt,request.refs,run);
                    if(!nodes.some(item=>item.id===nodeId))return;
                    if(!nodes.some(item=>item.id===output.id))continue;
                    if(!result.urls?.length) throw new Error('当前工作流未返回图片');
                    finalizePendingNode(output,result.urls,meta,'image');
                }
                node.appLastOutput=output.images?.[0]?.url || '';
                addSmartGenerationLog({run:log,outputs:output.images || [],runMs:nowMs() - started});
                node.appStatus = `已完成 ${index + 1} / ${count}，结果位于下游节点。`;
                scheduleSave();
            }
        }
    } catch(error){
        if(!nodes.some(item=>item.id===nodeId) || (output && !nodes.some(item=>item.id===output.id)))return;
        node.appStatus = `生成失败：${String(error.message || error).slice(0,240)}`;
        if(output && !output.pendingTasks?.length && output.type === 'smart-image'){
            output=nodes.find(item=>item.id===output.id) || output;
            if(typeof markSmartGenerationFailed==='function')markSmartGenerationFailed(output,node.appStatus);
            else {output.pending=0;output.error=node.appStatus;}
        }
        toast(node.appStatus);
    } finally {node = nodes.find(item=>item.id===nodeId) || node; node.running = false; delete node.appGuideRefs; if(approvedReview){approvedReview.running=false;approvedReview.reviewStatus=node.appStatus;} render(); scheduleSave();}
}
function refreshSmartApplicationOutputProgress(output){
    const source=nodes.find(n=>n.id===output?.sourceNodeId && n.type==='smart-application');
    if(!source || source.running)return;
    const children=nodes.filter(n=>n.sourceNodeId===source.id && (!source.appBatchId || n.applicationBatchId===source.appBatchId));
    const expected=Number(source.appBatchCount) || (source.application==='detail'||source.application==='generate'?Number(source.appCount)||1:children.length);
    const done=children.filter(n=>n.images?.length).length;
    const pending=children.some(n=>n.pending || n.pendingTasks?.length);
    if(done===expected && !pending)source.appStatus=`已完成 ${done} / ${expected}，结果位于下游节点。`;
    else if(pending)source.appStatus=`已完成 ${done} / ${expected}，其余任务仍在处理中。`;
    render();scheduleSave();
}
document.addEventListener('mousedown',event => {
    if(smartApplicationMenuState && !event.target.closest('#smartApplicationMenu')) closeSmartApplicationMenu();
},true);
document.addEventListener('keydown',event => {
    if(event.key !== 'Escape') return;
    if(smartApplicationMenuState){event.preventDefault(); event.stopImmediatePropagation(); closeSmartApplicationMenu(true);}
    else if(portDragState){
        event.preventDefault(); event.stopImmediatePropagation();
        portDragState = null; shell.classList.remove('port-dragging'); clearPortDragVisual(); discardPendingUndo();
    }
},true);
window.addEventListener('resize',() => closeSmartApplicationMenu());
window.addEventListener('load',() => {
    fetch('/api/local-skills').then(response => response.ok ? response.json() : Promise.reject(new Error('读取 Skills 失败'))).then(data => {
        smartApplicationSkills = data.skills || [];
        if(nodes.some(node => node.type === 'smart-application')) render();
    }).catch(() => {});
});
shell.addEventListener('wheel',() => closeSmartApplicationMenu(),{passive:true});
