"""Local MCP integration. Client settings are merged; all canvas writes use CAS."""
import copy
import ctypes
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException
from . import store, yaoguang, providers, jobs, skills, director_prompts
from . import mcp_workflow
from . import mcp_production

router=APIRouter(prefix='/api/mcp',tags=['MCP'])
CLIENTS={'codex':'Codex','deepseek':'DeepSeek Harness','antigravity':'Google Antigravity'}
NAME='comic_studio'
HOME=Path.home()
SCRIPT=store.ROOT/'scripts/studio_mcp.py'
KINDS=['text','split','character','location','prop','shot','txt2img','video','audio','compose']
FIELDS={'title','text','studioPrompt','studioVideoPrompt','studioCharacter','studioIdentityName','studioDuration','studioRatio','studioProvider','studioModel','studioResolution','studioGenerateAudio','studioWatermark'}
LOCKS={}

def schema(properties,required=()):return {'type':'object','properties':properties,'required':list(required),'additionalProperties':False}
STR={'type':'string'}
PID={'project_id':STR}
NODE={**PID,'node_id':STR}
def tool(name,description,properties,required=(),read=False,paid=False):
    return {'name':name,'description':description,'inputSchema':schema(properties,required),'annotations':{'readOnlyHint':read,'destructiveHint':paid,'idempotentHint':read,'openWorldHint':paid}}
TOOLS=[
    tool('studio_organize_video_prompt','调用本平台绑定的文字模型，执行与画布整理按钮相同的导演提示词编译。保留剧情、对白、卡片和引用；仅产生文字调用费用，不生成图片或视频。整理后内容或引用变化需重新整理。',{**NODE,'confirm_generation':{'type':'boolean','const':True}},['project_id','node_id','confirm_generation'],paid=True),
    tool('studio_start_production','完整制作唯一执行入口：已有结构化拆分后，指定镜头并授权实际生成。后台自动补资产→镜头图→视频。video_mode默认references，把镜头图和人物场景道具共同传入；first_frame仅在渠道明确支持首帧时使用。用studio_read_production查询，不直接建普通视频卡。',{**PID,'breakdown_id':STR,'shot_keys':{'type':'array','items':STR,'minItems':1,'maxItems':100},'video_mode':{'type':'string','enum':['references','first_frame']},'confirm_generation':{'type':'boolean','const':True}},['project_id','breakdown_id','shot_keys','confirm_generation'],paid=True),
    tool('studio_read_production','读取持久制作任务、阶段事件、失败原因和各镜头进度。needs_review只说明成品完成，仍需实际观看验收。',PID,['project_id'],True),
    tool('studio_get_creation_skill','按需读取本项目实际绑定的编剧、资产或分镜技能内容。拆分前读取storyboard和assets；写剧本前读取script。仅返回技能资料，不返回密钥。',{**PID,'stage':{'type':'string','enum':['script','assets','storyboard']}},['project_id','stage'],True),
    tool('studio_get_workflow','制作入口：先读取本项目的统一流程、结构化拆分进度、缺失资产和下一步。外部智能体必须先调用，不能直接用文本跳过资产与镜头。',PID,['project_id'],True),
    tool('studio_apply_breakdown','将你分析好的剧本一次整理成分镜总表、角色、默认身份、其他身份、场景、道具、镜头图和视频卡。自动复用已有同名资产与建立引用，不调用付费模型。同一breakdown_id重试幂等；内容变化用新ID。',{**PID,'source_node_id':STR,'breakdown_id':STR,'assets':{'type':'array','items':mcp_workflow.ASSET,'minItems':1,'maxItems':150},'shots':{'type':'array','items':mcp_workflow.SHOT,'minItems':1,'maxItems':100}},['project_id','source_node_id','breakdown_id','assets','shots']),
    tool('studio_prepare_shot','生成前检查流程镜头的资产引用；默认身份复用根角色图片，返回缺失素材、待完成任务、图/视频卡ID和下一步，不提交付费任务。',{**PID,'frame_id':STR},['project_id','frame_id']),
    tool('studio_record_review','记录实际观看成品后的质量检查。不得未看就passed；没有媒体不可验收。生成完成不等于质量通过。',{**NODE,'verdict':{'type':'string','enum':['passed','needs_revision']},'observations':STR},['project_id','node_id','verdict','observations']),
    tool('studio_list_projects','列出作品ID和名称，不返回密钥或服务配置。',{},read=True),
    tool('studio_read_canvas','读取画布节点、连线、当前素材和 updated_at。编辑前先读取，再调用studio_get_workflow了解制作流程。',PID,['project_id'],True),
    tool('studio_create_card','单卡自由编辑工具：创建空卡片，不生成媒体，返回真实节点ID。完整剧本制作优先studio_get_workflow与studio_apply_breakdown，不能以单文本卡替代资产和分镜流程。',{**PID,'kind':{'type':'string','enum':KINDS},'title':STR,'text':STR,'prompt':STR,'character':STR,'x':{'type':'number'},'y':{'type':'number'}},['project_id','kind','title']),
    tool('studio_create_identity','从已有角色创建独立身份卡；默认身份复用原角色图，已有默认身份不会重复创建。',{**PID,'parent_id':STR,'name':STR,'prompt':STR,'default':{'type':'boolean'}},['project_id','parent_id','name']),
    tool('studio_update_card','局部更新已有卡片；不能改用途、删除素材或覆盖整张画布。',{**NODE,'patch':schema({k:({'type':'number','minimum':1,'maximum':120} if k=='studioDuration' else {'type':'boolean'} if k in ('studioGenerateAudio','studioWatermark') else STR) for k in sorted(FIELDS)})},['project_id','node_id','patch']),
    tool('studio_connect_cards','连接现有卡片，拒绝自连接和循环，已有连线复用。',{**PID,'from_id':STR,'to_id':STR},['project_id','from_id','to_id']),
    tool('studio_list_media','列出本平台本地素材的名称和地址，不访问任意电脑文件。',{},read=True),
    tool('studio_attach_media','把已经在工作台里的图片/视频/音频附加到卡片。',{**NODE,'url':STR},['project_id','node_id','url']),
    tool('studio_generate_media','单卡实际生成。完整制作必须使用studio_start_production，不能创建普通视频卡跳过流程。普通视频卡只有用户明确要求自由文生视频时才传generation_mode=free；默认拒绝。用户明确授权付费才传confirm_generation=true；用studio_read_task查询真实完成。',{**NODE,'confirm_generation':{'type':'boolean','const':True},'generation_mode':{'type':'string','enum':['production','free'],'description':'默认production。free仅用于用户明确要求独立文生视频的任务，不能用于规避完整制作。'},'reference_node_ids':{'type':'array','items':STR,'maxItems':20},'first_frame_id':STR},['project_id','node_id','confirm_generation'],paid=True),
    tool('studio_read_task','查询任务真实状态。成功时把实际媒体回填对应画布卡片。',{**PID,'task_id':STR},['project_id','task_id']),
]

