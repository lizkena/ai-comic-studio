"""Creative agent with durable memory, scoped drafts and observable studio tools."""
import asyncio
import copy
import json
from fastapi import APIRouter
from . import store, domain, providers, skills, workflow, agent_memory, creative_agent

agent_locks = {}
agent_tasks = {}

router = APIRouter(prefix='/api')
with store.db() as db:
    db.execute('CREATE TABLE IF NOT EXISTS assistant_messages(id TEXT PRIMARY KEY, project_id TEXT, body TEXT NOT NULL)')


def messages(project_id):
    with store.db() as db:
        rows = db.execute('SELECT body FROM assistant_messages WHERE project_id=? ORDER BY rowid DESC LIMIT 40', (project_id,))
        return [json.loads(row['body']) for row in rows][::-1]


def put(message):
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT body FROM projects WHERE id=?', (message['project_id'],)).fetchone()
        if not row: raise KeyError(message['project_id'])
        if json.loads(row['body']).get('deleted_at'): raise ValueError('作品已移入回收站，请先恢复作品。')
        db.execute('INSERT OR REPLACE INTO assistant_messages VALUES(?,?,?)', (message['id'], message['project_id'], json.dumps(message, ensure_ascii=False)))
    return message


def get(ident):
    with store.db() as db:
        row = db.execute('SELECT body FROM assistant_messages WHERE id=?', (ident,)).fetchone()
    if not row: raise KeyError(ident)
    return json.loads(row['body'])


def read(obj, path):
    for key in path.split('.'):
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    return obj


def write(obj, path, value):
    keys = path.split('.')
    for key in keys[:-1]: obj = obj[int(key)] if isinstance(obj, list) else obj.setdefault(key, {})
    key = int(keys[-1]) if isinstance(obj, list) else keys[-1]
    obj[key] = value


def scope_fields(p, scope):
    """An allow-list built from stable IDs. IDs/references/files are never model editable."""
    stage = scope.get('stage', 'storyboard')
    target = scope.get('target_id')
    paths = {}
    targets = scope.get('target_ids') or []
    if targets:
        if not isinstance(targets, list) or not all(isinstance(x,str) for x in targets) or len(targets)>50 or len(set(targets))!=len(targets):
            raise ValueError('助手目标列表无效，最多选择50个对象')
        contexts = []
        for ident in targets:
            asset = next((a for a in p['assets'] if a['id']==ident), None)
            fields_for_target, obj = scope_fields(p, {**scope, 'target_ids':[], 'target_id':ident, 'stage':'assets' if asset else 'storyboard'})
            paths.update(fields_for_target); contexts.append(obj)
        return paths, {'objects':contexts}
    def fields(prefix, obj, names):
        for name in names:
            value = obj.get(name, '')
            if isinstance(value, (str, int, float)) and not isinstance(value, bool): paths[prefix + '.' + name] = value
    if stage in ('storyboard', 'video'):
        index = next((i for i, s in enumerate(p['segments']) if s['id'] == target), None)
        if index is None: raise ValueError('请先选中要协助的镜头')
        segment = p['segments'][index]
        fields(f'segments.{index}', segment, ('title', 'prompt', 'image_prompt', 'dialogue_text', 'duration'))
        if segment.get('continuity'): paths.pop(f'segments.{index}.image_prompt', None)
        shot_index = scope.get('shot_index')
        if shot_index is not None and (not isinstance(shot_index, int) or isinstance(shot_index, bool) or not 0 <= shot_index < len(segment.get('shots', []))):
            raise ValueError('镜号已不存在，请重新选择')
        for i, shot in enumerate(segment.get('shots', [])):
            if shot_index is None or i == shot_index:
                fields(f'segments.{index}.shots.{i}', shot, ('size', 'camera', 'action', 'dialogue', 'sound'))
        return paths, segment
    if stage == 'assets':
        index = next((i for i, a in enumerate(p['assets']) if a['id'] == target), None)
        if index is None: raise ValueError('请先选中要协助的资产')
        asset = p['assets'][index]
        fields(f'assets.{index}', asset, ('description', 'image_prompt'))
        return paths, asset
    output = p['outputs'].get(stage, {})
    if stage == 'source':
        if p.get('entry') != 'idea' or workflow.chapters(p) or p['segments'] or p['outputs'].get('script', {}).get('episodes'):
            raise ValueError('原始灵感只在故事生成前编辑；已有内容请选中章节或剧本进行协助')
        return {'source': p.get('source', '')}, {'source': p.get('source', ''), 'entry': p.get('entry')}
    if stage == 'production_setup':
        fields('outputs.production_setup', output, ('genre', 'era', 'region', 'visual_style', 'synopsis'))
        fields('outputs.production_setup.cinematography', output.get('cinematography', {}), ('camera', 'lens', 'depth', 'lighting', 'color', 'texture', 'reference', 'negative'))
        for i, character in enumerate(output.get('characters', [])):
            fields(f'outputs.production_setup.characters.{i}', character, ('name','role','description','tags','background','history','personality','goal','relationships','arc','catchphrase'))
        return paths, output
    if stage == 'direction':
        fields('outputs.direction', output, ('logline', 'theme', 'genre', 'conflict', 'synopsis'))
        return paths, output
    collection = {'script': 'episodes', 'scene_plan': 'episodes', 'novel': 'chapters', 'characters': 'characters', 'performance': 'beats'}.get(stage)
    if not collection: raise ValueError('这个工作区请先选中镜头或资产再使用助手')
    items = output.get(collection, [])
    ident = scope.get('episode_id') if collection == 'episodes' else target
    index = next((i for i, item in enumerate(items) if item['id'] == ident), None)
    if index is None: raise ValueError('请先准备并选中要修改的内容')
    item = items[index]
    prefix = f'outputs.{stage}.{collection}.{index}'
    fields(prefix, item, ('title', 'content', 'summary', 'character_states', 'goal', 'secret', 'relationships', 'arc', 'description', 'breath', 'gaze', 'weight', 'hands', 'rhythm', 'subtext'))
    for i, scene in enumerate(item.get('scenes', [])):
        fields(f'{prefix}.scenes.{i}', scene, ('title', 'location', 'time', 'action', 'sound', 'transition', 'goal', 'conflict', 'turn'))
        for j, line in enumerate(scene.get('dialogue', [])):
            fields(f'{prefix}.scenes.{i}.dialogue.{j}', line, ('text',))
    return paths, item


