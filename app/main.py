import asyncio
import base64
import copy
import io
import json
import mimetypes
import os
import re
import zipfile
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from xml.etree import ElementTree
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
from PIL import Image
from . import store, domain, skills, providers, jobs, media, deployment, presets, connections, library, assistant, creation, recycle, workflow
from . import video_versions
from . import video_exports
from . import task_records
from . import task_locks
from . import runtime
from . import canvas
from . import yaoguang
from . import mcp_integration

deploy_task = None


@asynccontextmanager
async def lifespan(app):
    assistant.recover_runs()
    state=deployment.status()
    if state['status']=='running': deployment.update(status='failed',error='部署被中断，可继续下载')
    await jobs.recover()
    mcp_integration.mcp_production.recover()
    yield
    mcp_integration.mcp_production.stop()
    for task in jobs.tasks.values():
        if not task.done(): task.cancel()


app=FastAPI(title='AI漫剧工作台',version='0.1.0',lifespan=lifespan)
app.include_router(library.router)
app.include_router(assistant.router)
app.include_router(recycle.router)
app.include_router(workflow.router)
app.include_router(video_versions.router)
app.include_router(canvas.router)
app.include_router(yaoguang.router)
app.include_router(mcp_integration.router)


@app.middleware('http')
async def local_guard(request, call_next):
    host=request.headers.get('host','').split(':')[0]
    if host not in ('localhost','127.0.0.1','testserver'):
        return JSONResponse({'detail':'仅允许本机访问'},status_code=403)
    origin=request.headers.get('origin')
    if origin and origin!=str(request.base_url).rstrip('/'):
        return JSONResponse({'detail':'不允许跨站访问本机工作台'},status_code=403)
    result=await call_next(request)
    # Desktop WebView must revalidate app assets after an update.
    if request.url.path != '/media' and not request.url.path.startswith('/media/'):
        result.headers['Cache-Control']='no-store, max-age=0'
    result.headers['X-Content-Type-Options']='nosniff'
    if result.headers.get('content-type','').startswith('application/json'):
        result.headers['content-type']='application/json; charset=utf-8'
    result.headers['Referrer-Policy']='no-referrer'
    ancestor="'self'" if request.url.path=='/vendor/yaoguang/smart-canvas.html' else "'none'"
    result.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors "+ancestor
    return result


@app.exception_handler(ValueError)
async def value_error(request,error): return JSONResponse({'detail':str(error)},status_code=400)


@app.exception_handler(KeyError)
async def missing_error(request,error): return JSONResponse({'detail':'目标对象不存在，请刷新后重试'},status_code=404)


@app.exception_handler(httpx.TransportError)
async def network_error(request,error): return JSONResponse({'detail':'无法连接服务，请检查地址、网络与服务启动状态'},status_code=502)


@app.get('/api/health')
def health():
    return {'ok':True,'name':'AI漫剧工作台','version':'0.1.0','data_dir':str(store.DATA),
            'workspace_id':base64.b64encode(str(store.DATA).encode()).decode(), 'pid':os.getpid(),
            'runtime_id':runtime.INSTANCE_ID, 'backend_fingerprint':runtime.LOADED_FINGERPRINT}


@app.get('/api/bootstrap')
def bootstrap():
    projects = store.project_summaries()
    return {'projects':projects,'trash_count':len(recycle.listing()),'creation_presets':creation.catalog(),
            'settings':providers.public_settings(),'skills':skills.list_skills(),'stages':domain.STAGES,
            'jobs':list_jobs(),'schemas':domain.SCHEMAS,'provider_presets':presets.catalog()}


@app.get('/api/projects')
def project_list():
    return {'projects':store.project_summaries(), 'trash_count':len(recycle.listing())}


@app.get('/api/projects/{ident}/revision')
def project_revision(ident):
    project, _ = store.project_overview(ident)
    return {'id':ident, 'revision':project['revision']}


@app.post('/api/projects')
def create_project(payload:dict):
    if payload.get('entry','idea') not in ('idea','novel','script'): raise ValueError('项目入口错误')
    if not payload.get('source','').strip(): raise ValueError('请填写灵感或导入原文')
    return store.save_project(domain.project_new(payload),reason='新建项目')


