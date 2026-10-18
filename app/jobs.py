import asyncio
import copy
import json
import threading
import httpx
from . import task_locks
from . import store, domain, providers, skills, media, creation, workflow, image_prompts, asset_visuals, deployment, director_prompts

tasks = {}
semaphore = asyncio.Semaphore(2)
ACTIVE = {'queued', 'waiting_dependency', 'running'}


def log(job, message, **changes):
    latest = store.get('jobs', job['id'])
    if changes.get('status')=='running' and latest.get('status')!='running':
        changes.setdefault('started_at',store.now())
        changes.setdefault('completed_at',None)
    if changes.get('status') in ('succeeded','failed','cancelled') and latest.get('status')!=changes['status']:
        changes.setdefault('completed_at',store.now())
    if changes.get('status')=='queued' and latest.get('status') in ('failed','cancelled'):
        changes.setdefault('completed_at',None)
        changes.setdefault('started_at',None)
    latest.update(changes)
    latest['logs'] = (latest.get('logs', []) + [{'at':store.now(), 'message':message}])[-100:]
    latest['updated_at'] = store.now(); store.put('jobs', latest)
    job.update(latest)


def mutate_project(ident, action, reason):
    for _ in range(5):
        p = store.get('projects', ident); revision = p['revision']; action(p)
        try: return store.save_project(p, revision, reason)
        except ValueError: continue
    raise ValueError('项目连续更新，请稍后重试')


submission_lock = threading.RLock()


def create(p, payload):
    with submission_lock:
        return _create(p, payload)


