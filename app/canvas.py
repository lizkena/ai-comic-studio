"""Native free canvas. Graph edits never call a model or rewrite the project."""
import copy
import json
import math
import re
from fastapi import APIRouter
from . import store, domain, providers, task_locks

router = APIRouter(prefix='/api', tags=['free-canvas'])
KINDS = {'text', 'script', 'shot', 'image', 'video', 'audio', 'asset', 'group'}
DATA_FIELDS = {'text', 'dialogue', 'duration', 'file', 'asset_id', 'segment_id', 'episode_id',
               'job_id', 'asset_kind', 'group_id', 'canvas_managed', 'completed_job_id', 'submitted_text', 'width', 'height',
               'duration_override','dialogue_override'}


def number(value, low, high):
    if isinstance(value, bool): raise ValueError('画布数值无效')
    try: result = float(value)
    except (ValueError, TypeError): raise ValueError('画布数值无效')
    if not math.isfinite(result) or not low <= result <= high: raise ValueError('画布数值超出范围')
    return result


def validate(project, graph):
    if not isinstance(graph, dict): raise ValueError('画布格式无效')
    nodes, edges = graph.get('nodes', []), graph.get('edges', [])
    if not isinstance(nodes, list) or not isinstance(edges, list) or len(nodes) > 500 or len(edges) > 1500:
        raise ValueError('画布最多支持 500 个节点和 1500 条连线')
    ids = set(); result = []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get('kind'),str) or node['kind'] not in KINDS: raise ValueError('节点类型无效')
        ident = node.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', ident) or ident in ids:
            raise ValueError('节点标识无效或重复')
        ids.add(ident)
        data = node.get('data', {})
        if not isinstance(data, dict): raise ValueError('节点内容无效')
        data = {k:copy.deepcopy(v) for k,v in data.items() if k in DATA_FIELDS}
        for key in ('text', 'dialogue','submitted_text'):
            if key in data and (not isinstance(data[key], str) or len(data[key]) > 100000): raise ValueError('节点文本过长或格式无效')
        for key in ('asset_id','segment_id','episode_id','job_id','completed_job_id','group_id','file'):
            if key in data and data[key] is not None and not isinstance(data[key],str): raise ValueError('节点引用格式无效')
        if data.get('file'): providers.file_path(data['file'])
        if data.get('file'):
            from pathlib import Path
            suffix=Path(data['file']).suffix.lower()
            allowed={ 'image':{'.png','.jpg','.jpeg','.webp'}, 'asset':{'.png','.jpg','.jpeg','.webp'},
                      'audio':{'.wav','.mp3','.m4a','.ogg'}, 'video':{'.mp4','.mov','.webm','.mkv'}}
            if node['kind'] in allowed and suffix not in allowed[node['kind']]: raise ValueError('素材类型与节点不匹配')
        if 'duration' in data: data['duration'] = number(data['duration'], 1, 120)
        for size in ('width','height'):
            if size in data: data[size]=number(data[size],200,100000)
        if data.get('asset_kind', 'prop') not in ('character', 'location', 'prop'): raise ValueError('资产类型无效')
        for key, objects in [('asset_id',project['assets']),('segment_id',project['segments']),
                             ('episode_id',project['outputs'].get('script',{}).get('episodes',[]))]:
            if data.get(key) and not any(x['id']==data[key] for x in objects): raise ValueError('节点不能引用其他作品或不存在的对象')
        if data.get('job_id'):
            with store.db() as c: job=c.execute('SELECT project_id FROM job_summaries WHERE id=?',(data['job_id'],)).fetchone()
            if not job or job['project_id'] != project['id']: raise ValueError('节点不能引用其他作品的任务')
        result.append({'id':ident, 'kind':node['kind'], 'title':str(node.get('title',''))[:120],
                       'x':number(node.get('x',0),-100000,100000),'y':number(node.get('y',0),-100000,100000),
                       'data':data})
    links = []; seen = set(); adjacency = {n:[] for n in ids}
    for edge in edges:
        if not isinstance(edge, dict): raise ValueError('连线格式无效')
        source, target = edge.get('source'), edge.get('target')
        if not isinstance(source,str) or not isinstance(target,str): raise ValueError('连线端点格式无效')
        if source not in ids or target not in ids or source==target or (source,target) in seen: raise ValueError('连线端点无效或重复')
        if any(n['id'] in (source,target) and n['kind']=='group' for n in result): raise ValueError('分组不能作为生成输入')
        seen.add((source,target)); adjacency[source].append(target)
        links.append({'source':source,'target':target})
    visiting = set(); done = set()
    def visit(ident):
        if ident in visiting: raise ValueError('连线不能形成循环依赖')
        if ident in done: return
        visiting.add(ident)
        for child in adjacency[ident]: visit(child)
        visiting.remove(ident); done.add(ident)
    for ident in ids: visit(ident)
    for node in result:
        group = node['data'].get('group_id')
        if group and node['kind']=='group': raise ValueError('分组不能嵌套或引用自身')
        if group and not any(n['id']==group and n['kind']=='group' for n in result): raise ValueError('节点所属分组不存在')
    view = graph.get('viewport', {})
    if not isinstance(view, dict): raise ValueError('画布视图无效')
    return {'nodes':result,'edges':links,'viewport':{'x':number(view.get('x',60),-100000,100000),
            'y':number(view.get('y',60),-100000,100000),'zoom':number(view.get('zoom',1),.2,2)}}


