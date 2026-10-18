"""Adapters for the user supplied canvas frontend; no original home/library server."""
import asyncio
import copy
import json
import math
import re
import time
import io
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse
from fastapi import APIRouter, Request, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from . import store, providers, domain, jobs, assistant, skills, media, recycle, canvas as native_canvas

router=APIRouter(prefix='/api/yaoguang',tags=['original-canvas'])
ID=re.compile(r'^[A-Za-z0-9_-]{1,100}$')


def local_file(url):
    if isinstance(url,dict): url=url.get('url') or url.get('file')
    if not isinstance(url,str): raise ValueError('引用素材地址无效')
    path=urlparse(url)
    if path.scheme or path.netloc: raise ValueError('请上传素材或选用当前资产库；尚不支持直接使用外部网址')
    if path.path.startswith('/media/'): name=unquote(path.path[7:])
    elif '/' not in url and '\\' not in url: name=url
    else: raise ValueError('只能引用当前工作台的素材')
    providers.file_path(name)
    return name


def validate_graph(value):
    if not isinstance(value,dict): raise ValueError('画布数据无效')
    if len(json.dumps(value,ensure_ascii=False))>8*1024*1024: raise ValueError('画布内容过大，请将媒体上传后引用')
    nodes=value.get('nodes',[]); connections=value.get('connections',[])
    if not isinstance(nodes,list) or len(nodes)>1000 or not isinstance(connections,list) or len(connections)>4000: raise ValueError('画布节点或连线过多')
    seen=set()
    for n in nodes:
        if not isinstance(n,dict) or not isinstance(n.get('id'),str) or not ID.fullmatch(n['id']) or n['id'] in seen: raise ValueError('节点标识无效或重复')
        seen.add(n['id'])
        for k in ('x','y'):
            if not isinstance(n.get(k),(int,float)) or isinstance(n[k],bool) or not math.isfinite(n[k]) or abs(n[k])>1000000: raise ValueError('节点位置无效')
    for c in connections:
        if not isinstance(c,dict) or not isinstance(c.get('from'),str) or not isinstance(c.get('to'),str) or c['from'] not in seen or c['to'] not in seen: raise ValueError('连线引用了不存在的节点')
    viewport=value.get('viewport',{'x':0,'y':0,'scale':1})
    if not isinstance(viewport,dict): raise ValueError('画布视角无效')
    for key in ('x','y','scale'):
        number=viewport.get(key)
        if not isinstance(number,(float,int)) or isinstance(number,bool) or not math.isfinite(number) or abs(number)>1000000: raise ValueError('画布视角无效')
    if not .01<=viewport['scale']<=10: raise ValueError('画布缩放无效')
    def safe(item):
        if isinstance(item,dict):
            if any(k in ('__proto__','prototype','constructor') for k in item): raise ValueError('画布包含非法字段')
            for x in item.values(): safe(x)
        elif isinstance(item,list):
            for x in item: safe(x)
    safe(value)
    return {k:copy.deepcopy(value.get(k,default)) for k,default in [('title','无限画布'),('icon','sparkles'),('nodes',[]),('connections',[]),('viewport',{'x':0,'y':0,'scale':1}),('logs',[]),('settings',{})]}


