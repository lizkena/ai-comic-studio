"""Chapter-based production. AI results are explicit drafts; IDs and media survive edits."""
import copy
import json
import re
import math
from fastapi import APIRouter
from . import store, domain, providers, skills, creation, asset_visuals, director_prompts, character_coverage

router = APIRouter(prefix='/api/projects', tags=['production-workflow'])
SETUP = {'genre': '题材', 'era': '时代', 'region': '地域', 'visual_style': '视觉风格',
         'synopsis': '故事梗概', 'cinematography': {'camera': '摄影机在场方式', 'lens': '机身与镜头组',
         'depth': '景深策略', 'lighting': '光的哲学', 'color': '色彩体系', 'texture': '质感',
         'reference': '参考气质', 'negative': '禁令'},
         'characters': [{'name': '人物', 'role': '角色类型', 'description': '视觉形象', 'tags': '核心标签',
         'background': '身份背景', 'history': '成长经历', 'personality': '性格特点', 'goal': '当前目标',
         'relationships': '角色关系', 'arc': '成长弧线', 'catchphrase': '口头禅'}]}
SCHEMAS = {
    'wf_canvas_text': {'text': '画布文本节点的完整输出；需要 JSON 内容时也放在 text 字符串中'},
    'wf_story': {'story': '根据灵感写的故事正文'}, 'wf_setup': SETUP,
    'wf_continue': {'chapter': {'title': '续写章节标题', 'content': '新增小说正文', 'summary': '章节大纲'}},
    'wf_chapters': {'chapters': [{'id': '已有章节ID；首次分章可留空', 'title': '章名', 'summary': '章节大纲', 'start_block': '首次分章时填写输入块ID；已有章节整理大纲时留空'}]},
    'wf_script': domain.SCHEMAS['script'],
    'wf_breakdown': {'assets': [{'key': '结果内唯一引用键', 'kind': 'character/location/prop', 'name': '资产名称', 'description': '外貌/空间/道具描述'}],
        'segments': [{'id': '已有镜头ID或留空', 'title': '镜头标题', 'scene_id': '当前剧本场次ID', 'duration': 8, 'transition': 'auto/continue/cut；回忆、跳时空或换场使用cut',
        'character_keys': [], 'location_key': '场景引用键', 'prop_keys': [], 'purpose': '叙事目的', 'emotion': '情绪',
        'shots': [{'start': 0, 'end': 8, 'size': '中景', 'camera': '固定', 'action': '画面与动作', 'dialogue': '角色:对白', 'sound': '声音'}]}]},
    'wf_prompts': {'prompts': [{'id': '输入目标ID', 'image_prompt': '静态生图提示词'}]},
    'wf_video_prompt': {'prompt': '保留镜头事实与对白的视频描述'}
}
RULES = {
    'wf_canvas_text': ('storyboard', '仅处理画布当前文本节点的明确任务，返回 text。保留用户指定的分隔符与输出格式。不要自动生成资产、图片或视频，不补造已生成媒体。项目创作规则与当前用户要求优先。'),
    'wf_story': ('direction', '只把标题、关键词或简介发展为一段完整故事正文。保留用户题材与要求。不要生成剧本或分镜。'),
    'wf_setup': ('direction', '从输入小说或故事分析题材、时代、地域、视觉风格、影像风格、梗概和主要人物。题材和视觉风格遵循用户在settings中选择的类型与画风，可补充相容的细分特征。人物信息提取自原文，未知时写未交代，不虚构作者事实。影像风格须涵盖摄影、镜头、景深、光、色彩、质感、参考气质和禁令。'),
    'wf_continue': ('novel', '仅续写一个新章节，承接现有正文、人物状态和设定。不重写或重复原文。'),
    'wf_chapters': ('novel', '仅做章节切分和大纲总结，不输出content，不复制小说正文。mode=outline_existing时保留全部已有章节id和顺序，只返回每章title、summary，start_block留空。mode=split_blocks时用输入blocks的ID指定每章start_block，首章从第一个块开始，后续起点严格递增；正文由本地按起点切分，禁止改写。尊重原章标题，大纲说明本章事件、转折和结尾钩子。'),
    'wf_script': ('script', '仅生成指定chapter对应的一集剧本。根据正文和章节大纲，受全局设定约束。必须只返回一个episode，source_chapters使用输入chapter.id。保留人物、顺序和对白事实，动作、声音可拍摄。'),
    'wf_breakdown': ('storyboard', '仅拆分指定一集的剧本，并提取其中出镜的角色、场景、道具。资产key唯一，可以直接使用已有资产ID。禁止创建未出镜资产。每个segment必须引用本集scene_id，引用assets的key或已有资产ID，location_key必填。小节内shots从0连续到duration。不生成提示词、图片或视频。'),
    'wf_prompts': ('storyboard', '仅为输入targets写提示词，保留每个id，全部目标必须覆盖。image_prompt描述静态画面构图、人物服装外形、景别、光色和风格；只生成静态生图提示词，不生成或修改视频提示词。视频描述由 wf_video_prompt 单独生成。角色资产用人物设定/多视图描述，场景与道具各用对应描述。不要改变资产关联或分镜事实。'),
    'wf_video_prompt': ('storyboard', '仅完善当前镜头的视频描述，保留角色、场景、道具、动作、时长和对白。视频不是静态图片描述，需明确时序与运镜。')
}


def ensure(project):
    p = copy.deepcopy(project)
    outputs = p.setdefault('outputs', {})
    old = outputs.get('direction', {})
    outputs.setdefault('production_setup', {'genre': p['settings'].get('genre', ''), 'era': '', 'region': '',
        'visual_style': p['settings'].get('style', ''), 'synopsis': old.get('synopsis', ''),
        'cinematography': {k: '' for k in SETUP['cinematography']},
        'characters': copy.deepcopy(outputs.get('characters', {}).get('characters', []))})
    outputs['production_setup'].setdefault('cinematography', {k: '' for k in SETUP['cinematography']})
    outputs['production_setup'].setdefault('characters', [])
    novel = outputs.get('novel')
    if novel:
        for index, chapter in enumerate(novel.get('chapters', [])):
            chapter.setdefault('id', store.uid('chapter'))
            if not chapter.get('summary') and index < len(novel.get('outline', [])):
                chapter['summary'] = novel['outline'][index].get('summary', '')
    return p


def chapters(p): return p.get('outputs', {}).get('novel', {}).get('chapters', [])
def episode(p, ident): return next((e for e in p['outputs'].get('script', {}).get('episodes', []) if e['id'] == ident), None)
def chapter(p, ident): return next((c for c in chapters(p) if c['id'] == ident), None)
def fulltext(p): return '\n\n'.join(c.get('content', '') for c in chapters(p)) or (p.get('source', '') if p['entry'] == 'novel' else p['outputs'].get('direction', {}).get('synopsis', ''))
def ep_for(p, c): return next((e for e in p['outputs'].get('script', {}).get('episodes', []) if c['id'] in e.get('source_chapters', []) or any(c['id'] in s.get('source_chapters', []) for s in e.get('scenes', []))), None)