def _create(p, payload):
    from . import agent_memory
    p = copy.deepcopy(p)
    p['_agent_memory'] = agent_memory.snapshot(p)
    if p.get('deleted_at'): raise ValueError('请先从回收站恢复作品')
    kind = payload.get('kind', 'text'); stage = payload.get('stage', 'direction')
    target = payload.get('target_id')
    if kind not in ('text','polish','image','video','white','assembly'): raise ValueError('任务类型不支持')
    if kind == 'text' and stage not in domain.SCHEMAS and stage not in workflow.SCHEMAS: raise ValueError('当前阶段无法调用文字生成')
    if stage in workflow.SCHEMAS:
        if kind != 'text': raise ValueError('流程分析阶段仅接受文字任务')
        workflow.context(p, stage, target, payload.get('workflow_options'))
    if kind not in ('assembly',):
        if stage=='wf_canvas_text' and payload.get('workflow_options',{}).get('canvas_model'):
            p.setdefault('model_bindings',{})['text']=payload['workflow_options']['canvas_model']
        provider = providers.provider_for(p, 'text' if kind in ('text','polish') else 'image' if kind in ('image','white') else 'video', payload.get('provider_id'))
        provider_id = provider['id']
        p = copy.deepcopy(p)
        model_kind = 'text' if kind in ('text','polish') else 'image' if kind in ('image','white') else 'video'
        p.setdefault('model_bindings', {})[model_kind] = provider.get('model', '')
    else: provider_id = None
    if payload.get('auto'):
        remaining=int(payload.get('remaining',0))
        if not 1<=remaining<=int(p['settings'].get('max_jobs',10)): raise ValueError('自动制作范围超出任务数量上限')
        budget=p['settings'].get('budget')
        if budget is not None:
            unit=provider.get('unit_price')
            if unit is None: raise ValueError('价格未知，无法校验自动制作费用上限')
            if float(unit)*remaining*2>float(budget): raise ValueError('自动制作费用估算（含一次结构修复）超出上限')
    skill_snapshots={}
    if kind=='text':
        base=workflow.RULES[stage][0] if stage in workflow.RULES else stage
        skill_snapshots[base]=skills.load(base,p.get('bindings',{}).get('skill_'+base))
        if stage=='wf_prompts': skill_snapshots['assets']=skills.load('assets',p.get('bindings',{}).get('skill_assets'))
    elif kind=='image': skill_snapshots['assets']=skills.load('assets',p.get('bindings',{}).get('skill_assets'))
    elif kind=='polish':
        asset=next((a for a in p['assets'] if a['id']==target),None)
        if not asset: raise ValueError('润色目标资产不存在')
        base='characters' if asset['kind']=='character' else 'world'
        skill_snapshots[base]=skills.load(base,p.get('bindings',{}).get('skill_'+base))
    from . import skill_dispatch
    for skill_stage,selected in list(skill_snapshots.items()):skill_snapshots[skill_stage]=skill_dispatch.resolve(selected,p,{**payload,'kind':kind,'stage':stage,'target_id':target})
    identity = domain.fingerprint({'p':p['id'],'revision':p['revision'],'kind':kind,'stage':stage,'target':target,'provider':provider_id,'model':provider.get('model') if kind!='assembly' else None,'skills':skill_snapshots,'memory':p['_agent_memory'],'preview':bool(payload.get('preview')),'instruction':payload.get('instruction',''),'workflow_options':payload.get('workflow_options',{}),'visual_policy':asset_visuals.VERSION if kind=='image' or stage=='wf_prompts' else None})
    if kind == 'text' and director_prompts.enhancement(stage, payload.get('workflow_options')):
        identity = domain.fingerprint({'base':identity,'prompt_compiler':director_prompts.VERSION})
    previous = next(iter(store.job_rows(identity=identity, statuses=ACTIVE | {'succeeded'}, limit=1)), None)
    if kind == 'video':
        from . import native_audio
        identity = domain.fingerprint({'base':identity,'audio_policy':native_audio.VERSION})
        previous = next(iter(store.job_rows(identity=identity, statuses=ACTIVE | {'succeeded'}, limit=1)), None)
    if previous: return public(previous)
    task_locks.assert_submission(p, payload)
    job = {'id':store.uid('job'),'project_id':p['id'],'project_name':p['name'],'kind':kind,'stage':stage,'target_id':target,
           'status':'queued','created_at':store.now(),'updated_at':store.now(),'provider_id':provider_id,'identity':identity,
           'instruction':payload.get('instruction',''),'preview':bool(payload.get('preview')),
           'source_revision':p['revision'],'source_snapshot':copy.deepcopy(p),'logs':[], 'attempt':0,
           'auto':payload.get('auto',False),'remaining':payload.get('remaining',0),'workflow_options':copy.deepcopy(payload.get('workflow_options',{})),
           'skill_snapshots':copy.deepcopy(skill_snapshots)}
    if kind != 'assembly':
        job['provider_snapshot'] = {k:copy.deepcopy(v) for k,v in provider.items() if k not in ('secret','ak_secret','sk_secret','api_key','access_key','secret_key')}
    if kind == 'video':
        segment = next((s for s in p['segments'] if s['id'] == target),None)
        if not segment: raise ValueError('找不到视频小节')
        errors=[c['message'] for c in domain.checks(p, providers.settings()) if c['severity']=='error' and c.get('target') in (None,target)]
        if errors: raise ValueError('关键节点未就绪：'+'；'.join(errors))
        job['input_bundle'] = domain.bundle(p,segment,allow_waiting=True,provider=provider)
    if kind == 'image':
        objects = p['segments'] if stage == 'storyboard' else p['assets']
        if not any(x['id'] == target for x in objects): raise ValueError('图片目标不存在')
    if kind in ('image','white') and not target: raise ValueError('请选择目标资产或视频小节')
    if kind in ('image','video'): workflow.guard_media(p, target)
    from . import generation_supervision
    generation_supervision.claim(p,payload,job)
    store.put('jobs',job); launch(job['id']); return public(job)


def public(job):
    result = {k:v for k,v in job.items() if k not in ('source_snapshot','request_snapshot','skill_snapshots','prompt_request_snapshot','provider_snapshot')}
    return result