def config_path(client):
    if client=='codex':return Path(os.environ.get('CODEX_HOME',str(HOME/'.codex')))/'config.toml'
    if client=='deepseek':return HOME/'.dsh/profiles/desktop/cordis.patch.yml'
    return HOME/'.gemini/config/mcp_config.json'

def command(client):
    python=store.ROOT/'runtime/python/python.exe'
    if not python.exists():python=Path(sys.executable)
    return {'command':str(python),'args':['-u',str(SCRIPT),'--client',client],'cwd':str(store.ROOT)}

def snippet(client):
    entry=command(client)
    if client=='codex':return '[mcp_servers.comic_studio]\n'+''.join(f'{k} = {json.dumps(v,ensure_ascii=False)}\n' for k,v in entry.items())
    if client=='deepseek':return '- id: comic-studio-mcp\n  name: "@deepseek-ai/dsh-mcp-client"\n  config:\n    serverName: comic_studio\n    transport: stdio\n'+''.join('    '+k+': '+json.dumps(v,ensure_ascii=False)+'\n' for k,v in entry.items() if k!='cwd')
    return json.dumps({'mcpServers':{NAME:entry}},ensure_ascii=False,indent=2)

def configured(client):
    path=config_path(client)
    if not path.exists():return False
    s=path.read_text(encoding='utf-8-sig')
    if client=='codex':return bool(re.search(r'^\[mcp_servers\.comic_studio\]',s,re.M))
    if client=='deepseek':return bool(re.search(r'^- id: comic-studio-mcp\s*$',s,re.M))
    try:return NAME in json.loads(s).get('mcpServers',{})
    except (ValueError,AttributeError):return False

