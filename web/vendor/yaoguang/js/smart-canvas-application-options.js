/* Task-specific controls and serializable editing guides for application nodes. */
const SMART_APP_DEFAULTS = {
    retouch:{category:'通用',projects:['清理污点','曝光校正','边缘整理','优化反光','保留自然纹理'],material:'自然',background:'原图',strength:'标准',protect:true},
    repair:{method:'去除瑕疵',brush:32,feather:4,protect:true,tool:'画笔',strokes:[]},
    transfer:{mode:'放入空场景',placement:'自动',scale:35,perspective:'自动',light:true,shadow:true,protect:true,tool:'标记位置',strokes:[]},
    compose:{arrangement:'自由摆放',occlusion:'按图层顺序',light:true,depth:true,keepScene:true,layers:{},tool:'移动'},
    generate:{keepSubject:true,keepComposition:false,keepColor:false,strength:60,referenceRoles:{}},
    describe:{target:'复现画面',dimensions:['主体','构图','材质','光影','配色','背景'],format:'完整提示词',detail:'标准'},
    detail:{color:'#d6bc98',font:'简洁现代',sellingPoints:'',screens:[]},
    layout:{preserve:['布局','文字层级','留白比例'],headline:'',subtitle:'',sellingPoints:'',colorMode:'沿用模板',color:'#d6bc98',fit:'完整展示'}
};
const SMART_APP_ACTIONS = {relight:'重新打光',retouch:'开始精修',repair:'修复选区',transfer:'开始迁移',compose:'生成合成图',generate:'生成',describe:'分析图片',detail:'生成详情图组',layout:'生成新画面'};
function smartApplicationOptions(node){
    const defaults = SMART_APP_DEFAULTS[node.application] || {};
    if(!node.appOptions) node.appOptions = JSON.parse(JSON.stringify(defaults));
    for(const [key,value] of Object.entries(defaults)) if(node.appOptions[key] === undefined) node.appOptions[key] = JSON.parse(JSON.stringify(value));
    return node.appOptions;
}
function appOptionSelect(label,key,values,value){return smartApplicationSelect(label,`option:${key}`,values,value);}
function appOptionInput(label,key,value,placeholder='',type='text'){
    return `<label class="application-field"><span>${escapeHtml(label)}</span><input type="${type}" data-app-field="option:${key}" value="${escapeHtml(String(value || ''))}" placeholder="${escapeHtml(placeholder)}"></label>`;
}
function appOptionChips(label,key,values,value,multiple=false){
    return `<fieldset class="application-choice"><legend>${escapeHtml(label)}</legend><div class="application-chips">${values.map(item => `<button type="button" data-app-option="${key}" data-app-value="${escapeHtml(item)}" ${multiple ? 'data-app-multiple' : ''} aria-pressed="${multiple ? value.includes(item) : value === item}">${escapeHtml(item)}</button>`).join('')}</div></fieldset>`;
}
function appOptionCheck(label,key,value){return `<label class="application-check"><input type="checkbox" data-app-field="option:${key}" ${value ? 'checked' : ''}><span>${escapeHtml(label)}</span></label>`;}
function appOptionRange(label,key,value,min,max,unit=''){
    return `<label class="application-slider"><span>${escapeHtml(label)}</span><input type="range" data-app-field="option:${key}" min="${min}" max="${max}" value="${value}"><output>${value}${unit}</output></label>`;
}
function appPromptHtml(node,inputs,label='补充要求（可选）',placeholder='填写本次要求…'){
    return `<div class="application-prompt-label"><span>${label}</span><button type="button" data-app-text>连接文本节点 ＋</button>${inputs.text.length ? '<button type="button" data-app-disconnect-text>断开文本</button>' : ''}</div>${inputs.text.length ? `<div class="application-connected-text">${escapeHtml(inputs.text.join('\n'))}</div>` : ''}<textarea data-app-field="appPrompt" rows="3" placeholder="${placeholder}">${escapeHtml(node.appPrompt || '')}</textarea>`;
}
function appTextModelsHtml(node,label='文本模型（支持识图）'){
    return `<div class="application-fields-grid">${smartApplicationSelect('文本平台','appChatProvider',chatApiProviders().map(p => [p.id,p.name || p.id]),node.appChatProvider)}${smartApplicationSelect(label,'appChatModel',providerChatModels(node.appChatProvider),node.appChatModel)}</div>`;
}
function appSkillHtml(node){
    const options = [['','选择技能（可选）'],...smartApplicationSkills.map(s => [s.id,s.name])];
    if(node.localSkill && !options.some(([id]) => id === node.localSkill.id)) options.push([node.localSkill.id,node.localSkill.name]);
    return smartApplicationSelect('Skills','skill',options,node.localSkill?.id || '');
}
function appImageModelsHtml(node){
    const run=node.runSettings || {}, providers=imageProviders().map(p=>[p.id,p.name || p.id]);
    const disabled=typeof apiProviders!=='undefined' && apiProviders.find(p=>p.id===run.provider_id)?.enabled===false;
    if(disabled)providers.unshift([run.provider_id,'原平台已禁用，请切换',true]);
    else if(!providers.some(([id])=>id===run.provider_id)) providers.unshift(['__current','当前画布工作流']);
    const models=providerImageModels(run.provider_id);
    return `<div class="application-fields-grid application-models">${smartApplicationSelect('生图平台','provider',providers,run.provider_id || '__current')}${smartApplicationSelect('生图模型','model',disabled?[['','请选择可用平台和模型',true]]:models.length ? models : [[run.model || '',run.model || '当前工作流']],disabled?'':run.model)}${node.application==='generate'?'':appSkillHtml(node)+smartApplicationSelect('画质','resolution',[['1k','标准 1K'],['2k','高清 2K'],['4k','超清 4K']],run.resolution || '2k')}</div>`;
}
const SMART_APP_RATIO_PRESETS = {
    'amazon-aplus': {label:'亚马逊 A+ · 970×600',ratio:'970:600'},
    'amazon-aplus-banner': {label:'亚马逊 A+ 横幅 · 970×300',ratio:'970:300'},
    'amazon-premium-aplus': {label:'亚马逊超级 A+ · 1464×600',ratio:'1464:600'},
};
function smartApplicationRatioPreset(value){return SMART_APP_RATIO_PRESETS[value] || null;}
function appRatioHtml(node,label='画面比例'){
    const custom=node.runSettings?.ratio==='custom'?[['custom',`自定义 · ${node.runSettings.customRatio || '原尺寸'}`]]:[];
    return smartApplicationSelect(label,'ratio',[['auto','Auto'],['','跟随输入图'],['1:1','1:1'],['3:4','3:4'],['4:3','4:3'],['9:16','9:16'],['16:9','16:9'],...custom,...Object.entries(SMART_APP_RATIO_PRESETS).map(([key,preset])=>[key,preset.label])],node.runSettings?.ratio ?? 'auto');
}
function appReferenceRowsHtml(node,inputs,roles){
    return roles.map(role=>`<div class="application-reference-row"><div class="application-reference-label"><strong>${SMART_APP_ROLE_LABELS[role]}</strong><small>${inputs[role].length} / 20</small></div><div class="application-thumbnails">${inputs[role].map((image,index)=>`<div class="application-thumbnail"><img src="${escapeHtml(image.url)}" alt="${SMART_APP_ROLE_LABELS[role]} ${index+1}" draggable="false"><button type="button" data-app-remove-role="${role}" data-app-remove-index="${index}" aria-label="移除${SMART_APP_ROLE_LABELS[role]} ${index+1}">×</button>${node.application==='generate' ? `<select aria-label="参考图作用" data-app-ref-role="${escapeHtml(image.url)}">${['主体','风格','构图','色彩'].map(r=>`<option ${(smartApplicationOptions(node).referenceRoles[image.url] || '主体')===r?'selected':''}>${r}</option>`).join('')}</select>`:''}</div>`).join('') || `<span class="application-reference-placeholder">添加${SMART_APP_ROLE_LABELS[role]}${role==='reference'?'（可选）':''}</span>`}</div><button type="button" class="application-reference-add" data-app-add="${role}" aria-label="添加${SMART_APP_ROLE_LABELS[role]}">＋</button></div>`).join('');
}
function appStageHtml(node,inputs){
    const type=node.application, o=smartApplicationOptions(node);
    const role=['transfer','compose'].includes(type)?'scene':type==='layout'?'template':type==='generate' || type==='describe'?'reference':'product';
    const image=inputs[role][0];
    if(type==='describe')return image?`<div class="application-source-preview"><img src="${escapeHtml(image.url)}" alt="反推源图"><button type="button" data-app-add="reference">添加源图</button></div>`:'';
    return `<div class="application-stage" data-app-stage tabindex="0" aria-label="${type==='repair'?'修复选区编辑':type==='transfer'?'迁移落位编辑':type==='compose'?'产品布局编辑':'源图预览'}">${image?`<img src="${escapeHtml(image.url)}" alt="${SMART_APP_ROLE_LABELS[role]}预览" draggable="false">`:`<span>添加${SMART_APP_ROLE_LABELS[role]}后在这里预览</span>`}${['repair','transfer','compose'].includes(type)?'<canvas data-app-overlay></canvas>':''}</div>${type==='retouch' && node.appLastOutput ? `<button type="button" data-app-compare>原图 / 精修结果对比</button>`:''}`;
}
function appScreenRowsHtml(node){
    const o=smartApplicationOptions(node), count=Math.max(1,Math.min(8,Number(node.appCount)||6));
    const topics=['产品主视觉','核心卖点','使用场景','细节展示','结构展示','收尾展示','使用步骤','信息补充'];
    while(o.screens.length<count)o.screens.push(topics[o.screens.length]);
    return `<div class="application-screen-list">${o.screens.slice(0,count).map((text,i)=>`<div class="application-screen-row"><span>${String(i+1).padStart(2,'0')}</span><textarea rows="1" aria-label="第${i+1}屏策划" data-app-screen="${i}">${escapeHtml(text)}</textarea><button type="button" data-app-screen-move="${i}" data-direction="-1" aria-label="上移第${i+1}屏">↑</button><button type="button" data-app-screen-move="${i}" data-direction="1" aria-label="下移第${i+1}屏">↓</button></div>`).join('')}</div>`;
}
function appVisibleProducts(node,inputs){
    const o=smartApplicationOptions(node);
    return inputs.product.filter(image=>o.layers[image.url]?.visible!==false);
}
function appLayerRowsHtml(node,inputs){
    const o=smartApplicationOptions(node);
    return `<div class="application-layer-list">${inputs.product.map((image,i)=>{
        const layer=o.layers[image.url] || {};
        return `<div class="application-layer-row"><img src="${escapeHtml(image.url)}" alt="产品图层 ${i+1}"><button type="button" data-app-layer-select="${escapeHtml(image.url)}" aria-pressed="${o.activeLayer===image.url}">${escapeHtml(image.name || `产品 ${i+1}`)}</button><button type="button" data-app-layer-action="visible" data-url="${escapeHtml(image.url)}" aria-label="显示或隐藏产品">${layer.visible===false?'隐藏':'显示'}</button><button type="button" data-app-layer-action="locked" data-url="${escapeHtml(image.url)}" aria-label="锁定或解锁图层">${layer.locked?'已锁':'锁定'}</button><button type="button" data-app-layer-action="up" data-url="${escapeHtml(image.url)}" aria-label="前移图层">↑</button><button type="button" data-app-layer-action="down" data-url="${escapeHtml(image.url)}" aria-label="后移图层">↓</button></div>`;
    }).join('')}</div>`;
}
function appTaskBodyHtml(node,inputs){
    const o=smartApplicationOptions(node), type=node.application;
    const stage=appStageHtml(node,inputs), refs=roles=>appReferenceRowsHtml(node,inputs,roles);
    if(type==='relight')return stage+refs(['product'])+
        appPromptHtml(node,inputs,'补充提示词（可选）','留空即可让 AI 重新打光，也可填写你希望的光影效果');
    if(type==='retouch')return stage+refs(['product'])+
        appOptionChips('产品类目','category',['通用','数码家电','饰品五金','服饰箱包','玻璃透明','包装袋','毛绒玩具'],o.category)+
        appOptionChips('精修项目','projects',['清理污点','曝光校正','边缘整理','优化反光','保留自然纹理'],o.projects,true)+
        appOptionChips('材质处理','material',['自然','突出质感','柔和反光'],o.material)+
        appOptionChips('背景','background',['原图','纯白','透明'],o.background)+
        appOptionChips('精修强度','strength',['轻度','标准','增强'],o.strength)+
        appOptionCheck('锁定产品结构、颜色、标志与文字','protect',o.protect)+
        `<details><summary>补充要求（可选）</summary>${appPromptHtml(node,inputs)}</details>`;
    if(type==='repair')return stage+`<div class="application-tool-row">${['画笔','橡皮','框选','撤销','清空'].map(t=>`<button type="button" data-app-tool="${t}" aria-pressed="${o.tool===t}">${t}</button>`).join('')}</div>`+
        appOptionRange('笔刷大小','brush',o.brush,4,100,' px')+refs(['product','reference'])+
        appOptionChips('修复方式','method',['去除瑕疵','补全缺损','替换局部'],o.method)+appPromptHtml(node,inputs,'描述选区需要怎样修改（必填）','例如：清除机身划痕，恢复磨砂质感')+
        appOptionRange('选区边缘融合','feather',o.feather,0,20,' px')+appOptionCheck('保护选区外画面','protect',o.protect)+
        '<small class="application-help">在预览图上涂抹或框选；也可点“选择中央区域”。</small><button type="button" data-app-central-region>选择中央区域</button>';
    if(type==='transfer')return stage+`<div class="application-tool-row">${['标记位置','涂抹替换区域','撤销','清空'].map(t=>`<button type="button" data-app-tool="${t}" aria-pressed="${o.tool===t}">${t}</button>`).join('')}</div>`+refs(['product','scene'])+
        appOptionChips('迁移方式','mode',['放入空场景','替换场景中物体'],o.mode)+
        `<div class="application-fields-grid">${appOptionSelect('位置','placement',['自动','按标记位置'],o.placement)}${appOptionSelect('透视匹配','perspective',['自动','正面','俯视','侧面'],o.perspective)}</div>`+
        appOptionRange('产品大小','scale',o.scale,10,80,'%')+appOptionCheck('匹配光向','light',o.light)+appOptionCheck('生成接触阴影','shadow',o.shadow)+appOptionCheck('保留产品结构与标志','protect',o.protect)+appPromptHtml(node,inputs)+
        '<small class="application-help">每张目标场景生成一张图；位置按相对坐标应用到各场景。</small>';
    if(type==='compose')return stage+`<div class="application-tool-row">${['移动','缩放','对齐'].map(t=>`<button type="button" data-app-tool="${t}" aria-pressed="${o.tool===t}">${t}</button>`).join('')}</div>`+refs(['scene','product'])+appLayerRowsHtml(node,inputs)+
        appOptionChips('摆放方案','arrangement',['自由摆放','主次组合','平铺陈列'],o.arrangement)+
        appOptionSelect('遮挡关系','occlusion',['按图层顺序','自动融合'],o.occlusion)+
        appOptionRange('选中产品大小','layerScale',o.layerScale || 30,10,80,'%')+
        `<div class="application-fields-grid">${appOptionRange('产品横向位置','layerX',Math.round((o.layers[o.activeLayer]?.x ?? .5)*100),0,100,'%')}${appOptionRange('产品纵向位置','layerY',Math.round((o.layers[o.activeLayer]?.y ?? .6)*100),0,100,'%')}</div>`+
        appOptionCheck('统一光影','light',o.light)+appOptionCheck('匹配景深','depth',o.depth)+appOptionCheck('保留场景布局','keepScene',o.keepScene)+appPromptHtml(node,inputs,'场景补充要求（可选）');
    if(type==='generate')return stage+refs(['reference'])+appPromptHtml(node,inputs,'生成描述','描述你希望生成的画面…')+
        `<div class="application-fields-grid">${appRatioHtml(node)}</div>`;
    if(type==='describe')return stage+refs(['reference'])+appTextModelsHtml(node)+appSkillHtml(node)+
        appOptionChips('分析目标','target',['复现画面','提取风格','仅分析产品'],o.target)+
        appOptionChips('分析维度','dimensions',['主体','构图','材质','光影','配色','背景','可见文字'],o.dimensions,true)+
        `<div class="application-fields-grid">${smartApplicationSelect('输出语言','appLanguage',['中文','英文'],node.appLanguage || '中文')}${appOptionSelect('输出格式','format',['完整提示词','分项描述'],o.format)}</div>`+
        appOptionChips('描述详细度','detail',['简短','标准','详细'],o.detail)+
        `<details><summary>补充分析要求</summary>${appPromptHtml(node,inputs)}</details>`+
        `<label class="application-field"><span>提示词结果（可编辑）</span><textarea data-app-field="appResult" rows="5" placeholder="分析后在这里查看并编辑结果">${escapeHtml(node.appResult || '')}</textarea></label><div class="application-tool-row"><button type="button" data-app-copy>复制</button><button type="button" data-app-export-text>创建文本节点</button><button type="button" data-app-send-generate>连接到生图</button></div>`;
    if(type==='detail')return refs(['product','reference'])+
        `<label class="application-field"><span>产品名称</span><input data-app-field="productName" value="${escapeHtml(node.productName || '')}" placeholder="输入产品名称"></label>`+
        `<label class="application-field"><span>已确认的卖点与参数</span><textarea rows="3" data-app-field="option:sellingPoints" placeholder="仅使用你提供的真实产品信息">${escapeHtml(o.sellingPoints)}</textarea></label>`+
        `<div class="application-fields-grid">${smartApplicationSelect('投放平台','appPlatform',['通用电商','淘宝 / 天猫','京东','亚马逊','独立站'],node.appPlatform || '通用电商')}${smartApplicationSelect('画面数量','appCount',Array.from({length:8},(_,i)=>[i+1,`${i+1} 屏`]),node.appCount || 6)}${appRatioHtml(node)}${smartApplicationSelect('图中文字','appTypography',['带字排版','不添加文字','少量文字'],node.appTypography)}${appOptionInput('配色','color',o.color,'','color')}${appOptionSelect('字体风格','font',['简洁现代','精致衬线','科技感','活泼圆体'],o.font)}${smartApplicationSelect('输出语言','appLanguage',['中文','英文'],node.appLanguage)}</div>`+
        '<div class="application-plan-head"><strong>分屏策划</strong><button type="button" data-app-plan>AI 生成策划</button></div>'+appTextModelsHtml(node,'策划模型（文本）')+appScreenRowsHtml(node)+
        `<details><summary>补充要求 / 完整策划</summary>${appPromptHtml(node,inputs)}<textarea rows="3" data-app-field="appPlan" placeholder="完整策划（可选）">${escapeHtml(node.appPlan || '')}</textarea></details>`;
    if(type==='layout')return stage+refs(['template','product'])+
        appOptionChips('沿用内容','preserve',['布局','文字层级','留白比例','配色','装饰素材'],o.preserve,true)+
        appOptionInput('主标题','headline',o.headline,'填写你自己的主标题')+appOptionInput('副标题','subtitle',o.subtitle)+appOptionInput('卖点','sellingPoints',o.sellingPoints)+
        appOptionChips('色彩方案','colorMode',['沿用模板','跟随产品','自定义'],o.colorMode)+(o.colorMode==='自定义'?appOptionInput('自定义配色','color',o.color,'','color'):'')+
        `<div class="application-fields-grid">${appRatioHtml(node,'输出尺寸 / 比例')}${appOptionSelect('产品适配','fit',['完整展示','填满产品区域'],o.fit)}</div>`+appPromptHtml(node,inputs);
    return '';
}
function smartApplicationTaskInstructions(node,roles,screen){
    const o=smartApplicationOptions(node), type=node.application;
    if(type==='retouch')return `产品类目：${o.category}。只执行以下精修项目：${o.projects.join('、') || '不做额外精修'}。材质处理：${o.material}；背景：${o.background==='透明'?'均匀纯绿色色键背景（#00FF00），供后续透明抠图；绿背景不反射到产品，保留产品原本颜色':o.background}；强度：${o.strength}。${o.protect?'锁定产品结构、颜色、标志、文字。':'允许按补充要求调整产品表现。'}`;
    if(type==='repair')return `局部处理方式：${o.method}。以最后附带的选区标记图为编辑范围，仅修改紫色标记区域；标记不是成品内容。必须保持原图的构图、主体位置和大小，不放大、不裁切、不移动产品。边缘融合 ${o.feather}px。${o.protect?'保护选区外的全部画面。':''}`;
    if(type==='transfer')return `迁移方式：${o.mode}。位置：${o.placement}${o.position?`（中心横向${Math.round(o.position.x*100)}%、纵向${Math.round(o.position.y*100)}%）`:''}。产品约占画面宽度${o.scale}%。透视：${o.perspective}。${o.light?'匹配场景光向。':'保留产品光向。'}${o.shadow?'生成自然接触阴影。':'不额外增加阴影。'}${o.protect?'保留产品结构、标志和真实颜色。':''}附带的位置标记图只作为指引，不要将框线和紫色区域画入成品。`;
    if(type==='compose')return `摆放方案：${o.arrangement}；遮挡关系：${o.occlusion}。产品图层按从后到前的顺序排列：${appVisibleProducts(node,roles).map((img,i)=>{
        const l=o.layers[img.url] || {};return `产品${i+1} ${img.name || ''}：中心横向${Math.round((l.x ?? ((i+1)/(appVisibleProducts(node,roles).length+1)))*100)}%、纵向${Math.round((l.y ?? .6)*100)}%、宽度${l.scale || 30}%，${l.locked?'锁定摆放位置':'按方案适配'}`;
    }).join('；')}。${o.light?'统一光影。':''}${o.depth?'匹配景深。':''}${o.keepScene?'保留场景布局。':''}最后的图层落位指引图仅用于位置参考，成品不能出现编号、框线或半透明标记。`;
    if(type==='generate')return `各参考图用途：${roles.reference.map((r,i)=>`参考${i+1}：${o.referenceRoles[r.url] || '主体'}`).join('；')}。按生成描述处理参考图。`;
    if(type==='describe')return `分析目标：${o.target}；仅分析维度：${o.dimensions.join('、')}；描述详细度：${o.detail}；输出格式：${o.format}；输出语言：${node.appLanguage || '中文'}。可见文字未勾选时不转写画面文字。`;
    if(type==='detail')return `已确认产品信息：${o.sellingPoints || '未提供，只呈现参考图可见外观，不编造参数或认证'}。整组统一主色${o.color}、字体风格${o.font}。本屏策划：${o.screens[screen] || ['产品主视觉','核心卖点','使用场景','细节展示','结构展示','收尾展示'][screen%6]}。最终事实约束：只显示用户已确认的卖点与参数；没有提供尺寸、重量、材质、性能、认证或价格时，禁止添加这些数值、单位、表格或宣传结论；参数主题改为可见结构介绍。保留产品图中已有标志及显示屏读数，不清空屏幕，不编造新读数。`;
    if(type==='layout')return `沿用模板的${o.preserve.join('、')}。${o.preserve.includes('布局')?'严格保留模板主标题、产品展示区和底部信息区的位置与相对面积；不要改成另外一种海报构图。':''}${o.preserve.includes('装饰素材')?'保留模板的环境、装饰和信息条，只移除模板原有产品及品牌宣传。':''}所有 ${roles.product.length} 张产品图均为必须展示的产品，每个产品都要出现在模板产品展示区，禁止漏掉任何一个；多产品按原版式中的产品数量分配，必要时在同一区域并排。主标题替换为：${o.headline || '不添加主标题'}；副标题：${o.subtitle || '不添加副标题'}；卖点：${o.sellingPoints || '不添加卖点'}。配色：${o.colorMode}${o.colorMode==='自定义'?` ${o.color}`:''}；产品适配：${o.fit}。不要照搬模板品牌或其宣传文字。`;
    return '';
}
function bindSmartApplicationOptionControls(el,node){
    const o=smartApplicationOptions(node);
    el.querySelectorAll('[data-app-option]').forEach(button=>button.addEventListener('click',()=>{
        if(node.running)return;pushUndo();const key=button.dataset.appOption,value=button.dataset.appValue;
        if(button.hasAttribute('data-app-multiple'))o[key]=o[key].includes(value)?o[key].filter(v=>v!==value):[...o[key],value];else o[key]=value;
        render();scheduleSave();
    }));
    el.querySelectorAll('[data-app-ref-role]').forEach(select=>select.addEventListener('change',()=>{o.referenceRoles[select.dataset.appRefRole]=select.value;scheduleSave();}));
    el.querySelectorAll('[data-app-screen]').forEach(input=>input.addEventListener('input',()=>{o.screens[Number(input.dataset.appScreen)]=input.value;scheduleSave();}));
    el.querySelectorAll('[data-app-screen-move]').forEach(button=>button.addEventListener('click',()=>{
        const i=Number(button.dataset.appScreenMove),j=i+Number(button.dataset.direction);
        if(j<0||j>=Number(node.appCount))return;pushUndo();[o.screens[i],o.screens[j]]=[o.screens[j],o.screens[i]];render();scheduleSave();
    }));
    el.querySelectorAll('[data-app-layer-select]').forEach(button=>button.addEventListener('click',()=>{o.activeLayer=button.dataset.appLayerSelect;o.layerScale=o.layers[o.activeLayer]?.scale || 30;render();scheduleSave();}));
    el.querySelectorAll('[data-app-layer-action]').forEach(button=>button.addEventListener('click',()=>{
        const url=button.dataset.url,action=button.dataset.appLayerAction;pushUndo();o.layers[url] ||= {};const layer=o.layers[url];
        if(action==='visible')layer.visible=layer.visible===false;else if(action==='locked')layer.locked=!layer.locked;else{
            const products=smartApplicationInputs(node).product.sort((a,b)=>(o.layers[a.url]?.order || 0)-(o.layers[b.url]?.order || 0));
            const i=products.findIndex(p=>p.url===url),j=i+(action==='up'?1:-1);if(j>=0&&j<products.length)[products[i],products[j]]=[products[j],products[i]];
            products.forEach((p,index)=>{o.layers[p.url] ||= {};o.layers[p.url].order=index;});
        }render();scheduleSave();
    }));
    el.querySelector('[data-app-optimize]')?.addEventListener('click',()=>optimizeSmartApplication(node.id));
    el.querySelector('[data-app-disconnect-text]')?.addEventListener('click',()=>{
        const ids=inputNodesFor(node).filter(n=>n.type==='smart-prompt').map(n=>n.id);pushUndo();
        canvas.connections=canvas.connections.filter(c=>!(c.to===node.id && c.kind==='input' && ids.includes(c.from)));node.inputNodeIds=(node.inputNodeIds || []).filter(id=>!ids.includes(id));render();scheduleSave();
    });
    el.querySelector('[data-app-copy]')?.addEventListener('click',()=>navigator.clipboard.writeText(node.appResult || '').then(()=>toast('提示词已复制')).catch(()=>toast('复制失败，可在结果框中选中复制')));
    el.querySelector('[data-app-export-text]')?.addEventListener('click',()=>exportSmartApplicationText(node));
    el.querySelector('[data-app-send-generate]')?.addEventListener('click',()=>{
        if(!node.appResult?.trim())return toast('请先分析图片');const source=nodes.find(n=>n.id===node.appSourceId);if(!source)return;
        const text=exportSmartApplicationText(node),app=createSmartApplicationNode(source.id,'generate',{x:node.x+750,y:node.y+430});if(app){app.appPrompt=node.appResult;connectInputNode(text.id,app.id);render();scheduleSave();}
    });
    el.querySelector('[data-app-compare]')?.addEventListener('click',()=>{
        const stage=el.querySelector('[data-app-stage] img'),source=smartApplicationInputs(node).product[0];
        if(stage && source)stage.src=stage.dataset.result==='yes'?source.url:node.appLastOutput; if(stage)stage.dataset.result=stage.dataset.result==='yes'?'no':'yes';
    });
    el.querySelectorAll('[data-app-tool]').forEach(button=>button.addEventListener('click',()=>{
        const tool=button.dataset.appTool;pushUndo();
        if(tool==='撤销')o.strokes?.pop();else if(tool==='清空'){o.strokes=[];delete o.position;}else if(tool==='对齐'){
            appVisibleProducts(node,smartApplicationInputs(node)).forEach((img,i,all)=>{const layer=o.layers[img.url] ||= {};if(!layer.locked)Object.assign(layer,{x:(i+1)/(all.length+1),y:.6});});
        }else o.tool=tool;render();scheduleSave();
    }));
    el.querySelector('[data-app-central-region]')?.addEventListener('click',()=>{pushUndo();o.strokes.push({tool:'框选',points:[{x:.3,y:.3},{x:.7,y:.7}],size:o.brush});render();scheduleSave();});
    bindSmartApplicationStage(el,node);
}
function appLayerGeometry(node,inputs){
    const o=smartApplicationOptions(node), products=appVisibleProducts(node,inputs);
    return products.map((image,i)=>{
        const layer=o.layers[image.url] || {}, preset=o.arrangement;
        let x=(i+1)/(products.length+1),y=.6,scale=30;
        if(preset==='主次组合'){scale=i===0?40:22;y=i===0?.54:.7;}
        if(preset==='平铺陈列'){y=.5;scale=Math.min(30,70/products.length);}
        return {image,x:layer.x ?? x,y:layer.y ?? y,scale:layer.scale || scale,locked:layer.locked};
    });
}
function appDrawStrokes(ctx,strokes,w,h,mask=false){
    for(const stroke of strokes || []){
        ctx.globalCompositeOperation=stroke.tool==='橡皮'?'destination-out':'source-over';
        ctx.strokeStyle=mask?'#fff':'rgba(151,130,255,.7)';ctx.fillStyle=mask?'#fff':'rgba(151,130,255,.4)';
        ctx.lineWidth=stroke.size/1000*w;ctx.lineCap='round';ctx.lineJoin='round';
        const p=stroke.points;if(!p?.length)continue;
        if(stroke.tool==='框选'){const end=p[p.length-1];ctx.fillRect(Math.min(p[0].x,end.x)*w,Math.min(p[0].y,end.y)*h,Math.abs(p[0].x-end.x)*w,Math.abs(p[0].y-end.y)*h);}
        else{ctx.beginPath();ctx.moveTo(p[0].x*w,p[0].y*h);p.slice(1).forEach(point=>ctx.lineTo(point.x*w,point.y*h));if(p.length===1)ctx.lineTo(p[0].x*w+.1,p[0].y*h);ctx.stroke();}
    }ctx.globalCompositeOperation='source-over';
}
function appPaintOverlay(canvasEl,node,inputs){
    const ctx=canvasEl.getContext('2d'),w=canvasEl.width,h=canvasEl.height,o=smartApplicationOptions(node);
    ctx.clearRect(0,0,w,h);appDrawStrokes(ctx,o.strokes,w,h);
    const boxes=node.application==='compose'?appLayerGeometry(node,inputs):o.position?[{...o.position,scale:o.scale}]:[];
    boxes.forEach((box,i)=>{const bw=box.scale/100*w,bh=bw*1.2;ctx.strokeStyle='#a497ff';ctx.lineWidth=2;ctx.strokeRect(box.x*w-bw/2,box.y*h-bh/2,bw,bh);ctx.fillStyle='#a497ff';ctx.font='18px sans-serif';ctx.fillText(node.application==='compose'?String(i+1):'产品落位',box.x*w-bw/2,box.y*h-bh/2-8);});
}
function bindSmartApplicationStage(el,node){
    const stage=el.querySelector('[data-app-stage]'),img=stage?.querySelector('img'),overlay=stage?.querySelector('canvas');
    if(!img || !overlay)return;
    const o=smartApplicationOptions(node);
    function refresh(){
        overlay.width=img.naturalWidth || 1000;overlay.height=img.naturalHeight || 1000;
        if(overlay.width>1200){overlay.height=Math.round(overlay.height*1200/overlay.width);overlay.width=1200;}
        appPaintOverlay(overlay,node,smartApplicationInputs(node));
    }
    img.addEventListener('load',refresh);if(img.complete)refresh();
    let active=null;
    const point=e=>{const r=overlay.getBoundingClientRect();return {x:Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),y:Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))};};
    stage.addEventListener('pointerdown',e=>{
        if(e.button!==0||node.running)return;e.preventDefault();e.stopPropagation();pushUndo();const p=point(e);
        if(node.application==='compose'){
            const boxes=appLayerGeometry(node,smartApplicationInputs(node));const hit=[...boxes].reverse().find(b=>Math.abs(p.x-b.x)<b.scale/200 && Math.abs(p.y-b.y)<b.scale/150);
            const box=hit || boxes.find(b=>b.image.url===o.activeLayer) || boxes[0];if(!box||box.locked)return;o.activeLayer=box.image.url;o.layers[o.activeLayer] ||= {};
            active={box,start:p,scale:box.scale};
        }else if(node.application==='transfer' && o.tool==='标记位置'){o.position=p;o.placement='按标记位置';active={position:true};}
        else{const stroke={tool:o.tool==='框选'?'框选':o.tool==='橡皮'?'橡皮':'画笔',points:[p],size:o.brush || 32};o.strokes.push(stroke);active={stroke};}
        stage.setPointerCapture(e.pointerId);refresh();
    });
    stage.addEventListener('pointermove',e=>{
        if(!active)return;e.preventDefault();const p=point(e);
        if(active.box){const layer=o.layers[o.activeLayer];if(o.tool==='缩放')layer.scale=Math.max(10,Math.min(80,active.scale+(p.x-active.start.x)*100));else Object.assign(layer,{x:p.x,y:p.y});}
        else if(active.position)o.position=p;else active.stroke.points.push(p);refresh();
    });
    const finish=e=>{if(!active)return;active=null;stage.releasePointerCapture?.(e.pointerId);scheduleSave();};
    stage.addEventListener('pointerup',finish);stage.addEventListener('pointercancel',finish);
}
async function appLoadImage(url){return new Promise((resolve,reject)=>{const img=new Image();img.crossOrigin='anonymous';img.onload=()=>resolve(img);img.onerror=()=>reject(new Error('无法读取编辑源图'));img.src=url;});}
async function smartApplicationPrepareGuides(node,inputs){
    const o=smartApplicationOptions(node),role=['transfer','compose'].includes(node.application)?'scene':'product';
    const source=inputs[role][0];if(!source || !['repair','transfer','compose'].includes(node.application))return [];
    const image=await appLoadImage(source.url),guide=document.createElement('canvas');guide.width=image.naturalWidth;guide.height=image.naturalHeight;
    const ctx=guide.getContext('2d');ctx.drawImage(image,0,0);const overlay=document.createElement('canvas');overlay.width=guide.width;overlay.height=guide.height;
    appPaintOverlay(overlay,node,inputs);ctx.drawImage(overlay,0,0);
    const blob=await new Promise(r=>guide.toBlob(r,'image/png'));const file=await uploadCroppedBlob(blob,`${node.application}_guide.png`);
    const result=[{...file,role:'reference',name:'编辑位置指引图（不是输出内容）'}];
    if(node.application==='repair'){
        const mask=document.createElement('canvas');mask.width=guide.width;mask.height=guide.height;
        appDrawStrokes(mask.getContext('2d'),o.strokes,mask.width,mask.height,true);
        const data=mask.getContext('2d').getImageData(0,0,mask.width,mask.height).data;
        if(!data.some((v,i)=>i%4===3 && v>0))throw new Error('请先涂抹或框选需要修复的区域');
        const maskBlob=await new Promise(r=>mask.toBlob(r,'image/png'));const maskFile=await uploadCroppedBlob(maskBlob,'application_selection.png');
        node.appMaskUrl=maskFile.url;node.appMaskSource=source.url;
    }
    return result;
}
function exportSmartApplicationText(node){
    if(!node.appResult?.trim()){toast('请先分析图片');return null;}pushUndo();
    const output=createPromptNode(node.x+750,node.y,{skipUndo:true,select:false});output.text=node.appResult;output.w=380;output.h=420;addConnection(node.id,output.id,'flow');render();scheduleSave();return output;
}
async function optimizeSmartApplication(nodeId){
    const node=nodes.find(n=>n.id===nodeId);if(!node || node.running)return;
    const inputs=smartApplicationInputs(node);if(!node.appPrompt?.trim()&&!inputs.text.length)return toast('请先填写生成描述或连接文本节点');
    node.running=true;node.appStatus='正在使用所选文本模型优化提示词…';render();
    try{
        const request=smartApplicationRequest(node,inputs);
        const textOnly=node.appChatModel==='deepseek-v4-pro';
        node.appPrompt=await smartApplicationChat(node,`优化下面的生成需求，保留用户意图、参考图约束与事实。${textOnly?'你没有看到参考图片，仅优化文字和图片角色约束，禁止推断图片内容。':''}只返回可直接用于生图的提示词，不要解释，不添加未经提供的参数。\n${request.prompt}`,textOnly?[]:request.refs);
        node.appStatus='提示词已优化，可编辑后生成。';
    }catch(e){node.appStatus=`优化失败：${e.message}`;toast(node.appStatus);}finally{node.running=false;render();scheduleSave();}
}