def timing_contract(p):
    settings=p.get('settings',{})
    instruction=settings.get('split_instruction','') or ''
    limits=re.findall(r'(?:单镜(?:头)?|每(?:个)?(?:镜头|小节|分镜)|每镜)[^。；\n]{0,18}?(?:不超过|最多|上限(?:为)?|≤|<=)\s*(\d+(?:\.\d+)?)\s*秒',instruction)
    ranges=re.findall(r'(?:单镜(?:头)?|每(?:个)?(?:镜头|小节|分镜)|每镜)[^。；\n]{0,12}?(\d+(?:\.\d+)?)\s*[-–—~～至]\s*(\d+(?:\.\d+)?)\s*秒',instruction)
    maximum=min([float(x) for x in limits]+[float(hi) for lo,hi in ranges],default=None)
    minimum=max([float(lo) for lo,hi in ranges],default=None)
    if maximum is not None and maximum<=0: raise ValueError('单镜时长上限必须为正数')
    if minimum is not None and (minimum<=0 or minimum>maximum): raise ValueError('单镜时长范围无效')
    profile = p.get('_storyboard_skill_profile')
    if profile is None:
        profile = skills.load('storyboard', p.get('bindings', {}).get('skill_storyboard'))
    fixed = profile.get('segment_duration')
    # Explicit project limits take precedence over a skill's default profile.
    if fixed and maximum is None and minimum is None:
        maximum = minimum = float(fixed)
    return {'total_duration_mode':'auto','max_segment_duration':maximum,'min_segment_duration':minimum,'split_instruction':instruction}


def source_blocks(source):
    """Stable paragraph/sentence blocks. Joining them always reproduces the source."""
    pieces = []
    for line in source.splitlines(keepends=True):
        while len(line) > 1600:
            cut = max((line.rfind(mark, 500, 1600) + 1 for mark in ('。', '！', '？', '；')), default=0)
            if cut < 500: cut = 1600
            pieces.append(line[:cut]); line = line[cut:]
        if line: pieces.append(line)
    return [{'id': 'block_' + str(i+1).zfill(6), 'text': text} for i, text in enumerate(pieces)]


PROP_POLICY = ('独立道具只提取实际出镜、需要单独保持外观一致的关键物件：剧情关键物、证据、'
    '特写对象、持续持有或交接、损坏变化、触发机关的物件。普通桌椅板凳、柜子、门窗、床铺、'
    '常规餐具等环境陈设默认写入场景资产description，不逐件创建prop，不因人物坐下或经过就单建资产。'
    '若普通物件确实承担关键剧情或特写，仍可作为独立道具。保留原剧本动作、对白及陈设事实，'
    '只减少独立资产拆分，不删剧情；优先复用已有资产ID，不重复创建。assets仅包含segments实际引用的资产。')


def context(p, stage, target=None, options=None):
    p = ensure(p); options = options or {}
    setup = p['outputs']['production_setup']
    settings = copy.deepcopy(p['settings'])
    settings.pop('episode_duration', None)  # Legacy field must not influence new planning.
    base = {'settings': settings, 'setup': setup}
    if stage == 'wf_breakdown':
        base['asset_extraction_policy'] = PROP_POLICY
        base['character_extraction_policy'] = ('逐一核对原剧本dialogue.character与镜头对白说话人。实际人物即使无姓名、'
            '只出现一次或不在主要人物设定中，也必须创建或复用角色资产并加入对应镜头character_keys，例如灰袍医修、店小二。'
            '对白使用与角色资产完全一致的称呼；保留旁白、系统提示等非实体声音，但不把这些声音创建为出镜人物。'
            '明确人物的画外音仍关联该人物，不擅自让其入画。外貌只写原文明确信息，未知年龄、性别与身份不得编造。')
    if stage == 'wf_video_prompt' or stage == 'wf_canvas_text' and options.get('canvas_task') == 'video_prompt':
        from . import providers, seedance
        selected=copy.deepcopy(p)
        if options.get('canvas_video_model'): selected.setdefault('model_bindings',{})['video']=options['canvas_video_model']
        if options.get('canvas_video_provider') or selected.get('bindings',{}).get('video'):
            provider=providers.provider_for(selected,'video',options.get('canvas_video_provider'))
            base['target_video_model']=seedance.context(provider)
            base['settings']['target_video']=provider['model']
            base['target_video_options']=copy.deepcopy(options.get('canvas_video_options',{}))
    if stage == 'wf_canvas_text':
        message=options.get('canvas_message')
        if not isinstance(message,str) or not message.strip() or len(message)>100000: raise ValueError('画布文本输入无效')
        base.update(text=message,canvas_instruction=options.get('canvas_instruction',''),canvas_node_id=options.get('canvas_node_id',''))
    elif stage == 'wf_story':
        if p['entry'] != 'idea': raise ValueError('已有小说或剧本应分析原文，不必再生成故事')
        if p['segments'] or p['outputs'].get('script', {}).get('episodes'): raise ValueError('已有剧本或分镜，请新建作品创作另一段故事')
        base['idea'] = p['source']
    elif stage == 'wf_setup':
        script = p['outputs'].get('script', {})
        source = fulltext(p) or script.get('original_text') or (json.dumps(script, ensure_ascii=False) if script.get('episodes') else '')
        if not source.strip(): raise ValueError('请先导入小说或生成故事正文')
        # Setup uses a disclosed representative sample for very long works; chapter scripts use exact chapter text.
        base['text'] = source if len(source) <= 100000 else source[:70000] + '\n[中段省略，以下为结尾摘录]\n' + source[-30000:]
        base['sampled'] = len(source) > 100000
    elif stage == 'wf_continue':
        if p['entry'] != 'idea': raise ValueError('导入小说保留作者原文，续写请使用灵感创作入口')
        if not setup.get('synopsis'): raise ValueError('请先完成剧本设定分析')
        base['chapters'] = chapters(p)[-3:]; base['story'] = fulltext(p)[-60000:]
    elif stage == 'wf_chapters':
        if target:
            selected = chapter(p, target)
            if not selected or not selected.get('content', '').strip(): raise ValueError('请选择有正文的小说章节')
            if len(selected['content']) > 100000: raise ValueError('本章正文超过10万字，请先拆分为较小章节')
            base.update(mode='outline_existing', existing_chapters=[{k: selected.get(k, '') for k in ('id', 'title', 'content', 'summary')}])
            return base
        text = fulltext(p)
        if not text.strip(): raise ValueError('请先准备小说正文')
        if len(text) > 100000: raise ValueError('正文较长，请先使用按原文章标题拆分，再逐章编辑大纲；原文会完整保留')
        existing = chapters(p)
        if len(existing) > 1:
            # Return outlines only. Re-emitting the whole novel wastes the output
            # budget and can corrupt quotes or truncate the last chapter.
            base.update(mode='outline_existing', existing_chapters=[{k: c.get(k, '') for k in ('id', 'title', 'content', 'summary')} for c in existing])
        else:
            base.update(mode='split_blocks', blocks=source_blocks(text), existing_chapters=[{k: c.get(k, '') for k in ('id', 'title')} for c in existing])
    elif stage == 'wf_script':
        c = chapter(p, target)
        if not c or not c.get('content', '').strip(): raise ValueError('请选择有正文的小说章节')
        if not c.get('summary', '').strip(): raise ValueError('请先整理或填写这一章的章节大纲')
        base['chapter'] = c
        base['character_facts']=p['outputs'].get('characters',{})
        base['world_facts']=p['outputs'].get('world',{})
        plan=p['outputs'].get('scene_plan',{})
        if plan:
            plan=copy.deepcopy(plan)
            plan['episodes']=[ep for ep in plan.get('episodes',[]) if c['id'] in ep.get('source_chapters',[]) or any(c['id'] in s.get('source_chapters',[]) for s in ep.get('scenes',[]))]
            if plan['episodes']:
                base['confirmed_scene_plan' if p.get('stage_status',{}).get('scene_plan')=='confirmed' else 'reference_scene_plan']=plan
    elif stage == 'wf_breakdown':
        ep = episode(p, target)
        if not ep or not ep.get('scenes'): raise ValueError('请先生成或编辑当前集的剧本')
        ep = copy.deepcopy(ep)
        ep.pop('duration', None)
        for scene in ep['scenes']: scene.pop('duration', None)
        base.update(episode=ep, assets=[{k: a.get(k) for k in ('id', 'kind', 'name', 'description')} for a in p['assets']],
                    segments=[{k:s.get(k) for k in ('id','title','scene_id','purpose','character_ids','location_id','prop_ids')} for s in p['segments'] if s.get('episode_id') == target],
                    timing_contract=timing_contract(p))
    elif stage == 'wf_prompts':
        ids = options.get('target_ids', [])
        if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids): raise ValueError('请选择需要生成提示词的镜头或资产')
        objects = p['assets'] + p['segments']
        if any(not any(x['id'] == ident for x in objects) for ident in ids): raise ValueError('提示词目标不存在')
        if any(x['id'] in ids and x.get('continuity') for x in p['segments']): raise ValueError('衔接尾帧镜头无需生图提示词，请选择其他镜头')
        base['targets'] = [{k: v for k, v in x.items() if k not in ('versions', 'images', 'references')} for x in objects if x['id'] in ids]
        base['assets'] = [{k: a.get(k) for k in ('id', 'kind', 'name', 'description')} for a in p['assets']]
        related = [s for s in p['segments'] if s['id'] in ids or set(ids).intersection(
            s.get('character_ids', []) + s.get('prop_ids', []) + [s.get('location_id')])]
        episode_ids = {s.get('episode_id') for s in related}
        for obj in base['targets']: episode_ids.update(obj.get('episode_ids', []))
        base['source_script'] = [copy.deepcopy(ep) for ep in p['outputs'].get('script', {}).get('episodes', []) if ep['id'] in episode_ids]
        base['source_storyboard'] = [{k: copy.deepcopy(v) for k,v in s.items() if k not in ('images','versions','prompt','image_prompt')} for s in related]
    elif stage == 'wf_video_prompt':
        seg = next((s for s in p['segments'] if s['id'] == target), None)
        if not seg: raise ValueError('请选择镜头')
        base['segment'] = {k: v for k, v in seg.items() if k not in ('images', 'versions')}
        base['target_video_options'] = copy.deepcopy(seg.get('video_options',{}))
        base['assets'] = [a for a in p['assets'] if a['id'] in seg.get('character_ids', []) + seg.get('prop_ids', []) + [seg.get('location_id')]]
    return base