def get_canvas(pid):
    p=store.project_overview(pid)[0]
    with store.db() as c: row=c.execute('SELECT body FROM original_canvases WHERE project_id=?',(pid,)).fetchone()
    if row: return json.loads(row['body'])
    old=native_canvas.read(pid); nodes=[]
    for n in old['nodes']:
        media=n['kind'] in ('image','video','audio','asset')
        item={'id':n['id'],'type':'smart-group' if n['kind']=='group' else 'smart-image' if media else 'smart-prompt',
              'x':n['x'],'y':n['y'],'title':n['title'],'text':n['data'].get('text',''),'images':[],
              'inputNodeIds':[e['source'] for e in old['edges'] if e['target']==n['id']],
              'studioLegacy':copy.deepcopy(n['data'])}
        if n['kind']!='group':
            item['studioKind']={'video':'video','audio':'audio','image':'image','asset':'image'}.get(n['kind'],'text')
            if item['studioKind']=='text': item['text']=n['data'].get('text') or n['data'].get('prompt') or ''
        if n['data'].get('file'): item['images']=[{'url':'/media/'+n['data']['file'],'name':n['title'],'kind':'audio' if n['kind']=='audio' else 'video' if n['kind']=='video' else 'image'}]
        nodes.append(item)
    return {'id':pid,'project':pid,'title':p['name'],'kind':'smart','nodes':nodes,
            'connections':[{'from':e['source'],'to':e['target'],'kind':'input'} for e in old['edges']],
            'viewport':{'x':old['viewport']['x'],'y':old['viewport']['y'],'scale':old['viewport']['zoom']},'settings':{},'logs':[],'updated_at':0}


def save_canvas(pid,payload,*,server_workflow=False):
    value=validate_graph(payload)
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        visible=c.execute('SELECT deleted_at FROM project_summaries WHERE id=?',(pid,)).fetchone()
        if not visible or visible['deleted_at']: raise ValueError('请先恢复作品再编辑画布')
        row=c.execute('SELECT updated_at,body FROM original_canvases WHERE project_id=?',(pid,)).fetchone()
        current=row['updated_at'] if row else 0
        if payload.get('base_updated_at',0)!=current:
            raise HTTPException(409,detail={'message':'画布已更新，旧版本未覆盖','canvas':json.loads(row['body']) if row else get_canvas(pid),'updated_at':current})
        if not server_workflow:
            previous=json.loads(row['body']) if row else {}
            for key in ('studioMcpProduction','studioMcpBreakdowns'):
                if key in previous.get('settings',{}):value['settings'][key]=copy.deepcopy(previous['settings'][key])
                else:value['settings'].pop(key,None)
            previous_nodes={n['id']:n for n in previous.get('nodes',[])}
            for n in value['nodes']:
                old=previous_nodes.get(n['id'],{})
                if old.get('studioMcpShotKey') or previous.get('settings',{}).get('studioMcpProduction'):
                    for key in ('studioMcpShotKey','studioMcpBreakdownId','studioMcpAssetIds','studioMcpFrameId','studioPendingTask','studioTaskState','studioJobId','studioError','studioMcpReview'):
                        if key in old:n[key]=copy.deepcopy(old[key])
                        else:n.pop(key,None)
        value.update(id=pid,project=pid,kind='smart',updated_at=max(current+1,int(time.time()*1000)))
        c.execute('INSERT OR REPLACE INTO original_canvases VALUES(?,?,?)',(pid,value['updated_at'],json.dumps(value,ensure_ascii=False)))
    return value


def config(pid):
    p=store.get('projects',pid); channels=[]
    for provider in providers.public_settings()['providers']:
        if provider.get('enabled') is False: continue
        row={'id':provider['id'],'name':provider.get('name',provider['id']),'enabled':True,'chat_models':[],'image_models':[],'video_models':[],'video_profiles':provider.get('video_profiles',{})}
        for kind,field in [('text','chat_models'),('image','image_models'),('video','video_models')]:
            row[field]=[m['id'] for m in provider.get('models',[]) if m.get('enabled',True) and m.get('kind')==kind]
        channels.append(row)
    return {'api_providers':channels,'comfy_instances':[],'project_bindings':p.get('bindings',{}),'project_models':p.get('model_bindings',{})}


async def wait_job(pid,ident):
    while True:
        job=store.get('jobs',ident)
        if job['project_id']!=pid: raise ValueError('任务不属于当前作品')
        if job['status']=='succeeded': return job
        if job['status'] in ('failed','cancelled'): raise ValueError(job.get('error') or '任务已停止')
        await asyncio.sleep(.5)


def result_media(job):
    result=job.get('result',{})
    if isinstance(result,str): result={'file':result}
    file=result.get('file')
    return {'job_id':job['id'],'urls':[{'url':'/media/'+file,'name':file,'kind':'video' if job['kind']=='video' else 'image'}] if file else []}