def launch(ident):
    if ident in tasks and not tasks[ident].done(): return
    tasks[ident] = asyncio.create_task(execute(ident))


async def recover():
    for summary in store.job_rows(statuses=ACTIVE | {'failed'}):
        if summary['status'] not in ACTIVE and summary.get('error') != '请在该模型的参数 JSON 中设置：prompt': continue
        j = store.get('jobs', summary['id'])
        # This exact error came from the former local Lingquan validator, before POST.
        if (j['status']=='failed' and not j.get('remote_id') and j.get('uncertain')
                and j.get('error')=='请在该模型的参数 JSON 中设置：prompt'):
            log(j,'已修复提示词参数校验；该次生成请求尚未提交，可手动重试',submission_started=False,uncertain=False)
        if j['status'] in ACTIVE:
            if j['status'] == 'running' and not j.get('remote_id'):
                log(j,'程序曾在调用期间退出。无法确定服务是否受理，请核查服务记录后手动重试。',status='failed',uncertain=True,error='上次运行中断；没有远程任务ID，未自动重复提交')
            else: launch(j['id'])


async def dependency(job, p):
    original = next(s for s in job['source_snapshot']['segments'] if s['id'] == job['target_id'])
    previous = original.get('previous_id') if original.get('continuity') else None
    if not previous: return p
    while True:
        if store.get('jobs',job['id'])['status']=='cancelled': raise asyncio.CancelledError()
        p = store.get('projects',job['project_id']); s = next((s for s in p['segments'] if s['id']==previous),None)
        if not s: raise ValueError('前序小节已不存在，请重新指定衔接来源')
        version = next((v for v in s.get('versions',[]) if v['id']==s.get('current_version')),None)
        ready = version and version.get('tail_accepted') and version.get('tail')
        if p['settings'].get('white_mode'): ready = ready and version.get('white') and version.get('white_accepted')
        if ready:
            if job['status']=='waiting_dependency': log(job,'前序视频与参考帧已就绪',status='queued')
            return p
        if job['status']!='waiting_dependency': log(job,'等待前序视频、有效尾帧'+('及已确认白模' if p['settings'].get('white_mode') else ''),status='waiting_dependency')
        await asyncio.sleep(2)


async def execute(ident):
    job = store.get('jobs',ident)
    try:
        p = store.get('projects',job['project_id'])
        if job['kind']=='video': p = await dependency(job,p)
        async with semaphore:
            if store.get('jobs',ident)['status']=='cancelled': return
            log(job,'开始执行',status='running',error=None)
            if job['kind']=='text': await run_text(job)
            elif job['kind']=='polish': await run_polish(job)
            elif job['kind']=='image': await run_image(job)
            elif job['kind']=='white': await run_white(job)
            elif job['kind']=='video': await run_video(job,p)
            else:
                result = await media.compose(job['source_snapshot'],job.get('target_id'))
                mutate_project(p['id'],lambda latest:latest['artifacts'].append({**result,'created_at':store.now()}),'导出成片')
                log(job,'成片可播放，源片段音轨已保留',result=result)
            log(job,'任务完成',status='succeeded')
        if job.get('auto') and job['kind']=='text': await chain(job)
    except asyncio.CancelledError:
        latest=store.get('jobs',ident)
        log(job,'已停止本地处理'+('；远程任务仍可能运行，可在服务端确认' if latest.get('remote_id') else ''),status='cancelled')
    except Exception as error:
        if store.get('jobs',ident)['status']!='cancelled':
            diagnostics = {'provider_diagnostics':error.provider_diagnostics} if getattr(error, 'provider_diagnostics', None) else {}
            if isinstance(error, providers.SubmissionNotSentError) and not job.get('remote_id'):
                log(job,'生成请求尚未提交：'+str(error)[:1800],status='failed',error=str(error)[:1800],submission_started=False,uncertain=False,**diagnostics)
            else:
                log(job,str(error)[:1800],status='failed',error=str(error)[:1800],uncertain=bool(job.get('uncertain') or (job.get('submission_started') and not job.get('remote_id'))),**diagnostics)