def scope_value(p, stage, target, options):
    """Granular conflict check: another episode may be edited while this draft is generated."""
    ctx = context(p, stage, target, options)
    if stage == 'wf_prompts': return {k:ctx[k] for k in ('targets','setup','assets','source_script','source_storyboard')}
    if stage == 'wf_breakdown': return {'episode':ctx['episode'],'segments':[s for s in p['segments'] if s.get('episode_id')==target],'setup':ctx['setup'],'timing_contract':ctx['timing_contract']}
    if stage == 'wf_script': return {**ctx, 'existing_episode': ep_for(p, chapter(p, target))}
    if stage == 'wf_story': return {**ctx, 'existing_novel': p['outputs'].get('novel')}
    return ctx


def text(value, key):
    if not isinstance(value.get(key), str) or not value[key].strip(): raise ValueError('模型缺少文本：' + key)
    return value[key].strip()


def split_generation_units(segments, contract):
    """Partition complete shot timelines; never stretch actions or duplicate dialogue."""
    maximum = contract['max_segment_duration']
    minimum = contract['min_segment_duration'] or 0
    if maximum is None: return segments
    output = []
    for seg in segments:
        duration = float(seg.get('duration', 0))
        if duration <= maximum + .001:
            output.append(seg); continue
        shots = seg.get('shots', [])
        cursor = 0
        for sh in shots:
            start, end = float(sh['start']), float(sh['end'])
            if not all(math.isfinite(x) for x in (start, end)) or abs(start-cursor) > .001 or end <= start:
                raise ValueError('长分镜的镜号时间必须连续，不能自动补齐或重叠')
            if end-start > maximum+.001:
                raise ValueError(f'内部镜号超过单镜上限 {maximum:g} 秒，需要重新规划动作与对白')
            cursor = end
        if not shots or abs(cursor-duration) > .001:
            raise ValueError('长分镜的镜号时间必须完整覆盖小节时长')
        # Find a partition satisfying both bounds, avoiding a too-short tail.
        paths = {len(shots): []}
        for i in range(len(shots)-1, -1, -1):
            for j in range(i+1, len(shots)+1):
                span = float(shots[j-1]['end'])-float(shots[i]['start'])
                if span > maximum+.001: break
                if span >= minimum-.001 and j in paths: paths[i] = [(i,j)] + paths[j]
        if 0 not in paths: raise ValueError('内部镜号无法在保留对白的同时满足单镜时长范围，请重新规划')
        # Explicit edited dialogue is authoritative and cannot safely be repartitioned here.
        if seg.get('dialogue_text') is not None:
            raise ValueError('长分镜含独立编辑的台词时间轴，请重新规划后拆分')
        for number, (i,j) in enumerate(paths[0], 1):
            part = copy.deepcopy(seg); part.pop('id', None)
            start = float(shots[i]['start'])
            part['duration'] = round(float(shots[j-1]['end'])-start, 6)
            part['title'] = f"{seg['title']} · {number:02d}"
            part['transition'] = seg.get('transition', 'auto') if number == 1 else 'continue'
            part['shots'] = copy.deepcopy(shots[i:j])
            for sh in part['shots']:
                sh['start'] = round(float(sh['start'])-start, 6)
                sh['end'] = round(float(sh['end'])-start, 6)
            output.append(part)
    return output