def read(ident):
    store.project_overview(ident)
    with store.db() as c: row = c.execute('SELECT revision,body FROM canvases WHERE project_id=?',(ident,)).fetchone()
    body=json.loads(row['body']) if row else {'nodes':[],'edges':[],'viewport':{'x':60,'y':60,'zoom':1}}
    body.pop('_project_revision',None)
    return {**body,
            'revision':row['revision'] if row else 0}


def write(project, payload):
    if not isinstance(payload.get('nodes',[]),list): raise ValueError('画布节点格式无效')
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT revision,body FROM canvases WHERE project_id=?',(project['id'],)).fetchone()
        if payload.get('revision') != (row['revision'] if row else 0): raise ValueError('画布已有更新，请先重新打开；未覆盖当前内容')
        live=c.execute('SELECT revision,deleted_at FROM project_summaries WHERE id=?',(project['id'],)).fetchone()
        if not live or live['deleted_at']: raise ValueError('作品已不存在或位于回收站')
        old=json.loads(row['body']) if row else {}
        fields=('asset_id','segment_id','episode_id')
        pairs={(key,n['data'][key]) for n in old.get('nodes',[]) for key in fields if n['data'].get(key)}
        incoming={(key,n.get('data',{}).get(key)) for n in payload.get('nodes',[]) if isinstance(n,dict) and isinstance(n.get('data',{}),dict) for key in fields if isinstance(n.get('data',{}).get(key),str)}
        if old.get('_project_revision')==live['revision'] and incoming.issubset(pairs):
            # Moving, renaming or wiring validated nodes does not parse a long novel again.
            context={'id':project['id'],'assets':[{'id':ident} for key,ident in pairs if key=='asset_id'],
                     'segments':[{'id':ident} for key,ident in pairs if key=='segment_id'],
                     'outputs':{'script':{'episodes':[{'id':ident} for key,ident in pairs if key=='episode_id']}}}
        else: context=json.loads(c.execute('SELECT body FROM projects WHERE id=?',(project['id'],)).fetchone()['body'])
        graph = validate(context, payload)
        revision = (row['revision'] if row else 0)+1
        c.execute('INSERT OR REPLACE INTO canvases VALUES(?,?,?)',(project['id'],revision,json.dumps({**graph,'_project_revision':live['revision']},ensure_ascii=False)))
    return {**graph,'revision':revision}


@router.post('/canvas-projects')
def new_project(payload:dict):
    settings = {**payload.get('settings',{}),'free_canvas':True}
    project = domain.project_new({'entry':'script','name':payload.get('name') or '自由创作短片',
                                 'source':payload.get('source') or '自由创作','settings':settings})
    return store.save_project(project, reason='创建自由画布作品')