def install_config(client):
    if client not in CLIENTS:raise ValueError('未知 MCP 客户端')
    path=config_path(client);path.parent.mkdir(parents=True,exist_ok=True)
    old=path.read_text(encoding='utf-8-sig') if path.exists() else ''
    if client=='antigravity':
        data=json.loads(old) if old.strip() else {}
        if not isinstance(data,dict) or not isinstance(data.get('mcpServers',{}),dict):raise ValueError('客户端配置格式无效，未覆盖')
        previous=data.setdefault('mcpServers',{}).get(NAME)
        if previous and str(SCRIPT) not in previous.get('args',[]):raise ValueError('comic_studio 已有其他配置，未覆盖')
        data['mcpServers'][NAME]=command(client);new=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
    else:
        begin='# comic-studio MCP begin';end='# comic-studio MCP end'
        block=begin+'\n'+snippet(client)+end+'\n'
        pattern=re.escape(begin)+r'.*?'+re.escape(end)+r'\n?'
        if begin in old:
            if end not in old:raise ValueError('已有配置标记不完整，未覆盖')
            new=re.sub(pattern,lambda m:block,old,flags=re.S)
        else:
            if configured(client):raise ValueError('已有同名 MCP 配置，未覆盖；请使用配置示例核对')
            new=old.rstrip()+'\n\n'+block
    if old and new!=old:
        backup=path.with_name(path.name+f'.comic-studio-{time.time_ns()}.bak');backup.write_text(old,encoding='utf-8')
    if new!=old:path.write_text(new,encoding='utf-8')
    return {'client':client,'configured':True,'path':str(path),'message':'配置已写入，请在客户端刷新 MCP 或重启客户端；实际握手后才会显示已连接。'}

def alive(pid):
    if not isinstance(pid,int) or pid<=0:return False
    if os.name=='nt':
        kernel=ctypes.windll.kernel32;kernel.OpenProcess.restype=ctypes.c_void_p
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:return False
        code=ctypes.c_ulong();ok=kernel.GetExitCodeProcess(ctypes.c_void_p(handle),ctypes.byref(code));kernel.CloseHandle(ctypes.c_void_p(handle))
        return bool(ok and code.value==259)
    try:os.kill(pid,0);return True
    except OSError:return False

def status():
    with store.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS mcp_sessions(id TEXT PRIMARY KEY,body TEXT NOT NULL)')
        active=[json.loads(r['body']) for r in c.execute('SELECT body FROM mcp_sessions')]
    rows=[]
    for ident,name in CLIENTS.items():
        sessions=[s for s in active if s.get('client')==ident and alive(s.get('pid'))]
        installed=(HOME/'.codex').exists() if ident=='codex' else (HOME/'AppData/Local/Programs/DeepSeek Harness/DeepSeek Harness.exe').exists() if ident=='deepseek' else any((HOME/x).exists() for x in ('AppData/Local/Programs/Antigravity/Antigravity.exe','AppData/Local/Programs/Antigravity/antigravity.exe'))
        rows.append({'id':ident,'name':name,'installed':installed,'configured':configured(ident),'connected':bool(sessions),'last_seen':max((s.get('last_seen',0) for s in sessions),default=None),'path':str(config_path(ident)),'config':snippet(ident)})
    installer=store.ROOT/'downloads/Antigravity/Antigravity-x64-2.22.0.exe'
    return {'clients':rows,'tools_count':len(TOOLS),'downloaded':installer.exists(),'installer':str(installer) if installer.exists() else None}

def get_node(graph,ident):
    n=next((n for n in graph['nodes'] if n['id']==ident),None)
    if not n:raise ValueError('卡片不存在')
    return n
def save_graph(pid,graph):graph['base_updated_at']=graph['updated_at'];return yaoguang.save_canvas(pid,graph,server_workflow=True)
def valid_fields(values):
    if not isinstance(values,dict) or any(k not in FIELDS for k in values):raise ValueError('包含不允许修改的卡片字段')
    for k,v in values.items():
        if k=='studioDuration':
            if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or not 1<=v<=120:raise ValueError('时长须为1–120秒')
        elif k in ('studioGenerateAudio','studioWatermark'):
            if not isinstance(v,bool):raise ValueError('声音与水印参数须为布尔值')
        elif not isinstance(v,str) or len(v)>(100000 if k in ('text','studioPrompt') else 500):raise ValueError('卡片字段无效或过长')
        if k=='studioRatio' and v not in ('16:9','9:16','1:1','4:3','3:4','21:9','adaptive'):raise ValueError('画面比例无效')
        if k=='studioResolution' and v not in ('480p','720p','1080p'):raise ValueError('分辨率无效')