def restrict_fields(paths, instruction):
    # A request explicitly limited to dialogue cannot alter visual descriptions.
    if any(x in instruction for x in ('只', '仅', '仅仅')) and any(x in instruction for x in ('对白', '台词')):
        return {k: v for k, v in paths.items() if k.endswith(('.dialogue', '.dialogue_text', '.text'))}
    return paths


@router.get('/projects/{project_id}/assistant')
def history(project_id):
    store.get('projects', project_id)
    return messages(project_id)


@router.post('/projects/{project_id}/assistant')
async def ask(project_id, payload: dict):
    if any(str(k).startswith('_') for k in (payload.get('scope') or {})): raise ValueError('助手范围包含保留字段')
    topic_id = payload.get('topic_id', 'main')
    if not isinstance(topic_id, str) or not topic_id or len(topic_id) > 80: raise ValueError('话题ID无效')
    lock = agent_locks.setdefault(project_id, asyncio.Lock())
    async with lock:
        request_id = payload.get('request_id')
        if request_id:
            if not isinstance(request_id,str) or len(request_id)>80: raise ValueError('请求ID无效')
            old=next((m for m in messages(project_id) if m.get('request_id')==request_id),None)
            if old:
                if old.get('topic_id','main')!=topic_id or old.get('request')!=payload.get('message','').strip() or old.get('scope')!=(payload.get('scope') or {}): raise ValueError('请求ID已用于其他内容')
                return old
        task=asyncio.current_task();agent_tasks[project_id]=task
        try: return await _ask(project_id,payload)
        except Exception as error:
            pending=next((m for m in reversed(messages(project_id)) if m.get('status')=='running' and m.get('request')==payload.get('message','').strip()),None)
            if pending:
                pending.update(status='failed',reply='本轮未通过校验：'+str(error)+'。原内容未被覆盖。');put(pending)
            raise
        finally:
            if agent_tasks.get(project_id) is task: agent_tasks.pop(project_id,None)


@router.post('/projects/{project_id}/assistant/stop')
async def stop_agent(project_id):
    store.get('projects',project_id)
    task=agent_tasks.get(project_id)
    if task and not task.done(): task.cancel()
    return {'stopped':bool(task and not task.done()),'reply':'已停止助手处理；已提交的制作任务保留在任务面板。'}


def recover_runs():
    with store.db() as db:
        for row in db.execute('SELECT body FROM assistant_messages').fetchall():
            message=json.loads(row['body'])
            if message.get('status')=='running':
                message.update(status='interrupted',reply='上次助手处理因程序关闭而中断。执行记录和已提交任务已保留，可核对任务面板后继续。')
                db.execute('UPDATE assistant_messages SET body=? WHERE id=?',(json.dumps(message,ensure_ascii=False),message['id']))