@app.post('/api/projects/{ident}/trash')
def trash_project(ident, payload:dict):
    if payload.get('revision') is None: raise ValueError('请刷新作品列表后再删除')
    project = recycle.change(ident, True, payload['revision'])
    return store.project_summary(project) if payload.get('summary') else project


@app.get('/api/projects/{ident}')
def get_project(ident): return store.get('projects',ident)


@app.put('/api/projects/{ident}')
def save_project(ident,payload:dict):
    with jobs.submission_lock:
        return save_project_locked(ident,payload)


def save_project_locked(ident,payload):
    previous=store.get('projects',ident); p=copy.deepcopy(payload)
    task_locks.assert_available(previous, task_locks.changes(previous, p))
    if p.get('id')!=ident: raise ValueError('项目 ID 不匹配')
    expected=p.get('revision')
    if expected is None: raise ValueError('保存须包含项目版本号')
    required=('outputs','assets','segments','settings','stage_status','bindings','artifacts')
    if any(k not in p for k in required): raise ValueError('项目字段不完整')
    if p.get('settings',{}).get('episode_duration',0)<=0: raise ValueError('单集时长必须为正数')
    for a in p['assets']:
        for reference in a.get('references',[]): providers.file_path(reference['file'])
        if a.get('voice'): providers.file_path(a['voice'])
    for segment in p['segments']:
        for image in segment.get('images', []):
            file = providers.file_path(image['file'])
            if file.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'): raise ValueError('镜头参考图必须为图片')
        if segment.get('current_image') and not any(x['id']==segment['current_image'] for x in segment.get('images', [])): raise ValueError('选用的镜头图片不存在')
    ids={a['id'] for a in p['assets']}
    deleted={a['id'] for a in previous['assets']}-ids
    if any(deleted.intersection(s.get('character_ids',[])+s.get('prop_ids',[])+[s.get('location_id')]) for s in p['segments']):
        raise ValueError('被分镜引用的资产不能删除，请先解除关联')
    changed={a['id'] for a in p['assets'] if a!=next((old for old in previous['assets'] if old['id']==a['id']),None)}
    old_segments={s['id']:s for s in previous['segments']}
    for s in p['segments']:
        if changed.intersection(s.get('character_ids',[])+s.get('prop_ids',[])+[s.get('location_id')]): s['status']='stale'
        old=old_segments.get(s['id'])
        if old and s.get('shots') != old.get('shots') and s.get('dialogue_text') == old.get('dialogue_text'):
            s.pop('dialogue_text', None)
        if old and any(s.get(k)!=old.get(k) for k in ('prompt','shots','dialogue_text','duration','character_ids','prop_ids','location_id','variant_ids','previous_id','current_image','input_mode')):
            s['status']='stale' if s.get('versions') else 'draft'; domain.stale_dependents(p,s['id'])
    if p['segments']: p['outputs']['storyboard']={'segments':p['segments']}
    workflow.sync_manual(previous, p)
    domain.derive_assets(p)
    return store.save_project(p,expected)


@app.get('/api/projects/{ident}/revisions')
def list_revisions(ident):
    return [{'id':r['id'],'at':r['at'],'reason':r['reason'],'revision':r['project']['revision']} for r in store.revisions(ident)]


@app.post('/api/projects/{ident}/restore/{revision_id}')
def restore(ident,revision_id):
    task_locks.assert_available(store.get('projects',ident), {'reads':set(), 'writes':{'*'}})
    revision=next((r for r in store.revisions(ident) if r['id']==revision_id),None)
    if not revision: raise KeyError(revision_id)
    return store.save_project(revision['project'],reason='恢复历史版本')


@app.get('/api/projects/{ident}/checks')
def checks(ident): return domain.checks(store.get('projects',ident),providers.settings())


@app.post('/api/projects/{ident}/validate-stage/{stage}')
def validate_stage(ident,stage,payload:dict):
    if stage not in domain.SCHEMAS: raise ValueError('阶段不存在')
    return domain.normalize(stage,payload,store.get('projects',ident))


@app.get('/api/projects/{ident}/bundle/{segment_id}')
def bundle(ident,segment_id):
    p=store.get('projects',ident); segment=next(s for s in p['segments'] if s['id']==segment_id)
    return domain.bundle(p,segment,provider=providers.provider_for(p,'video'))