def refs_for(graph,n,explicit=None):
    refs=[];texts=[];seen=set();byid={x['id']:x for x in graph['nodes']}
    def walk(ident):
        if ident in seen:return
        seen.add(ident);source=byid.get(ident)
        if not source:raise ValueError('引用卡片不存在')
        kind=source.get('studioKind')
        if kind in ('text','split'):
            if source.get('text'):texts.append(source['text'].strip())
            if kind=='text':
                for e in graph['connections']:
                    upstream=byid.get(e['from'],{})
                    if e['to']==ident and not (source.get('studioDetachedText') and upstream.get('studioKind') in ('text','split')):walk(e['from'])
            return
        if kind in ('audio','video'):
            items=[m for m in source.get('images',[]) if m.get('kind')==kind]
            if not items:raise ValueError('上游素材未就绪：'+source.get('title',ident))
            for m in items:refs.append({**m,'name':source.get('studioCharacter') or source.get('title','素材'),'node_id':ident,'kind':kind})
            return
        if kind not in ('character','location','prop','shot','txt2img','image'):return
        if kind=='character':
            voice=byid.get(source.get('studioVoiceNodeId')) if source.get('studioVoiceNodeId') else None
            samples=[m for m in voice.get('images',[]) if m.get('kind')=='audio'][:1] if voice else [source['studioVoice']] if source.get('studioVoice') else []
            if source.get('studioVoiceNodeId') and not samples:raise ValueError('绑定的音色素材尚未就绪')
            for m in samples:refs.append({**m,'kind':'audio','name':source.get('studioCharacter') or source.get('title','素材'),'node_id':ident})
        if kind in ('shot','txt2img','image') and not n.get('studioIdentityParentId'):
            for e in graph['connections']:
                upstream=byid.get(e['from'],{})
                if e['to']==ident and upstream.get('studioKind') in ('text','split','character','location','prop'):walk(e['from'])
            if source.get('studioPrompt'):texts.append(source['studioPrompt'].strip())
        images=[m for m in source.get('images',[]) if m.get('kind','image')=='image']
        if not images:raise ValueError('上游素材未就绪：'+source.get('title',ident))
        for m in images:
            name=((source.get('studioCharacter') or '角色')+' · '+source.get('studioIdentityName','')) if source.get('studioIdentityParentId') else source.get('studioCharacter') or source.get('title','素材')
            purpose=kind if kind in ('character','location','prop') else 'shot'
            role='character' if purpose=='character' else n.get('studioRefRoles',{}).get(ident+':'+m['url'],'reference') if purpose=='shot' else 'reference'
            refs.append({**m,'kind':'image','name':name,'node_id':ident,'image_purpose':purpose,'role':role,'character_name':source.get('studioCharacter') or name})
    for ident in explicit if explicit is not None else [e['from'] for e in graph['connections'] if e['to']==n['id'] and e.get('kind')!='flow']:walk(ident)
    # A root and its reused default identity are one reference, not two costumes.
    refs=[r for r in refs if not any(byid.get(o['node_id'],{}).get('studioIdentityParentId')==r['node_id'] and o['url']==r['url'] for o in refs)]
    names={}
    for r in refs:
        if r.get('role')=='character':
            if r['character_name'] in names and names[r['character_name']]!=r['node_id']:raise ValueError('同一角色引用了多套身份，请只选择本镜头的一套')
            names[r['character_name']]=r['node_id']
    unique=[]
    for r in refs:
        if not any((o['url'],o['name'],o['kind'])==(r['url'],r['name'],r['kind']) for o in unique):unique.append(r)
    return unique,texts

