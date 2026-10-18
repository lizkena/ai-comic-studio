"""Compile image instructions into a single static picture, not a skill manual."""
from . import providers, creation, asset_visuals


def target_context(target, assets=(), variant=None):
    is_shot='shots' in target
    result={k:target.get(k,'') for k in ('id','kind','name','title','description','image_prompt') if k in target}
    result['target_type']='shot_first_frame' if is_shot else target.get('kind','asset')
    if is_shot:
        shots=target.get('shots') or []
        first=min(shots,key=lambda s:float(s.get('start',0))) if shots else {}
        # Dialogue, sound, later beats and video instructions aren't image input.
        result['opening_shot']={k:first[k] for k in ('size','camera','action','start_pose') if k in first}
        if target.get('start_pose'): result['start_pose']=target['start_pose']
    if variant: result['selected_variant']={k:variant.get(k,'') for k in ('id','name','description')}
    refs=[target] if not is_shot else assets
    result['reference_assets']=[{k:a.get(k,'') for k in ('id','kind','name','description')} | {
        'has_image_reference':bool(a.get('references'))} for a in refs]
    return result


async def compile_prompt(p, job, skill, target, assets, variant, log):
    # A recovered async image polls the existing ID without another paid text call.
    saved=job.get('compiled_image_prompt')
    if saved: return saved
    if job.get('remote_id'): return job.get('image_prompt','')
    provider=providers.provider_for(p,'text')
    log(job,'使用 '+skill['name']+' 整理静态生图提示词',
        skill={'id':skill['id'],'version':skill['version']})
    ctx={'target':target_context(target,assets,variant),'request':job.get('instruction','')}
    instruction=skill['content']+'\n'+creation.guidance(p,'assets',visual_only=True)+'\n只返回 prompt；不要输出剧本、对白、声音、时间线或工作说明。\n底层输出规范优先于技能中的布局建议：'+asset_visuals.rules(target)
    output,usage,request=await providers.text_generate(provider,instruction,ctx,{'prompt':'一段中文静态生图提示词'})
    prompt=output.get('prompt') if isinstance(output,dict) else None
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>6000:
        raise ValueError('生图提示词编译结果无效，尚未提交图片生成')
    prompt=asset_visuals.enforce(prompt.strip(),target)
    log(job,'静态提示词已保存，开始使用所选图片模型',compiled_image_prompt=prompt,
        prompt_compilation={'skill':{'id':skill['id'],'version':skill['version']},
            'provider_id':provider['id'],'model':provider['model'],'usage':usage},
        prompt_request_snapshot=request)
    return prompt