@router.get('/projects/{ident}/canvas')
def get_canvas(ident):
    graph = read(ident); project = store.get('projects',ident)
    for node in graph['nodes']:
        data = node['data']; segment = next((s for s in project['segments'] if s['id']==data.get('segment_id')),None)
        asset = next((a for a in project['assets'] if a['id']==data.get('asset_id')),None)
        if segment:
            versions = segment.get('versions',[]) if node['kind']=='video' else segment.get('images',[])
            chosen = segment.get('current_version') if node['kind']=='video' else segment.get('current_image')
            item = next((x for x in versions if x['id']==chosen),None)
            if item: data['file'] = item['file']
        if asset and node['kind']=='audio' and asset.get('voice'): data['file']=asset['voice']
        elif asset and asset.get('references'): data['file'] = asset['references'][-1]['file']
    return graph


@router.put('/projects/{ident}/canvas')
def save_canvas(ident, payload:dict): return write(store.project_overview(ident)[0],payload)


def upstream(graph, node_id, stop_at_video=False):
    wanted = set()
    def collect(ident):
        for edge in graph['edges']:
            if edge['target']==ident and edge['source'] not in wanted:
                wanted.add(edge['source'])
                source=next(n for n in graph['nodes'] if n['id']==edge['source'])
                if not stop_at_video or source['kind']!='video': collect(edge['source'])
    collect(node_id)
    return [n for n in graph['nodes'] if n['id'] in wanted]