async def text_task(pid,payload):
    p=store.get('projects',pid)
    options={'canvas_message':payload.get('message',''),'canvas_instruction':payload.get('system_prompt',''),
             'canvas_node_id':str(payload.get('studio_node_id','text'))[:100],'canvas_model':payload.get('model','')}
    if payload.get('prompt_task') == 'video_prompt':
        options.update(canvas_task='video_prompt',canvas_video_provider=payload.get('target_video_provider'),canvas_video_model=payload.get('target_video_model'),canvas_video_options=payload.get('video_options',{}))
    if payload.get('images') or payload.get('videos'):
        # Multimodal inputs require an explicit model path; never pretend text-only jobs viewed them.
        raise ValueError('当前文本助手不会读取图片或视频。请使用文本节点描述，图像与视频引用可传给生成节点')
    if isinstance(payload.get('agent_request'),str): options['canvas_user_request']=payload['agent_request'][:12000]
    result=await assistant.button_action(pid,{'kind':'text','stage':'wf_canvas_text','revision':p['revision'],
        'provider_id':payload.get('provider') or p.get('bindings',{}).get('text'),'workflow_options':options,
        'instruction':payload.get('system_prompt',''),'request_id':store.uid('canvasreq'),'topic_id':'canvas'})
    if not result.get('job'): raise ValueError(result['message'].get('reply') or '助手尚未提交文本任务')
    job=await wait_job(pid,result['job']['id'])
    return {'text':job['result']['text'],'job_id':job['id'],'model':job.get('model','')}