@app.post('/api/projects/{ident}/jobs')
async def create_job(ident,payload:dict): return jobs.create(store.get('projects',ident),payload)


@app.post('/api/projects/{ident}/batch/estimate')
def estimate(ident,payload:dict):
    p=store.get('projects',ident); targets=payload.get('targets',[])
    kind=payload.get('kind','video'); provider=providers.provider_for(p,'image' if kind=='image' else 'video')
    if len(set(targets))!=len(targets): raise ValueError('批量目标重复')
    available={s['id'] for s in (p['assets'] if kind=='image' else p['segments'])}
    if any(t not in available for t in targets): raise ValueError('批量目标不存在')
    count=len(targets)
    unit=provider.get('unit_price')
    price=(sum(float(s['duration']) for s in p['segments'] if s['id'] in targets) if provider.get('price_unit')=='second' and kind=='video' else count)*float(unit) if unit is not None else None
    blocks=[]
    if count<1: blocks.append('请选择制作对象')
    if count>int(p['settings'].get('max_jobs',10)): blocks.append('任务数量超出项目上限')
    budget=p['settings'].get('budget')
    if budget is not None:
        if price is None: blocks.append('价格未知，无法校验费用上限，请填写服务单价或清除上限后人工判断')
        elif price>float(budget): blocks.append('估算费用超过项目上限')
    if kind=='video': blocks += [c['message'] for c in domain.checks(p,providers.settings()) if c['severity']=='error' and c.get('target') in targets]
    return {'count':count,'model':provider['model'],'provider':provider['name'],'estimated_cost':round(price,4) if price is not None else None,'currency':provider.get('currency','CNY'), 'basis':'用户配置单价×秒数' if provider.get('price_unit')=='second' else '用户配置单价×任务数','blockers':list(dict.fromkeys(blocks))}


@app.post('/api/projects/{ident}/batch')
async def batch(ident,payload:dict):
    e=estimate(ident,payload)
    if e['blockers']: raise ValueError('；'.join(e['blockers']))
    p=store.get('projects',ident)
    for target in payload['targets']:
        task_locks.assert_submission(p, {'kind':payload.get('kind','video'),'target_id':target})
    return [jobs.create(p,{'kind':payload.get('kind','video'),'stage':'assets' if payload.get('kind')=='image' else 'video','target_id':target}) for target in payload['targets']]


@app.get('/api/jobs')
def list_jobs(offset:int=0, limit:int=150):
    if offset < 0 or not 1 <= limit <= 150: raise ValueError('任务分页参数无效')
    # Running jobs must never disappear behind a long list of newer completed jobs.
    active = store.job_rows(statuses=store.ACTIVE_JOBS, visible=True)
    terminal = store.job_rows(statuses=('succeeded','failed','cancelled'), visible=True, limit=limit, offset=offset)
    return active + terminal


@app.get('/api/jobs/{ident}')
def job_detail(ident):
    job = store.get('jobs', ident)
    store.project_overview(job['project_id'])
    return jobs.public(job)


@app.get('/api/projects/{ident}/tasks')
def project_tasks(ident, limit:int=50, offset:int=0, status:str='all', stage:str='all', query:str=''):
    if not 1 <= limit <= 100 or offset < 0: raise ValueError('任务分页参数无效')
    return task_records.listing(ident, limit=limit, offset=offset, status=status, stage=stage, query=query)


@app.post('/api/jobs/{ident}/cancel')
def cancel(ident): return jobs.cancel(ident)


@app.post('/api/jobs/{ident}/retry')
async def retry(ident,payload:dict): return jobs.retry(ident,payload.get('acknowledged',False))


@app.post('/api/jobs/{ident}/apply')
def apply(ident):
    job=store.get('jobs',ident)
    task_locks.assert_submission(store.get('projects',job['project_id']), job, exclude=ident)
    if not job.get('result') or job['kind'] not in ('text','polish'): raise ValueError('没有可应用的文本结果')
    if job.get('applied_at') and not job.get('pending_apply'): return workflow.ensure(store.get('projects',job['project_id']))
    if job['stage'] in workflow.SCHEMAS:
        if not job.get('pending_apply'): return workflow.ensure(store.get('projects',job['project_id']))
        if job['status'] != 'succeeded': raise ValueError('请等待建议稿完成后采用')
    job['applied_by_user']=True; jobs.apply_result(job,job['result']); jobs.log(job,'用户已应用改稿',pending_apply=False,applied_by_user=True,applied_at=store.now())
    return workflow.ensure(store.get('projects',job['project_id']))