async def run_text(job):
    if job['stage'] in workflow.SCHEMAS:
        await workflow.run_text(job, log)
        if job['stage']=='wf_canvas_text':
            log(job,'画布文本结果已保留，返回对应节点；未改写其他作品内容',pending_apply=False)
            return
        latest=store.get('jobs',job['id'])
        apply_result(latest,latest['result'])
        log(job,'生成结果已自动更新到当前作品',pending_apply=False,applied_automatically=True,applied_at=store.now())
        return
    p=job['source_snapshot']; stage=job['stage']; provider=providers.provider_for(p,'text',job['provider_id'])
    skill=skills.for_job(job,stage)
    log(job,'加载 Skill：'+skill['name']+' '+skill['version'],skill={'id':skill['id'],'version':skill['version'],'availability':skill['availability']},model=provider['model'])
    context={'source':p['source'],'settings':p['settings'],'outputs':p['outputs'],'assets':p['assets'],'segments':p['segments'], 'request':job['instruction'], 'target_id':job.get('target_id')}
    if job.get('target_id'): context['request']+='\n仅返回 target_id 对象的修改结果，保留其 ID，不重写其他对象。'
    schema=domain.SCHEMAS[stage]
    result=None
    for attempt in range(2):
        log(job,'调用模型并校验结构',attempt=attempt+1)
        try:
            output,usage,request=await providers.text_generate(provider,skill['content']+'\n'+creation.guidance(p,stage),context,schema)
            result=domain.normalize(stage,output,p); break
        except ValueError as error:
            # Only invalid model structure gets one additional model request; HTTP failures do not retry.
            if 'JSON' not in str(error) and not any(x in str(error) for x in ('模型缺少','输出缺少','分镜结构','正文','每集至少')): raise
            if attempt: raise
            context['validation_error']=str(error); context['request']+='\n修正上次格式错误，严格使用提供的结构。'
    log(job,'结构校验通过',result=result,usage=usage,request_snapshot=request)
    apply_result(job,result)
    log(job,'生成结果已自动更新到当前作品',pending_apply=False,applied_automatically=True,applied_at=store.now())


def apply_result(job,result):
    def apply(p):
        if job['stage'] in workflow.SCHEMAS:
            workflow.apply(p, job, result)
            return
        if job['kind']=='polish':
            a=next(a for a in p['assets'] if a['id']==job['target_id'])
            original=next(a for a in job['source_snapshot']['assets'] if a['id']==job['target_id'])
            if a.get('description') != original.get('description'): raise ValueError('资产描述在生成期间发生变化，原内容已保留，请重新生成')
            a['description']=result['description']; a['version']+=1; a['status']='draft'
            for s in p['segments']:
                if a['id'] in s.get('character_ids',[])+s.get('prop_ids',[])+[s.get('location_id')]: s['status']='stale'
            return
        if p['revision']!=job['source_revision'] and job['kind']=='text' and not job.get('applied_by_user'):
            if p['outputs'].get(job['stage']) != job['source_snapshot']['outputs'].get(job['stage']):
                raise ValueError('本阶段在生成期间已被编辑；结果保存在任务中，请重新生成')
        stage=job['stage']
        if stage=='novel' and job.get('target_id'):
            chapters=p['outputs'].get('novel',{}).get('chapters',[])
            original=next((c for c in chapters if c['id']==job['target_id']),None)
            if not original: raise ValueError('指定章节已不存在')
            replacement=result['chapters'][0]; replacement['id']=original['id']; chapters[chapters.index(original)]=replacement
        else: p['outputs'][stage]=result
        p['stage_status'][stage]='draft'
        primary='script' if stage=='scene_plan' else stage
        if stage=='scene_plan': p['stage_status']['script']='draft'
        index=[s[0] for s in domain.STAGES].index(primary)
        for downstream,_,_ in domain.STAGES[index+1:]:
            if downstream in p['stage_status']: p['stage_status'][downstream]='stale'
        if stage=='storyboard':
            old={s['id']:s for s in p['segments']}
            incoming=result['segments']
            if job.get('target_id'):
                replacement=incoming[0]; replacement['id']=job['target_id']
                incoming=[replacement if s['id']==job['target_id'] else s for s in p['segments']]
            for s in incoming:
                previous=old.get(s['id'])
                if previous:
                    s['versions']=previous.get('versions',[]); s['current_version']=previous.get('current_version'); s['status']='stale' if s['versions'] else 'draft'
            # Removed generated segments are kept in the archived output revision.
            p['segments']=incoming
            p['outputs']['storyboard']={'segments':incoming}
        domain.derive_assets(p)
    mutate_project(job['project_id'],apply,'AI生成 '+job['stage'])


