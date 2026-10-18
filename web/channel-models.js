export function createChannelModels({state,esc,icon,render,dialog,closeDialog,toast}) {
  const groups=[['image','生图模型','用于角色、场景、道具与白模出图。'],['text','聊天模型','用于小说、剧本、分镜与创作助手。'],['video','视频模型','用于镜头和视频生成。']];
  function entries(provider=state().inlineProvider) {
    const s=state();s.channelModelDrafts||={};
    return s.channelModelDrafts[s.platformSelection] ||= structuredClone(provider.models || (provider.model?[{id:provider.model,kind:provider.kind,protocol:provider.protocol}]:[]));
  }
  function defaultProtocol(kind){const p=document.getElementById('platform-provider-form')?.elements.protocol.value||state().inlineProvider.protocol;return state().provider_presets.protocols[kind]?.[p]?p:kind==='video'?'json-video':'openai';}
  function capture() {
    const rows=[...document.querySelectorAll('.channel-model-row')];
    if(!document.querySelector('.channel-model-registry'))return;
    const models=entries();rows.forEach(row=>{const i=Number(row.dataset.index);if(models[i]){models[i].id=row.querySelector('input').value.trim();models[i].protocol=row.querySelector('select').value;const params=row.querySelector('textarea');if(params){try{models[i].lingquan_params=JSON.parse(params.value);}catch{models[i].lingquan_params_invalid=true;return;}delete models[i].lingquan_params_invalid;}}});
  }
  function view(provider) {
    const s=state(),models=entries(provider),result=s.modelLists?.[s.platformSelection];
    return `<section class="channel-model-registry"><div class="channel-model-toolbar"><div><h3>模型列表</h3><p class="help" id="platform-model-hint">${esc(result?.message || '从上游 API 拉取可用模型并按类型分类；无法识别的类型请手动确认。')}</p></div><div class="row"><button type="button" data-action="provider-models">${icon('refresh')}拉取模型</button><button type="button" data-model-action="choose" ${!result?.models?.length?'disabled':''}>${icon('check')}选择模型</button></div></div>
      ${groups.map(([kind,name,hint])=>`<section class="channel-model-group"><div class="row between"><div><h3>${name}</h3><p class="help">${hint}</p></div><button type="button" data-model-action="add" data-kind="${kind}">${icon('plus')}模型</button></div><div class="channel-model-rows">${models.map((m,i)=>m.kind===kind?`<div class="channel-model-row" data-index="${i}"><input aria-label="${name} ID ${i+1}" value="${esc(m.id)}" placeholder="输入模型 ID"><select aria-label="${name}调用协议 ${i+1}">${Object.entries(s.provider_presets.protocols[kind]).map(([id,label])=>`<option value="${id}" ${id===m.protocol?'selected':''}>${esc(label)}</option>`).join('')}</select><button type="button" class="ghost" data-model-action="remove" data-index="${i}" aria-label="移除此模型">${icon('trash')}</button>${m.protocol==='lingquan'&&kind!=='text'?`<label class="lingquan-model-params">模型参数 JSON（按该模型文档填写；时长、比例和首帧由分镜自动传入）<textarea aria-label="${name}参数 ${i+1}" rows="2">${esc(JSON.stringify(m.lingquan_params||{},null,2))}</textarea></label>`:''}</div>`:'').join('') || '<div class="channel-model-empty">暂无模型</div>'}</div></section>`).join('')}</section>`;
  }
  function choose() {
    capture();const s=state(),models=entries(),result=s.modelLists[s.platformSelection];
    const rows=result.model_details || result.models.map(id=>({id,kind:'unclassified'}));
    dialog('选择渠道模型',`<p class="help mb">类型识别只是建议，请确认后添加。同一渠道共用地址和密钥，不同类型使用对应调用协议。</p><div class="row mb"><input id="channel-model-search" placeholder="搜索模型"><button data-model-action="all">全选</button><button data-model-action="none">清空</button></div><div class="channel-model-choices">${rows.map((m,i)=>`<div class="channel-model-choice"><label><input type="checkbox" value="${esc(m.id)}" ${models.some(x=>x.id===m.id)?'checked':''}>${esc(m.id)}</label><select aria-label="模型类型 ${i+1}"><option value="unclassified">待分类</option>${groups.map(([kind,name])=>`<option value="${kind}" ${kind===m.kind?'selected':''}>${name}</option>`).join('')}</select></div>`).join('')}</div>`,`<button data-action="close-dialog">取消</button><button class="primary" data-model-action="import">添加所选模型</button>`,true);
  }
  document.addEventListener('input',e=>{
    if(e.target.closest('.channel-model-row'))capture();
    if(e.target.id==='channel-model-search'){const query=e.target.value.toLowerCase();document.querySelectorAll('.channel-model-choice').forEach(row=>row.hidden=!row.querySelector('input').value.toLowerCase().includes(query));}
  });
  document.addEventListener('click',e=>{
    const button=e.target.closest('[data-model-action]');if(!button)return;
    try {
      const action=button.dataset.modelAction;capture();
      if(action==='choose'){choose();return;}
      if(action==='all'||action==='none'){document.querySelectorAll('.channel-model-choice:not([hidden]) input').forEach(x=>x.checked=action==='all');return;}
      const models=entries();
      if(action==='add')models.push({id:'',kind:button.dataset.kind,protocol:defaultProtocol(button.dataset.kind)});
      if(action==='remove')models.splice(Number(button.dataset.index),1);
      if(action==='import'){
        const selected=[...document.querySelectorAll('.channel-model-choice')].filter(row=>row.querySelector('input').checked);
        if(selected.some(row=>row.querySelector('select').value==='unclassified'))throw Error('请先为已选择的模型确认类型');
        for(const row of selected){const id=row.querySelector('input').value,kind=row.querySelector('select').value;if(!models.some(m=>m.id===id&&m.kind===kind))models.push({id,kind,protocol:defaultProtocol(kind)});}
        closeDialog();
      }
      render();
    }catch(error){toast(error.message,true);}
  });
  return {entries,capture,view};
}