def normalize(p, stage, result, target, options):
    if not isinstance(result, dict): raise ValueError('模型输出必须是 JSON 对象')
    value = copy.deepcopy(result)
    if stage == 'wf_canvas_text':
        if options.get('canvas_task') == 'video_prompt' and '结束状态' not in text(value, 'text'):
            raise ValueError('视频编译缺少结束状态；请依据已有动作明确镜头结束时的位置、朝向/视线、持物与动作余势，不编造新事件')
        value['text'] = director_prompts.finalize_canvas(text(value, 'text'), options or {})
    elif stage == 'wf_story': text(value, 'story')
    elif stage == 'wf_setup':
        for key in ('genre', 'era', 'region', 'visual_style', 'synopsis'): text(value, key)
        if not isinstance(value.get('cinematography'), dict): raise ValueError('模型缺少影像风格')
        for key in SETUP['cinematography']: text(value['cinematography'], key)
        if not isinstance(value.get('characters'), list) or not value['characters']: raise ValueError('模型缺少主要人物')
        names = []
        for item in value['characters']:
            if not isinstance(item, dict): raise ValueError('人物条目必须为对象')
            names.append(text(item, 'name')); text(item, 'description')
        if len(set(names)) != len(names): raise ValueError('人物名称重复')
    elif stage == 'wf_continue':
        c = value.get('chapter')
        if not isinstance(c, dict): raise ValueError('模型缺少续写章节')
        for key in ('title', 'content', 'summary'): text(c, key)
        c['id'] = store.uid('chapter')
    elif stage == 'wf_chapters':
        items = value.get('chapters')
        if not isinstance(items, list) or not items: raise ValueError('模型缺少章节')
        if target:
            previous = chapter(p, target)
            if not previous or len(items) != 1 or not isinstance(items[0], dict) or items[0].get('id') != target:
                raise ValueError('章节大纲必须只返回指定章节，保持ID不变')
            incoming = items[0]
            text(incoming, 'summary')
            if 'content' in incoming and incoming['content'] != previous['content']:
                raise ValueError('整理大纲禁止改写章节正文')
            value['chapters'] = [dict(copy.deepcopy(previous), summary=incoming['summary'])]
            return value
        if all(isinstance(c, dict) and 'content' not in c for c in items):
            old = chapters(p)
            incoming_ids = [c.get('id') for c in items]
            old_ids = [c['id'] for c in old]
            if old and len(items) == len(old) and all(isinstance(ident, str) for ident in incoming_ids) and set(incoming_ids) == set(old_ids):
                # Outline responses may be sorted by the model. Resolve by ID
                # and retain the author's order, text, titles and metadata.
                by_id = {c['id']: c for c in items}
                ordered = []
                for previous in old:
                    incoming = by_id[previous['id']]
                    text(incoming, 'summary')
                    ordered.append(dict(copy.deepcopy(previous), summary=incoming['summary']))
                value['chapters'] = ordered
                return value
            elif len(old) > 1:
                raise ValueError('章节大纲必须覆盖全部已有章节，保持ID和顺序；原文未改变')
            else:
                blocks = source_blocks(fulltext(p)); positions = {b['id']: i for i, b in enumerate(blocks)}
                starts = [positions.get(c.get('start_block')) for c in items]
                if not starts or starts[0] != 0 or any(x is None for x in starts) or starts != sorted(set(starts)):
                    raise ValueError('分章起点必须来自原文块，首章从第一个块开始，后续起点严格递增')
                for i, c in enumerate(items):
                    end = starts[i+1] if i+1 < len(items) else len(blocks)
                    c['content'] = ''.join(b['text'] for b in blocks[starts[i]:end])
        for c in items:
            if not isinstance(c, dict): raise ValueError('章节条目必须为对象')
            for key in ('title', 'summary', 'content'): text(c, key)
        if re.sub(r'\s+', '', ''.join(c['content'] for c in items)) != re.sub(r'\s+', '', fulltext(p)):
            raise ValueError('章节拆分改变或遗漏了原文，请修正，禁止改写正文')
        old = chapters(p); used = set()
        for i, c in enumerate(items):
            match = next((x for x in old if x['id'] == c.get('id') or x.get('content') == c['content']), None)
            c['id'] = match['id'] if match else store.uid('chapter')
            if c['id'] in used: raise ValueError('章节 ID 重复')
            used.add(c['id'])
    elif stage == 'wf_script':
        c = chapter(p, target); normalized = domain.normalize('script', value, p)
        if len(normalized['episodes']) != 1: raise ValueError('仅允许生成当前章节的一集剧本')
        ep = normalized['episodes'][0]; old = ep_for(p, c)
        ep['id'] = old['id'] if old else 'episode_' + c['id'].removeprefix('chapter_')
        ep['source_chapters'] = [c['id']]
        for sc in ep['scenes']:
            text(sc, 'location'); text(sc, 'action')
            if not isinstance(sc.get('dialogue', []), list) or any(not isinstance(d, dict) or not isinstance(d.get('character'), str) or not isinstance(d.get('text'), str) for d in sc.get('dialogue', [])): raise ValueError('剧本对白格式无效')
            sc['source_chapters'] = [c['id']]
            matches = [s for s in (old or {}).get('scenes', [])
                       if s.get('title') == sc.get('title') and s.get('location') == sc.get('location')]
            if len(matches) == 1 and sum(s.get('title') == sc.get('title') and s.get('location') == sc.get('location') for s in ep['scenes']) == 1:
                sc['id'] = matches[0]['id']
        value = normalized
    elif stage == 'wf_breakdown':
        ep = episode(p, target); scene_ids = {s['id'] for s in ep['scenes']}
        if not isinstance(value.get('assets'), list) or not isinstance(value.get('segments'), list) or not value['segments']: raise ValueError('模型缺少分镜或出镜资产')
        original_count = len(value['segments'])
        value['segments'] = split_generation_units(value['segments'], timing_contract(p))
        if len(value['segments']) != original_count:
            value['timing_split'] = {'original_count': original_count, 'final_count': len(value['segments'])}
        existing = {a['id']: copy.deepcopy(a) for a in p['assets']}; mapping = {k: k for k in existing}; incoming = []; keys = set()
        for a in value['assets']:
            if not isinstance(a, dict) or a.get('kind') not in ('character', 'location', 'prop'): raise ValueError('出镜资产类型无效')
            key = text(a, 'key'); name = text(a, 'name'); text(a, 'description')
            if key in keys: raise ValueError('出镜资产引用键重复')
            keys.add(key)
            previous = next((x for x in p['assets'] if x['kind'] == a['kind'] and x['name'] == name), None)
            ident = previous['id'] if previous else store.uid(a['kind']); mapping[key] = ident
            asset = copy.deepcopy(previous) if previous else {'id': ident, 'kind': a['kind'], 'name': name, 'description': a['description'], 'references': [], 'version': 1, 'status': 'draft'}
            asset['episode_ids'] = list(dict.fromkeys(asset.get('episode_ids', []) + [target]))
            if a['kind'] == 'character' and not asset.get('variants'): asset['variants'] = [{'id': store.uid('variant'), 'name': '默认服装', 'description': ''}]
            existing[ident] = asset
            if not any(x['id'] == ident for x in incoming): incoming.append(asset)
        def ref(key, kind):
            aid = mapping.get(key)
            if not aid or existing[aid]['kind'] != kind: raise ValueError('分镜资产引用无效：' + str(key))
            return aid
        old_segments = {s['id']: s for s in p['segments'] if s.get('episode_id') == target}
        ids = set()
        for seg in value['segments']:
            if not isinstance(seg, dict): raise ValueError('分镜条目必须为对象')
            if seg.get('scene_id') not in scene_ids: raise ValueError('分镜必须引用当前集的剧本场次')
            text(seg, 'title')
            if not math.isfinite(float(seg.get('duration', 0))): raise ValueError('分镜时长必须是有限数值')
            for sh in seg.get('shots', []):
                if not isinstance(sh, dict) or not all(math.isfinite(float(sh.get(k, 0))) for k in ('start', 'end')): raise ValueError('镜号时间格式无效')
            old = old_segments.get(seg.get('id'))
            seg['id'] = old['id'] if old else store.uid('segment')
            if seg['id'] in ids: raise ValueError('分镜 ID 重复')
            ids.add(seg['id']); seg['episode_id'] = target
            seg['character_ids'] = [ref(x, 'character') for x in seg.pop('character_keys', [])]
            seg['location_id'] = ref(seg.pop('location_key', ''), 'location')
            seg['prop_ids'] = [ref(x, 'prop') for x in seg.pop('prop_keys', [])]
            seg['variant_ids'] = [existing[x]['variants'][0]['id'] for x in seg['character_ids']]
            previous = value['segments'][value['segments'].index(seg)-1] if value['segments'].index(seg) else None
            same_scene = previous and previous.get('scene_id') == seg.get('scene_id') and previous.get('location_id') == seg.get('location_id')
            transition = seg.get('transition', 'auto')
            if transition not in ('auto', 'continue', 'cut'): raise ValueError('镜头转场须为 auto、continue 或 cut')
            chained = bool(previous)
            seg.update(previous_id=previous['id'] if chained else None,
                continuity=chained, tail_shot=False, prompt='', image_prompt='',
                versions=copy.deepcopy(old.get('versions', [])) if old else [], current_version=old.get('current_version') if old else None,
                images=copy.deepcopy(old.get('images', [])) if old else [], current_image=old.get('current_image') if old else None,
                status='stale' if old and old.get('versions') else 'draft', input_mode='shot_image')
        contract=timing_contract(p)
        for seg in value['segments']:
            scene = next(s for s in ep['scenes'] if s['id'] == seg['scene_id'])
            missing = character_coverage.missing_speakers(seg, existing.values(), scene)
            if missing: raise ValueError('说话角色缺少资产或镜头关联：' + '、'.join(missing) + '；镜头：' + seg['title'] + '。请补全角色资产与character_keys，保留原对白')
            duration=float(seg['duration']);maximum=contract['max_segment_duration'];minimum=contract['min_segment_duration']
            if maximum is not None and duration>maximum+.001: raise ValueError(f"分镜「{seg['title']}」为 {duration:g} 秒，超过用户设置的单镜上限 {maximum:g} 秒，请拆分")
            if minimum is not None and duration<minimum-.001: raise ValueError(f"分镜「{seg['title']}」短于用户设置的单镜下限 {minimum:g} 秒")
        test = copy.deepcopy(p); test['assets'] = list(existing.values()); test['segments'] = value['segments']
        errors = [x['message'] for x in domain.checks(test, {}, 'storyboard') if x['severity'] == 'error']
        if errors: raise ValueError('分镜结构校验失败：' + '；'.join(errors))
        used_assets = {ident for seg in value['segments'] for ident in
            seg['character_ids'] + seg['prop_ids'] + [seg['location_id']]}
        value['assets'] = [asset for asset in incoming if asset['id'] in used_assets]
    elif stage == 'wf_prompts':
        items = value.get('prompts', []); ids = options['target_ids']
        received = [x.get('id') for x in items if isinstance(x, dict)] if isinstance(items, list) else []
        if not isinstance(items, list) or len(items) != len(ids) or set(received) != set(ids):
            missing = [ident for ident in ids if ident not in received]
            extra = [str(ident) for ident in received if ident not in ids]
            duplicates = [str(ident) for i, ident in enumerate(received) if ident in received[:i]]
            detail = []
            if missing: detail.append('缺少目标：' + '、'.join(missing))
            if extra: detail.append('未指定目标：' + '、'.join(extra))
            if duplicates: detail.append('重复目标：' + '、'.join(duplicates))
            raise ValueError('提示词必须覆盖全部指定目标且 ID 一致；' + '；'.join(detail or ['prompts 必须为目标列表']))
        for x in items:
            text(x, 'image_prompt')
            obj=next(t for t in p['assets']+p['segments'] if t['id']==x['id'])
            x['image_prompt']=asset_visuals.enforce(x['image_prompt'],obj)
            x.pop('video_prompt', None)
    elif stage == 'wf_video_prompt': text(value, 'prompt')
    return value