async def run_polish(job):
    p=job['source_snapshot']; a=next(a for a in p['assets'] if a['id']==job['target_id'])
    base='characters' if a['kind']=='character' else 'world'
    skill=job.get('skill_snapshots',{}).get(base) or skills.load(base,p.get('bindings',{}).get('skill_'+base))
    provider=providers.provider_for(p,'text',job['provider_id'])
    result,usage,request=await providers.text_generate(provider,skill['content']+'\n'+creation.guidance(p,'assets')+'\n仅润色当前资产描述，保持身份、名称和既有事实。',{'asset':a,'settings':p['settings'],'request':job['instruction']},{'description':'润色后描述'})
    if not isinstance(result.get('description'),str) or not result['description'].strip(): raise ValueError('模型缺少润色后描述')
    log(job,'资产描述校验通过',result=result,pending_apply=False,usage=usage,skill={'id':skill['id'],'version':skill['version']},request_snapshot=request)
    apply_result(job,result)
    log(job,'资产描述已自动更新',pending_apply=False,applied_automatically=True,applied_at=store.now())


async def run_image(job):
    if job['stage']=='storyboard': return await run_shot_image(job)
    p=job['source_snapshot']; asset=next(a for a in p['assets'] if a['id']==job['target_id'])
    provider=image_provider(p,job); skill=skills.for_job(job,'assets')
    target=store.MEDIA/(store.uid('image')+'.png')
    selected_variant=next((v for v in asset.get('variants',[]) if v['id'] in job['instruction']),None)
    prompt=skill['content']+'\n'+creation.guidance(p,'assets',visual_only=True)+'\n'+asset['name']+' '+asset.get('description','')+'\n'+asset.get('image_prompt','')+'\n'+job['instruction']
    if selected_variant: prompt+='\n指定版本：'+selected_variant['name']+' '+selected_variant.get('description','')
    reference_file=None
    if skill.get('image_mode')=='compiled':
        prompt=await image_prompts.compile_prompt(p,job,skill,asset,[],selected_variant,log)
        reference_file=asset['references'][-1]['file'] if asset.get('references') else None
    if not job.get('remote_id'): prompt=asset_visuals.enforce(prompt,asset)
    if not job.get('remote_id'): log(job,'即将提交图片生成；受理结果不明时禁止自动重复',submission_started=True)
    result=await providers.image_generate(provider,prompt,target,reference_file,remote_id=job.get('remote_id'),
        submitted=lambda remote:log(job,'异步生图已提交，恢复时继续查询原任务',remote_id=remote,model=provider['model']))
    reference={'file':result,'job_id':job['id'],'prompt':prompt,'variant_id':selected_variant['id'] if selected_variant else None}
    def apply(latest):
        a=next(a for a in latest['assets'] if a['id']==asset['id']); a['references'].append(reference); a['version']+=1
        for segment in latest['segments']:
            if asset['id'] in segment.get('character_ids',[])+segment.get('prop_ids',[])+[segment.get('location_id')]: segment['status']='stale'
    mutate_project(p['id'],apply,'生成资产参考图'); log(job,'参考图已保存',result=reference,skill={'id':skill['id'],'version':skill['version']},model=provider['model'])