@router.post('/projects/{ident}/canvas/prepare/{node_id}')
def prepare(ident, node_id, payload:dict):
    project = store.get('projects',ident); graph = get_canvas(ident)
    if payload.get('revision') != graph['revision'] or payload.get('project_revision') != project['revision']:
        raise ValueError('画布或作品已更新，请刷新后制作')
    node = next((n for n in graph['nodes'] if n['id']==node_id),None)
    if not node or node['kind'] not in ('script','shot','image','video'): raise ValueError('该节点不支持生成')
    original = copy.deepcopy(project)
    data = node['data']; parents = upstream(graph,node_id)
    source_shots=[n for n in upstream(graph,node_id,True) if n['kind']=='shot'] if node['kind'] in ('image','video') else []
    if len(source_shots)>1: raise ValueError('图片或视频节点只能对应一个分镜，请分别连接制作')
    source_shot=source_shots[0] if source_shots else None
    if source_shot:
        if not data.get('duration_override'): data['duration']=source_shot['data'].get('duration',8)
        if not data.get('dialogue_override'): data['dialogue']=source_shot['data'].get('dialogue','')
    direct_ids={e['source'] for e in graph['edges'] if e['target']==node_id}
    direct=[n for n in parents if n['id'] in direct_ids]
    texts=[n['data'].get('text','') for n in direct if n['kind'] in ('text','script','shot')]
    content = '\n\n'.join(texts + [data.get('text','')]).strip()
    if source_shot and not data.get('text'): content=source_shot['data'].get('text','') or content
    if not content:
        content='\n\n'.join(n['data'].get('text','') for n in parents if n['kind'] in ('text','script','shot')).strip()
    if not content: raise ValueError('请填写描述或连接文本、剧本、分镜节点')
    # Resolve input media before any project mutation or API submission.
    for parent in parents:
        if node['kind']=='video' and parent['kind'] in ('image','audio','asset') and not parent['data'].get('file'):
            raise ValueError('上游素材尚未就绪，请先上传、选用或生成：'+parent['title'])
    episodes = project['outputs'].setdefault('script',{}).setdefault('episodes',[])
    episode = next((ep for ep in episodes if ep['id']==data.get('episode_id')),None)
    segment = next((s for s in project['segments'] if s['id']==data.get('segment_id')),None)
    if not segment and node['kind'] in ('image','video'):
        source=next((n for n in direct if n['kind'] in ('shot','image') and n['data'].get('segment_id')),None)
        if not source and source_shot and source_shot['data'].get('segment_id'): source=source_shot
        if source:
            segment=next((s for s in project['segments'] if s['id']==source['data']['segment_id']),None)
            if segment:
                data['segment_id']=segment['id']
                data.setdefault('duration',segment['duration'])
    if segment: episode = next(ep for ep in episodes if ep['id']==segment['episode_id'])
    if not episode:
        episode = {'id':store.uid('episode'),'title':node['title'] or '自由短片','scenes':[
            {'id':store.uid('scene'),'title':node['title'] or '自由场次','location':'','time':'','interior':'',
             'goal':'','conflict':'','turn':'','duration':data.get('duration',8),'action':content,
             'dialogue':[],'sound':'','transition':'','source_chapters':[]}]}
        episodes.append(episode); data['episode_id']=episode['id']; data['canvas_managed']=True
    if node['kind']=='script':
        if data.get('canvas_managed'): episode['scenes'][0]['action']=content
        target = episode['id']; stage = 'wf_breakdown'; kind = 'text'
    else:
        duration = data.get('duration',8)
        if not segment:
            segment = {'id':store.uid('segment'),'episode_id':episode['id'],'scene_id':episode['scenes'][0]['id'],
                       'title':(source_shot or node)['title'] or '自由镜头','duration':duration,'prompt':source_shot['data'].get('text') if source_shot else content,'image_prompt':content,
                       'shots':[{'start':0,'end':duration,'size':'中景','camera':'固定','action':content,
                                 'dialogue':data.get('dialogue',''),'sound':''}], 'character_ids':[], 'variant_ids':[],
                       'location_id':'','prop_ids':[],'previous_id':None,'continuity':False,'tail_shot':False,
                       'status':'draft','images':[],'versions':[],'current_image':None,'current_version':None}
            project['segments'].append(segment); data['segment_id']=segment['id']; data['canvas_managed']=True
        if source_shot and not source_shot['data'].get('segment_id'):
            source_shot['data'].update(segment_id=segment['id'],episode_id=episode['id'],canvas_managed=True)
        if node['kind']=='video':
            for parent in direct:
                if parent['kind']=='image' and not parent['data'].get('segment_id'): parent['data']['segment_id']=segment['id']
        task_locks.assert_available(project, {'reads':set(), 'writes':{'segment:'+segment['id']}})
        if node['kind']=='image': segment['image_prompt']=data.get('text') or content
        else:
            if node['kind']=='video' and not data.get('text') and segment.get('prompt'): content=segment['prompt']
            segment['prompt']=content
            if not segment.get('image_prompt'): segment['image_prompt']=content
        if data.get('canvas_managed') and node['kind']!='image':
            segment['duration']=duration; segment['shots']=[{'start':0,'end':duration,'size':'中景','camera':'固定',
                'action':content,'dialogue':data.get('dialogue',''),'sound':''}]
            if re.match(r'^\s*\d+:\d+',data.get('dialogue','')): segment['dialogue_text']=data['dialogue']
            else: segment.pop('dialogue_text',None)
        elif node['kind']!='image':
            if data.get('duration_override') or source_shot:
                old=float(segment['duration']); segment['duration']=duration
                for shot in segment['shots']:
                    shot['start']=round(float(shot['start'])*duration/old,3)
                    shot['end']=round(float(shot['end'])*duration/old,3)
                segment['shots'][-1]['end']=duration
            if data.get('dialogue_override') or source_shot:
                text=data.get('dialogue','')
                for shot in segment['shots']: shot['dialogue']=''
                if re.match(r'^\s*\d+:\d+',text): segment['dialogue_text']=text
                else:
                    from .native_audio import dialogue_rows
                    rows=dialogue_rows({'duration':duration,'shots':[{'start':0,'end':duration,'dialogue':text}]})
                    def stamp(value): return f'{int(value)//60:02d}:{value%60:05.2f}'
                    segment['dialogue_text']='\n'.join(f"{stamp(r['start'])}–{stamp(r['end'])} {r['speaker']}：{r['text']}" for r in rows)
        first_frames=[n for n in direct if n['kind']=='image'] if node['kind']=='video' else []
        predecessors=[n for n in direct if n['kind']=='video'] if node['kind']=='video' else []
        if len(first_frames)>1 or len(predecessors)>1 or (first_frames and predecessors):
            raise ValueError('一个视频节点只能连接一张首帧图或一个前段视频；其他参考图请使用资产节点')
        if predecessors:
            prev=next((s for s in project['segments'] if s['id']==predecessors[0]['data'].get('segment_id')),None)
            version=next((v for v in (prev or {}).get('versions',[]) if v['id']==prev.get('current_version')),None) if prev else None
            if not version or not version.get('tail') or not version.get('tail_accepted'): raise ValueError('前段视频尚无已确认的尾帧，请先完成或检查前段视频')
            providers.file_path(version['tail'])
            segment.update(previous_id=prev['id'], continuity=True, input_mode='previous_tail')
        elif first_frames:
            segment.update(previous_id=None, continuity=False)
        elif data.get('canvas_managed'):
            segment.update(previous_id=None,continuity=False,input_mode='references')
        if data.get('canvas_managed'):
            segment.update(character_ids=[],prop_ids=[],location_id='')
        for parent in parents:
            pd = parent['data']; file = pd.get('file')
            if not file and not pd.get('asset_id') and parent['kind']!='asset': continue
            if file: providers.file_path(file)
            if parent['kind'] in ('video','script','shot','text','group'): continue
            if parent['kind']=='audio':
                # Optional voice sample: attach it to a named character, never make it mandatory.
                name = parent['title']; asset = next((a for a in project['assets'] if a['kind']=='character' and a['name']==name),None)
                if not asset:
                    asset={'id':store.uid('character'),'kind':'character','name':name,'description':'','references':[], 'version':1,'status':'draft'}
                    project['assets'].append(asset)
                asset['voice']=file
                pd['asset_id']=asset['id']
            elif parent in first_frames:
                image={'id':store.uid('shotimg'),'file':file,'source':'canvas','created_at':store.now()}
                segment['images'].append(image); segment['current_image']=image['id']; segment['input_mode']='shot_image'
                continue
            elif parent['kind']=='image' and node['kind']=='video': continue
            else:
                asset = next((a for a in project['assets'] if a['id']==pd.get('asset_id')),None)
                if not asset:
                    asset={'id':store.uid('asset'),'kind':pd.get('asset_kind','prop'),'name':parent['title'],
                           'description':pd.get('text',''),'image_prompt':pd.get('text',''),'references':[{'file':file}] if file else [],
                           'version':1,'status':'draft'}
                    project['assets'].append(asset); pd['asset_id']=asset['id']
            key={'character':'character_ids','prop':'prop_ids','location':'location_id'}[asset['kind']]
            if key=='location_id': segment[key]=asset['id']
            elif asset['id'] not in segment[key]: segment[key].append(asset['id'])
        target = segment['id']; kind = 'text' if node['kind']=='shot' else node['kind']
        stage = 'wf_video_prompt' if kind=='text' else 'storyboard' if kind=='image' else 'video'
    changes=task_locks.changes(original,project)
    task_locks.assert_available(original, changes)
    normalized=validate(project,graph)
    def save_graph(connection, saved_project):
        row=connection.execute('SELECT revision FROM canvases WHERE project_id=?',(ident,)).fetchone()
        if (row['revision'] if row else 0)!=payload['revision']: raise ValueError('画布已有更新，请刷新后制作')
        task_locks.assert_available(original, changes)
        connection.execute('INSERT OR REPLACE INTO canvases VALUES(?,?,?)',
                           (ident,graph['revision']+1,json.dumps({**normalized,'_project_revision':saved_project['revision']},ensure_ascii=False)))
    project = store.save_project(project,payload['project_revision'],'画布节点准备制作',transaction_hook=save_graph)
    graph = {**normalized,'revision':graph['revision']+1}
    return {'project':project,'canvas':graph,'payload':{'kind':kind,'stage':stage,'target_id':target,
            'instruction':'沿用画布中用户已有内容、台词与引用；只处理当前目标。'}}