def merge_breakdown_batches(batches):
    """Batch-local keys may collide; reconcile assets by kind/name, never by key."""
    result = {'assets': [], 'segments': []}; names = {}
    for batch_index, batch in enumerate(batches):
        mapping = {}
        for asset in batch['assets']:
            identity = (asset['kind'], asset['name'].strip())
            if identity not in names:
                key = 'batch_asset_' + str(len(names))
                names[identity] = key
                result['assets'].append(dict(copy.deepcopy(asset), key=key))
            mapping[asset['key']] = names[identity]
        for original in batch['segments']:
            seg = copy.deepcopy(original)
            for field in ('character_keys', 'prop_keys'):
                seg[field] = [mapping.get(key, key) for key in seg.get(field, [])]
            seg['location_key'] = mapping.get(seg.get('location_key'), seg.get('location_key'))
            result['segments'].append(seg)
    return result


async def generate_breakdown_batches(p, job, log, provider, instructions, ctx, schema):
    scenes = ctx['episode']['scenes']; completed = copy.deepcopy(job.get('breakdown_batches', []))
    if len(completed) > len(scenes): raise ValueError('保存的分批结果与场次不一致')
    usages = []; requests = []
    for index, scene in enumerate(scenes):
        allowed = {scene['id']}
        if index < len(completed):
            candidate = completed[index]
            if {s.get('scene_id') for s in candidate['segments']} != allowed:
                raise ValueError('保存的分批结果与场次不一致')
            normalize(p, 'wf_breakdown', merge_breakdown_batches(completed[:index+1]), job['target_id'], {})
            continue
        batch_ctx = copy.deepcopy(ctx)
        batch_ctx['episode']['scenes'] = [scene]
        batch_ctx['segments'] = [s for s in ctx['segments'] if s.get('scene_id') in allowed]
        batch_ctx['batch'] = {'index': index+1, 'count': len(scenes), 'scene_ids': [scene['id']]}
        batch_instructions = instructions + '\n本次为分场批次，只输出当前 episode.scenes 中这一场的分镜和出镜资产。完整保留该场动作和对白，不返回其他场次或已生成内容。资产描述保持简洁，镜头写可执行动作，不反复复制背景设定。不要因分批处理而改变剧情节奏或凑时长。'
        log(job, f'分场生成 {index+1}/{len(scenes)}：' + scene.get('title', scene['id']))
        for attempt in range(2):
            try:
                output, usage, request = await providers.text_generate(provider, batch_instructions, batch_ctx, schema)
                if not isinstance(output, dict) or not isinstance(output.get('segments'), list) or not isinstance(output.get('assets'), list):
                    raise ValueError('本批缺少分镜或资产')
                if {s.get('scene_id') for s in output['segments']} != allowed:
                    raise ValueError('本批必须完整覆盖指定场次，不能生成其他场次')
                if len({a.get('key') for a in output['assets']}) != len(output['assets']):
                    raise ValueError('本批资产引用键重复')
                normalize(p, 'wf_breakdown', merge_breakdown_batches(completed+[output]), job['target_id'], {})
                break
            except (ValueError, TypeError, KeyError) as error:
                # HTTP/auth failures must not be re-submitted as model repairs.
                if isinstance(error, ValueError) and str(error).startswith('服务 HTTP'): raise
                if isinstance(error, providers.ModelOutputError):
                    log(job, f'第 {index+1} 场模型响应未通过：{error}', response_diagnostics=error.diagnostics)
                if attempt: raise ValueError(f'第 {index+1} 场结果未通过校验，已保留完成批次和原作品：{error}') from error
                batch_ctx['validation_error'] = str(error)
                batch_instructions += '\n修正本批结构。若长度不足，减少重复的背景描述和冗余字段，完整保留剧情、动作和对白；只返回 schema 指定字段，不输出提示词或解析。'
                log(job, f'第 {index+1} 场进行一次修复：{error}')
        completed.append(output); usages.append(usage); requests.append(request)
        log(job, f'第 {index+1} 场已通过校验，暂存结果；全部完成后统一更新作品', breakdown_batches=copy.deepcopy(completed))
    result = normalize(p, 'wf_breakdown', merge_breakdown_batches(completed), job['target_id'], {})
    return result, {'batches': usages}, {'batches': requests}