@router.get('/projects/{project_id}/assistant-memory')
def memory(project_id): return agent_memory.get(project_id)


@router.put('/projects/{project_id}/assistant-memory')
def update_memory(project_id,payload:dict):
    return agent_memory.save(project_id,payload.get('entries'),payload.get('revision'))


async def _ask(project_id, payload):
    p = store.get('projects', project_id)
    scope = payload.get('scope') or {}
    instruction = str(payload.get('message', '')).strip()
    if not instruction or len(instruction) > 6000: raise ValueError('请输入1至6000字的请求')
    if not scope or scope.get('stage') in ('storyboard','video','assets','novel','script') and not scope.get('target_id') and not scope.get('target_ids') and (not scope.get('episode_id') or scope.get('stage') in ('storyboard','video','assets')):
        allowed, context = {}, creative_agent.brief(p)
    else: allowed, context = scope_fields(p, scope)
    allowed = restrict_fields(allowed, instruction)
    message_id=store.uid('assist');tool_trace=[]
    if payload.get('mode') == 'check':
        findings = domain.checks(p, providers.settings(), stage='storyboard')
        target = scope.get('target_id')
        if target: findings = [f for f in findings if f.get('target') in (None, target)]
        reply = '\n'.join(f['message'] for f in findings) or '当前结构与关键引用检查通过。实际画面、对白与生成质量仍需预览验收。'
        changes = []; usage = {}; model = '本地结构检查'
    else:
        provider = providers.provider_for(p, 'text')
        turns = [{'request': m['request'][:1200], 'reply': m.get('reply','')[:1600], 'scope':m['scope'],'job_id':m.get('job_id')} for m in [m for m in messages(project_id) if m.get('topic_id','main') == payload.get('topic_id','main')][-8:]]
        def persist_trace(trace):
            put({'id':message_id,'project_id':project_id,'scope':copy.deepcopy(scope),'request':instruction,
                 'topic_id':payload.get('topic_id','main'),'request_id':payload.get('request_id'),'reply':'智能体正在读取信息或执行任务…','changes':[],
                 'created_at':store.now(),'status':'running','tool_trace':trace,'model':provider['model']})
        persist_trace([])
        try: result=await creative_agent.run(p,scope,instruction,allowed,context,turns,provider,persist_trace)
        except asyncio.CancelledError:
            running=get(message_id);running.update(status='cancelled',reply='已停止本轮助手处理。已提交的制作任务仍保留在任务面板。')
            return put(running)
        except Exception as error:
            try: running=get(message_id)
            except KeyError: raise
            running.update(status='failed',reply='本轮处理未完成：'+str(error)+'。已执行的工具记录和已提交的任务已保留。')
            return put(running)
        usage=result.get('usage',{});tool_trace=result.get('tool_trace',[])
        if not isinstance(result, dict) or not isinstance(result.get('reply'), str): raise ValueError('助手返回格式无效，请重试')
        reply = result['reply'][:8000]
        incoming = result.get('changes', [])
        if not isinstance(incoming, list) or len(incoming) > 50: raise ValueError('助手修改列表无效')
        changes = []; seen = set()
        for change in incoming:
            if not isinstance(change, dict): raise ValueError('助手修改条目无效')
            path = change.get('path'); value = change.get('value')
            if path not in allowed or path in seen: raise ValueError('助手建议超出了当前修改范围，原内容未改动')
            before = allowed[path]
            if isinstance(before, (int, float)):
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 < value <= 600: raise ValueError('建议时长无效')
            elif not isinstance(value, str) or len(value) > 50000: raise ValueError('助手建议内容格式无效')
            seen.add(path)
            if value != before: changes.append({'path': path, 'before': before, 'value': value})
        model = provider['model']
    message = put({'id': message_id, 'project_id': project_id, 'scope': copy.deepcopy(scope),
        'request': instruction, 'reply': reply, 'changes': changes, 'created_at': store.now(),
        'source_revision': p['revision'], 'source_fingerprint': domain.fingerprint(context),
        'status': 'pending' if changes else 'answered', 'model': model, 'usage': usage,
        'topic_id':payload.get('topic_id','main'),'request_id':payload.get('request_id'),'tool_trace':tool_trace})
    if changes and payload.get('auto_apply') is True and scope.get('workspace')=='storyboard':
        try:
            creative_agent.authorize(instruction, '回填修改', r'写|修改|调整|更新|改成|改为|补充|优化|完善|生成')
        except ValueError: return message
        try:
            apply(project_id, message_id, {'revision':store.get('projects',project_id)['revision']})
            message = get(message_id)
            message['reply'] += f'\n已回填 {len(changes)} 处修改，原内容保存在历史版本。'
        except ValueError as error:
            message['reply'] += '\n自动回填未执行：'+str(error)+'。建议内容已保留。'
        put(message)
    return message


