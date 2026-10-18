"""One spoken-line timeline for native video audio; no separate dubbing."""
import re
import math

VERSION = 'h3-dialogue-v2'


def dialogue_rows(segment):
    if not isinstance(segment.get('dialogue_text'), str):
        rows = []
        for shot in segment.get('shots', []):
            lines = [line.strip() for line in shot.get('dialogue', '').splitlines() if line.strip()]
            start, end = float(shot.get('start', 0)), float(shot.get('end', segment['duration']))
            for i, line in enumerate(lines):
                speaker, words = split_line(line)
                rows.append(dict(start=round(start+(end-start)*i/len(lines), 2), end=round(start+(end-start)*(i+1)/len(lines), 2), speaker=speaker, text=words))
        return rows
    rows, previous_end = [], 0
    for line in segment['dialogue_text'].splitlines():
        if not line.strip(): continue
        match = re.match(r'^\s*(\d+:\d+(?:\.\d+)?)\s*[–—-]\s*(\d+:\d+(?:\.\d+)?)\s+([^：:\n]+)[：:]\s*(.+)$', line)
        if not match: raise ValueError('台词请使用“00:00–00:02 角色：台词”格式')
        def seconds(value):
            result = 0
            for part in value.split(':'): result = result*60+float(part)
            return result
        start, end = seconds(match[1]), seconds(match[2])
        if not (math.isfinite(end) and previous_end <= start < end <= float(segment['duration'])+.001):
            raise ValueError('台词时间戳超出镜头时长或互相重叠，请重新生成时间戳')
        rows.append(dict(start=start, end=end, speaker=match[3].strip(), text=match[4].strip()))
        previous_end = end
    return rows


def split_line(line):
    match = re.match(r'^\s*([^:：\n]{1,40})[:：]\s*(.+)$', line)
    return (match.group(1).strip(), match.group(2).strip()) if match else ('按镜头指定说话人', line.strip())


def compile_timeline(segment, prompt):
    shots = segment.get('shots', [])
    rows = dialogue_rows(segment)
    # The editor's timeline is authoritative even if an older visual prompt
    # still contains a dialogue clause from a previous draft.
    prompt = re.sub(r'(?:对白|台词)[:：].*?(?=声音[:：]|\n|\d+\s*[-–]\s*\d+秒|$)', '（对白见唯一时间表）', prompt)
    # Keep the user's visual/video instructions while stating each spoken line
    # only in the authoritative timeline, rather than in both prose and JSON.
    for shot in shots:
        for line in shot.get('dialogue', '').splitlines():
            if line.strip():
                _, words = split_line(line)
                if words: prompt = prompt.replace(words, '（对白见唯一时间表）')
    for row in rows:
        prompt = prompt.replace(row['text'], '（对白见唯一时间表）')
    timeline = []
    for shot in shots:
        period = f"{shot.get('start', 0)}–{shot.get('end', segment.get('duration'))}秒"
        timeline.append(f"{period}：画面动作：{shot.get('action', '')}。声音：{shot.get('sound', '')}。")
    speakers = speaker_ids(rows)
    for row in rows:
        timeline.append(f"At {row['start']:g}–{row['end']:g} seconds, {row['speaker']} ({speakers[row['speaker']]}) says: <d>[{dialogue_language(row['text'])}] {row['text']}</d>")
    if not rows: timeline.append('全镜头无人说话，不生成任何人声。')
    contract = (
        '\n原生声音规则：自然清晰的普通话。下方是唯一对白时间表，只说指定原句一次，按顺序在指定时段内完成。'
        '不得朗读镜头描述、人物名字、标点、时间、JSON、声音标签或参考图中的文字；不增词、不重复、不生成乱码、哼唱或无意义人声。'
        '脚步、纸张摩擦和海浪等环境声不得变成拟声词或人声。对白清晰居前，环境声轻且自然，不用持续的高音噪声或夸张低频盖住对白。'
        '只让指定角色说话，其他可见人物保持嘴部闭合；画外音和从信件、电话等发出的声音不驱动画面人物嘴型。'
        '年龄、性别与情绪服从角色设定和当前情节；不将角色名或括号内表演说明当作台词。'
        '只在下列指定的对白时间段说话，其他时间不生成任何人声。'
        '\n唯一对白与声音时间表：\n' + '\n'.join(timeline)
    )
    return prompt + contract


def is_h3(provider):
    return bool(provider and (any(n.get('class_type', '').startswith('MiniMaxH3') for n in provider.get('workflow', {}).values())
                             or re.search(r'(?:minimax[-_ ]?h3|h3[-_ ]?(?:ref|base|native))', provider.get('model', ''), re.I)))


def speaker_ids(rows):
    names = list(dict.fromkeys(r['speaker'] for r in rows))
    return {name: f'S{i+1}' for i, name in enumerate(names)}


def dialogue_language(text):
    return 'Chinese' if re.search(r'[\u3400-\u9fff]', text) else 'English'


