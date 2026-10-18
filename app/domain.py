import copy
import hashlib
import json
import re
from .store import uid, now
from . import creation, native_audio as native_audio_rules

STAGES = [
    ('direction', '故事方向', '01'), ('characters', '人物设定', '02'),
    ('world', '世界规则', '03'), ('novel', '大纲与小说', '04'),
    ('script', '分场与剧本', '05'), ('assets', '图像与声音', '06'),
    ('performance', '表演设计', '07'), ('storyboard', '分镜与提示词', '08'),
    ('video', '视频生成', '09'), ('assembly', '剪辑与成片', '10')]

SCHEMAS = {
    'scene_plan': {'episodes':[{'title':'集名','scenes':[{'title':'场次标题','location':'地点','goal':'场次目标','conflict':'冲突','turn':'转折','duration':8,'source_chapters':[]}]}]},
    'direction': {'logline': '一句话故事', 'theme': '主题', 'genre': '类型', 'conflict': '核心冲突', 'synopsis': '梗概', 'constraints': ['创作约束']},
    'characters': {'characters': [{'name': '角色名', 'aliases': [], 'goal': '目标', 'secret': '秘密', 'relationships': '关系', 'arc': '变化', 'description': '外观', 'variants': [{'name': '默认服装', 'description': '服装与状态'}]}]},
    'world': {'locations': [{'name': '地点', 'description': '空间描述'}], 'organizations': [], 'rules': [], 'props': [{'name': '关键物件', 'description': '描述'}]},
    'novel': {'outline': [{'title': '章节标题', 'summary': '内容与伏笔'}], 'chapters': [{'title': '章节标题', 'content': '小说正文', 'summary': '前文摘要', 'character_states': '人物状态'}]},
    'script': {'episodes': [{'title': '集名', 'scenes': [{'title': '场景标题', 'location': '地点名称', 'time': '日/夜', 'interior': '内/外', 'goal': '场次目标', 'conflict': '冲突', 'turn': '转折', 'duration': 8, 'source_chapters': [], 'action': '动作', 'dialogue': [{'character': '人物名称', 'text': '台词'}], 'sound': '声音', 'transition': '转场'}]}]},
    'performance': {'beats': [{'scene_id': '原场次ID', 'character_id': '人物ID', 'breath': '呼吸', 'gaze': '眼神', 'weight': '重心', 'hands': '手部', 'rhythm': '节拍', 'subtext': '潜台词'}]},
    'storyboard': {'segments': [{'title': '小节标题', 'scene_id': '原场次ID', 'episode_id': '集ID', 'duration': 8, 'character_ids': [], 'variant_ids': [], 'location_id': '场景资产ID', 'prop_ids': [], 'previous_id': None, 'continuity': True, 'tail_shot': True, 'prompt': 'H3或Seedance提示词', 'shots': [{'start': 0, 'end': 7, 'size': '中景', 'camera': '缓慢推近', 'action': '动作', 'dialogue': '', 'sound': ''}, {'start': 7, 'end': 8, 'size': '中全景', 'camera': '固定', 'action': '关系镜：完整人物站位、朝向与遮挡', 'dialogue': '', 'sound': ''}]}]}
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def project_new(payload):
    mode = payload.get('entry', 'idea')
    source = payload.get('source', '').strip()
    settings = creation.normalize_settings(payload.get('settings', {}))
    p = {'id': uid('project'), 'name': payload.get('name') or '未命名作品', 'entry': mode,
         'source': source, 'created_at': now(), 'revision': 0, 'sample': False,
         'settings': {'genre': '悬疑', 'style': '电影感国风动漫', 'ratio': '16:9', 'episodes': 1, 'episode_duration': 40,
                      'novel_scope': 'current', 'chapters': 3, 'max_jobs': 10, 'budget': None,
                      'pause_at': ['script', 'assets', 'video'], 'tail_shot': True, 'white_mode': False,
                      'target_video': 'MiniMax H3', 'allow_no_references': False, **settings},
         'outputs': {}, 'assets': [], 'segments': [], 'stage_status': {}, 'bindings': {}, 'artifacts': []}
    if mode == 'novel':
        p['outputs']['novel'] = {'outline': [], 'chapters': split_chapters(source)}
        p['stage_status']['novel'] = 'draft'
    elif mode == 'script':
        p['outputs']['script'] = {'original_text': source, 'episodes': []}
        if payload.get('source_format') == 'json':
            try: parsed = json.loads(source)
            except (ValueError, TypeError): raise ValueError('剧本 JSON 无效，请检查格式')
            if not isinstance(parsed, dict) or not isinstance(parsed.get('episodes'), list) or not parsed['episodes']: raise ValueError('剧本 JSON 需要非空 episodes 数组')
            for index, episode in enumerate(parsed['episodes']):
                if not isinstance(episode, dict) or not isinstance(episode.get('scenes'), list) or not episode['scenes']: raise ValueError('每集剧本需要非空 scenes 数组')
                episode.setdefault('title', '第'+str(index+1)+'集')
                for scene in episode['scenes']:
                    if not isinstance(scene, dict): raise ValueError('剧本场次必须为对象')
                    for key in ('title','location','time','interior','goal','conflict','turn','action','sound','transition'): scene.setdefault(key, '')
                    scene.setdefault('duration', 8); scene.setdefault('source_chapters', []); scene.setdefault('dialogue', [])
                    if not isinstance(scene['dialogue'], list) or any(not isinstance(d,dict) or not isinstance(d.get('character'),str) or not isinstance(d.get('text'),str) for d in scene['dialogue']): raise ValueError('剧本对白需要 character 与 text 文本')
            parsed = normalize('script', parsed, p)
            parsed['original_text'] = source
            p['outputs']['script'] = parsed
            derive_assets(p)
        p['stage_status']['script'] = 'draft'
    p['start_stage'] = creation.start_stage(p)
    return p


def split_chapters(source):
    pieces = re.split(r'(?m)^(?=(?:第[一二三四五六七八九十百千\d]+[章回]|#{1,3}\s))', source)
    return [{'id': uid('chapter'), 'title': part.splitlines()[0][:80] if len(pieces) > 1 else '导入正文', 'content': part.strip(), 'summary': '', 'character_states': ''} for part in pieces if part.strip()]


def normalize(stage, value, p):
    if not isinstance(value, dict):
        raise ValueError('输出必须是 JSON 对象')
    key = {'characters': 'characters', 'novel': 'chapters', 'scene_plan':'episodes', 'script': 'episodes', 'performance': 'beats', 'storyboard': 'segments'}.get(stage)
    if key and (not isinstance(value.get(key), list) or not value[key]):
        raise ValueError('模型缺少非空数组：' + key)
    if stage == 'direction' and not all(isinstance(value.get(k), str) and value[k].strip() for k in ('logline', 'conflict', 'synopsis')):
        raise ValueError('故事输出缺少一句话故事、核心冲突或梗概')
    if stage == 'novel' and any(not c.get('content', '').strip() for c in value['chapters']):
        raise ValueError('小说章节缺少正文')
    for collection in ('characters', 'chapters', 'episodes', 'locations', 'props', 'segments', 'beats'):
        for item in value.get(collection, []):
            if not isinstance(item, dict):
                raise ValueError(collection + ' 条目必须是对象')
            existing = p['outputs'].get(stage, {}).get(collection, [])
            match = next((old for old in existing if old.get('name') and old.get('name') == item.get('name')), None)
            item['id'] = match['id'] if match else item.get('id') or uid(collection.rstrip('s'))
            for sub in item.get('scenes', []): sub['id'] = sub.get('id') or uid('scene')
            for sub in item.get('variants', []): sub['id'] = sub.get('id') or uid('variant')
    if stage in ('script','scene_plan') and any(not e.get('scenes') for e in value['episodes']):
        raise ValueError('每集至少包含一场戏')
    if stage == 'storyboard':
        for item in value['segments']:
            item.update({'status': 'draft', 'versions': [], 'current_version': None})
        test = copy.deepcopy(p)
        merged={s['id']:s for s in test['segments']}
        merged.update({s['id']:s for s in value['segments']})
        test['segments']=list(merged.values())
        targets={s['id'] for s in value['segments']}
        errors = [x['message'] for x in checks(test, {}, stage='storyboard') if x['severity'] == 'error' and x.get('target') in targets]
        if errors: raise ValueError('分镜结构校验失败：' + '；'.join(errors[:8]))
    return value


def derive_assets(p):
    existing = {a['id']: a for a in p['assets']}
    for character in p['outputs'].get('characters', {}).get('characters', []):
        ident = character['id']
        if ident not in existing:
            p['assets'].append({'id': ident, 'kind': 'character', 'name': character['name'], 'description': character.get('description', ''), 'source_id': ident, 'aliases': character.get('aliases', []), 'variants': character.get('variants') or [{'id': uid('variant'), 'name': '默认', 'description': ''}], 'references': [], 'voice': None, 'status': 'draft', 'version': 1})
    for kind, items in [('location', p['outputs'].get('world', {}).get('locations', [])), ('prop', p['outputs'].get('world', {}).get('props', []))]:
        for item in items:
            if item['id'] not in existing:
                p['assets'].append({'id': item['id'], 'kind': kind, 'name': item['name'], 'description': item.get('description', ''), 'source_id': item['id'], 'references': [], 'status': 'draft', 'version': 1})
    for episode in p['outputs'].get('script', {}).get('episodes', []):
        for scene in episode.get('scenes', []):
            name = scene.get('location')
            if name and not any(a['kind'] == 'location' and a['name'] == name for a in p['assets']):
                p['assets'].append({'id': uid('location'), 'kind': 'location', 'name': name, 'description': scene.get('action', ''), 'source_id': scene['id'], 'references': [], 'status': 'draft', 'version': 1})


def checks(p, settings, stage='video'):
    findings = []
    def add(message, severity='error', target=None): findings.append({'message': message, 'severity': severity, 'target': target})
    segments = p.get('segments', [])
    ids = {s['id'] for s in segments}; asset_ids = {a['id'] for a in p['assets']}
    scene_ids = {s['id'] for e in p['outputs'].get('script', {}).get('episodes', []) for s in e.get('scenes', [])}
    for s in segments:
        target = s['id']; name = s.get('title', target)
        try: duration = float(s['duration'])
        except (KeyError, ValueError, TypeError):
            add(name + ' 缺少合法时长', target=target); continue
        if duration <= 0 or duration > 120: add(name + ' 时长需在 0–120 秒内', target=target)
        shots = s.get('shots', [])
        if not shots: add(name + ' 至少需要一个镜号', target=target)
        end = 0
        for i, shot in enumerate(shots):
            try: start, stop = float(shot['start']), float(shot['end'])
            except (KeyError, ValueError, TypeError):
                add(name + f' 镜号 {i+1} 时间非法', target=target); continue
            if abs(start - end) > .05 or stop <= start: add(name + f' 镜号 {i+1} 时序有重叠或空档', target=target)
            if len(shot.get('dialogue', '')) / 4 > stop - start: add(name + f' 镜号 {i+1} 台词可能超时（按约4字/秒）', 'warning', target)
            end = stop
        if abs(end - duration) > .05: add(name + ' 镜号总时长与小节不一致', target=target)
        if s.get('tail_shot') and shots and float(shots[-1].get('end', 0)) - float(shots[-1].get('start', 0)) > 1.5:
            add(name + ' 关系镜建议使用原时长的末约1秒', 'warning', target)
        previous = s.get('previous_id') if s.get('continuity') else None
        if s.get('continuity') and not previous: add(name + ' 已启用衔接但未选择上一镜头', target=target)
        if previous and (previous not in ids or previous == target): add(name + ' 衔接来源无效', target=target)
        if previous in ids:
            previous_index = next(i for i, item in enumerate(segments) if item['id'] == previous)
            if previous_index >= segments.index(s): add(name + ' 衔接来源必须位于当前镜头之前', target=target)
        if s.get('scene_id') not in scene_ids: add(name + ' 剧本场次引用缺失', target=target)
        variants={v['id'] for a in p['assets'] if a['id'] in s.get('character_ids',[]) for v in a.get('variants',[])}
        for variant in s.get('variant_ids',[]):
            if variant not in variants: add(name+' 人物版本引用无效：'+variant,target=target)
        for character in (a for a in p['assets'] if a['id'] in s.get('character_ids',[]) and a.get('variants')):
            if not set(s.get('variant_ids',[])).intersection(v['id'] for v in character['variants']): add(name+' 未选择人物版本：'+character['name'],target=target)
        for aid in s.get('character_ids', []) + s.get('prop_ids', []) + ([s.get('location_id')] if s.get('location_id') else []):
            if aid not in asset_ids: add(name + ' 引用的资产不存在：' + str(aid), target=target)
            elif stage == 'video':
                a = next(a for a in p['assets'] if a['id'] == aid)
                if not s.get('continuity') and s.get('input_mode') != 'shot_image' and not a.get('references') and not p['settings'].get('allow_no_references'):
                    add(name + ' 缺少参考图：' + a['name'], target=target)
        if not s.get('location_id'): add(name + ' 没有关联场景资产', target=target)
        if stage == 'video':
            if not s.get('continuity') and s.get('input_mode') == 'shot_image' and not any(x['id'] == s.get('current_image') for x in s.get('images', [])):
                add(name + ' 尚未选用镜头图片，请前往图片制作', target=target)
            v = next((v for v in settings.get('providers', []) if v['id'] == p.get('bindings', {}).get('video')), None)
            if not v: add('请选择视频服务', target=target)
            else:
                from . import model_catalog
                v = model_catalog.resolve(v,'video',p.get('model_bindings',{}).get('video'))
                cap = v.get('capabilities', {})
                if duration < cap.get('min_duration', .5) or duration > cap.get('max_duration', 15): add(name + ' 超出配置的视频服务时长范围', target=target)
                if cap.get('durations') and duration not in cap['durations']: add(name + ' 当前服务时长支持：' + '、'.join(map(str,cap['durations'])) + ' 秒', target=target)
                if cap.get('audio_reference') is False and any(a.get('voice') for a in p['assets'] if a['id'] in s.get('character_ids', [])):
                    add(name + ' 当前服务不支持音频参考，角色音色不会自动传入', 'warning', target)
    for s in segments:
        seen = set(); current = s
        while current.get('continuity') and current.get('previous_id'):
            if current['id'] in seen:
                add('连续性依赖存在循环：' + s.get('title', ''), target=s['id']); break
            seen.add(current['id']); current = next((x for x in segments if x['id'] == current['previous_id']), {})
    return findings


def bundle(p, segment, allow_waiting=False, provider=None):
    refs = []
    native_audio = native_audio_rules.is_h3(provider) or provider is None and p.get('settings', {}).get('video_audio_source') == 'h3_native'
    chained = bool(segment.get('continuity'))
    shot_mode = segment.get('input_mode') == 'shot_image' or chained
    if shot_mode and not chained:
        image = next((x for x in segment.get('images', []) if x['id'] == segment.get('current_image')), None)
        if not image: raise ValueError('请先在图片制作中选用当前镜头图片')
        refs.append({'number': 1, 'purpose': 'shot', 'name': '当前镜头选用图片', 'file': image['file'], 'source_image': image['id']})
    for aid in segment.get('character_ids', []) + ([segment.get('location_id')] if segment.get('location_id') else []) + segment.get('prop_ids', []):
        asset = next((a for a in p['assets'] if a['id'] == aid), None)
        if not asset: continue
        selected_variants = segment.get('variant_ids', [])
        candidates=[r for r in asset.get('references',[]) if not r.get('variant_id') or r['variant_id'] in selected_variants]
        selected_refs=[]
        for variant in selected_variants:
            matching=[r for r in candidates if r.get('variant_id')==variant]
            if matching: selected_refs.append(matching[-1])
        if not selected_refs and candidates: selected_refs=[candidates[-1]]
        for reference in selected_refs:
            refs.append({'number': len(refs)+1, 'asset_id': aid, 'asset_version': asset.get('version', 1), 'name': asset['name'], 'purpose': 'identity' if asset['kind'] == 'character' else reference.get('canvas_reference_purpose','space'), 'file': reference['file']})
        if asset['kind'] == 'character' and asset.get('voice'): refs.append({'number': len(refs)+1, 'asset_id': aid, 'name': asset['name'], 'purpose': 'voice', 'file': asset['voice']})
    for reference in segment.get('video_references', []):
        refs.append({'number':len(refs)+1, 'purpose':'motion', 'name':reference.get('name','视频参考'), **{k:reference[k] for k in ('file','url') if k in reference}})
    prev = next((s for s in p['segments'] if s['id'] == segment.get('previous_id')), None) if segment.get('continuity') else None
    if prev:
        version = next((v for v in prev.get('versions', []) if v['id'] == prev.get('current_version')), None)
        if version and version.get('tail_accepted'):
            tail = version.get('white') if p['settings'].get('white_mode') else version.get('tail')
            if tail:
                # One primary visual reference and the first-frame guide share
                # the same actual predecessor frame. Never mix a new shot image.
                refs.insert(0, {'number': 1, 'purpose': 'shot', 'name': '上一镜头尾帧（本镜头起点）', 'file': tail, 'source_segment': prev['id'], 'source_version': version['id']})
                refs.append({'number': len(refs)+1, 'purpose': 'continuity', 'name': '上一小节空间状态', 'file': tail, 'source_segment': prev['id'], 'source_version': version['id']})
        if not any(r['purpose'] == 'continuity' for r in refs) and not allow_waiting:
            raise ValueError('上一镜头视频或有效尾帧尚未就绪，请先完成前段；无需单独生成本镜头图片')
    if segment.get('continuity') and not prev: raise ValueError('已启用衔接但未选择有效的上一镜头')
    for number, reference in enumerate(refs, 1): reference['number'] = number
    prompt = '\n'.join([creation.guidance(p, 'video', visual_only=True), segment.get('prompt', ''), *[f"参考{r['number']} {r['name']} 用于{r['purpose']}" for r in refs]])
    visual_prompt = prompt
    if native_audio and not segment.get('canvas_raw_prompt'):
        native_audio_rules.validate_pacing(segment)
        prompt = native_audio_rules.compile_timeline(segment, prompt)
    else:
        prompt += '\n' + json.dumps(segment.get('shots', []), ensure_ascii=False)
    visual_contract = '\n保持当前镜头图片与关联角色设定中的同一人物身份、脸型、发型、年龄、体态及服装状态，不重新设计角色。'
    if any(r['purpose'] == 'continuity' for r in refs):
        visual_contract += '\n从上一镜头实际尾帧开始，延续人物站位、朝向、动作状态、道具位置和光线；在此基础上执行本镜头动作与运镜，不把角色设定拼版绘入画面。'
    if p['settings'].get('white_mode'): visual_contract += '\n白模仅用于空间与姿势参考。首帧即为正常彩色画面，不呈现白模转彩色。'
    prompt += visual_contract
    visual_prompt += visual_contract
    dialogue_audio = None if native_audio else segment.get('dialogue_audio')
    if dialogue_audio:
        prompt += '\nUse the anchored dialogue soundtrack at its exact timestamps. Match visible speakers and their mouth movement to each spoken line. Generate natural scene ambience and action effects. Do not invent extra speech, captions or subtitles.'
    first_frame = refs[0]['file'] if refs and shot_mode and (chained or p['settings'].get('pin_shot_first_frame')) else None
    return {'project_id': p['id'], 'project_revision': p['revision'], 'segment_id': segment['id'], 'prompt': prompt, 'references': refs, 'duration': segment['duration'], 'ratio': p['settings']['ratio'], 'seed': segment.get('seed', 42), 'dialogue_audio': dialogue_audio, 'first_frame': first_frame, 'last_frame':segment.get('last_frame'), 'video_options':copy.deepcopy(segment.get('video_options',{})), 'video_input_mode':segment.get('canvas_video_input_mode'), 'audio_source': 'h3_native' if native_audio else 'default', 'render': copy.deepcopy(p['settings'].get('h3_render', {})),
            'visual_prompt': visual_prompt, 'speech_segment': {k:copy.deepcopy(segment[k]) for k in ('duration','shots','dialogue_text') if k in segment} if native_audio and not segment.get('canvas_raw_prompt') else None,
            'speaker_assets': [{k:a.get(k) for k in ('id','name','description')} for a in p['assets'] if a['kind']=='character' and a['id'] in segment.get('character_ids',[])]}


def stale_dependents(p, ident):
    affected = {ident}
    changed = True
    while changed:
        changed = False
        for s in p['segments']:
            if s.get('previous_id') in affected and s['id'] not in affected:
                affected.add(s['id']); s['status'] = 'stale'; changed = True
    return list(affected - {ident})