@router.post('/projects/{project_id}/assistant/actions')
async def button_action(project_id, payload: dict):
    """A real agent turn for every explicitly clicked text-generation button."""
    from . import jobs
    lock=agent_locks.setdefault(project_id,asyncio.Lock())
    async with lock:
        p=workflow.ensure(store.get('projects',project_id))
        kind=payload.get('kind','text');stage=payload.get('stage')
        if not (kind=='text' and stage in set(workflow.SCHEMAS)|set(domain.SCHEMAS) or kind=='polish' and stage=='assets'): raise ValueError('仅支持已定义的文本制作按钮')
        target=payload.get('target_id');options=payload.get('workflow_options') or {}
        task_payload={k:copy.deepcopy(payload[k]) for k in ('kind','stage','target_id','workflow_options','instruction','provider_id','preview','auto','remaining') if k in payload}
        task_payload.setdefault('kind',kind)
        if stage in workflow.SCHEMAS: task_payload['preview']=True
        signature=domain.fingerprint(task_payload)
        request_id=payload.get('request_id');topic=payload.get('topic_id','main')
        if not isinstance(request_id,str) or not 1<=len(request_id)<=80 or not isinstance(topic,str) or not 1<=len(topic)<=80: raise ValueError('按钮请求或话题标识无效')
        old=next((m for m in messages(project_id) if m.get('request_id')==request_id),None)
        if old:
            if old.get('action_signature')!=signature or old.get('topic_id')!=topic: raise ValueError('按钮请求标识已用于其他操作')
            return {'message':old,'job':jobs.public(store.get('jobs',old['job_id'])) if old.get('job_id') else None}
        if payload.get('revision') != p['revision']: raise ValueError('作品已更新，请刷新后操作')
        if target and not any(x['id']==target for x in creative_agent.objects(p)): raise ValueError('按钮目标不属于当前作品')
        if stage in workflow.SCHEMAS: context=workflow.context(p,stage,target,options)
        else: context={'project':creative_agent.brief(p),'selected':next((x for x in creative_agent.objects(p) if x['id']==target),None)}
        task_payload['revision']=p['revision']
        fingerprint=creative_agent.action_fingerprint(p,task_payload)
        names={'wf_story':'生成故事正文','wf_setup':'分析剧本设定','wf_continue':'续写小说','wf_chapters':'整理章节大纲','wf_script':'生成剧本','wf_breakdown':'拆分分镜','wf_prompts':'生成生图提示词','wf_video_prompt':'生成镜头描述','direction':'生成故事设定','characters':'生成人物档案','world':'生成世界规则','novel':'生成大纲与小说','scene_plan':'生成分场大纲','script':'生成分集剧本','performance':'生成表演设计','storyboard':'生成分镜建议稿'}
        request=names.get(stage,'润色资产描述' if kind=='polish' else '生成本阶段文本')
        message={'id':store.uid('assist'),'project_id':project_id,'scope':{'stage':stage,'target_id':target},'request':request,'reply':'正在读取项目要求并调配技能…','status':'running','changes':[], 'tool_trace':[], 'created_at':store.now(),'topic_id':topic,'request_id':request_id,'action_signature':signature,'origin':'button'}
        if options.get('target_ids'): message['scope']['target_ids']=copy.deepcopy(options['target_ids'])
        put(message)
        scope={**message['scope'],'_text_action':task_payload,'_action_fingerprint':fingerprint}
        turns=[{'request':m['request'][:1200],'reply':m.get('reply','')[:1600],'scope':m.get('scope',{}),'job_id':m.get('job_id')} for m in messages(project_id) if m.get('topic_id','main')==topic and m['id']!=message['id']][-8:]
        def trace(events):
            message['tool_trace']=events
            accepted=next((t.get('result') for t in events if t.get('name')=='execute_text_action' and t.get('status')=='succeeded'),None)
            if accepted: message['job_id']=accepted['id']
            put(message)
        def response():
            return {'message':message,'job':jobs.public(store.get('jobs',message['job_id'])) if message.get('job_id') else None}
        agent_tasks[project_id]=asyncio.current_task()
        try:
            if stage=='wf_canvas_text' and options.get('canvas_model'):
                p.setdefault('model_bindings',{})['text']=options['canvas_model']
            provider=providers.provider_for(p,'text',payload.get('provider_id'))
            result=await creative_agent.run(p,scope,request,{},context,turns,provider,trace)
            submitted=next((t.get('result') for t in result.get('tool_trace',[]) if t.get('name')=='execute_text_action' and t.get('status')=='succeeded'),None)
            message.update(reply=result.get('reply',''),status='answered' if submitted else 'failed',tool_trace=result.get('tool_trace',[]),usage=result.get('usage',{}),model=provider['model'])
            if submitted:
                message['job_id']=submitted['id'];message['reply']+='\n制作任务已提交，校验通过后更新对应内容。'
            else: message['reply']+='\n助手没有提交制作任务，请查看执行记录。'
            put(message)
            return response()
        except asyncio.CancelledError:
            message.update(status='cancelled',reply='已停止助手处理，已提交的制作任务保留。');put(message)
            return response()
        except Exception as error:
            message.update(status='failed',reply='助手处理未完成：'+str(error)+'。已执行记录保留。');put(message)
            return response()
        finally:
            if agent_tasks.get(project_id) is asyncio.current_task():agent_tasks.pop(project_id,None)