def media_target(pid,payload,kind):
    p=store.get('projects',pid); before=p['revision']; prompt=payload.get('prompt',''); original_models=copy.deepcopy(p.get('model_bindings',{}));had_models='model_bindings' in p
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>100000: raise ValueError('请填写当前节点提示词')
    ident=payload.get('provider_id') or p.get('bindings',{}).get(kind)
    p.setdefault('model_bindings',{})[kind]=payload.get('model') or p.get('model_bindings',{}).get(kind,'')
    channel = providers.provider_for(p,kind,ident)
    from . import seedance
    sd25 = kind=='video' and seedance.is_25(channel)
    images=payload.get('reference_images',[]) if kind=='image' else payload.get('images',[])
    if payload.get('production_required') and not images:raise ValueError('完整制作必须有实际参考素材，不能降级文生视频')
    image_purpose=payload.get('image_purpose','shot')
    if image_purpose not in ('shot','character','location','prop'): raise ValueError('图片用途无效')
    if not isinstance(images,list) or len(images)>(30 if sd25 else 20): raise ValueError('图片引用无效或超过当前模型上限')
    if not sd25 and any(isinstance(x,dict) and x.get('role')=='last_frame' for x in images): raise ValueError('当前工作台接口没有尾帧映射，请改用普通参考图或首帧')
    files=[local_file(x) for x in images]
    for image in images:
        if isinstance(image,dict) and image.get('image_purpose')=='character' and image.get('role')=='first_frame':
            raise ValueError('角色参考图不能作为首帧，请使用镜头图片')
    videos = payload.get('videos', [])
    if not isinstance(videos, list): raise ValueError('视频参考列表无效')
    if videos and (kind != 'video' or not channel.get('capabilities', {}).get('video_reference')):
        raise ValueError('当前视频渠道未声明支持视频参考，请选择支持的模型或导出参考帧')
    if len(videos) > channel.get('capabilities', {}).get('max_video', 3): raise ValueError('视频参考数量超过当前渠道上限')
    def video_file(x):
        url=x.get('url','') if isinstance(x,dict) else str(x)
        if sd25 and url.startswith(('https://','asset://')): return url
        if sd25: raise ValueError('Seedance 2.5 视频参考须为公网 HTTPS URL 或 asset:// ID，本地视频尚未上传，未提交')
        return local_file(x)
    video_files = [video_file(x) for x in videos]
    if not sd25 and any(Path(file).suffix.lower() not in ('.mp4', '.mov', '.webm', '.mkv') for file in video_files):
        raise ValueError('视频参考必须为本地视频素材')
    audio=[local_file(x) for x in payload.get('audios',[])]
    if audio and channel.get('capabilities', {}).get('audio_reference') is False:
        raise ValueError('当前渠道的音频参考参数尚未验证或不受支持，未提交；请提供站方最新请求示例')
    if len(audio)>channel.get('capabilities', {}).get('max_audio',3): raise ValueError('音频参考数量超过当前渠道上限')
    duration=float(payload.get('duration',8))
    if not math.isfinite(duration) or not 1<=duration<=120: raise ValueError('视频时长须为 1–120 秒')
    ep_id=store.uid('episode'); scene_id=store.uid('scene'); seg_id=store.uid('segment')
    title=str(payload.get('studio_node_title') or '画布镜头')[:120]
    ep={'id':ep_id,'title':title,'scenes':[{'id':scene_id,'title':title,'action':prompt,'location':'','time':'','interior':'','goal':'','conflict':'','turn':'','sound':'','transition':'','dialogue':[],'duration':duration}]}
    p['outputs'].setdefault('script',{}).setdefault('episodes',[]).append(ep)
    seg={'id':seg_id,'episode_id':ep_id,'scene_id':scene_id,'title':title,'duration':duration,'prompt':prompt,'image_prompt':prompt,
         'shots':[{'start':0,'end':duration,'action':prompt,'size':'中景','camera':'固定','dialogue':str(payload.get('dialogue','')),'sound':''}],
         'character_ids':[],'prop_ids':[],'location_id':'','variant_ids':[],'previous_id':None,'continuity':False,
         'images':[],'versions':[],'current_image':None,'current_version':None,'status':'draft','input_mode':'references',
         'canvas_raw_prompt':not bool(payload.get('dialogue')),'canvas_node_id':payload.get('studio_node_id'),'canvas_image_purpose':image_purpose,'canvas_video_input_mode':payload.get('video_input_mode'),
         'video_references':[{('url' if file.startswith(('https://','asset://')) else 'file'):file,'name':str(videos[i].get('name') or '视频参考')[:120] if isinstance(videos[i],dict) else '视频参考','purpose':'motion'} for i,file in enumerate(video_files)],
         'video_options':{k:payload[k] for k in ('resolution','generate_audio','watermark','camera_fixed') if k in payload}}
    last_indexes=[i for i,x in enumerate(images) if isinstance(x,dict) and x.get('role')=='last_frame']
    if len(last_indexes)>1: raise ValueError('只能选择一张尾帧图片')
    if last_indexes: seg['last_frame']=files[last_indexes[0]]
    first_indexes=[i for i,x in enumerate(images) if isinstance(x,dict) and x.get('role')=='first_frame'] if kind=='video' else []
    if len(first_indexes)>1: raise ValueError('只能选择一张首帧图片')
    first_index=first_indexes[0] if first_indexes else (0 if kind=='video' and payload.get('video_input_mode')!='references' and len(files)==1 and (not isinstance(images[0],dict) or not images[0].get('role')) else None)
    first=first_index is not None
    location_id=store.uid('location')
    p['assets'].append({'id':location_id,'kind':'location','name':'画布场景','description':prompt,'references':[],'version':1,'status':'draft'})
    seg['location_id']=location_id
    characters={}
    def character_asset(name):
        name=str(name).strip()[:120]
        if name not in characters:
            asset={'id':store.uid('character'),'kind':'character','name':name,'description':'画布角色身份参考','references':[],'version':1,'status':'draft'}
            characters[name]=asset;p['assets'].append(asset);seg['character_ids'].append(asset['id'])
        return characters[name]
    for index,file in enumerate(files):
        if index==first_index:
            image={'id':store.uid('shotimg'),'file':file,'source':'canvas','created_at':store.now()};seg['images'].append(image);seg.update(current_image=image['id'],input_mode='shot_image')
        else:
            reference=images[index] if isinstance(images[index],dict) else {}
            name=reference.get('name')
            if reference.get('role')=='character' or reference.get('image_purpose')=='character':
                asset=character_asset(reference.get('character_name') or name or f'画布角色{index+1}')
                asset['references'].append({'file':file})
            elif reference.get('image_purpose')=='location':
                asset=next(a for a in p['assets'] if a['id']==location_id)
                asset['name']=str(name or '画布场景')[:120]
                asset['references'].append({'file':file,'canvas_reference_purpose':'space'})
            else:
                aid=store.uid('prop');p['assets'].append({'id':aid,'kind':'prop','name':str(name or f'画布参考{index+1}')[:120],'description':'用户选择的参考图片','references':[{'file':file,'canvas_reference_purpose':'prop' if reference.get('image_purpose')=='prop' else 'shot' if reference.get('image_purpose')=='shot' else 'space'}],'version':1,'status':'draft'});seg['prop_ids'].append(aid)
    for index,file in enumerate(audio):
        name=payload['audios'][index].get('name') if isinstance(payload['audios'][index],dict) else None
        asset=character_asset(name or f'音色参考{index+1}')
        if asset.get('voice') and asset['voice']!=file: raise ValueError('同一角色只能连接一个音色参考')
        asset['voice']=file
    p['segments'].append(seg)
    # Only this generation snapshot uses selected size/model; do not overwrite project preferences.
    selected_model=p['model_bindings'][kind]
    p['model_bindings']=original_models
    if not had_models: p.pop('model_bindings')
    saved=store.save_project(p,before,'原版画布准备当前生成节点')
    saved.setdefault('model_bindings',{})[kind]=selected_model
    if ident: saved.setdefault('bindings',{})[kind]=ident
    saved['settings']['ratio']=payload.get('aspect_ratio') or p['settings']['ratio']
    saved['settings']['allow_no_references']=not bool(payload.get('production_required'))
    if first: saved['settings']['pin_shot_first_frame']=True
    if kind=='image' and payload.get('size'): saved['settings']['image_size']=str(payload['size'])
    return saved,seg_id,ident