def validate_pacing(segment):
    rows = dialogue_rows(segment)
    previous = 0
    for row in rows:
        start, end = row['start'], row['end']
        if not (math.isfinite(start) and math.isfinite(end) and previous <= start < end <= float(segment['duration'])+.001):
            raise ValueError('台词时间戳超出镜头时长或互相重叠，请调整台词时间')
        previous = end
        chinese = len(re.findall(r'[\u3400-\u9fff]', row['text']))
        words = len(re.findall(r'[A-Za-z0-9]+', row['text']))
        # Conservative feasibility ceiling, not a promise of frame-accurate speech.
        required = chinese / 6 + words / 3
        if required > end-start+.05:
            raise ValueError(f"{row['speaker']}的台词在 {start:g}–{end:g} 秒内过长，请缩短台词、延长时段或拆分镜头；不要靠加快配音挤入")
    return rows


def h3_prompt(bundle, image_refs, audio_refs):
    """Compile labels against actual upload order, never require a voice sample."""
    segment = bundle.get('speech_segment')
    if segment is None:
        # Legacy hand-built bundles have no authoritative dialogue to compile.
        return '\n'.join([*[f"<Picture {i+1}>: {r['name']}" for i,r in enumerate(image_refs)],
                          *[f"<Audio {i+1}>: {r['name']} voice-timbre reference only." for i,r in enumerate(audio_refs)], bundle['prompt']])
    rows = validate_pacing(segment)
    assets = bundle.get('speaker_assets', [])
    rows = [dict(r, speaker=next((a['name'] for a in assets if a['id']==r['speaker']), r['speaker'])) for r in rows]
    speakers = speaker_ids(rows)
    definitions, retention, bindings = [], [], {}
    subjects = {}
    for name, sid in speakers.items():
        asset = next((a for a in assets if a['name'] == name or a['id'] == name), None)
        image = next((i+1 for i,r in enumerate(image_refs) if (asset and r.get('asset_id') == asset['id']) or r.get('name') == name), None)
        offscreen = bool(re.search(r'旁白|画外|解说|narrator|voice.?over', name, re.I))
        if image and not offscreen:
            label = f'<Subject {len(subjects)+1}>'
            subjects[name] = label
            definitions.append(f"{label} is {name} ({sid}), whose appearance comes from <Picture {image}>. {asset.get('description','') if asset else ''}")
            retention.append(f'{label}: fully_preserved - preserve the referenced identity and clothing.')
        else:
            label = f'{name} ({sid})'
            definitions.append(f"{label} is {'an off-screen narrator' if offscreen else 'the speaking character'}. Use a natural Mandarin voice consistent with the character description: {asset.get('description','') if asset else name}.")
        bindings[name] = (f'{subjects[name]} ({sid})' if name in subjects else label) + (' off-screen' if offscreen else '')
    for i,r in enumerate(image_refs,1):
        if r.get('purpose') != 'identity':
            definitions.append(f"<Picture {i}> is the {r.get('purpose','visual')} reference: {r['name']}.")
            retention.append(f'<Picture {i}>: fully_preserved - preserve its visual reference role.')
    for i,r in enumerate(audio_refs,1):
        name = next((n for n in speakers if n == r.get('name') or any(a['id']==r.get('asset_id') and a['name']==n for a in assets)), None)
        if not name: continue
        definitions.append(f"<Audio {i}> is the voice-timbre reference for {bindings[name]}. Use only its timbre, never its original words or audio signal.")
        retention.append(f'<Audio {i}>: reference - generate the requested words in the referenced voice; do not copy the recording.')
    visual = bundle.get('visual_prompt', '')
    # Remove stale dialogue tags and previous spoken words from visual prose.
    visual = re.sub(r'<d>.*?</d>', '(speech specified below)', visual, flags=re.S)
    visual = re.sub(r'(?:对白|台词)[:：].*?(?=声音[:：]|\n|$)', '(speech specified below)', visual)
    visual = re.sub(r'((?:旁白|画外音|说|问|回答)[^\n。：「“"]{0,50}[:：]\s*)[「“"]([^」”"\n]*)[」”"]', r'\1(speech specified below)', visual)
    visual = re.sub(r'(?:旁白|画外音)[^\n。:：]{0,50}[:：][^\n。]*(?:。|$)', '(speech specified below)', visual)
    for shot in segment.get('shots', []):
        for line in shot.get('dialogue', '').splitlines():
            _, words = split_line(line)
            if words: visual = visual.replace(words, '(speech specified below)')
    for row in rows: visual = visual.replace(row['text'], '(speech specified below)')
    events = [f"At {r['start']:g} seconds until {r['end']:g} seconds, {bindings[r['speaker']]} says exactly once: <d>[{dialogue_language(r['text'])}] {r['text']}</d>" for r in rows]
    sound = ' '.join(shot.get('sound', '') for shot in segment.get('shots', []))
    return '\n'.join([
        'subject_definitions:', *definitions,
        'summary:', '[reference generation] Generate the described video with native Mandarin dialogue and scene sounds.',
        'retention_analysis:', *retention,
        'detailed_description:', visual,
        'The following is the sole spoken dialogue. Never speak visual instructions, names, timestamps or reference text. Keep other visible mouths closed. Off-screen narration never animates a visible mouth.',
        *events, 'No speech outside these intervals.' if rows else 'No dialogue or vocal sounds throughout the entire video.',
        'overall_soundscape:', 'Natural low-volume scene ambience and physical sounds only. Dialogue remains clear. '+sound,
        'non_diegetic_music:', 'N/A'])