async def run_white(job):
    p=store.get('projects',job['project_id']); s=next(s for s in p['segments'] if s['id']==job['target_id'])
    v=next(v for v in s['versions'] if v['id']==s['current_version'])
    if not v.get('tail') or not v.get('tail_accepted'): raise ValueError('请先确认系统截取的原尾帧')
    provider=providers.provider_for(p,'image',job['provider_id'])
    target=store.MEDIA/(store.uid('white')+'.png')
    prompt='将这张尾帧转换为白色无纹理模型参考。严格保持所有人物、姿势、站位、朝向、遮挡、道具和场景布局以及相机位置，不增删任何对象。柔和灰色背景。'+job['instruction']
    result=await providers.image_generate(provider,prompt,target,v['tail'])
    def apply(latest):
        segment=next(x for x in latest['segments'] if x['id']==s['id']); version=next(x for x in segment['versions'] if x['id']==v['id'])
        version.update(white=result,white_accepted=False,white_source=v['tail'],white_method=provider['model'],white_job=job['id'])
    mutate_project(p['id'],apply,'白模转换待确认'); log(job,'白模已生成，请确认站位与原尾帧一致后使用',result={'file':result,'source':v['tail'],'source_version':v['id']})


async def run_video(job,p):
    provider=provider_for_job(job,'video')
    if provider['protocol'] not in ('comfy','json-video','ark','dashscope','jimeng','lingquan'): raise ValueError('视频服务协议不受支持')
    target=store.MEDIA/(job['id']+'.mp4')
    if not job.get('remote_id'):
        original=next(s for s in job['source_snapshot']['segments'] if s['id']==job['target_id'])
        # Keep queued assets/settings immutable, but use the finished predecessor from this chain.
        snapshot=copy.deepcopy(job['source_snapshot'])
        previous=original.get('previous_id')
        if previous:
            latest_previous=next(s for s in p['segments'] if s['id']==previous)
            latest_previous=copy.deepcopy(latest_previous)
            selected=next((v for v in latest_previous.get('versions',[]) if v['id']==latest_previous.get('current_version')),None)
            # The seam must use the last retained frame, not a frame after the edit out-point.
            if selected and latest_previous.get('trim_end'):
                info=await media.probe(selected['file'])
                end=min(float(latest_previous['trim_end']),float(info['format']['duration']))
                frame=await media.tail(selected['file'],max(0,end-1/24))
                selected.update(frame)
            snapshot['segments']=[copy.deepcopy(latest_previous) if s['id']==previous else s for s in snapshot['segments']]
        input_bundle=domain.bundle(snapshot,original,provider=provider)
        if deployment.is_managed_h3(provider):
            log(job,'检查本地 H3 服务；未启动时自动启动并等待就绪',submission_started=False)
            await deployment.ensure_service_ready(lambda message:log(job,message))
        log(job,'输入包已编译，即将提交；提交结果不明时禁止自动重复',input_bundle=input_bundle,submission_started=True)
        try:
            remote,request=await providers.video_submit(provider,input_bundle)
        except (httpx.ConnectError, httpx.ConnectTimeout) as error:
            # No connection was established, so no generation request was accepted.
            log(job,'未连接到视频服务，任务尚未提交',submission_started=False,uncertain=False)
            message = ('本地 H3 服务就绪后连接中断，视频尚未提交，请查看服务日志后恢复任务'
                       if deployment.is_managed_h3(provider) else '无法连接视频服务，请检查渠道地址和网络后重试')
            raise ValueError(message) from error
        except (httpx_error_types()):
            log(job,'服务提交结果不明，请核查后再决定重试',uncertain=True); raise
        log(job,'远程任务已提交',remote_id=remote,request_snapshot=request,model=provider['model'])
    else: log(job,'恢复查询已有远程任务，未重复提交')
    poll_failures=0
    poll_started=asyncio.get_running_loop().time()
    while True:
        if provider['protocol']=='lingquan' and asyncio.get_running_loop().time()-poll_started>4200:
            raise ValueError('灵泉视频查询超过 70 分钟；已保留远程任务 ID，请先核查平台任务记录再恢复查询')
        try:
            result=await providers.video_poll(provider,job['remote_id'],target)
            poll_failures=0
        except httpx_error_types():
            poll_failures+=1
            if poll_failures>=3: raise ValueError('视频服务连接断开；已保留远程任务ID，可恢复查询')
            log(job,'连接暂时失败，继续查询原任务'); await asyncio.sleep(5); continue
        if result: break
        await asyncio.sleep(5 if provider['protocol'] == 'lingquan' else 3)
    await media.probe(result)
    frame=await media.tail(result)
    version={'id':store.uid('version'),'file':result,'created_at':store.now(),'job_id':job['id'],'remote_id':job['remote_id'],**frame,'bundle':job['input_bundle']}
    def apply(latest):
        s=next(s for s in latest['segments'] if s['id']==job['target_id']); s['versions'].append(version)
        if job.get('preview'):
            version['preview']=True
        else:
            s['current_version']=version['id']; s['status']='draft'
            domain.stale_dependents(latest,s['id'])
    latest=mutate_project(p['id'],apply,'视频生成新版本')
    log(job,'视频已回收，系统已自动截取尾帧',result=version)
    if latest['settings'].get('white_mode') and frame['tail_accepted']:
        try:
            image=providers.provider_for(latest,'image')
            white=create(latest,{'kind':'white','stage':'video','target_id':job['target_id'],'provider_id':image['id']})
            log(job,'已自动排入白模转换；下一段等待布局确认',white_job_id=white['id'])
        except ValueError as error: log(job,'白模转换待配置：'+str(error))