@app.post('/api/jobs/{ident}/discard')
def discard_job(ident):
    job=store.get('jobs',ident); store.get('projects',job['project_id'])
    if job['stage'] not in workflow.SCHEMAS or job['status'] != 'succeeded': raise ValueError('没有可放弃的流程建议稿')
    jobs.log(job,'用户保留原内容，建议稿仍保存在任务历史',pending_apply=False,discarded=True)
    return jobs.public(job)


@app.get('/api/settings')
def settings(): return providers.public_settings()


@app.get('/api/provider-presets')
def provider_presets(): return presets.catalog()


@app.put('/api/settings')
def set_settings(payload:dict): return providers.save_settings(payload)


@app.get('/api/genres')
def list_genres():
    """返回所有可选题材。"""
    return creation.GENRE_OPTIONS


@app.get('/api/projects/{ident}/genre')
def get_project_genre(ident):
    p = store.get('projects', ident)
    genre_preset = p.get('settings', {}).get('genre_preset', '')
    return {'genre_preset': genre_preset, 'genre_label': p.get('settings', {}).get('genre', '')}


@app.put('/api/projects/{ident}/genre')
def set_project_genre(ident, payload: dict):
    genre_preset = payload.get('genre_preset', '').strip()
    if genre_preset and genre_preset != 'custom' and genre_preset not in creation.GENRE_IDS:
        raise ValueError(f'未知题材: {genre_preset}')

    p = store.get('projects', ident)
    p.setdefault('settings', {})['genre_preset'] = genre_preset

    # 自动填充 genre 字段（向后兼容）
    if genre_preset and genre_preset != 'custom':
        p['settings']['genre'] = creation.genre_label(genre_preset)

    return store.save_project(p, p['revision'], '修改项目题材')


@app.get('/api/projects/{ident}/settings/cinematic-mode')
def get_cinematic_mode(ident):
    p = store.get('projects', ident)
    return {'enabled': p.get('settings', {}).get('cinematic_mode', False)}


@app.put('/api/projects/{ident}/settings/cinematic-mode')
def set_cinematic_mode(ident, payload: dict):
    p = store.get('projects', ident)
    enabled = bool(payload.get('enabled', False))
    p.setdefault('settings', {})['cinematic_mode'] = enabled
    return store.save_project(p, p['revision'], '切换电影感模式')


@app.post('/api/projects/{ident}/storyboard/review')
def review_storyboard(ident, payload: dict):
    from . import storyboard_review
    p = store.get('projects', ident)
    settings = p.get('settings', {})
    rules = payload.get('rules', settings.get('review_rules_mode', 'core'))
    enabled = payload.get('enabled_rules', settings.get('enabled_review_rules'))
    return storyboard_review.review_project_storyboard(ident, rules, enabled)


@app.get('/api/storyboard/review/rules')
def review_rule_catalog():
    from . import storyboard_review
    return storyboard_review.get_rule_catalog()


@app.get('/api/projects/{ident}/settings/review-rules')
def get_review_rules(ident):
    p = store.get('projects', ident)
    settings = p.get('settings', {})
    return {'rules_mode': settings.get('review_rules_mode', 'core'),
            'enabled_rules': settings.get('enabled_review_rules', [])}


@app.put('/api/projects/{ident}/settings/review-rules')
def set_review_rules(ident, payload: dict):
    p = store.get('projects', ident)
    settings = p.setdefault('settings', {})
    mode = payload.get('rules_mode', 'core')
    if mode not in ('core', 'full', 'custom'):
        raise ValueError('rules_mode 必须是 core/full/custom')
    settings['review_rules_mode'] = mode
    if mode == 'custom':
        enabled = payload.get('enabled_rules', [])
        if not isinstance(enabled, list) or not all(isinstance(r, int) and 1 <= r <= 19 for r in enabled):
            raise ValueError('enabled_rules 必须是 1-19 的整数数组')
        settings['enabled_review_rules'] = enabled
    return store.save_project(p, p['revision'], '修改审查规则配置')