async def run_text(job, log):
    p = ensure(job['source_snapshot']); stage = job['stage']; target = job.get('target_id'); options = job.get('workflow_options', {})
    if stage == 'wf_breakdown':
        p['_storyboard_skill_profile'] = skills.for_job(job, 'storyboard')
    if stage == 'wf_breakdown' and job.get('invalid_response') and job.get('attempt', 0):
        try: recovered = normalize(p, stage, job['invalid_response'], target, options)
        except (ValueError, TypeError, KeyError): pass
        else:
            log(job, '已复用上次保留的模型结果，按镜号时间拆分并通过校验，无需再次调用模型', result=recovered, pending_apply=False)
            return
    base, instruction = RULES[stage]; skill = skills.for_job(job,base)
    active_skills=[skill]
    if skill.get('auto_dispatch'):
        log(job,'自动调度专业技能：'+'；'.join(m['name']+'（'+m['reason']+'）' for m in skill['auto_dispatch']['modules']),skill_dispatch=skill['auto_dispatch'])
    if stage=='wf_prompts':
        image_skill=skills.for_job(job,'assets'); active_skills.append(image_skill)
        instruction+='\n以下生图规范约束 image_prompt，仅生成生图提示词，不生成视频描述：\n'+image_skill['content']+'\n'+asset_visuals.prompt_generation_rules()
    provider = providers.provider_for(p, 'text', job['provider_id'])
    ctx = context(p, stage, target, options); ctx['request'] = job.get('instruction', '')
    supplement = director_prompts.enhancement(stage, options)
    if supplement:
        director_prompts.canvas_references(options)
        instruction += '\n' + supplement
        ctx = director_prompts.enrich_context(p, stage, ctx, options)
        log(job, '已加载导演提示词编译补充：参考职责、镜头调度、光色材质与结束状态', prompt_compiler=director_prompts.VERSION)
    if stage=='wf_breakdown':
        timing=ctx['timing_contract']
        instruction+='\n时长优先级：总时长由 AI 根据剧情、对白和自然表演节奏自行判断，没有固定总时长、下限或上限。忽略旧 episode_duration、旧场次时长、技能示例和 split_instruction 中的单集或总时长要求；禁止为凑时长拉长或为固定总时长删减剧情。每镜仍严格遵守 timing_contract 的 min/max_segment_duration（非空时）。旧 segments 仅供复用 ID 和识别内容，不限制镜头数量或时长。执行 split_instruction 中的单镜时长和其他内容要求。完整保留原剧情与对白。shots 从 0 连续覆盖各 segment.duration。'
        log(job,'按当前拆分设置规划：总时长由 AI 根据剧情判断'+(f"，单镜不超过 {timing['max_segment_duration']:g} 秒" if timing['max_segment_duration'] is not None else ''),timing_contract=timing)
    schema = SCHEMAS[stage]
    if stage == 'wf_prompts':
        # The general schema is only illustrative. Use exact IDs in this request
        # so the model cannot copy the placeholder or expand to reference assets.
        schema = {'prompts': [{'id': obj['id'], 'image_prompt': '该目标的静态生图提示词'}
                              for obj in ctx['targets']]}
        ctx['required_target_ids'] = [obj['id'] for obj in ctx['targets']]
        instruction += '\n只输出 targets 中的目标。assets 是参考资料，不是待生成列表。prompts 每个 ID 必须与 required_target_ids 逐字一致，每个目标恰好一次，禁止用名称、序号或示例 ID 替代。'
    log(job, '加载 ' + ' + '.join(s['name'] for s in active_skills) + ' · 按文档流程执行', model=provider['model'], skill={'id': skill['id'], 'version': skill['version']},
        skills=[{'id':s['id'],'version':s['version']} for s in active_skills])
    if stage == 'wf_breakdown':
        result, usage, request = await generate_breakdown_batches(p, job, log, provider,
            skill['content'] + '\n' + creation.guidance(p, base) + '\n' + instruction, ctx, schema)
        log(job, '全部场次已通过校验，正在统一更新作品', result=result, usage=usage, request_snapshot=request, pending_apply=False)
        return
    for attempt in range(2):
        failure = None
        try:
            output, usage, request = await providers.text_generate(provider, skill['content'] + '\n' + creation.guidance(p, base) + '\n' + instruction, ctx, schema)
        except providers.ModelOutputError as error:
            failure = error
            log(job, str(error), response_diagnostics=error.diagnostics)
            if error.diagnostics.get('finish_reason') != 'length': ctx['invalid_response'] = error.raw_output[:12000]
        else:
            try: result = normalize(p, stage, output, target, options); break
            except (ValueError, TypeError, KeyError) as error:
                failure = error
                ctx['invalid_response'] = json.dumps(output, ensure_ascii=False)[:24000]
                log(job, '结构校验未通过：' + str(error), validation_error=str(error), invalid_response=output)
        if attempt: raise ValueError('模型结果仍未通过校验，原内容已保留：' + str(failure)) from failure
        ctx['validation_error'] = str(failure); ctx['request'] += '\n修正格式、引用与时长，遵守 timing_contract（如有）和原文保留要求。只返回要求的JSON字段；章节任务不得重复输出小说正文。'
        log(job, '结果未通过校验，进行一次结构修复', attempt=attempt + 1)
    if result.get('timing_split'):
        split = result['timing_split']
        log(job, f"已按内部镜号拆分：{split['original_count']} 个小节 → {split['final_count']} 个生成镜头，保留总时长、动作和对白")
    log(job, '结果已通过校验，正在更新作品', result=result, usage=usage, request_snapshot=request, pending_apply=False)


def apply(p, job, result):
    stage = job['stage']; target = job.get('target_id'); options = job.get('workflow_options', {})
    if domain.fingerprint(scope_value(ensure(p), stage, target, options)) != domain.fingerprint(scope_value(ensure(job['source_snapshot']), stage, target, options)):
        raise ValueError('本次输入或目标在生成后已改变，请重新生成；建议稿和原内容均已保留')
    p['outputs'].setdefault('production_setup', ensure(p)['outputs']['production_setup'])
    if stage == 'wf_story':
        p['outputs']['novel'] = {'chapters': [{'id': store.uid('chapter'), 'title': p['name'], 'content': result['story'], 'summary': ''}], 'outline': []}
        p['outputs']['direction'] = {'synopsis': result['story'], 'logline': p['source'], 'conflict': '', 'theme': '', 'genre': p['settings']['genre']}
    elif stage == 'wf_setup':
        setup = copy.deepcopy(result)
        previous = p['outputs'].get('characters', {}).get('characters', [])
        for c in setup['characters']:
            old = next((x for x in previous if x.get('name') == c['name']), None)
            asset = next((x for x in p['assets'] if x.get('kind') == 'character' and x.get('name') == c['name']), None)
            c['id'] = old['id'] if old else asset['id'] if asset else store.uid('character')
            c.setdefault('variants', old.get('variants', []) if old else [])
        p['outputs']['production_setup'] = setup
        p['outputs']['characters'] = {'characters': copy.deepcopy(setup['characters'])}
        p['outputs']['direction'] = {'logline': p.get('source', '')[:150], 'theme': '', 'genre': setup['genre'], 'conflict': setup['synopsis'][:200], 'synopsis': setup['synopsis'], 'constraints': [setup['cinematography']['negative']]}
        p['settings'].update(genre=setup['genre'], style=setup['visual_style'])
    elif stage == 'wf_continue':
        p['outputs'].setdefault('novel', {'chapters': [], 'outline': []})['chapters'].append(copy.deepcopy(result['chapter']))
    elif stage == 'wf_chapters':
        if target:
            incoming = result['chapters'][0]
            current_chapter = chapter(p, target)
            current_chapter['summary'] = incoming['summary']
            novel_output = p['outputs']['novel']
            novel_output['outline'] = [{'chapter_id': c['id'], 'title': c['title'], 'summary': c.get('summary', '')} for c in chapters(p)]
            for ep in p['outputs'].get('script', {}).get('episodes', []):
                if target in ep.get('source_chapters', []) or any(target in sc.get('source_chapters', []) for sc in ep.get('scenes', [])): ep['outline_stale'] = True
            p['outputs']['storyboard'] = {'segments': p['segments']}
            p['stage_status'][stage] = 'draft'
            return
        p['outputs']['novel'] = {'chapters': copy.deepcopy(result['chapters']), 'outline': [{'chapter_id': c['id'], 'title': c['title'], 'summary': c['summary']} for c in result['chapters']]}
        for ep in p['outputs'].get('script', {}).get('episodes', []): ep['outline_stale'] = True
    elif stage == 'wf_script':
        ep = copy.deepcopy(result['episodes'][0]); episodes = p['outputs'].setdefault('script', {'episodes': []})['episodes']
        old = next((e for e in episodes if e['id'] == ep['id']), None)
        if old: episodes[episodes.index(old)] = ep
        else: episodes.append(ep)
        order = {c['id']: i for i, c in enumerate(chapters(p))}
        episodes.sort(key=lambda x: order.get((x.get('source_chapters') or [''])[0], len(order)))
        for s in p['segments']:
            if s.get('episode_id') == ep['id']: s['status'] = 'stale'; s['script_stale'] = True
    elif stage == 'wf_breakdown':
        # Do not remove old media or assets. Superseded shots are archived in project and revisions.
        old = [s for s in p['segments'] if s.get('episode_id') == target]
        incoming = copy.deepcopy(result['segments'])
        # Two episodes generated concurrently may discover the same asset. Reuse its current identity.
        remap = {}; variant_map = {}
        for a in result['assets']:
            current = next((x for x in p['assets'] if x['kind'] == a['kind'] and x['name'] == a['name']), None)
            if current and current['id'] != a['id']:
                remap[a['id']] = current['id']
                for v in a.get('variants', []):
                    match = next((x for x in current.get('variants', []) if x['name'] == v['name']), None)
                    if match: variant_map[v['id']] = match['id']
        for seg in incoming:
            seg['character_ids'] = [remap.get(x, x) for x in seg['character_ids']]
            seg['location_id'] = remap.get(seg['location_id'], seg['location_id'])
            seg['prop_ids'] = [remap.get(x, x) for x in seg['prop_ids']]
            seg['variant_ids'] = [variant_map.get(x, x) for x in seg['variant_ids']]
        ids = {s['id'] for s in incoming}
        removed = [s for s in old if s['id'] not in ids]
        p.setdefault('archived_segments', []).extend(removed)
        p['segments'] = [s for s in p['segments'] if s.get('episode_id') != target] + incoming
        for a in result['assets']:
            current = next((x for x in p['assets'] if x['id'] == remap.get(a['id'], a['id'])), None)
            if current: current['episode_ids'] = list(dict.fromkeys(current.get('episode_ids', []) + [target]))
            else: p['assets'].append(copy.deepcopy(a))
    elif stage == 'wf_prompts':
        for prompt in result['prompts']:
            obj = next(x for x in p['assets'] + p['segments'] if x['id'] == prompt['id'])
            obj['image_prompt'] = prompt['image_prompt']
            obj.pop('prompt_stale', None)
            # Video descriptions are managed separately by wf_video_prompt.
    elif stage == 'wf_video_prompt':
        segment = next(s for s in p['segments'] if s['id'] == target)
        segment['prompt'] = result['prompt']
        segment.pop('video_prompt_stale', None)
    p['outputs']['storyboard'] = {'segments': p['segments']}
    p['stage_status'][stage] = 'draft'