def httpx_error_types():
    import httpx
    return (httpx.TransportError, asyncio.TimeoutError)


async def chain(job):
    if job.get('preview'): return
    p=store.get('projects',job['project_id']); order=['direction','characters','world','novel','script','performance','storyboard']
    if job['stage'] not in order or job['remaining']<=1: return
    if job['stage'] in p['settings'].get('pause_at',[]):
        log(job,'自动制作暂停于本阶段，请确认后继续',chain_paused=True); return
    idx=order.index(job['stage'])+1
    if idx>=len(order): return
    create(p,{'kind':'text','stage':order[idx],'auto':True,'remaining':job['remaining']-1})


def cancel(ident):
    job=store.get('jobs',ident)
    if job['status'] not in ACTIVE: raise ValueError('该任务当前不能取消')
    log(job,'用户停止任务',status='cancelled')
    if ident in tasks: tasks[ident].cancel()
    return public(job)


def retry(ident, acknowledged=False):
    with submission_lock:
        return _retry(ident, acknowledged)


def _retry(ident, acknowledged=False):
    job=store.get('jobs',ident)
    p=store.get('projects',job['project_id'])
    task_locks.assert_submission(p, job, exclude=ident)
    if job['status'] not in ('failed','cancelled'): raise ValueError('仅失败/取消任务可恢复')
    if job.get('uncertain') and not acknowledged: raise ValueError('提交是否成功不明，请先核查服务任务并勾选确认后重试')
    if job.get('attempt',0)>=4: raise ValueError('已达恢复次数上限，请检查配置后创建新任务')
    log(job,'恢复已有任务'+('，继续查询原ID' if job.get('remote_id') else ''),status='queued',attempt=job.get('attempt',0)+1,error=None)
    launch(ident); return public(job)