@router.post('/projects/{project_id}/assistant/{ident}/apply')
def apply(project_id, ident, payload: dict):
    message = get(ident)
    if message['project_id'] != project_id: raise ValueError('建议稿不属于当前作品')
    if message['status'] == 'applied': return store.get('projects', project_id)
    if message['status'] != 'pending': raise ValueError('这份建议稿不可采用')
    p = store.get('projects', project_id)
    if payload.get('revision') != p['revision']: raise ValueError('项目已有更新，请刷新后核对建议稿')
    previous = copy.deepcopy(p)
    allowed, context = scope_fields(p, message['scope'])
    if domain.fingerprint(context) != message['source_fingerprint']:
        raise ValueError('当前对象已被编辑，请重新获取建议；没有覆盖你的修改')
    for change in message['changes']:
        if change['path'] not in allowed or allowed[change['path']] != change['before']:
            raise ValueError('对象的位置或内容已变化，请重新获取建议')
        write(p, change['path'], change['value'])
    stage = message['scope'].get('stage')
    if stage in ('storyboard', 'video', 'assets'):
        affected_segments = {int(c['path'].split('.')[1]) for c in message['changes'] if c['path'].startswith('segments.')}
        affected_assets = {int(c['path'].split('.')[1]) for c in message['changes'] if c['path'].startswith('assets.')}
        for index in affected_segments:
            segment = p['segments'][index]
            if 'dialogue_text' in segment:
                from . import native_audio
                native_audio.dialogue_rows(segment)
            errors = [f['message'] for f in domain.checks(p, {}, 'storyboard') if f['severity'] == 'error' and f.get('target') == segment['id']]
            if errors: raise ValueError('建议稿未通过分镜校验：' + '；'.join(errors))
            segment['status'] = 'stale' if segment.get('versions') else 'draft'
            domain.stale_dependents(p, segment['id'])
            p['outputs']['storyboard'] = {'segments': p['segments']}
            p['stage_status']['storyboard'] = 'draft'
        for index in affected_assets:
            asset = p['assets'][index]
            asset['version'] += 1; asset['status'] = 'draft'
            for segment in p['segments']:
                if asset['id'] in segment.get('character_ids', []) + segment.get('prop_ids', []) + [segment.get('location_id')]: segment['status'] = 'stale'
    else:
        p['stage_status'][stage] = 'draft'
        primary = 'direction' if stage in ('production_setup','source') else 'script' if stage == 'scene_plan' else stage
        stages = [item[0] for item in domain.STAGES]
        for downstream in stages[stages.index(primary) + 1:]:
            if downstream in p['stage_status']: p['stage_status'][downstream] = 'stale'
        domain.derive_assets(p)
    workflow.sync_manual(previous, p)
    from . import task_locks
    task_locks.assert_available(previous, task_locks.changes(previous, p))
    result = store.save_project(p, p['revision'], '采用创作助手建议（当前范围）')
    message['status'] = 'applied'; message['applied_at'] = store.now(); put(message)
    return result


@router.post('/projects/{project_id}/assistant/{ident}/discard')
def discard(project_id, ident):
    message = get(ident)
    if message['project_id'] != project_id: raise ValueError('建议稿不属于当前作品')
    if message['status'] == 'pending': message['status'] = 'discarded'; put(message)
    return message