def sync_manual(previous, p):
    from . import project_assets
    old_segments = {segment['id']:segment for segment in previous.get('segments', [])}
    for segment in p.get('segments', []):
        old_segment = old_segments.get(segment['id'])
        fields = ('character_ids', 'variant_ids', 'location_id', 'prop_ids')
        if old_segment and any(segment.get(key) != old_segment.get(key) for key in fields):
            characters = [a for a in p['assets'] if a['kind'] == 'character' and a['id'] in segment.get('character_ids', [])]
            valid = {v['id'] for a in characters for v in a.get('variants', [])}
            segment['variant_ids'] = [ident for ident in segment.get('variant_ids', []) if ident in valid]
            for asset in characters:
                if asset['id'] not in old_segment.get('character_ids', []) and asset.get('variants'):
                    if not set(segment['variant_ids']).intersection(v['id'] for v in asset['variants']):
                        segment['variant_ids'].append(asset['variants'][0]['id'])
            project_assets.touch(segment)
    setup = p['outputs'].get('production_setup')
    if setup and setup != previous['outputs'].get('production_setup'):
        for c in setup.get('characters', []):
            c.setdefault('id', store.uid('character')); c.setdefault('variants', [])
        p['settings'].update(genre=setup.get('genre') or p['settings']['genre'], style=setup.get('visual_style') or p['settings']['style'])
        p['outputs']['characters'] = {'characters': copy.deepcopy(setup.get('characters', []))}
        for c in setup.get('characters', []):
            asset = next((a for a in p['assets'] if a['id'] == c['id'] and a['kind'] == 'character'), None)
            if asset and (asset['name'] != c['name'] or asset.get('description', '') != c.get('description', '')):
                asset.update(name=c['name'], description=c.get('description', ''), status='stale', version=asset.get('version', 1)+1)
                asset['prompt_stale'] = True
    old_chapters = {c['id']: c for c in chapters(previous)}
    changed = {c['id'] for c in chapters(p) if c != old_chapters.get(c['id'])}
    old_episodes = {ep['id']: ep for ep in previous['outputs'].get('script', {}).get('episodes', [])}
    for ep in p['outputs'].get('script', {}).get('episodes', []):
        if changed.intersection(ep.get('source_chapters', [])): ep['outline_stale'] = True
        old = old_episodes.get(ep['id'])
        if old and ep.get('scenes') != old.get('scenes'):
            for seg in p['segments']:
                if seg.get('episode_id') == ep['id']: seg['script_stale'] = True; seg['status'] = 'stale'


def guard_media(p, target):
    seg = next((x for x in p['segments'] if x['id'] == target), None)
    if seg and seg.get('script_stale'): raise ValueError('本集剧本已更新，请重新拆分或核对分镜后确认沿用')


@router.post('/{ident}/workflow/confirm-shots')
def confirm_shots(ident, payload: dict):
    from . import task_locks
    p = store.get('projects', ident)
    task_locks.assert_available(p, {'reads':set(), 'writes':{'board:'+str(payload.get('episode_id'))}})
    if payload.get('revision') != p['revision']: raise ValueError('作品已更新，请刷新后确认')
    ep = episode(p, payload.get('episode_id'))
    if not ep: raise ValueError('剧集不存在')
    scene_ids = {scene['id'] for scene in ep.get('scenes', [])}
    missing = [seg.get('title', seg['id']) for seg in p['segments']
               if seg.get('episode_id') == ep['id'] and seg.get('scene_id') not in scene_ids]
    if missing: raise ValueError('请先在核对场次关联中为这些镜头选择当前剧本场次：' + '、'.join(missing))
    for seg in p['segments']:
        if seg.get('episode_id') == payload['episode_id']: seg.pop('script_stale', None)
    return ensure(store.save_project(p, payload['revision'], '核对剧本后沿用本集分镜'))


@router.get('/{ident}/workflow')
def state(ident): return ensure(store.get('projects', ident))


@router.post('/{ident}/workflow/shot-assets')
def edit_shot_assets(ident, payload: dict):
    from . import project_assets
    return ensure(project_assets.edit_shot(ident, payload))


@router.post('/{ident}/workflow/delete-asset')
def delete_project_asset(ident, payload: dict):
    from . import project_assets
    return ensure(project_assets.delete_asset(ident, payload))


@router.post('/{ident}/workflow/source')
def source(ident, payload: dict):
    from . import task_locks
    p = store.get('projects', ident); content = payload.get('content', '')
    task_locks.assert_available(p, {'reads':set(), 'writes':{'source','chapter:*'}})
    if payload.get('revision') != p['revision']: raise ValueError('作品已更新，请刷新后再导入')
    if not isinstance(content, str) or not content.strip(): raise ValueError('请填写或导入正文')
    mode = payload.get('mode', 'replace')
    if mode not in ('append', 'replace'): raise ValueError('请选择追加章节或替换全文')
    if mode == 'append':
        novel = p['outputs'].setdefault('novel', {'chapters': [], 'outline': []})
        novel.setdefault('chapters', []).extend(domain.split_chapters(content))
        p['source'] = '\n\n'.join(c['content'] for c in novel['chapters'])
        p['entry'] = 'novel'
        return ensure(store.save_project(p, payload['revision'], '追加小说章节'))
    if p['segments'] or p['outputs'].get('script', {}).get('episodes'): raise ValueError('已有剧本或分镜，请新建作品导入另一篇小说，避免错配已生成素材')
    p['source'] = content; p['entry'] = 'novel'
    p['outputs']['novel'] = {'chapters': domain.split_chapters(content), 'outline': []}
    return ensure(store.save_project(p, payload['revision'], '导入小说正文'))