@app.get('/api/projects/{ident}/settings/expert-mode')
def get_expert_mode(ident):
    p = store.get('projects', ident)
    return {'enabled': p.get('settings', {}).get('expert_mode', False),
            'export_markdown': p.get('settings', {}).get('export_markdown', True)}


@app.put('/api/projects/{ident}/settings/expert-mode')
def set_expert_mode(ident, payload: dict):
    p = store.get('projects', ident)
    settings = p.setdefault('settings', {})
    settings['expert_mode'] = bool(payload.get('enabled', False))
    settings['export_markdown'] = bool(payload.get('export_markdown', True))
    return store.save_project(p, p['revision'], '切换专家模式')


@app.get('/api/projects/{ident}/storyboard/markdown')
def storyboard_markdown(ident):
    from . import markdown_export
    p = store.get('projects', ident)
    return {'markdown': markdown_export.generate_markdown_storyboard(p),
            'filename': f"{p.get('name', '未命名')}_分镜脚本.md"}


@app.get('/api/projects/{ident}/storyboard/markdown/download')
def storyboard_markdown_download(ident):
    from . import markdown_export
    from fastapi.responses import Response
    from urllib.parse import quote
    p = store.get('projects', ident)
    content = markdown_export.generate_markdown_storyboard(p)
    filename = f"{p.get('name', '未命名')}_分镜脚本.md"
    # 头部必须 latin-1 可编码：ASCII 兜底名 + RFC 5987 的 UTF-8 文件名
    return Response(content=content.encode('utf-8'), media_type='text/markdown; charset=utf-8',
                    headers={'Content-Disposition': f"attachment; filename=\"storyboard.md\"; filename*=UTF-8''{quote(filename)}"})


@app.post('/api/projects/{ident}/segments/{segment_id}/enhance')
async def enhance_segment(ident, segment_id):
    """用电影感核心约束重新生成单个 segment（预览稿，不直接覆盖）。"""
    p = store.get('projects', ident)
    segment = next((s for s in p.get('segments', []) if s['id'] == segment_id), None)
    if not segment: raise KeyError(segment_id)

    # 仅让本次任务的提交快照带上电影感开关，随后恢复，不写回项目
    original = p.get('settings', {}).get('cinematic_mode', False)
    p.setdefault('settings', {})['cinematic_mode'] = True
    try:
        job = jobs.create(p, {
            'kind': 'text',
            'stage': 'storyboard',
            'target_id': segment_id,
            'instruction': '用电影级镜头语言重新设计这个镜头，遵循核心8条约束',
            'preview': True,
        })
    finally:
        p['settings']['cinematic_mode'] = original
    return jobs.public(job)


@app.post('/api/providers/models')
async def provider_models(payload:dict):
    return await connections.models(connections.prepare(payload))


@app.post('/api/providers/probe')
async def provider_probe(payload:dict):
    return await connections.probe(connections.prepare(payload))


@app.post('/api/providers/{ident}/test')
async def test_provider(ident):
    provider=next((p for p in providers.settings()['providers'] if p['id']==ident),None)
    if not provider: raise KeyError(ident)
    if provider['protocol']=='lingquan': return await connections.probe(provider)
    if provider['protocol']=='comfy': return await providers.comfy_check(provider)
    if provider['protocol'] in ('ark','dashscope','jimeng'):
        from .official import check
        return await check(provider)
    async with httpx.AsyncClient(timeout=20) as client:
        path=provider.get('contract',{}).get('health_path','/models')
        response=await client.get(providers.endpoint(provider,path),headers=providers.headers(provider)); providers.require_ok(response)
        try: body=response.json()
        except ValueError: body={}
    return {'ok':True,'models':[m['id'] for m in body.get('data',[]) if isinstance(m,dict) and 'id' in m],'message':'连接成功；实际生成需提交样片验证'}


@app.post('/api/skills')
def add_skill(payload:dict): return skills.import_skill(payload)


@app.put('/api/skills/defaults')
def set_skill_default(payload:dict): return skills.set_default(payload.get('stage'),payload.get('id'))

@app.put('/api/skills/modules/{ident}')
def set_skill_module(ident,payload:dict):
    from . import skill_dispatch
    skill_dispatch.set_enabled(ident,payload.get('enabled'))
    return {'skills':skills.list_skills()}