async def media_task(pid,payload,kind,wait=True):
    for reference in payload.get('videos', []):
        url=reference.get('url','') if isinstance(reference,dict) else str(reference)
        if not url.startswith(('https://','asset://')): await media.probe(local_file(reference))
    p,target,provider=media_target(pid,payload,kind)
    job=jobs.create(p,{'kind':kind,'stage':'storyboard' if kind=='image' else 'video','target_id':target,'provider_id':provider})
    if kind=='image' or not wait: return {'task_id':job['id'],'status':job['status']}
    return result_media(await wait_job(pid,job['id']))


def replace_urls(value,mapping):
    if isinstance(value,dict): return {k:replace_urls(v,mapping) for k,v in value.items()}
    if isinstance(value,list): return [replace_urls(v,mapping) for v in value]
    return mapping.get(value,value) if isinstance(value,str) else value


async def import_workflow(request):
    form=await request.form();file=form.get('file')
    if not file: raise ValueError('请选择工作流文件')
    content=await file.read(100*1024*1024+1)
    if len(content)>100*1024*1024: raise ValueError('工作流包最大 100 MB')
    try:
        if not zipfile.is_zipfile(io.BytesIO(content)): value=json.loads(content.decode('utf-8-sig'))
        else:
            from .main import upload
            mapping={}
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos=archive.infolist()
                if len(infos)>200 or sum(i.file_size for i in infos)>100*1024*1024: raise ValueError('工作流资源过多或解压后超过 100 MB')
                value=json.loads(archive.read('workflow.json').decode('utf-8-sig'))
                # Validate the graph before importing any media. Never extract arbitrary paths.
                validate_graph({**value,'viewport':value.get('viewport',{'x':0,'y':0,'scale':1})})
                for item in infos:
                    parts=PurePosixPath(item.filename).parts
                    if len(parts)!=2 or parts[0]!='media' or item.is_dir(): continue
                    result=await upload(UploadFile(filename=parts[1],file=io.BytesIO(archive.read(item))))
                    mapping['/media/'+parts[1]]=result['url']
            value=replace_urls(value,mapping)
        if isinstance(value,dict) and isinstance(value.get('workflow'),dict): value=value['workflow']
        if isinstance(value,list): value={'nodes':value,'connections':[]}
        return validate_graph(value)
    except (json.JSONDecodeError,UnicodeDecodeError,zipfile.BadZipFile,KeyError) as error:
        raise ValueError('工作流文件无效，请选择 JSON 或工作台导出的 ZIP') from error