@router.post('/{ident}/workflow/chapter-order')
def reorder_chapters(ident, payload: dict):
    from . import task_locks
    p = store.get('projects', ident)
    task_locks.assert_available(p, {'reads':set(), 'writes':{'source', 'chapter:*'}})
    if payload.get('revision') != p['revision']: raise ValueError('作品已更新，请刷新后再调整顺序')
    items = chapters(p); ids = payload.get('chapter_ids')
    if (not isinstance(ids, list) or not all(isinstance(ident, str) for ident in ids)
            or len(ids) != len(items) or len(set(ids)) != len(ids) or set(ids) != {c['id'] for c in items}):
        raise ValueError('排序必须包含全部现有章节且不能重复，请刷新后重试')
    if not items: raise ValueError('请先导入章节')
    by_id = {c['id']: c for c in items}
    novel = p['outputs']['novel']
    novel['chapters'] = [by_id[ident] for ident in ids]
    # Retain each outline and its provenance, including legacy partial outlines.
    rank = {ident: index for index, ident in enumerate(ids)}
    if novel.get('outline'):
        outlines = [dict(item) for item in novel['outline']]
        for index, item in enumerate(outlines):
            if not item.get('chapter_id') and index < len(items): item['chapter_id'] = items[index]['id']
        novel['outline'] = sorted(outlines, key=lambda item: rank.get(item.get('chapter_id'), len(ids)))
    p['source'] = '\n\n'.join(c['content'] for c in novel['chapters'])
    return ensure(store.save_project(p, payload['revision'], '调整章节顺序（保留正文、大纲与剧本关联）'))


@router.post('/{ident}/workflow/split-local')
def split_local(ident, payload: dict):
    from . import task_locks
    p = store.get('projects', ident)
    task_locks.assert_available(p, {'reads':set(), 'writes':{'chapter:*'}})
    if payload.get('revision') != p['revision']: raise ValueError('作品已更新，请刷新后再拆分')
    items = domain.split_chapters(fulltext(p))
    if not items: raise ValueError('请先准备小说正文')
    old = chapters(p)
    for c in items:
        found = next((x for x in old if x.get('content') == c['content']), None)
        if found: c.update(id=found['id'], summary=found.get('summary', ''))
    p['outputs']['novel'] = {'chapters': items, 'outline': []}
    for ep in p['outputs'].get('script', {}).get('episodes', []): ep['outline_stale'] = True
    return ensure(store.save_project(p, payload['revision'], '按原文章标题拆分（不改写正文）'))


@router.post('/{ident}/workflow/jobs')
async def create_job(ident, payload: dict):
    from . import jobs
    p = ensure(store.get('projects', ident)); stage = payload.get('stage')
    if stage not in SCHEMAS: raise ValueError('流程任务不存在')
    if payload.get('revision') != p['revision']: raise ValueError('作品已更新，请刷新后提交')
    from . import agent_workflow
    if stage in agent_workflow.STAGES: return agent_workflow.submit(p, payload)
    context(p, stage, payload.get('target_id'), payload.get('workflow_options'))
    return jobs.create(p, {**payload, 'kind': 'text', 'preview': True})


@router.post('/{ident}/workflow/batch-images')
async def batch_images(ident, payload: dict):
    from . import jobs, task_locks
    p = ensure(store.get('projects', ident)); ids = payload.get('target_ids', [])
    if payload.get('revision') != p['revision']: raise ValueError('作品已更新，请刷新后提交')
    if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids): raise ValueError('请选择不重复的生图目标')
    if len(ids) > int(p['settings'].get('max_jobs', 10)): raise ValueError('本批任务数量超过项目上限，请分批生成')
    objects = {x['id']: x for x in p['assets'] + p['segments']}
    if any(x not in objects for x in ids): raise ValueError('生图目标不存在')
    if any(not objects[x].get('image_prompt', '').strip() for x in ids): raise ValueError('请先生成或填写所有所选对象的生图提示词')
    # Check the whole selection before starting any task. A later stale shot must
    # not leave an earlier paid request running after the batch is rejected.
    for target in ids:
        guard_media(p, target)
        task_locks.assert_submission(p, {'kind':'image', 'target_id':target})
    provider = providers.provider_for(p, 'image')
    price = provider.get('unit_price'); budget = p['settings'].get('budget')
    if budget is not None and (price is None or float(price) * len(ids) > float(budget)): raise ValueError('费用未知或超过项目上限，请在项目设定中调整')
    submitted = []
    for target in ids:
        submitted.append(jobs.create(p, {'kind': 'image', 'stage': 'assets' if 'kind' in objects[target] else 'storyboard', 'target_id': target, 'instruction': objects[target]['image_prompt']}))
    return {'jobs': submitted}


@router.post('/{ident}/workflow/adopt-image')
def adopt_image(ident, payload: dict):
    from pathlib import Path
    from PIL import Image
    from . import task_locks, library
    p = ensure(store.get('projects', ident))
    if payload.get('revision') != p['revision']: raise ValueError('作品已更新，请刷新后再选用图片')
    target = payload.get('target_id')
    obj = next((a for a in p['assets'] + p['segments'] if a['id'] == target), None)
    if not obj: raise ValueError('图片目标已不存在')
    task_locks.assert_available(p, task_locks.scope(p, {'kind':'image','target_id':target}))
    guard_media(p, target)
    file = payload.get('file')
    provenance = {}
    if payload.get('library_id'):
        item = store.get('library', payload['library_id'])
        selected = next((v for v in item['versions'] if v['version'] == payload.get('library_version')), None)
        if not selected: raise ValueError('资产库图片版本不存在，请重新选择')
        content = selected['content']
        if content['kind'] not in ('character','location','prop','image'): raise ValueError('请选择图片素材')
        files = [r['file'] for r in content.get('references', [])]
        if content.get('file'): files.append(content['file'])
        if file not in files: raise ValueError('图片不属于所选资产库版本')
        provenance = {'library_id':item['id'],'library_version':selected['version']}
    if not isinstance(file, str) or not file: raise ValueError('请选择图片文件')
    path = Path(providers.file_path(file))
    if path.suffix.lower() not in library.IMAGES: raise ValueError('请选择 PNG、JPEG 或 WebP 图片')
    try:
        with Image.open(path) as picture: picture.verify()
    except (OSError, SyntaxError) as error:
        raise ValueError('图片无法读取，请重新上传有效图片') from error
    if obj.get('kind'):
        obj.setdefault('references', []).append({'file':file, **provenance})
        obj['version'] = obj.get('version', 0) + 1
        for seg in p['segments']:
            if target in seg.get('character_ids', []) + seg.get('prop_ids', []) + [seg.get('location_id')]: seg['status'] = 'stale'
    else:
        image = {'id':store.uid('shotimg'),'file':file,'created_at':store.now(),'source':'library' if provenance else 'upload', **provenance}
        obj.setdefault('images', []).append(image)
        obj['current_image'] = image['id']; obj['input_mode'] = 'shot_image'; obj['continuity'] = False
        obj['status'] = 'stale'
    return ensure(store.save_project(p, payload['revision'], '选用资产库图片' if provenance else '上传并选用图片'))