@app.post('/api/import/text')
async def import_text(file:UploadFile=File(...)):
    body=await file.read(50*1024**2+1)
    if len(body)>50*1024**2: raise ValueError('文档最大50MB')
    if not body: raise ValueError('文件为空，请确认文件已下载完成后重新选择')
    suffix=Path(file.filename).suffix.lower()
    if suffix=='.docx':
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            info=z.getinfo('word/document.xml')
            if info.file_size>20*1024**2: raise ValueError('文档内容过大')
            root=ElementTree.fromstring(z.read(info)); ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            text='\n'.join(''.join(p.itertext()) for p in root.findall('.//w:body//w:p',ns))
    elif suffix in ('.txt','.md'):
        if body.startswith((b'\xff\xfe',b'\xfe\xff')):
            text=body.decode('utf-16')
        else:
            try: text=body.decode('utf-8-sig')
            except UnicodeDecodeError: text=body.decode('gb18030')
    else: raise ValueError('首版支持 TXT、Markdown、DOCX 文本导入')
    if not text.strip(): raise ValueError('文件中没有小说正文，请检查文件内容后重新选择')
    if '\x00' in text: raise ValueError('文本编码无法识别，请将文件另存为 UTF-8 后重新导入')
    return {'name':file.filename,'text':text}


from pathlib import Path


@app.post('/api/media/upload')
async def upload(file:UploadFile=File(...)):
    suffix=Path(file.filename).suffix.lower()
    if suffix not in ('.png','.jpg','.jpeg','.webp','.mp4','.mov','.webm','.mkv','.wav','.mp3','.m4a','.ogg'): raise ValueError('素材类型不支持')
    name=store.uid('upload')+suffix; target=store.MEDIA/name; size=0
    try:
        with target.open('wb') as out:
            while chunk:=await file.read(1024**2):
                size+=len(chunk)
                if size>500*1024**2: raise ValueError('单个素材最大500MB')
                out.write(chunk)
        if suffix in ('.png','.jpg','.jpeg','.webp'):
            with Image.open(target) as img: img.verify()
        if suffix in ('.mp4','.mov','.webm','.mkv'): await media.probe(name)
        if suffix in ('.wav','.mp3','.m4a','.ogg'): await media.validate_audio(name)
    except Exception as error:
        target.unlink(missing_ok=True)
        if isinstance(error,ValueError): raise
        raise ValueError('素材内容无效，文件类型与实际内容不符') from error
    return {'file':name,'original_name':file.filename,'size':size,'url':'/media/'+name}


@app.post('/api/projects/{ident}/tail/{segment_id}')
async def extract_tail(ident,segment_id,payload:dict):
    task_locks.assert_available(store.get('projects',ident), {'reads':set(), 'writes':{'segment:'+segment_id}})
    p=store.get('projects',ident); s=next(s for s in p['segments'] if s['id']==segment_id); v=next(v for v in s['versions'] if v['id']==s['current_version'])
    result=await media.tail(v['file'],payload.get('at'))
    def apply(latest):
        segment=next(s for s in latest['segments'] if s['id']==segment_id); version=next(x for x in segment['versions'] if x['id']==v['id'])
        version.update(result); version.pop('white',None); version['white_accepted']=False; domain.stale_dependents(latest,segment_id)
    return jobs.mutate_project(ident,apply,'重新选择尾帧')


@app.post('/api/projects/{ident}/import-video/{segment_id}')
async def import_video(ident,segment_id,payload:dict):
    task_locks.assert_available(store.get('projects',ident), {'reads':set(), 'writes':{'segment:'+segment_id}})
    filename=payload['file']; await media.probe(filename); frame=await media.tail(filename)
    version={'id':store.uid('version'),'file':filename,'created_at':store.now(),'source':'手工导入',**frame}
    def apply(latest):
        segment=next(s for s in latest['segments'] if s['id']==segment_id)
        segment['versions'].append(version); segment['current_version']=version['id']; segment['status']='draft'; domain.stale_dependents(latest,segment_id)
    return jobs.mutate_project(ident,apply,'导入视频片段')