def archive_response(value,items=None):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        if value is not None: archive.writestr('workflow.json',json.dumps(value,ensure_ascii=False,indent=2))
        paths=recycle.media_paths(value) if value is not None else {providers.file_path(local_file(item)) for item in items or []}
        for path in paths: archive.write(path,'media/'+path.name)
    return Response(output.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="canvas-resources.zip"'})


@router.api_route('/{pid}/{path:path}',methods=['GET','POST','PUT','PATCH','DELETE'])
async def bridge(pid,path,request:Request):
    store.project_overview(pid)
    method=request.method
    if path=='config': return config(pid)
    if path=='assistant-history':
        messages=[]
        for entry in assistant.messages(pid):
            if entry.get('topic_id')!='canvas': continue
            result={};job={}
            if entry.get('job_id'):
                try:
                    job=store.get('jobs',entry['job_id']);result=job.get('result') or {}
                except KeyError: pass
            reply=entry.get('canvas_reply') or result.get('text') or entry.get('reply','')
            if not entry.get('canvas_reply'):
                try:
                    plan=json.loads(reply.strip().removeprefix('```json').removesuffix('```').strip())
                    if isinstance(plan,dict) and isinstance(plan.get('reply'),str): reply=plan['reply']
                except (ValueError,AttributeError): pass
            messages.append({'request':job.get('workflow_options',{}).get('canvas_user_request') or entry['request'],'reply':reply})
        return {'messages':messages[-30:]}
    if path=='canvas-agent-report' and method=='POST':
        body=await request.json();job=store.get('jobs',body.get('job_id',''))
        if job.get('project_id')!=pid or job.get('stage')!='wf_canvas_text': raise ValueError('助手记录不属于当前画布')
        reply=body.get('reply')
        if not isinstance(reply,str) or not reply.strip() or len(reply)>4000: raise ValueError('助手执行记录无效')
        entry=next((m for m in assistant.messages(pid) if m.get('topic_id')=='canvas' and m.get('job_id')==job['id']),None)
        if not entry: raise ValueError('助手记录不存在')
        entry['canvas_reply']=reply;assistant.put(entry)
        return {'ok':True}
    if path==f'canvases/{pid}' and method=='GET': return {'canvas':get_canvas(pid)}
    if path==f'canvases/{pid}' and method=='PUT': return {'canvas':save_canvas(pid,await request.json())}
    if path==f'canvases/{pid}/meta':
        with store.db() as c:
            row=c.execute('SELECT updated_at FROM original_canvases WHERE project_id=?',(pid,)).fetchone()
        return {'id':pid,'updated_at':row['updated_at'] if row else 0}
    if path==f'canvases/{pid}/touch': return {'ok':True}
    if path in ('workflows','runninghub/workflows'): return {'workflows':[]}
    if path=='local-skills': return {'skills':skills.list_skills()}
    if path=='prompt-libraries': return {'library':{'libraries':[]}}
    if path=='smart-canvas/prompt-templates': return {'templates':[]}
    if path=='canvas-assets': return {'assets':[]}
    if path in ('asset-library','local-assets'):
        items=[]
        for item in store.all_rows('library'):
            file=item.get('file') or item.get('voice') or next((r.get('file') for r in item.get('references',[]) if r.get('file')),None)
            if file: items.append({'id':item['id'],'url':'/media/'+file,'name':item['name'],'kind':'audio' if item['kind']=='audio' else 'video' if item['kind']=='video' else 'image'})
        return {'items':items,'tree':None} if path=='local-assets' else {'library':{'libraries':[{'id':'studio','name':'当前工作台资产','categories':[{'id':'studio','name':'素材','type':'image','items':items}]}]}}
    if path in ('ai/upload','local-assets/upload') and method=='POST':
        from .main import upload
        form=await request.form();files=[]
        for item in form.getlist('files') or form.getlist('file'):
            result=await upload(item);suffix=result['file'].rsplit('.',1)[-1]
            files.append({'url':result['url'],'file':result['file'],'name':result['original_name'],'kind':'video' if suffix in ('mp4','mov','webm','mkv') else 'audio' if suffix in ('wav','mp3','m4a','ogg') else 'image'})
        return {'files':files,'items':files}
    if path=='media-preview': return FileResponse(providers.file_path(local_file(request.query_params.get('url',''))))
    if path=='canvas-llm' and method=='POST': return await text_task(pid,await request.json())
    if path=='canvas-image-tasks' and method=='POST': return await media_task(pid,await request.json(),'image')
    if path.startswith('canvas-image-tasks/') and method=='GET':
        job=store.get('jobs',path.rsplit('/',1)[-1])
        if job['project_id']!=pid: raise ValueError('任务不属于当前作品')
        return {'task_id':job['id'],'status':job['status'],'result':result_media(job),'error':job.get('error')}
    if path=='canvas-tail-frame' and method=='POST':
        body=await request.json()
        name=local_file(body.get('url'))
        result=await media.tail(name,body.get('at'))
        return {'image':{'url':'/media/'+result['tail'],'name':'video-tail.png','kind':'image'},
                'tail_at':result['tail_at'],'tail_warning':result.get('tail_warning','')}
    if path=='canvas-video' and method=='POST': return await media_task(pid,await request.json(),'video')
    if path=='canvas-video-tasks' and method=='POST': return await media_task(pid,await request.json(),'video',wait=False)
    if path=='canvas-workflows/import' and method=='POST': return await import_workflow(request)
    if path=='canvas-workflows/export' and method=='POST':
        body=await request.json();value=validate_graph(body)
        if body.get('include_resources'): return archive_response(value)
        return Response(json.dumps(value,ensure_ascii=False),media_type='application/json',headers={'Content-Disposition':'attachment; filename="canvas-workflow.json"'})
    if path=='canvas-assets/download' and method=='POST':
        body=await request.json();items=body.get('items') or body.get('urls',[])
        if not isinstance(items,list) or not 1<=len(items)<=100: raise ValueError('请选择 1–100 个本地资源')
        return archive_response(None,items)
    if path=='smart-canvas/minimax-export' and method=='POST':
        body=await request.json();clips=body.get('clips',[])
        if not isinstance(clips,list) or not 1<=len(clips)<=100: raise ValueError('请选择要导出的视频片段')
        p=copy.deepcopy(store.get('projects',pid));p['segments']=[];p['settings']['subtitles']=False
        for clip in clips:
            if not isinstance(clip,dict): raise ValueError('视频片段格式无效')
            name=local_file(clip);ident=store.uid('clip')
            start=float(clip.get('start',0));end=float(clip.get('end',0))
            if not math.isfinite(start) or not math.isfinite(end) or start<0 or end<0 or (end and end<=start): raise ValueError('裁剪时间无效：出点须大于入点，0 表示保留到片尾')
            p['segments'].append({'id':ident,'title':ident,'current_version':'selected','versions':[{'id':'selected','file':name}], 'trim_start':start, 'trim_end':end or None})
        result=await media.compose(p)
        return {'url':'/media/'+result['file'],'name':'canvas-timeline.mp4','kind':'video'}
    raise HTTPException(400,detail='该原版服务入口尚未接入；请使用当前工作台已配置的文字、图片或视频模型')