async def call_tool(name,args):
    definition=next((t for t in TOOLS if t['name']==name),None)
    if not definition:raise ValueError('未知 MCP 工具')
    shape=definition['inputSchema']
    if not isinstance(args,dict) or any(k not in shape['properties'] for k in args) or any(k not in args for k in shape['required']):raise ValueError('工具参数缺失或无效')
    for key,spec in shape['properties'].items():
        if key in args and spec['type']=='string' and (not isinstance(args[key],str) or len(args[key])>100000):raise ValueError('文字参数无效')
    if name=='studio_list_projects':return [{'id':p['id'],'name':p['name'],'free_canvas':p.get('settings',{}).get('free_canvas',False)} for p in store.project_summaries()]
    if name=='studio_list_media':
        return [{'url':'/media/'+p.name,'name':p.name} for p in sorted(store.MEDIA.iterdir()) if p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg','.webp','.mp4','.webm','.wav','.mp3','.m4a')][:1000]
    pid=args['project_id'];graph=yaoguang.get_canvas(pid)
    if name=='studio_get_creation_skill':
        stage=args['stage']
        if stage not in ('script','assets','storyboard'):raise ValueError('技能阶段无效')
        project=store.get('projects',pid);skill=skills.load(stage,project.get('bindings',{}).get('skill_'+stage))
        result={k:skill[k] for k in ('id','name','stage','content')}
        if stage in ('storyboard','assets'):
            result['prompt_guidance']=director_prompts.VIDEO_RULES if stage=='storyboard' else director_prompts.IMAGE_RULES
            result['prompt_compiler']=director_prompts.VERSION
            result['organize_tool']='studio_organize_video_prompt'
        return result
    if name=='studio_organize_video_prompt':
        p=store.get('projects',pid)
        if args.get('confirm_generation') is not True:raise ValueError('整理提示词需要授权实际文字模型调用')
        n=get_node(graph,args['node_id'])
        if n.get('studioKind')!='video':raise ValueError('请选择视频卡整理提示词')
        refs,texts=refs_for(graph,n)
        ordered=[r for kind in ('image','audio','video') for r in refs if r['kind']==kind]
        labels={'character':'人物','location':'场景','prop':'道具','shot':'镜头图','audio':'音色','video':'视频'}
        refs=[]
        for i,r in enumerate(ordered,1):
            category=r['kind'] if r['kind']!='image' else r['image_purpose']
            refs.append({**r,'category':category,'token':f"【{labels[category]}:{r['name']}·R{i}】"})
        source='\n\n'.join(x for x in [*dict.fromkeys(texts),n.get('studioPrompt','').strip()] if x)
        draft=n.get('studioVideoPrompt',source)
        if not source.strip() and not draft.strip():raise ValueError('请先填写镜头文本')
        signature=json.dumps({'prompt':source,'refs':[[r['node_id'],r['url'],r['name'],r['category'],r.get('role')] for r in refs],
                              'duration':n.get('studioDuration',8),'ratio':n.get('studioRatio','16:9'),'provider':n.get('studioProvider') or p.get('bindings',{}).get('video',''),'model':n.get('studioModel') or p.get('model_bindings',{}).get('video',''),'resolution':n.get('studioResolution') or '720p','generate_audio':n.get('studioGenerateAudio') is not False,'watermark':bool(n.get('studioWatermark'))},ensure_ascii=False,separators=(',',':'))
        result=await yaoguang.text_task(pid,{'target_video_provider':n.get('studioProvider'),'target_video_model':n.get('studioModel'),'prompt_task':'video_prompt','message':json.dumps({'connected_text':source,'edited_prompt':draft,
            'duration':n.get('studioDuration',8),'references':[{k:r.get(k) for k in ('token','category','name','role','node_id')} for r in refs]},ensure_ascii=False),
            'system_prompt':'整理当前镜头的完整视频提示词，只返回正文。保持原剧情与对白，使用所给引用清单。',
            'studio_node_id':n['id'],'studio_node_title':n['title']})
        latest=yaoguang.get_canvas(pid)
        if latest['updated_at']!=graph['updated_at']:raise ValueError('整理期间画布已修改；文字结果保留在任务记录，请重新整理')
        out=get_node(latest,n['id']);out.update(studioVideoPrompt=result['text'],studioVideoPrepared=True,studioVideoSource=signature,studioVideoArrangeJob=result['job_id'])
        save_graph(pid,latest)
        return {'node_id':n['id'],'prompt':result['text'],'job_id':result['job_id'],'prompt_compiler':director_prompts.VERSION}
    if name=='studio_get_workflow':return {**mcp_workflow.workflow_state(graph),'production':mcp_production.task(graph),'model_choices':yaoguang.config(pid)}
    if name=='studio_start_production':
        result=mcp_production.start(pid,graph,args);mcp_production.launch(pid);return result
    if name=='studio_read_production':
        result=mcp_production.refresh_review(pid,graph)
        if result and result['status']=='running':mcp_production.launch(pid)
        return {'production':result,'shots':mcp_workflow.workflow_state(graph)['shots']}
    if name=='studio_apply_breakdown':return mcp_workflow.apply_breakdown(pid,graph,args)
    if name=='studio_prepare_shot':return mcp_workflow.prepare_shot(pid,graph,args['frame_id'])
    if name=='studio_read_canvas':return graph
    if name=='studio_read_task':
        job=store.get('jobs',args['task_id'])
        if job['project_id']!=pid:raise ValueError('任务不属于当前作品')
        for n in graph['nodes']:
            if n.get('studioPendingTask')!=job['id'] and not (n.get('studioLastTask')==job['id'] and not n.get('studioPendingTask')):continue
            if job['status']=='succeeded':
                result=yaoguang.result_media(job)
                if not result['urls']:raise ValueError('任务成功但没有实际媒体，未覆盖卡片')
                n['images']=result['urls'];n['studioJobId']=job['id'];n['studioLastTask']=job['id'];n.pop('studioPendingTask',None);n['studioError']='';n['studioTaskState']='succeeded';save_graph(pid,graph)
            elif job['status'] in ('failed','cancelled'):
                n['studioError']=job.get('error') or job['status'];n['studioTaskState']=job['status'];n['studioLastTask']=job['id'];n.pop('studioPendingTask',None);save_graph(pid,graph)
        return {'task_id':job['id'],'status':job['status'],'error':job.get('error'),'result':yaoguang.result_media(job) if job['status']=='succeeded' else None}
    if name=='studio_create_card':
        kind=args['kind']
        if kind not in KINDS:raise ValueError('卡片类型无效')
        values={'title':args['title'],'text':args.get('text',''),'studioPrompt':args.get('prompt',''),'studioCharacter':args.get('character') or (args['title'] if kind=='character' else '')};valid_fields(values)
        n={'id':store.uid('mcp'),'type':'smart-prompt' if kind in ('text','split') else 'smart-minimax' if kind=='compose' else 'smart-image','studioKind':kind,'studioImagePurpose':kind if kind in ('character','location','prop') else 'shot','images':[],'x':args.get('x',200),'y':args.get('y',200),'w':360,'h':520,'studioDuration':8,'studioRatio':'16:9',**values}
        if kind in ('text','split'):n['llmEnabled']=False
        graph['nodes'].append(n);saved=save_graph(pid,graph);return {'node':n,'updated_at':saved['updated_at']}
    if name=='studio_create_identity':
        parent=get_node(graph,args['parent_id'])
        if parent.get('studioKind')!='character' or parent.get('studioIdentityParentId'):raise ValueError('请使用根角色卡作为来源')
        if args.get('default'):
            existing=next((n for n in graph['nodes'] if n.get('studioIdentityParentId')==parent['id'] and n.get('studioIdentityDefault')),None)
            if existing:return {'node':existing,'reused':True}
        name=args['name'];valid_fields({'title':name,'studioPrompt':args.get('prompt','')})
        n={'id':store.uid('mcp'),'type':'smart-image','studioKind':'character','studioImagePurpose':'character','studioIdentityParentId':parent['id'],'studioIdentityRootId':parent['id'],'studioIdentityName':name,'studioCharacter':parent.get('studioCharacter') or parent['title'],'title':(parent.get('studioCharacter') or parent['title'])+' · '+name,'studioPrompt':args.get('prompt',''),'studioRatio':parent.get('studioRatio','16:9'),'images':copy.deepcopy(parent.get('images',[])) if args.get('default') else [],'studioIdentityDefault':args.get('default',False),'x':parent['x']+500,'y':parent['y'],'w':360,'h':820}
        graph['nodes'].append(n);graph['connections'].append({'from':parent['id'],'to':n['id'],'kind':'input'});save_graph(pid,graph);return {'node':n}
    if name=='studio_connect_cards':
        a,b=args['from_id'],args['to_id'];get_node(graph,a);get_node(graph,b)
        if a==b:raise ValueError('不能自连接')
        stack=[b];visited=set()
        while stack:
            x=stack.pop()
            if x==a:raise ValueError('连线会造成循环')
            if x in visited:continue
            visited.add(x);stack.extend(e['to'] for e in graph['connections'] if e['from']==x)
        if any(e['from']==a and e['to']==b for e in graph['connections']):return {'reused':True}
        graph['connections'].append({'from':a,'to':b,'kind':'input'});save_graph(pid,graph);return {'connected':True}
    n=get_node(graph,args['node_id'])
    if name=='studio_record_review':
        if args['verdict'] not in ('passed','needs_revision') or not n.get('images'):raise ValueError('请先查看真实成品再验收')
        observation=mcp_workflow.text(args['observations'],'验收观察',10000)
        n['studioMcpReview']={'verdict':args['verdict'],'observations':observation,'media_urls':[m['url'] for m in n['images']],'reviewed_at':store.now()};save_graph(pid,graph);mcp_production.refresh_review(pid,yaoguang.get_canvas(pid));return {'review':n['studioMcpReview']}
    if name=='studio_update_card':
        valid_fields(args['patch']);values=copy.deepcopy(args['patch'])
        if n.get('studioKind') not in ('text','split','audio','compose') and 'text' in values and 'studioPrompt' not in values:values['studioPrompt']=values['text']
        if n.get('studioKind')=='video' and any(k in values for k in ('studioPrompt','studioVideoPrompt')):
            values['studioVideoPrepared']=False
            if 'studioVideoPrompt' in values:values['studioPrompt']=values['studioVideoPrompt']
        n.update(values);save_graph(pid,graph);return {'node':n}
    if name=='studio_attach_media':
        file=yaoguang.local_file(args['url']);suffix=Path(file).suffix.lower();kind='video' if suffix in ('.mp4','.webm','.mov') else 'audio' if suffix in ('.mp3','.wav','.m4a','.ogg') else 'image' if suffix in ('.png','.jpg','.jpeg','.webp') else None
        expected=n.get('studioKind') if n.get('studioKind') in ('video','audio') else 'image'
        if kind!=expected:raise ValueError('素材类型不符合当前卡片')
        item={'url':'/media/'+file,'name':n['title'],'kind':kind}
        if not any(m['url']==item['url'] for m in n['images']):n['images'].append(item);save_graph(pid,graph)
        return {'media':item}
    if name=='studio_generate_media':
        if args.get('confirm_generation') is not True:raise ValueError('仅用户明确要求实际生成时才能提交付费任务')
        production=mcp_production.scope(graph)
        production_row=None
        if production:
            t,rows,allowed=production
            if n['id'] not in allowed:raise ValueError('完整制作任务禁止绕过范围创建普通视频；请使用计划中的镜头和资产')
            production_row=next((r for r in rows if n['id'] in (r['frame_id'],r['video_id'])),None)
        if n.get('studioPendingTask'):
            existing=store.get('jobs',n['studioPendingTask'])
            if existing['status'] in ('queued','running','waiting_dependency'):return {'task_id':existing['id'],'status':existing['status'],'reused':True}
        kind='video' if n.get('studioKind')=='video' else 'image' if n.get('studioKind') in ('character','location','prop','shot','txt2img','image') else None
        if not kind:raise ValueError('该卡片不支持媒体生成')
        if args.get('generation_mode','production') not in ('production','free'):raise ValueError('生成模式无效')
        if kind=='video' and not production and not n.get('studioMcpShotKey') and args.get('generation_mode')!='free':raise ValueError('普通视频卡不能代替完整制作，请先读取studio_get_workflow，使用studio_apply_breakdown与studio_start_production；仅用户明确要求独立文生视频时可选择generation_mode=free')
        if n.get('studioMcpShotKey') or production_row:
            frame=get_node(graph,production_row['frame_id'] if production_row else n.get('studioMcpFrameId',n['id']))
            state=mcp_workflow.shot_state(graph,frame)
            if state['missing_assets']:raise ValueError('流程镜头缺少资产或连线，请先 studio_prepare_shot：'+json.dumps(state['missing_assets'],ensure_ascii=False))
            if kind=='video' and (not frame.get('images') or state['next_step']=='repair_video_link'):raise ValueError('请先完成镜头图片并保持图到视频的引用')
            if args.get('reference_node_ids') is not None:raise ValueError('流程镜头请使用已建好的引用，修改引用后再准备镜头，不能跳过流程资产')
        if n.get('studioIdentityDefault') and not n.get('studioPrompt'):
            parent=get_node(graph,n['studioIdentityParentId'])
            if not parent.get('images'):raise ValueError('请先生成来源角色图')
            n['images']=copy.deepcopy(parent['images']);save_graph(pid,graph);return {'reused':True,'media':n['images']}
        explicit=args.get('reference_node_ids')
        if explicit is not None and (not isinstance(explicit,list) or len(explicit)>20 or any(not isinstance(i,str) for i in explicit)):raise ValueError('参考卡片列表无效')
        refs,texts=refs_for(graph,n,explicit)
        if production_row and kind=='video' and production[0].get('video_mode')=='first_frame':
            # Select the actual frame as an anchor, not as an anonymous prop reference.
            args={**args,'first_frame_id':production_row['frame_id']}
        prompt=n.get('studioVideoPrompt') if kind=='video' and n.get('studioVideoPrepared') else '\n\n'.join([*texts,n.get('studioPrompt','')])
        if not prompt or not prompt.strip():raise ValueError('请先填写完整提示词')
        if n.get('studioIdentityParentId') and kind=='image':prompt='保持来源角色的同一脸型、五官、年龄与体态，只按用户要求改变服装或状态。\n'+prompt
        if args.get('first_frame_id'):
            p=copy.deepcopy(store.get('projects',pid));p.setdefault('model_bindings',{})[kind]=n.get('studioModel') or p.get('model_bindings',{}).get(kind)
            channel=providers.provider_for(p,kind,n.get('studioProvider') or None)
            if channel['protocol']=='json-video' and not channel.get('capabilities',{}).get('first_frame') and not channel.get('contract',{}).get('fields',{}).get('first_frame'):raise ValueError('当前通用视频渠道没有首帧字段映射，不能静默忽略首帧')
            chosen=[r for r in refs if r['node_id']==args['first_frame_id'] and r['kind']=='image']
            if len(chosen)!=1 or chosen[0]['image_purpose']=='character':raise ValueError('首帧须为已连接的一张镜头图')
            chosen[0]['role']='first_frame'
        payload={'prompt':prompt,'duration':n.get('studioDuration',8),'aspect_ratio':n.get('studioRatio','16:9'),'provider_id':n.get('studioProvider') or None,'model':n.get('studioModel') or None,'studio_node_id':n['id'],'studio_node_title':n['title'],'image_purpose':n.get('studioImagePurpose','shot'),'production_required':bool(production_row),'video_input_mode':production[0].get('video_mode') if production_row and kind=='video' else None,('images' if kind=='video' else 'reference_images'):refs}
        payload['images' if kind=='video' else 'reference_images']=[r for r in refs if r['kind']=='image']
        if kind=='video':
            payload.update(resolution=n.get('studioResolution') or '720p',generate_audio=n.get('studioGenerateAudio') is not False,watermark=bool(n.get('studioWatermark')))
            payload.update(audios=[r for r in refs if r['kind']=='audio'],videos=[r for r in refs if r['kind']=='video'])
        result=await yaoguang.media_task(pid,payload,kind,wait=False)
        latest=yaoguang.get_canvas(pid);out=get_node(latest,n['id']);out.pop('studioMcpReview',None);out.update(studioPendingTask=result['task_id'],studioLastTask=result['task_id'],studioTaskState=result['status'],studioError='');save_graph(pid,latest)
        return result
    raise ValueError('工具未实现')

@router.get('/status')
async def status_route():return status()
@router.get('/catalog')
@router.post('/catalog')
async def catalog_route():return {'version':'1.2.0','tools':TOOLS,'guide':mcp_workflow.GUIDE}
@router.post('/configure/{client}')
async def configure_route(client:str):
    try:return install_config(client)
    except (ValueError,OSError) as e:raise HTTPException(400,str(e))
@router.post('/session')
async def session_route(body:dict):
    client=body.get('client');ident=body.get('session_id')
    if client not in CLIENTS or not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{32}',ident) or not isinstance(body.get('pid'),int):raise HTTPException(400,'会话无效')
    with store.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS mcp_sessions(id TEXT PRIMARY KEY,body TEXT NOT NULL)')
        c.execute('INSERT OR REPLACE INTO mcp_sessions VALUES(?,?)',(ident,json.dumps({'id':ident,'client':client,'pid':body['pid'],'last_seen':time.time()})))
    return {'ok':True}
@router.get('/installer')
async def installer_route():
    from fastapi.responses import FileResponse
    path=store.ROOT/'downloads/Antigravity/Antigravity-x64-2.22.0.exe'
    if not path.is_file():raise HTTPException(404,'安装包尚未下载')
    return FileResponse(path,filename=path.name,media_type='application/octet-stream')
@router.post('/call')
async def call_route(body:dict):
    import asyncio
    args=body.get('arguments',{});pid=args.get('project_id','global') if isinstance(args,dict) else 'global'
    lock=LOCKS.setdefault(pid,asyncio.Lock())
    started=time.time();outcome='failed';result=None;error=None
    try:
        async with lock:result=await call_tool(body.get('name'),args)
        outcome='succeeded';return result
    except (ValueError,KeyError,TypeError,OSError) as e:
        error=str(e)[:1500];raise HTTPException(400,str(e))
    finally:
        # No prompt text, file contents, model settings or credentials in the audit.
        event={'at':store.now(),'client':body.get('client','local-api'),'tool':body.get('name'),'project_id':pid,'argument_keys':sorted(args) if isinstance(args,dict) else [],'outcome':outcome,'error':error,'duration_ms':round((time.time()-started)*1000),'task_id':result.get('task_id') if isinstance(result,dict) else None}
        with store.db() as c:
            c.execute('CREATE TABLE IF NOT EXISTS mcp_call_audit(id INTEGER PRIMARY KEY,body TEXT NOT NULL)')
            c.execute('INSERT INTO mcp_call_audit(body) VALUES(?)',(json.dumps(event,ensure_ascii=False),))