async def run_shot_image(job):
    p=job['source_snapshot']; segment=next(s for s in p['segments'] if s['id']==job['target_id'])
    provider=image_provider(p,job)
    skill=skills.for_job(job,'assets')
    refs=[a for a in p['assets'] if a['id'] in segment.get('character_ids',[])+segment.get('prop_ids',[])+[segment.get('location_id')]]
    prompt=skill['content']+'\n'+creation.guidance(p,'assets',visual_only=True)+'\n'+segment.get('image_prompt',segment.get('prompt',''))+'\n'+json.dumps(segment.get('shots',[]),ensure_ascii=False)+'\n'+json.dumps([{'name':a['name'],'description':a.get('description','')} for a in refs],ensure_ascii=False)+'\n'+job['instruction']
    if not segment.get('image_prompt') and not segment.get('prompt') and not any(s.get('action') for s in segment.get('shots', [])): raise ValueError('请先填写镜头画面描述')
    direct_canvas=bool(segment.get('canvas_node_id') and segment.get('image_prompt'))
    if direct_canvas:
        visual_kind=segment.get('canvas_image_purpose')
        visual_target={'kind':visual_kind} if visual_kind in asset_visuals.ASSET_KINDS else segment
        prompt=asset_visuals.enforce(segment['image_prompt'],visual_target)
        if not job.get('remote_id'): log(job,'使用画布卡片的完整生图提示词，直接调用所选图片模型')
    else:
        if skill.get('image_mode')=='compiled': prompt=await image_prompts.compile_prompt(p,job,skill,segment,refs,None,log)
        if not job.get('remote_id'): prompt=asset_visuals.enforce(prompt,segment)
    target=store.MEDIA/(store.uid('shotimage')+'.png')
    reference=next((a['references'][-1]['file'] for a in refs if a.get('references')),None)
    if providers.async_image_contract(provider) or provider.get('protocol')=='lingquan':
        reference=[a['references'][-1]['file'] for a in refs if a.get('references')]
    if not job.get('remote_id'): log(job,'即将提交镜头图片；受理结果不明时禁止自动重复',submission_started=True)
    result=await providers.image_generate(provider,prompt,target,reference,remote_id=job.get('remote_id'),
        submitted=lambda remote:log(job,'异步生图已提交，恢复时继续查询原任务',remote_id=remote,model=provider['model']))
    image={'id':store.uid('shotimg'),'file':result,'job_id':job['id'],'source':'generated','created_at':store.now(),'source_revision':p['revision'],'prompt':prompt}
    def apply(latest):
        current=next((s for s in latest['segments'] if s['id']==segment['id']),None)
        if not current: raise ValueError('镜头已不存在，生成图片保留在任务结果中')
        current.setdefault('images',[]).append(image)
        current['current_image']=image['id']
        current['input_mode']='shot_image'
    mutate_project(p['id'],apply,'生成并自动选用镜头图片')
    log(job,'镜头图片已生成并自动选用',result=image,model=provider['model'],skill={'id':skill['id'],'version':skill['version']})


def image_provider(p, job):
    provider=provider_for_job(job,'image')
    if job['source_snapshot']['settings'].get('image_size'): provider['size']=job['source_snapshot']['settings']['image_size']
    return provider


def provider_for_job(job,kind):
    snapshot=job.get('provider_snapshot')
    if not snapshot: return providers.provider_for(job['source_snapshot'],kind,job['provider_id'])
    current=next((p for p in providers.settings()['providers'] if p['id']==job['provider_id']),None)
    if not current or current.get('base_url')!=snapshot.get('base_url'):
        raise ValueError('任务渠道地址已变更或移除，请恢复原渠道后重试；未提交到其他服务')
    return {**copy.deepcopy(snapshot),**{k:current[k] for k in ('secret','ak_secret','sk_secret') if k in current}}