@app.get('/api/projects/{ident}/video-download')
def download_project_video(ident, segment_id:str='', version_id:str='', artifact_id:str=''):
    p=store.get('projects',ident)
    if segment_id and not artifact_id:
        segment=next((s for s in p['segments'] if s['id']==segment_id),None)
        if not segment: raise ValueError('镜头不存在')
        version=next((v for v in segment.get('versions',[]) if v['id']==(version_id or segment.get('current_version'))),None)
        if not version: raise ValueError('当前镜头没有选用视频')
        filename=video_exports.download_name(p,segment=segment,version=version)
        file=version['file']
    elif artifact_id and not segment_id:
        artifact=next((a for a in p['artifacts'] if a.get('id')==artifact_id and a.get('sources') and a.get('file','').endswith('.mp4')),None)
        if not artifact: raise ValueError('成片不存在，请先导出视频')
        filename=video_exports.download_name(p,episode_id=artifact.get('episode_id'))
        file=artifact['file']
    else:
        raise ValueError('请选择要下载的镜头或成片')
    path=providers.file_path(file)
    if path.suffix.lower()!='.mp4': raise ValueError('当前结果不是 MP4 视频')
    return FileResponse(path,media_type='video/mp4',filename=filename)


@app.get('/api/projects/{ident}/export')
def export_project(ident):
    p=store.get('projects',ident); target=store.DATA/'exports'/(ident+'.zip')
    manifest={'format_version':1,'project':p,'jobs':[jobs.public(j) for j in store.all_rows('jobs') if j['project_id']==ident]}
    files=set()
    def collect(obj):
        if isinstance(obj,dict):
            for key,value in obj.items():
                if key in ('file','tail','white','voice') and isinstance(value,str): files.add(value)
                else: collect(value)
        elif isinstance(obj,list):
            for item in obj: collect(item)
    manifest['canvas']=canvas.get_canvas(ident)
    manifest['original_canvas']=yaoguang.get_canvas(ident)
    collect(p)
    collect(manifest['canvas'])
    files.update(path.name for path in recycle.media_paths(manifest['original_canvas']))
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('project.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        for name in files:
            try: z.write(providers.file_path(name),'media/'+name)
            except ValueError: pass
        for skill in skills.list_skills(): z.writestr('skills/'+skill['id']+'/SKILL.md',skill['content'])
    return FileResponse(target,filename=re.sub(r'[^\w\u4e00-\u9fff-]','_',p['name'])+'-素材包.zip')


@app.get('/api/hardware')
async def hardware(): return await asyncio.to_thread(deployment.hardware)


@app.get('/api/deployment')
def deployment_state(): return deployment.status()


@app.get('/api/deployment/service/status')
async def h3_service_state():
    address='http://127.0.0.1:8190'
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response=await client.get(address+'/system_stats')
            response.raise_for_status()
            system=response.json().get('system',{})
        args=system.get('argv',[])
        own=bool(args) and Path(args[0]).resolve()==(store.ROOT/'runtime/h3/ComfyUI/main.py').resolve()
        return {'running':own,'url':address,'message':'本地服务运行中' if own else '端口被其他服务占用'}
    except (httpx.HTTPError,ValueError,TypeError):
        return {'running':False,'url':address,'message':'本地服务未启动'}


@app.post('/api/deployment/start')
async def deploy(payload:dict):
    global deploy_task
    if not payload.get('acknowledged'): raise ValueError('请先阅读部署计划并勾选下载确认')
    if deploy_task and not deploy_task.done(): raise ValueError('部署正在进行中')
    hardware=await asyncio.to_thread(deployment.hardware)
    if hardware['blockers']: raise ValueError('；'.join(hardware['blockers']))
    deployment.update(status='running',progress=0,error=None)
    deploy_task=asyncio.create_task(deployment.install()); return deployment.status()


@app.post('/api/deployment/cancel')
def cancel_deploy(): return deployment.update(status='cancelled')


@app.post('/api/deployment/service')
def start_comfy(): return deployment.start_service()


@app.post('/api/sample')
def sample():
    from .sample import make_sample
    return store.save_project(make_sample(),reason='载入示例（人工编写）')


app.mount('/media',StaticFiles(directory=store.MEDIA),name='media')
app.mount('/',StaticFiles(directory=store.ROOT/'web',html=True),name='web')
