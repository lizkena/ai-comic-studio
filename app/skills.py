import json
import copy
from pathlib import Path
from . import store
from .store import ROOT, uid

# Built-in skills remain available; explicit project bindings take precedence.
BUNDLED_DEFAULTS = {'script': 'yangzi-screenplay', 'assets': 'yangzi-lira-assets'}


def defaults():
    try: configured = store.get('settings', 'main').get('skill_defaults', {})
    except KeyError: configured = {}
    return {stage: configured.get(stage, BUNDLED_DEFAULTS.get(stage, stage)) for stage, _, _ in DEFINITIONS}

DEFINITIONS = [
 ('direction','定故事方向','得到一句话故事、主题、类型、核心冲突与梗概。冲突可落到明确人物的选择，保留用户约束。'),
 ('characters','定人物','为主角与配角设计目标、秘密、关系、变化。改编已有作品时从原文提取，引用来源，不擅自替换原人物。稳定身份与服装/年龄/状态版本分开。'),
 ('world','定世界规则','整理地点、组织、世界规则、关键物件。普通现实题材保持简洁，不增加无必要设定。'),
 ('novel','分章小说','先规划章节，再写正文、章节摘要、伏笔与角色状态。current 仅生成当前集所需章节；full 按项目章节数量生成。局部重写仅返回指定章节，保留原 ID。避免反复介绍前文。'),
 ('scene_plan','拆成每一场戏','从故事或小说拆出分场大纲，为每场给出地点、目标、冲突、转折和时长预算，记录来源章节。保留事件顺序与人物动机。这里只制定场次计划，专业剧本阶段再写完整动作、对白、声音与转场。'),
 ('script','分场与专业剧本','先拆分每场目标、冲突、转折、时长预算，再整理标准场景标题、内外景、时间、动作、人物、对白、声音、转场。可接管作者原剧本。记录来源章节 ID。总时长服从项目单集预算。'),
 ('assets','图像资产','按项目视觉风格和角色版本，制作角色、场景、道具图。构图与服装明确、空间稳定，禁止把不同版本人物混作同一版本。'),
 ('performance','设计表演','把抽象情绪转化为呼吸、眼神、重心、手部、节拍、潜台词。场次 ID、角色 ID 必须引用输入，台词不随意改写。'),
 ('storyboard','拆镜头与写提示词','输出视频小节与小节内镜号，持续引用稳定角色、场景、道具和集/场次 ID。将表演设计写入动作。按目标 H3 / Seedance 编译提示词与连续性表。小节可以多镜号；时序从0连续到总时长。开启关系镜时末约1秒安排中全景站位镜，包含于原时长。切场、闪回断开衔接。不要虚构素材 ID。')]


def initialize():
    for stage, name, instruction in DEFINITIONS:
        folder = ROOT / 'skills' / stage; folder.mkdir(parents=True, exist_ok=True)
        source = folder / 'SKILL.md'; config = folder / 'adapter.json'
        if not source.exists(): source.write_text(f'---\nname: {stage}\ndescription: {name}\n---\n\n# {name}\n\n{instruction}\n', encoding='utf-8')
        if not config.exists(): config.write_text(json.dumps({'id':stage,'name':name,'stage':stage,'version':'1.0.0','availability':'完整可用','tools':['image_api'] if stage=='assets' else ['text_api'],'input':'项目设定与前序结构化对象','output':'图像文件' if stage=='assets' else '本阶段 JSON 结构'}, ensure_ascii=False, indent=2), encoding='utf-8')


def list_skills():
    rows=[]; selected=defaults()
    for f in (ROOT / 'skills').glob('*/adapter.json'):
        item=json.loads(f.read_text(encoding='utf8')); item['content']=(f.parent/'SKILL.md').read_text(encoding='utf8')
        item['is_default']=selected.get(item['stage'])==item['id']; rows.append(item)
    from . import skill_dispatch
    for module in skill_dispatch.modules():
        folder=module.pop('folder')
        rows.append({**module,'role':'supplement','stage':'supplement','availability':'仅指令可用',
                     'is_default':False,'tools':['text_api'],'input':'当前镜头与项目设定','output':'专业方法补充；保持原阶段输出格式',
                     'content':((folder/'README.md').read_text(encoding='utf-8')+'\n\n' if (folder/'README.md').exists() else '')+(folder/'SKILL.md').read_text(encoding='utf-8')})
    return rows


def load(stage, ident=None):
    found=next((s for s in list_skills() if s['id']==(ident or defaults().get(stage,stage)) and s['stage']==stage),None)
    if not found: raise ValueError('找不到本阶段可用 Skill')
    if found['availability']=='缺少工具': raise ValueError('Skill 缺少工具，不能执行')
    return found


def set_default(stage, ident):
    selected=load(stage,ident)
    # Merge inside the transaction so changing a skill cannot overwrite API keys.
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT body FROM settings WHERE id=?',('main',)).fetchone()
        value=json.loads(row['body']) if row else {'id':'main','providers':[]}
        value.setdefault('skill_defaults',{})[stage]=selected['id']
        c.execute('INSERT OR REPLACE INTO settings(id,body) VALUES(?,?)',('main',json.dumps(value,ensure_ascii=False)))
    return {'defaults':defaults(),'skills':list_skills()}


def for_job(job, stage):
    """Resolve saved instructions rather than changing a running/retried job."""
    from .creation import genre_instruction, genre_label

    pinned=job.get('skill_snapshots',{}).get(stage)
    skill=copy.deepcopy(pinned) if pinned else load(stage,job.get('source_snapshot',{}).get('bindings',{}).get('skill_'+stage))

    # 项目题材指引：注入快照与实时解析两条路径（题材随 revision 变化使任务缓存失效）
    project_id=job.get('project_id')
    if project_id:
        try: genre_id=store.get('projects',project_id).get('settings',{}).get('genre_preset','')
        except Exception: genre_id=''
        if genre_id and genre_id != 'custom':
            hint=genre_instruction(genre_id)
            if hint:
                skill=copy.deepcopy(skill)
                skill['content']=f'【当前题材：{genre_label(genre_id)}】\n{hint}\n\n'+skill['content']
    return skill


def import_skill(payload):
    if payload.get('stage') not in {x[0] for x in DEFINITIONS}: raise ValueError('请选择可适配阶段')
    content=payload.get('content','')
    if not content.strip(): raise ValueError('SKILL.md 为空')
    ident=uid('skill'); folder=ROOT/'skills'/ident; folder.mkdir()
    (folder/'SKILL.md').write_text(content,encoding='utf8')
    tools=payload.get('tools',[])
    config={'id':ident,'name':payload.get('name','导入 Skill'),'stage':payload['stage'],'version':'1.0.0',
            'availability':'缺少工具' if tools else '仅指令可用','tools':tools,'input':'项目上下文','output':'本阶段 JSON 结构'}
    (folder/'adapter.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')
    return config


initialize()
